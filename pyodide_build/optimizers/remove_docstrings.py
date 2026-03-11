import ast
import io
import tokenize
from pathlib import Path

from pyodide_build.optimizers.base import ORDER_NORMAL, WheelOptimizer


class RemoveDocstringsOptimizer(WheelOptimizer):
    """Strip docstrings from ``.py`` files to reduce wheel size."""

    name = "remove_docstrings"
    description = "Strip docstrings from .py files"
    default_enabled = False
    order = ORDER_NORMAL

    def should_process(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def process_file(self, full_path: Path) -> None:
        source = full_path.read_bytes()
        try:
            result = _remove_docstrings(source)
        except SyntaxError:
            # If the file can't be parsed, leave it untouched.
            return

        if result != source:
            full_path.write_bytes(result)


def _remove_docstrings(source: bytes) -> bytes:
    """Remove docstrings from *source* and return the modified bytes.

    The approach:
      1. Parse the source into an AST to find the byte-offsets of every
         docstring node.
      2. Walk the token stream and blank out tokens that fall inside those
         byte-ranges, replacing them with empty strings.
      3. Re-join the (possibly modified) tokens via :func:`tokenize.untokenize`.

    Using the token stream (rather than simple string slicing) keeps
    encoding cookies, comments, and indentation intact.
    """
    tree = ast.parse(source)
    docstring_ranges = _collect_docstring_ranges(tree, source)
    if not docstring_ranges:
        return source

    return _blank_tokens(source, docstring_ranges)


def _collect_docstring_ranges(tree: ast.Module, source: bytes) -> list[tuple[int, int]]:
    """Return a sorted list of ``(start, end)`` byte-offset pairs for every
    docstring in *tree*.
    """
    ranges: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        docstring_node = _get_docstring_node(node)
        if docstring_node is None:
            continue

        start = _node_byte_offset(source, docstring_node)
        # end_col_offset is the column *after* the last character.
        end = _node_end_byte_offset(source, docstring_node)
        if start is not None and end is not None:
            ranges.append((start, end))

    ranges.sort()
    return ranges


def _get_docstring_node(node: ast.AST) -> ast.Constant | None:
    """If *node* has a docstring as its first statement, return the
    :class:`ast.Constant` node; otherwise return ``None``.
    """
    if not isinstance(
        node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ):
        return None

    body = node.body
    if not body:
        return None

    first = body[0]
    if not isinstance(first, ast.Expr):
        return None
    if not isinstance(first.value, ast.Constant):
        return None
    if not isinstance(first.value.value, str):
        return None

    return first.value


def _node_byte_offset(source: bytes, node: ast.AST) -> int | None:
    """Return the byte offset of the start of *node* in *source*."""
    lineno = node.lineno  # type: ignore[attr-defined]
    col = node.col_offset  # type: ignore[attr-defined]
    if lineno is None or col is None:
        return None
    line_offset = _line_byte_offsets(source)[lineno - 1]
    # col_offset is in *characters* for the AST, so we need to encode the
    # prefix of that line to get the correct byte offset.
    line_bytes = source[line_offset:]
    line_text = line_bytes.split(b"\n", 1)[0]
    # Decode with surrogateescape to handle any encoding
    prefix = line_text.decode("utf-8", errors="surrogateescape")[:col]
    return line_offset + len(prefix.encode("utf-8", errors="surrogateescape"))


def _node_end_byte_offset(source: bytes, node: ast.AST) -> int | None:
    """Return the byte offset of the end of *node* in *source*."""
    lineno = node.end_lineno  # type: ignore[attr-defined]
    col = node.end_col_offset  # type: ignore[attr-defined]
    if lineno is None or col is None:
        return None
    line_offset = _line_byte_offsets(source)[lineno - 1]
    line_bytes = source[line_offset:]
    line_text = line_bytes.split(b"\n", 1)[0]
    prefix = line_text.decode("utf-8", errors="surrogateescape")[:col]
    return line_offset + len(prefix.encode("utf-8", errors="surrogateescape"))


def _line_byte_offsets(source: bytes) -> list[int]:
    """Return a list mapping 0-based line indices to byte offsets."""
    offsets = [0]
    idx = 0
    while True:
        idx = source.find(b"\n", idx)
        if idx == -1:
            break
        idx += 1
        offsets.append(idx)
    return offsets


def _blank_tokens(source: bytes, ranges: list[tuple[int, int]]) -> bytes:
    """Replace tokens that overlap with *ranges* with empty strings.

    After blanking, consecutive blank lines left behind are collapsed.
    """
    tokens = list(tokenize.tokenize(io.BytesIO(source).readline))

    line_offsets = _line_byte_offsets(source)

    for i, tok in enumerate(tokens):
        if tok.type in (
            tokenize.STRING,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.COMMENT,
        ):
            tok_start = _tok_byte_offset(tok.start, line_offsets, source)
            tok_end = _tok_byte_offset(tok.end, line_offsets, source)
            if tok_start is None or tok_end is None:
                continue
            if _overlaps(tok_start, tok_end, ranges):
                # Replace the token string with empty content.
                tokens[i] = tok._replace(string="")

    result = tokenize.untokenize(tokens)
    # untokenize may leave blank lines where the docstring was; collapse them.
    return _collapse_blank_lines(result)


def _tok_byte_offset(
    pos: tuple[int, int], line_offsets: list[int], source: bytes
) -> int | None:
    """Convert a tokenize ``(line, col)`` pair to a byte offset."""
    line, col = pos
    if line < 1 or line > len(line_offsets):
        return None
    line_start = line_offsets[line - 1]
    line_bytes = source[line_start:]
    line_text = line_bytes.split(b"\n", 1)[0]
    prefix = line_text.decode("utf-8", errors="surrogateescape")[:col]
    return line_start + len(prefix.encode("utf-8", errors="surrogateescape"))


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    """Return ``True`` if the ``[start, end)`` interval overlaps any range."""
    for r_start, r_end in ranges:
        if start < r_end and end > r_start:
            return True
    return False


def _collapse_blank_lines(source: bytes) -> bytes:
    """Remove runs of more than one consecutive blank line."""
    lines = source.split(b"\n")
    result: list[bytes] = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == b""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return b"\n".join(result)

import ast
import shutil
import textwrap
from pathlib import Path

import pytest

from pyodide_build.optimizers.remove_docstrings import (
    RemoveDocstringsOptimizer,
    _remove_docstrings,
)

FIXTURES = Path(__file__).parent / "_fixtures"


class TestShouldProcess:
    def test_py_files(self):
        opt = RemoveDocstringsOptimizer()
        assert opt.should_process(Path("pkg/module.py")) is True

    def test_non_py_files(self):
        opt = RemoveDocstringsOptimizer()
        assert opt.should_process(Path("pkg/data.txt")) is False
        assert opt.should_process(Path("pkg/lib.so")) is False
        assert opt.should_process(Path("pkg/module.pyc")) is False


class TestRemoveDocstrings:
    """Unit tests for the core _remove_docstrings function."""

    def test_module_docstring(self):
        source = b'"""Module doc."""\nx = 1\n'
        result = _remove_docstrings(source)
        assert b'"""Module doc."""' not in result
        assert b"x = 1" in result

    def test_function_docstring(self):
        source = textwrap.dedent("""\
            def f():
                \"\"\"Function doc.\"\"\"
                return 1
        """).encode()
        result = _remove_docstrings(source)
        assert b"Function doc." not in result
        assert b"return 1" in result

    def test_class_docstring(self):
        source = textwrap.dedent("""\
            class C:
                \"\"\"Class doc.\"\"\"
                x = 1
        """).encode()
        result = _remove_docstrings(source)
        assert b"Class doc." not in result
        assert b"x = 1" in result

    def test_method_docstring(self):
        source = textwrap.dedent("""\
            class C:
                def m(self):
                    \"\"\"Method doc.\"\"\"
                    return 1
        """).encode()
        result = _remove_docstrings(source)
        assert b"Method doc." not in result
        assert b"return 1" in result

    def test_async_function_docstring(self):
        source = textwrap.dedent("""\
            async def f():
                \"\"\"Async doc.\"\"\"
                return 1
        """).encode()
        result = _remove_docstrings(source)
        assert b"Async doc." not in result
        assert b"return 1" in result

    def test_preserves_regular_strings(self):
        source = textwrap.dedent("""\
            x = "not a docstring"
            y = 'also not a docstring'
        """).encode()
        result = _remove_docstrings(source)
        assert b"not a docstring" in result
        assert b"also not a docstring" in result

    def test_preserves_comments(self):
        source = b"# A comment\nx = 1\n"
        result = _remove_docstrings(source)
        assert b"# A comment" in result

    def test_preserves_inline_assignment_strings(self):
        source = textwrap.dedent("""\
            def f():
                msg = \"\"\"This is a multi-line
                string assignment, not a docstring.\"\"\"
                return msg
        """).encode()
        result = _remove_docstrings(source)
        assert b"multi-line" in result

    def test_no_docstrings_is_noop(self):
        source = b"x = 1\ny = 2\n"
        assert _remove_docstrings(source) == source

    def test_single_quote_docstring(self):
        source = textwrap.dedent("""\
            def f():
                '''Single-quoted docstring.'''
                return 1
        """).encode()
        result = _remove_docstrings(source)
        assert b"Single-quoted" not in result
        assert b"return 1" in result

    def test_multiline_docstring(self):
        source = textwrap.dedent('''\
            def f():
                """
                Multi-line
                docstring.
                """
                return 1
        ''').encode()
        result = _remove_docstrings(source)
        assert b"Multi-line" not in result
        assert b"return 1" in result

    def test_result_is_valid_python(self):
        source = textwrap.dedent("""\
            \"\"\"Module doc.\"\"\"

            def f():
                \"\"\"Function doc.\"\"\"
                return 1

            class C:
                \"\"\"Class doc.\"\"\"
                def m(self):
                    \"\"\"Method doc.\"\"\"
                    return 2
        """).encode()
        result = _remove_docstrings(source)
        # Must parse without error
        ast.parse(result)

    def test_syntax_error_returns_original(self):
        source = b"def f(\n"  # invalid syntax
        # _remove_docstrings should raise SyntaxError (caught in process_file)
        with pytest.raises(SyntaxError):
            _remove_docstrings(source)

    def test_empty_file(self):
        assert _remove_docstrings(b"") == b""

    def test_encoding_cookie_preserved(self):
        source = b'# -*- coding: utf-8 -*-\n"""Doc."""\nx = 1\n'
        result = _remove_docstrings(source)
        assert b"# -*- coding: utf-8 -*-" in result


class TestProcessFile:
    def test_modifies_file_in_place(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text('"""Remove me."""\nx = 1\n')
        opt = RemoveDocstringsOptimizer()
        opt.process_file(f)

        content = f.read_text()
        assert "Remove me." not in content
        assert "x = 1" in content

    def test_syntax_error_leaves_file_unchanged(self, tmp_path):
        f = tmp_path / "bad.py"
        original = "def f(\n"
        f.write_text(original)
        opt = RemoveDocstringsOptimizer()
        opt.process_file(f)

        assert f.read_text() == original

    def test_fixture_file(self, tmp_path):
        """Run optimizer on the fixture sample_module.py and verify result."""
        src = FIXTURES / "sample_module.py"
        dst = tmp_path / "sample_module.py"
        shutil.copy(src, dst)

        opt = RemoveDocstringsOptimizer()
        opt.process_file(dst)

        result = dst.read_text()

        # Docstrings should be gone
        assert "module-level docstring" not in result
        assert "Return a greeting" not in result
        assert "Example class docstring" not in result
        assert "Method docstring" not in result
        assert "Async method docstring" not in result
        assert "triple-single-quoted" not in result

        # Code and comments should be preserved
        assert "import os" in result
        assert "# A regular comment" in result
        assert 'VERSION = "1.0.0"' in result
        assert "return 42" in result
        assert 'class_var = "keep me"' in result

        # Must still be valid Python
        ast.parse(result)

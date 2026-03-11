from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from pyodide_build.common import search_pyproject_toml


class OptimizerConfig(BaseModel):
    """Configuration for wheel post-processing optimizers.

    Loaded from ``[tool.pyodide.optimizer]`` in ``pyproject.toml``.
    Each field corresponds to an optimizer name; the boolean value controls
    whether it is enabled.  When a field is not set the optimizer's own
    ``default_enabled`` attribute is used instead.

    Setting ``disable_all = True`` turns every optimizer off regardless of
    per-optimizer flags.
    """

    disable_all: bool = False
    remove_docstrings: bool = False
    model_config = ConfigDict(extra="forbid")


def load_optimizer_config(
    curdir: Path | None = None,
) -> OptimizerConfig:
    """Load ``[tool.pyodide.optimizer]`` from the nearest ``pyproject.toml``.

    Parameters
    ----------
    curdir
        Directory to start searching from.  Defaults to the current working
        directory.

    Returns
    -------
    OptimizerConfig
        Parsed configuration, or defaults if no config section is found.
    """
    if curdir is None:
        curdir = Path.cwd()

    _, configs = search_pyproject_toml(curdir)
    if configs is None:
        return OptimizerConfig()

    optimizer_section = _extract_optimizer_section(configs)
    if optimizer_section is None:
        return OptimizerConfig()

    return OptimizerConfig(**optimizer_section)


def _extract_optimizer_section(
    configs: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the ``[tool.pyodide.optimizer]`` table, or ``None``."""
    try:
        optimizer = configs["tool"]["pyodide"]["optimizer"]
        return optimizer if isinstance(optimizer, dict) else None
    except (KeyError, TypeError):
        return None

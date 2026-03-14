from abc import ABC, abstractmethod
from pathlib import Path

# ---------------------------------------------------------------------------
# Order constants
#
# Optimizers are sorted by ``order`` (ascending) before execution.
# Using named constants keeps individual optimizer modules readable and
# makes it obvious where a new optimizer should slot in.
# ---------------------------------------------------------------------------

"""Run before most other optimizers (e.g. removing files entirely)."""
ORDER_EARLY: int = 100

"""Default order for source-level transforms."""
ORDER_NORMAL: int = 500

"""Run after source transforms (e.g. compiling .py -> .pyc)."""
ORDER_LATE: int = 900


class WheelOptimizer(ABC):
    """Base class for wheel post-processing optimizers.

    Subclasses implement file-level transformations that are applied to
    the unpacked contents of a wheel before it is repacked.

    Attributes
    ----------
    name
        Identifier used as the config key in ``[tool.pyodide.optimizer]``.
    description
        Human-readable one-liner shown in log output.
    default_enabled
        Whether this optimizer runs when not explicitly mentioned in config.
        Safe optimizers default to ``True``; aggressive ones to ``False``.
    order
        Determines execution order. Lower values run first.
        Use the constants :data:`ORDER_EARLY`, :data:`ORDER_NORMAL`, and
        :data:`ORDER_LATE` as starting points.  For example, an optimizer
        that compiles ``.py`` to ``.pyc`` should run *after* all source-level
        transforms and therefore use :data:`ORDER_LATE`.
    """

    name: str
    description: str
    default_enabled: bool = False
    order: int = ORDER_NORMAL

    @abstractmethod
    def should_process(self, file_path: Path) -> bool:
        """Return ``True`` if this optimizer should handle *file_path*.

        Parameters
        ----------
        file_path
            Path **relative** to the unpacked wheel root directory.
        """
        raise NotImplementedError

    @abstractmethod
    def process_file(self, full_path: Path) -> None:
        """Apply the optimization to a single file **in-place**.

        Parameters
        ----------
        full_path
            Absolute path to the file inside the unpacked wheel temporary
            directory.
        """
        raise NotImplementedError

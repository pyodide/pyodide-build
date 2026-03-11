from pathlib import Path

from pyodide_build.logger import logger
from pyodide_build.optimizers.base import WheelOptimizer
from pyodide_build.optimizers.config import OptimizerConfig
from pyodide_build.optimizers.remove_docstrings import RemoveDocstringsOptimizer

# ---------------------------------------------------------------------------
# Registry
#
# All built-in optimizers are listed here.  To add a new optimizer:
#   1. Create the class in its own module under ``optimizers/``
#   2. Append an instance to ``ALL_OPTIMIZERS``
#   3. Add the corresponding field to ``OptimizerConfig``
# ---------------------------------------------------------------------------

ALL_OPTIMIZERS: list[WheelOptimizer] = [
    RemoveDocstringsOptimizer(),
]


class OptimizerPipeline:
    """Resolve enabled optimizers from config and run them on a wheel directory."""

    def __init__(self, config: OptimizerConfig) -> None:
        self.optimizers = _resolve_optimizers(config)

    def run(self, wheel_dir: Path) -> None:
        """Walk *wheel_dir* and apply each enabled optimizer to matching files."""
        if not self.optimizers:
            return

        names = ", ".join(o.name for o in self.optimizers)
        logger.info("Running optimizers: %s", names)

        for optimizer in self.optimizers:
            _run_single(optimizer, wheel_dir)


def _resolve_optimizers(config: OptimizerConfig) -> list[WheelOptimizer]:
    """Return the ordered list of optimizers that should run."""
    if config.disable_all:
        return []

    enabled: list[WheelOptimizer] = []
    for opt in ALL_OPTIMIZERS:
        # If the config has an explicit value for this optimizer, use it.
        # Otherwise fall back to the optimizer's own default.
        is_enabled = getattr(config, opt.name, opt.default_enabled)
        if is_enabled:
            enabled.append(opt)

    # Sort by order so that e.g. ORDER_LATE optimizers run last.
    enabled.sort(key=lambda o: o.order)
    return enabled


def _run_single(optimizer: WheelOptimizer, wheel_dir: Path) -> None:
    """Apply *optimizer* to every matching file under *wheel_dir*."""
    processed = 0
    for file_path in sorted(wheel_dir.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(wheel_dir)

        # Never touch .dist-info contents.
        if relative.parts and relative.parts[0].endswith(".dist-info"):
            continue

        if optimizer.should_process(relative):
            optimizer.process_file(file_path)
            processed += 1

    logger.info(
        "Optimizer %s: processed %d file(s)",
        optimizer.name,
        processed,
    )

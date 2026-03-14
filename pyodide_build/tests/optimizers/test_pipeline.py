from pathlib import Path

from pyodide_build.optimizers.base import (
    ORDER_EARLY,
    ORDER_LATE,
    ORDER_NORMAL,
    WheelOptimizer,
)
from pyodide_build.optimizers.config import OptimizerConfig
from pyodide_build.optimizers.pipeline import OptimizerPipeline, _resolve_optimizers

# ---------------------------------------------------------------------------
# Stub optimizers for testing pipeline behaviour
# ---------------------------------------------------------------------------


class _StubEarly(WheelOptimizer):
    name = "stub_early"
    description = "stub"
    default_enabled = True
    order = ORDER_EARLY

    def should_process(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def process_file(self, full_path: Path) -> None:
        full_path.write_text(full_path.read_text() + "# early\n")


class _StubNormal(WheelOptimizer):
    name = "stub_normal"
    description = "stub"
    default_enabled = True
    order = ORDER_NORMAL

    def should_process(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def process_file(self, full_path: Path) -> None:
        full_path.write_text(full_path.read_text() + "# normal\n")


class _StubLate(WheelOptimizer):
    name = "stub_late"
    description = "stub"
    default_enabled = False
    order = ORDER_LATE

    def should_process(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def process_file(self, full_path: Path) -> None:
        full_path.write_text(full_path.read_text() + "# late\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveOptimizers:
    def test_disable_all(self, monkeypatch):
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubEarly(), _StubNormal()],
        )
        config = OptimizerConfig(disable_all=True)
        assert _resolve_optimizers(config) == []

    def test_default_enabled_respected(self, monkeypatch):
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubEarly(), _StubLate()],
        )
        # StubEarly has default_enabled=True, StubLate has default_enabled=False
        config = OptimizerConfig()
        resolved = _resolve_optimizers(config)
        names = [o.name for o in resolved]
        assert "stub_early" in names
        assert "stub_late" not in names

    def test_sorted_by_order(self, monkeypatch):
        # Register in wrong order — pipeline should sort.
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubLate(), _StubNormal(), _StubEarly()],
        )
        config = OptimizerConfig(disable_all=False)
        # Force all to be enabled via default_enabled
        for opt in [_StubLate, _StubNormal, _StubEarly]:
            opt.default_enabled = True
        try:
            resolved = _resolve_optimizers(config)
            orders = [o.order for o in resolved]
            assert orders == sorted(orders)
        finally:
            # Reset
            _StubLate.default_enabled = False


class TestOptimizerPipeline:
    def _make_wheel_dir(self, tmp_path: Path) -> Path:
        wheel_dir = tmp_path / "mypkg-1.0"
        pkg = wheel_dir / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "core.py").write_text("x = 1\n")
        (pkg / "data.txt").write_text("keep me\n")

        dist_info = wheel_dir / "mypkg-1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text("Name: mypkg\n")
        (dist_info / "RECORD").write_text("")
        return wheel_dir

    def test_skips_dist_info(self, tmp_path, monkeypatch):
        """Optimizers must never touch .dist-info contents."""
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubNormal()],
        )
        wheel_dir = self._make_wheel_dir(tmp_path)
        config = OptimizerConfig()
        # StubNormal is default_enabled=True and matches .py
        OptimizerPipeline(config).run(wheel_dir)

        # .dist-info should be untouched
        metadata = (wheel_dir / "mypkg-1.0.dist-info" / "METADATA").read_text()
        assert "# normal" not in metadata

    def test_processes_matching_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubNormal()],
        )
        wheel_dir = self._make_wheel_dir(tmp_path)
        config = OptimizerConfig()
        OptimizerPipeline(config).run(wheel_dir)

        assert "# normal" in (wheel_dir / "mypkg" / "core.py").read_text()

    def test_skips_non_matching_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubNormal()],
        )
        wheel_dir = self._make_wheel_dir(tmp_path)
        config = OptimizerConfig()
        OptimizerPipeline(config).run(wheel_dir)

        # .txt file should not be touched
        assert (wheel_dir / "mypkg" / "data.txt").read_text() == "keep me\n"

    def test_order_applied_correctly(self, tmp_path, monkeypatch):
        """Early optimizer runs before Normal."""
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [_StubNormal(), _StubEarly()],
        )
        wheel_dir = self._make_wheel_dir(tmp_path)
        config = OptimizerConfig()
        OptimizerPipeline(config).run(wheel_dir)

        content = (wheel_dir / "mypkg" / "core.py").read_text()
        early_pos = content.index("# early")
        normal_pos = content.index("# normal")
        assert early_pos < normal_pos

    def test_no_optimizers_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyodide_build.optimizers.pipeline.ALL_OPTIMIZERS",
            [],
        )
        wheel_dir = self._make_wheel_dir(tmp_path)
        config = OptimizerConfig()
        OptimizerPipeline(config).run(wheel_dir)

        assert (wheel_dir / "mypkg" / "core.py").read_text() == "x = 1\n"

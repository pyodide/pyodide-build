import pytest
from pydantic import ValidationError

from pyodide_build.optimizers.config import (
    OptimizerConfig,
    _extract_optimizer_section,
    load_optimizer_config,
)


class TestOptimizerConfig:
    def test_defaults(self):
        config = OptimizerConfig()
        assert config.disable_all is False
        assert config.remove_docstrings is False

    def test_explicit_values(self):
        config = OptimizerConfig(disable_all=True, remove_docstrings=True)
        assert config.disable_all is True
        assert config.remove_docstrings is True

    def test_extra_forbid_rejects_unknown_optimizer(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            OptimizerConfig(unknown_optimizer=True)  # type: ignore[call-arg]


class TestExtractOptimizerSection:
    def test_returns_section(self):
        configs = {"tool": {"pyodide": {"optimizer": {"remove_docstrings": True}}}}
        assert _extract_optimizer_section(configs) == {"remove_docstrings": True}

    def test_no_tool(self):
        assert _extract_optimizer_section({}) is None

    def test_no_pyodide(self):
        assert _extract_optimizer_section({"tool": {}}) is None

    def test_no_optimizer(self):
        assert _extract_optimizer_section({"tool": {"pyodide": {}}}) is None

    def test_non_dict_tool(self):
        assert _extract_optimizer_section({"tool": "not a dict"}) is None


class TestLoadOptimizerConfig:
    def test_no_pyproject(self, tmp_path):
        config = load_optimizer_config(tmp_path)
        assert config == OptimizerConfig()

    def test_pyproject_without_optimizer_section(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.pyodide.build]\n")
        config = load_optimizer_config(tmp_path)
        assert config == OptimizerConfig()

    def test_pyproject_with_optimizer_section(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pyodide.optimizer]\nremove_docstrings = true\n"
        )
        config = load_optimizer_config(tmp_path)
        assert config.remove_docstrings is True
        assert config.disable_all is False

    def test_pyproject_disable_all(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pyodide.optimizer]\ndisable_all = true\nremove_docstrings = true\n"
        )
        config = load_optimizer_config(tmp_path)
        assert config.disable_all is True
        assert config.remove_docstrings is True

    def test_pyproject_rejects_unknown_key(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pyodide.optimizer]\nnot_a_real_optimizer = true\n"
        )
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            load_optimizer_config(tmp_path)

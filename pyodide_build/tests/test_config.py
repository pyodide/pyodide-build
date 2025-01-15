from pyodide_build import common
from pyodide_build.config import (
    BUILD_KEY_TO_VAR,
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_COMPUTED,
    ConfigManager,
    CrossBuildEnvConfigManager,
)
from pyodide_build.xbuildenv import CrossBuildEnvManager


class TestConfigManager:
    def test_default_config(self, reset_env_vars, reset_cache):
        config_manager = ConfigManager()
        default_config = config_manager._load_default_config()
        assert default_config.keys() == DEFAULT_CONFIG.keys()

    def test_load_config_from_env(self, reset_env_vars, reset_cache):
        config_manager = ConfigManager()
        env = {
            "CMAKE_TOOLCHAIN_FILE": "/path/to/toolchain",
            "MESON_CROSS_FILE": "/path/to/crossfile",
        }

        config = config_manager._load_config_from_env(env)
        assert config["cmake_toolchain_file"] == "/path/to/toolchain"
        assert config["meson_cross_file"] == "/path/to/crossfile"

    def test_load_config_from_file(self, tmp_path, reset_env_vars, reset_cache):
        pyproject_file = tmp_path / "pyproject.toml"

        env = {
            "MESON_CROSS_FILE": "/path/to/crossfile",
        }

        pyproject_file.write_text("""[tool.pyodide.build]
                                  invalid_flags = "this_should_not_be_parsed"
                                  default_cross_build_env_url = "https://example.com/cross_build_env.tar.gz"
                                  """)

        config_manager = ConfigManager()
        config = config_manager._load_config_file(pyproject_file, env)

        assert "invalid_flags" not in config
        assert (
            config["default_cross_build_env_url"]
            == "https://example.com/cross_build_env.tar.gz"
        )


class TestCrossBuildEnvConfigManager_OutOfTree:
    def test_default_config(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        default_config = config_manager._load_default_config()
        assert default_config.keys() == DEFAULT_CONFIG.keys()

    def test_makefile_envs(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        makefile_vars = config_manager._load_makefile_envs()

        # It should contain information about the cpython and emscripten versions
        assert "pyversion" in makefile_vars
        assert "pyodide_emscripten_version" in makefile_vars
        assert "pythoninclude" in makefile_vars

        default_config = config_manager._load_default_config()
        for key in default_config:
            assert key not in makefile_vars

    def test_get_make_environment_vars(
        self, dummy_xbuildenv, reset_env_vars, reset_cache
    ):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )
        make_vars = config_manager._get_make_environment_vars()
        assert make_vars["PYODIDE_ROOT"] == str(xbuildenv_manager.pyodide_root)

    def test_computed_vars(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        makefile_vars = config_manager._load_makefile_envs()

        for k, v in DEFAULT_CONFIG_COMPUTED.items():
            assert k in makefile_vars
            assert makefile_vars[k] != v  # The template should have been substituted
            assert "$(" not in makefile_vars[k]

    def test_load_config_from_env(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        env = {
            "CMAKE_TOOLCHAIN_FILE": "/path/to/toolchain",
            "MESON_CROSS_FILE": "/path/to/crossfile",
        }

        config = config_manager._load_config_from_env(env)
        assert config["cmake_toolchain_file"] == "/path/to/toolchain"
        assert config["meson_cross_file"] == "/path/to/crossfile"

    def test_load_config_from_file(
        self, tmp_path, dummy_xbuildenv, reset_env_vars, reset_cache
    ):
        pyproject_file = tmp_path / "pyproject.toml"

        env = {
            "MESON_CROSS_FILE": "/path/to/crossfile",
            "CFLAGS_BASE": "-O2",
        }

        pyproject_file.write_text("""[tool.pyodide.build]
                                  invalid_flags = "this_should_not_be_parsed"
                                  cflags = "$(CFLAGS_BASE) -I/path/to/include"
                                  ldflags = "-L/path/to/lib"
                                  rust_toolchain = "nightly"
                                  meson_cross_file = "$(MESON_CROSS_FILE)"
                                  build_dependency_index_url = "https://example.com/simple"
                                  """)

        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        config = config_manager._load_config_file(pyproject_file, env)

        assert "invalid_flags" not in config
        assert config["cflags"] == "-O2 -I/path/to/include"
        assert config["ldflags"] == "-L/path/to/lib"
        assert config["rust_toolchain"] == "nightly"
        assert config["meson_cross_file"] == "/path/to/crossfile"
        assert config["build_dependency_index_url"] == "https://example.com/simple"

    def test_config_all(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )
        config = config_manager.config

        for key in BUILD_KEY_TO_VAR.keys():
            assert key in config

    def test_to_env(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )
        env = config_manager.to_env()
        for env_var in BUILD_KEY_TO_VAR.values():
            assert env_var in env

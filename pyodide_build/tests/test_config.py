from pyodide_build import common
from pyodide_build.config import (
    BUILD_KEY_TO_VAR,
    BUILD_VAR_TO_KEY,
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_COMPUTED,
    PYODIDE_CLI_CONFIGS,
    ConfigManager,
    CrossBuildEnvConfigManager,
    _parse_makefile_envs,
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
            "PYODIDE_XBUILDENV_PATH": "/path/to/xbuildenv",
        }

        config = config_manager._load_config_from_env(env)
        assert config["cmake_toolchain_file"] == "/path/to/toolchain"
        assert config["meson_cross_file"] == "/path/to/crossfile"
        assert config["xbuildenv_path"] == "/path/to/xbuildenv"

    def test_load_config_from_file(self, tmp_path, reset_env_vars, reset_cache):
        pyproject_file = tmp_path / "pyproject.toml"

        env = {
            "MESON_CROSS_FILE": "/path/to/crossfile",
        }

        pyproject_file.write_text("""[tool.pyodide.build]
                                  invalid_flags = "this_should_not_be_parsed"
                                  default_cross_build_env_url = "https://example.com/cross_build_env.tar.gz"
                                  skip_emscripten_version_check = "1"
                                  xbuildenv_path = "my_custom/xbuildenv_path"
                                  ignored_build_requirements = "cmake foo bar"
                                  """)

        config_manager = ConfigManager()
        config = config_manager._load_config_file(pyproject_file, env)

        assert "invalid_flags" not in config
        assert (
            config["default_cross_build_env_url"]
            == "https://example.com/cross_build_env.tar.gz"
        )
        assert config["skip_emscripten_version_check"] == "1"
        assert config["xbuildenv_path"] == "my_custom/xbuildenv_path"
        assert config["ignored_build_requirements"] == "cmake foo bar"


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

    def test_cross_build_envs(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        xbuildenv_manager = CrossBuildEnvManager(
            dummy_xbuildenv / common.xbuildenv_dirname()
        )
        config_manager = CrossBuildEnvConfigManager(
            pyodide_root=xbuildenv_manager.pyodide_root
        )

        makefile_vars = config_manager._load_cross_build_envs()

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

        makefile_vars = config_manager._load_cross_build_envs()

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
            "PYODIDE_XBUILDENV_PATH": "/path/to/xbuildenv",
            "IGNORED_BUILD_REQUIREMENTS": "cmake foo bar",
            "RUST_EMSCRIPTEN_TARGET_URL": "https://example.com/rust_wasm32_emscripten_target.tar.gz",
        }

        config = config_manager._load_config_from_env(env)
        assert config["cmake_toolchain_file"] == "/path/to/toolchain"
        assert config["meson_cross_file"] == "/path/to/crossfile"
        assert config["xbuildenv_path"] == "/path/to/xbuildenv"
        assert config["ignored_build_requirements"] == "cmake foo bar"
        assert (
            config["rust_emscripten_target_url"]
            == "https://example.com/rust_wasm32_emscripten_target.tar.gz"
        )

    def test_load_config_from_file(
        self, tmp_path, dummy_xbuildenv, reset_env_vars, reset_cache
    ):
        pyproject_file = tmp_path / "pyproject.toml"

        env = {
            "MESON_CROSS_FILE": "/path/to/crossfile",
            "CFLAGS_BASE": "-O2",
            "RUST_EMSCRIPTEN_TARGET_URL": "https://example.com/rust_wasm32_emscripten_target.tar.gz",
        }

        pyproject_file.write_text("""[tool.pyodide.build]
                                  invalid_flags = "this_should_not_be_parsed"
                                  cflags = "$(CFLAGS_BASE) -I/path/to/include"
                                  ldflags = "-L/path/to/lib"
                                  rust_toolchain = "nightly"
                                  meson_cross_file = "$(MESON_CROSS_FILE)"
                                  build_dependency_index_url = "https://example.com/simple"
                                  xbuildenv_path = "../my_custom/xbuildenv_path" # also helps check relative paths
                                  ignored_build_requirements = "cmake foo bar"
                                  rust_emscripten_target_url = "$(RUST_EMSCRIPTEN_TARGET_URL)"
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
        assert config["xbuildenv_path"] == "../my_custom/xbuildenv_path"
        assert config["ignored_build_requirements"] == "cmake foo bar"
        assert (
            config["rust_emscripten_target_url"]
            == "https://example.com/rust_wasm32_emscripten_target.tar.gz"
        )

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


def test_cli_config_subset():
    for value in PYODIDE_CLI_CONFIGS.values():
        assert value in BUILD_VAR_TO_KEY, (
            f"All cli config values should be in build var to key mapping, but {value} is not"
        )


class TestParseMakefileEnvs:
    def test_parse_makefile_envs_basic(self, tmp_path, reset_env_vars, reset_cache):
        """Test basic parsing of Makefile.envs without make command"""
        # Create a simple mock Makefile.envs
        makefile = tmp_path / "Makefile.envs"
        makefile.write_text("""# Comment line
export PYVERSION ?= 3.13.2
export PYODIDE_EMSCRIPTEN_VERSION ?= 4.0.9
export PYODIDE_VERSION ?= 0.30.0.dev0

# Another comment
export PLATFORM_TRIPLET=wasm32-emscripten
""")
        env = {"PYODIDE_ROOT": str(tmp_path)}
        result = _parse_makefile_envs(env, makefile)

        assert result["PYVERSION"] == "3.13.2"
        assert result["PYODIDE_EMSCRIPTEN_VERSION"] == "4.0.9"
        assert result["PYODIDE_VERSION"] == "0.30.0.dev0"
        assert result["PLATFORM_TRIPLET"] == "wasm32-emscripten"

    def test_parse_makefile_envs_variable_substitution(
        self, tmp_path, reset_env_vars, reset_cache
    ):
        """Test variable substitution in Makefile.envs"""
        makefile = tmp_path / "Makefile.envs"
        makefile.write_text("""export PYVERSION ?= 3.13.2
export PYMAJOR=3
export PYMINOR=13
export PYMICRO=2

export PYTHONINCLUDE=$(PYODIDE_ROOT)/cpython/installs/python-$(PYVERSION)/include/python$(PYMAJOR).$(PYMINOR)
export PLATFORM_TRIPLET=wasm32-emscripten
export SYSCONFIG_NAME=_sysconfigdata__emscripten_$(PLATFORM_TRIPLET)
""")
        env = {"PYODIDE_ROOT": "/test/root"}
        result = _parse_makefile_envs(env, makefile)

        assert (
            result["PYTHONINCLUDE"]
            == "/test/root/cpython/installs/python-3.13.2/include/python3.13"
        )
        assert (
            result["SYSCONFIG_NAME"] == "_sysconfigdata__emscripten_wasm32-emscripten"
        )

    def test_parse_makefile_envs_skips_irrelevant_vars(
        self, tmp_path, reset_env_vars, reset_cache
    ):
        """Test that parser only processes variables in BUILD_VAR_TO_KEY"""
        makefile = tmp_path / "Makefile.envs"
        makefile.write_text("""export PYVERSION ?= 3.13.2
export SOME_RANDOM_VAR=should_not_be_included
export ANOTHER_VAR=also_ignored
export PLATFORM_TRIPLET=wasm32-emscripten
""")

        env = {"PYODIDE_ROOT": str(tmp_path)}
        result = _parse_makefile_envs(env, makefile)

        assert result["PYVERSION"] == "3.13.2"
        assert result["PLATFORM_TRIPLET"] == "wasm32-emscripten"
        # These should not be in result since they're not in BUILD_VAR_TO_KEY
        assert "SOME_RANDOM_VAR" not in result
        assert "ANOTHER_VAR" not in result

    def test_parse_makefile_envs_empty_lines_and_comments(
        self, tmp_path, reset_env_vars, reset_cache
    ):
        """Test that parser handles comments and empty lines correctly"""
        makefile = tmp_path / "Makefile.envs"
        makefile.write_text("""
# This is a comment
export PYVERSION ?= 3.13.2

# Another comment

export PLATFORM_TRIPLET=wasm32-emscripten
# End comment
""")

        env = {"PYODIDE_ROOT": str(tmp_path)}
        result = _parse_makefile_envs(env, makefile)

        assert result["PYVERSION"] == "3.13.2"
        assert result["PLATFORM_TRIPLET"] == "wasm32-emscripten"

    def test_parse_makefile_envs_nested_substitution(
        self, tmp_path, reset_env_vars, reset_cache
    ):
        """Test nested variable substitution"""
        makefile = tmp_path / "Makefile.envs"
        makefile.write_text("""export PYMAJOR=3
export PYMINOR=13
export PYVERSION=$(PYMAJOR).$(PYMINOR).2
export CPYTHONINSTALL=$(PYODIDE_ROOT)/cpython/installs/python-$(PYVERSION)
export PYTHONINCLUDE=$(CPYTHONINSTALL)/include
export TARGETINSTALLDIR=$(PYODIDE_ROOT)/cpython/installs/python-$(PYVERSION)
""")

        env = {"PYODIDE_ROOT": "/root"}
        result = _parse_makefile_envs(env, makefile)

        assert result["PYVERSION"] == "3.13.2"
        assert result["CPYTHONINSTALL"] == "/root/cpython/installs/python-3.13.2"
        assert result["PYTHONINCLUDE"] == "/root/cpython/installs/python-3.13.2/include"
        assert result["TARGETINSTALLDIR"] == "/root/cpython/installs/python-3.13.2"

from pathlib import Path
from typing import Any, Literal, cast

import attrs
import cattrs
from attrs import Factory, define, field
from cattrs.gen import make_dict_structure_fn, override

from pyodide_build.spec import _BuildSpecExports


class SpecValidationError(ValueError):
    """Raised when a recipe spec fails validation."""


def _afield(
    default: Any = attrs.NOTHING,
    *,
    alias: str | None = None,
    factory: Any = None,
    converter: Any = None,
) -> Any:
    """attrs field helper that stores the YAML alias in the field metadata."""
    metadata = {"alias": alias} if alias is not None else {}
    kwargs: dict[str, Any] = {"metadata": metadata}
    if converter is not None:
        kwargs["converter"] = converter
    if factory is not None:
        return field(factory=factory, **kwargs)
    return field(default=default, **kwargs)


def _to_path(value: Any) -> Path | None:
    if value is None:
        return None
    return Path(value)


@define
class _PackageSpec:
    name: str
    version: str
    top_level: list[str] = _afield(factory=list, alias="top-level")
    tag: list[str] = _afield(factory=list)
    disabled: bool = _afield(False, alias="_disabled")
    pinned: bool = _afield(False, alias="pinned")


@define
class _SourceSpec:
    url: str | None = None
    extract_dir: str | None = None
    path: Path | None = _afield(None, converter=_to_path)
    sha256: str | None = None
    patches: list[str] = _afield(factory=list)
    extras: list[tuple[str, str]] = _afield(factory=list)

    def __attrs_post_init__(self) -> None:
        self._check_url_has_hash()
        self._check_in_tree_url()
        self._check_patches_extra()

    def _check_url_has_hash(self) -> None:
        if self.url is not None and self.sha256 is None:
            raise SpecValidationError(
                "If source is downloaded from url, it must have a 'source/sha256' hash."
            )

    def _check_in_tree_url(self) -> None:
        in_tree = self.path is not None
        from_url = self.url is not None

        # cpython_modules is a special case, it is not in the tree
        # TODO: just copy the file into the tree?
        # if not (in_tree or from_url):
        #     raise SpecValidationError("Source section should have a 'url' or 'path' key")

        if in_tree and from_url:
            raise SpecValidationError(
                "Source section should not have both a 'url' and a 'path' key"
            )

    def _check_patches_extra(self) -> None:
        in_tree = self.path is not None
        url_is_wheel = self.url and self.url.endswith(".whl")

        if in_tree and (self.patches or self.extras):
            raise SpecValidationError(
                "If source is in tree, 'source/patches' and 'source/extras' keys "
                "are not allowed"
            )

        if url_is_wheel and (self.patches or self.extras):
            raise SpecValidationError(
                "If source is a wheel, 'source/patches' and 'source/extras' "
                "keys are not allowed"
            )


_BuildSpecTypes = Literal[
    "package", "static_library", "shared_library", "cpython_module"
]


@define
class _BuildSpec:
    exports: _BuildSpecExports = "pyinit"
    backend_flags: str = _afield("", alias="backend-flags")
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    package_type: _BuildSpecTypes = _afield("package", alias="type")
    cross_script: str | None = _afield(None, alias="cross-script")
    script: str | None = None
    post: str | None = None
    unvendor_tests: bool = _afield(True, alias="unvendor-tests")
    retain_test_patterns: list[str] = _afield(
        factory=list, alias="_retain-test-patterns"
    )
    vendor_sharedlib: bool = _afield(True, alias="vendor-sharedlib")
    cross_build_env: bool = _afield(False, alias="cross-build-env")
    cross_build_files: list[str] = _afield(factory=list, alias="cross-build-files")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "_BuildSpec":
        return _converter.structure(data, cls)

    def __attrs_post_init__(self) -> None:
        self._check_config()

    def _check_config(self) -> None:
        static_library = self.package_type == "static_library"
        shared_library = self.package_type == "shared_library"
        cpython_module = self.package_type == "cpython_module"

        if not (static_library or shared_library or cpython_module):
            return

        allowed_keys = {
            "package_type",
            "script",
            "exports",
            "unvendor_tests",
        }

        typ = self.package_type
        for key in _non_default_fields(self):
            if key not in allowed_keys:
                raise SpecValidationError(
                    f"If building a {typ}, 'build/{key}' key is not allowed."
                )


@define
class _RequirementsSpec:
    run: list[str] = _afield(factory=list)
    host: list[str] = _afield(factory=list)
    executable: list[str] = _afield(factory=list)
    constraint: list[str] = _afield(factory=list)


@define
class _TestSpec:
    imports: list[str] = _afield(factory=list)


@define
class _AboutSpec:
    home: str | None = None
    PyPI: str | None = None
    summary: str | None = None
    license: str | None = None


@define
class _ExtraSpec:
    recipe_maintainers: list[str] = _afield(factory=list, alias="recipe-maintainers")


@define
class MetaConfig:
    package: _PackageSpec
    source: _SourceSpec = Factory(_SourceSpec)
    build: _BuildSpec = Factory(_BuildSpec)
    requirements: _RequirementsSpec = Factory(_RequirementsSpec)
    test: _TestSpec = Factory(_TestSpec)
    about: _AboutSpec = Factory(_AboutSpec)
    extra: _ExtraSpec = Factory(_ExtraSpec)

    def __attrs_post_init__(self) -> None:
        self._check_wheel_host_requirements()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaConfig":
        return _converter.structure(data, cls)

    def clone(self) -> "MetaConfig":
        """Return a deep copy of this configuration."""
        import copy

        return copy.deepcopy(self)

    @classmethod
    def from_yaml(cls, path: Path) -> "MetaConfig":
        """Load the meta.yaml from a path

        Parameters
        ----------
        path
            path to the meta.yaml file
        """
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")

        config_raw = yaml.load(path)

        config = cls.from_dict(config_raw)
        if config.source.path:
            config.source.path = path.parent / config.source.path
        return config

    def to_yaml(self, path: Path) -> None:
        """Serialize the configuration to meta.yaml file

        Parameters
        ----------
        path
            path to the meta.yaml file
        """
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.representer.ignore_aliases = lambda *_: True

        with open(path, "w") as f:
            yaml.dump(_unstructure_spec(self), f)

    def _check_wheel_host_requirements(self) -> None:
        """Check that if sources is a wheel it shouldn't have host dependencies."""
        if self.source.path is None and self.source.url is None:
            raise SpecValidationError(
                'either "path" or "url" must be provided in the "source" section'
            )

        source_url = self.source.url
        requirements_host = self.requirements.host

        if source_url is not None and source_url.endswith(".whl"):
            if len(requirements_host):
                raise SpecValidationError(
                    f"When source -> url is a wheel ({source_url}) the package cannot have host "
                    f"dependencies. Found {requirements_host}"
                )

            allowed_keys = {
                "post",
                "cross_build_env",
                "cross_build_files",
                "exports",
                "unvendor_tests",
                "retain_test_patterns",
                "package_type",
                "vendor_sharedlib",
            }
            for key in _non_default_fields(self.build):
                if key not in allowed_keys:
                    raise SpecValidationError(
                        f"If source is a wheel, 'build/{key}' key is not allowed"
                    )

            # A wheel is prebuilt, so shared libraries are never vendored into it.
            self.build.vendor_sharedlib = False

    def is_rust_package(self) -> bool:
        """
        Check if a package requires rust toolchain to build.
        """
        return any(
            q in self.requirements.executable for q in ("rustc", "cargo", "rustup")
        )


# (de)serialization helpers


def _field_default(f: "attrs.Attribute[Any]") -> Any:
    default = f.default
    if isinstance(default, cast(type, Factory)):
        return cast(Any, default).factory()
    return default


def _non_default_fields(inst: Any) -> set[str]:
    """Return the set of field names whose value differs from the field default."""
    result: set[str] = set()
    for f in attrs.fields(type(inst)):
        default = _field_default(f)
        if default is attrs.NOTHING:
            result.add(f.name)
            continue
        if getattr(inst, f.name) != default:
            result.add(f.name)
    return result


def _is_spec(value: Any) -> bool:
    return attrs.has(type(value))


def _unstructure_spec(inst: Any) -> dict[str, Any]:
    """Serialize an attrs spec to a dict, using YAML aliases and omitting
    fields that are the default value
    """
    result: dict[str, Any] = {}
    for f in attrs.fields(type(inst)):
        value = getattr(inst, f.name)
        alias = f.metadata.get("alias", f.name)

        if _is_spec(value):
            sub = _unstructure_spec(value)
            if sub:
                result[alias] = sub
            continue

        default = _field_default(f)
        if default is not attrs.NOTHING and value == default:
            continue

        if isinstance(value, Path):
            value = str(value)
        result[alias] = value
    return result


def _rename_overrides(cls: type) -> dict[str, Any]:
    return {
        f.name: override(rename=f.metadata["alias"])
        for f in attrs.fields(cls)
        if f.metadata.get("alias")
    }


def _structure_exports(value: Any, _type: Any) -> _BuildSpecExports:
    if isinstance(value, str):
        if value not in ("pyinit", "requested", "whole_archive"):
            raise SpecValidationError(f"Invalid value for 'build/exports': {value!r}")
        return cast(_BuildSpecExports, value)
    return [str(item) for item in value]


_converter = cattrs.Converter(detailed_validation=False)
_converter.register_structure_hook(_BuildSpecExports, _structure_exports)

for _cls in (
    _PackageSpec,
    _SourceSpec,
    _BuildSpec,
    _RequirementsSpec,
    _TestSpec,
    _AboutSpec,
    MetaConfig,
):
    _converter.register_structure_hook(
        _cls,
        make_dict_structure_fn(
            _cls,
            _converter,
            _cattrs_forbid_extra_keys=True,
            **_rename_overrides(_cls),
        ),
    )

_converter.register_structure_hook(
    _ExtraSpec,
    make_dict_structure_fn(
        _ExtraSpec,
        _converter,
        _cattrs_forbid_extra_keys=False,
        **_rename_overrides(_ExtraSpec),
    ),
)

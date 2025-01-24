from typing import Literal

_ExportTypes = Literal["pyinit", "requested", "whole_archive"]
_BuildSpecExports = _ExportTypes | list[str]

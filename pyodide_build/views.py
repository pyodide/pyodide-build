# Class for generating "views", i.e., tabular and JSON outputs from
# metadata objects, currently used in the xbuildenv CLI (search command).


import json
from dataclasses import dataclass


@dataclass
class MetadataView:
    version: str
    python: str
    emscripten: str
    pyodide_build: dict[str, str | None]
    compatible: bool

    @classmethod
    def to_table(cls, views: list["MetadataView"]) -> str:
        columns = [
            ("Version", 10),
            ("Python", 10),
            ("Emscripten", 10),
            ("pyodide-build", 25),
            ("Compatible", 10),
        ]

        # Unicode box-drawing characters
        top_left, top_right = "┌", "┐"
        bottom_left, bottom_right = "└", "┘"
        horizontal, vertical = "─", "│"
        t_down, t_up, t_right, t_left = "┬", "┴", "├", "┤"
        cross = "┼"

        # Table elements
        top_border = (
            top_left
            + t_down.join(horizontal * (width + 2) for _, width in columns)
            + top_right
        )
        header = (
            vertical
            + vertical.join(f" {name:<{width}} " for name, width in columns)
            + vertical
        )
        separator = (
            t_right
            + cross.join(horizontal * (width + 2) for _, width in columns)
            + t_left
        )
        bottom_border = (
            bottom_left
            + t_up.join(horizontal * (width + 2) for _, width in columns)
            + bottom_right
        )

        ### Printing
        table = [top_border, header, separator]
        for view in views:
            pyodide_build_range = (
                f"{view.pyodide_build['min'] or ''} - {view.pyodide_build['max'] or ''}"
            )
            row = [
                f"{view.version:<{columns[0][1]}}",
                f"{view.python:<{columns[1][1]}}",
                f"{view.emscripten:<{columns[2][1]}}",
                f"{pyodide_build_range:<{columns[3][1]}}",
                f"{'Yes' if view.compatible else 'No':<{columns[4][1]}}",
            ]
            table.append(
                vertical + vertical.join(f" {cell} " for cell in row) + vertical
            )
        table.append(bottom_border)
        return "\n".join(table)

    @classmethod
    def to_json(cls, views: list["MetadataView"]) -> str:
        result = json.dumps(
            {
                "environments": [
                    {
                        "version": view.version,
                        "python": view.python,
                        "emscripten": view.emscripten,
                        "pyodide_build": view.pyodide_build,
                        "compatible": view.compatible,
                    }
                    for view in views
                ]
            },
            indent=2,
        )
        return result

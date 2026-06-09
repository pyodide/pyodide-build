# Class for generating "views", i.e., tabular and JSON outputs from
# metadata objects, currently used in the xbuildenv CLI (search command).


import json
from dataclasses import dataclass, field


@dataclass
class MetadataView:
    version: str
    python: str
    emscripten: str
    pyodide_build: dict[str, str | None]
    compatible: bool
    published_at: str = ""
    source: str = field(
        default="stable"
    )  # "stable", "stable-debug", "nightly", or "nightly-debug"

    @classmethod
    def to_table(cls, views: list["MetadataView"], show_source: bool = False) -> str:
        # Build cell values first so we can measure them for column widths
        rows: list[list[str]] = []
        for view in views:
            mn, mx = view.pyodide_build["min"], view.pyodide_build["max"]
            if mn and mx:
                pyodide_build_range = f"{mn} - {mx}"
            elif mn:
                pyodide_build_range = f"{mn} and later"
            else:
                pyodide_build_range = "-"
            row = [
                view.version,
                view.python,
                view.emscripten,
                pyodide_build_range,
                view.published_at[:10],
                "Yes" if view.compatible else "No",
            ]
            if show_source:
                row.append(view.source)
            rows.append(row)

        headers = [
            "Version",
            "Python",
            "Emscripten",
            "pyodide-build",
            "Published",
            "Compatible",
        ]
        if show_source:
            headers.append("Source")

        # Column width = max of header width and widest cell value
        widths = [
            max(len(headers[i]), *(len(row[i]) for row in rows) if rows else [0])
            for i in range(len(headers))
        ]

        # Unicode box-drawing characters
        top_left, top_right = "┌", "┐"
        bottom_left, bottom_right = "└", "┘"
        horizontal, vertical = "─", "│"
        t_down, t_up, t_right, t_left = "┬", "┴", "├", "┤"
        cross = "┼"

        def _border(left: str, mid: str, right: str) -> str:
            return left + mid.join(horizontal * (w + 2) for w in widths) + right

        top_border = _border(top_left, t_down, top_right)
        header_row = (
            vertical
            + vertical.join(f" {h:<{w}} " for h, w in zip(headers, widths, strict=True))
            + vertical
        )
        separator = _border(t_right, cross, t_left)
        bottom_border = _border(bottom_left, t_up, bottom_right)

        table = [top_border, header_row, separator]
        for row in rows:
            table.append(
                vertical
                + vertical.join(
                    f" {cell:<{w}} " for cell, w in zip(row, widths, strict=True)
                )
                + vertical
            )
        table.append(bottom_border)
        return "\n".join(table)

    @classmethod
    def to_json(cls, views: list["MetadataView"], show_source: bool = False) -> str:
        result = json.dumps(
            {
                "environments": [
                    {
                        "version": view.version,
                        "python": view.python,
                        "emscripten": view.emscripten,
                        "pyodide_build": view.pyodide_build,
                        "published_at": view.published_at,
                        **({"source": view.source} if show_source else {}),
                        "compatible": view.compatible,
                    }
                    for view in views
                ]
            },
            indent=2,
        )
        return result

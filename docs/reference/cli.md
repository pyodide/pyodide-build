# CLI Reference

All commands are accessed through the `pyodide` CLI, provided by the [pyodide-cli](https://pypi.org/project/pyodide-cli/) package (installed automatically with pyodide-build).

```{eval-rst}
.. pyodide-cli-reference::
```

(export-modes)=
## Export modes

The `--exports` option to `pyodide build` controls which symbols are exported when linking `.so` files.

| Mode | Description |
|---|---|
| `pyinit` | Export only the `PyInit_<module>` symbol. Minimises output size; use when no other extension needs to call into this one at the C level. |
| `requested` (default) | Export symbols explicitly requested by the build system (e.g. via `EXPORTED_FUNCTIONS`). Balances size and compatibility. |
| `whole_archive` | Export every symbol from every linked archive. Use when other extensions need to call into this one at the C level. |

You can also pass a comma-separated list of symbol names to export specific symbols, for example: `--exports PyInit__core,helper_fn`.

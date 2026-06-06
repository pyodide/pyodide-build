import click

from pyodide_build.build_env import (
    get_build_environment_vars,
    get_pyodide_root,
    init_environment,
)
from pyodide_build.config import PYODIDE_CLI_CONFIGS


@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx: click.Context) -> None:
    """Manage config variables used in pyodide."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _get_configs() -> dict[str, str]:
    init_environment(quiet=True)

    configs: dict[str, str] = get_build_environment_vars(get_pyodide_root())

    configs_filtered = {k: configs[v] for k, v in PYODIDE_CLI_CONFIGS.items()}
    return configs_filtered


@app.command("list")
def list_config() -> None:
    """List config variables used in pyodide."""
    configs = _get_configs()

    for k, v in configs.items():
        click.echo(f'{k}="{v}"')


@app.command("get")
@click.argument("config_var")
def get_config(config_var: str) -> None:
    """Get a value of a single config variable used in pyodide.

    \b
    Arguments:
        CONFIG_VAR: A config variable to get. Use `list` to see all possible values.
    """
    configs = _get_configs()

    if config_var not in configs:
        click.echo(f"Config variable {config_var} not found.")
        raise SystemExit(1)

    click.echo(configs[config_var])

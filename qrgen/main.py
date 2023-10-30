import click
from logging import getLogger
import uvicorn
from .api import api
from .version import VERSION

_log = getLogger(__name__)


@click.version_option(version=VERSION, prog_name="qrgen")
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=3000, show_default=True)
@click.option("--verbose/--quiet", default=None)
def server(host, port, verbose):
    from logging import basicConfig
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    if verbose is None:
        basicConfig(format=fmt, level="INFO")
    elif verbose:
        basicConfig(format=fmt, level="DEBUG")
    else:
        basicConfig(format=fmt, level="WARNING")
    uvicorn.run(api, host=host, port=port, log_config=None)


if __name__ == "__main__":
    cli()

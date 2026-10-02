import logging
import sys
from typing import Annotated

import typer

from home.apps.financitos.cli import app as financitos
from home.core.config import get_settings

app = typer.Typer(no_args_is_help=True, help="Monolito pessoal: financitos, tarot...")
app.add_typer(financitos, name="financitos")


@app.callback()
def main() -> None:
    logging.basicConfig(level=get_settings().log_level, stream=sys.stderr)
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Padrão: API_HOST")] = None,
    port: Annotated[int | None, typer.Option(help="Padrão: API_PORT")] = None,
    reload: Annotated[bool, typer.Option(help="Recarrega ao editar o código (dev)")] = False,
) -> None:
    """Sobe a API HTTP (e a UI compilada, se existir)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "home.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
    )

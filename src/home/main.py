import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from home.apps.financitos.api import router as financitos
from home.core.deps import require_token

app = FastAPI(title="home", version="0.1.0")

# cada app expõe um APIRouter, montado em /api/<app> atrás do mesmo token
APPS: dict[str, APIRouter] = {"financitos": financitos}
for name, router in APPS.items():
    app.include_router(router, prefix=f"/api/{name}", dependencies=[Depends(require_token)])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def mount_web(app: FastAPI, directory: Path) -> None:
    """Serve a UI compilada (web/dist). Paths sem arquivo (ex.: /tarot) caem no
    index.html para o roteador do front resolver; /api desconhecido continua 404."""
    if not directory.is_dir():
        return
    root = directory.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(root / "index.html")


# lido direto do ambiente para não exigir OPENROUTER_API_KEY só para importar o app
mount_web(app, Path(os.environ.get("WEB_DIST", "web/dist")))

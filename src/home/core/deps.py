import secrets
import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from home.core import db
from home.core.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_token(
    settings: Annotated[Settings, Depends(get_settings)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = settings.api_token
    if expected is None:
        return  # sem token configurado: acesso aberto (uso local / rede privada)
    if creds is None or not secrets.compare_digest(creds.credentials, expected.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")


def get_conn(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[sqlite3.Connection]:
    conn = db.connect(settings.database_url)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

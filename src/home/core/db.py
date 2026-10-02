import sqlite3
from collections.abc import Callable
from pathlib import Path

# Cada app registra uma função que cria/migra suas tabelas (prefixadas com o nome do app)
Initializer = Callable[[sqlite3.Connection], None]
_initializers: list[Initializer] = []

# Nome do arquivo antes do monolito: renomeado para o atual na primeira conexão
LEGACY_FILE = "financitos.db"


def register(init: Initializer) -> Initializer:
    if init not in _initializers:
        _initializers.append(init)
    return init


def path_from_url(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"DATABASE_URL não suportada: {url}")
    return Path(url.removeprefix(prefix))


def connect(url: str) -> sqlite3.Connection:
    path = path_from_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = path.with_name(LEGACY_FILE)
    if not path.exists() and legacy.exists():
        legacy.rename(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for init in _initializers:
        init(conn)
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return row.fetchone() is not None


def rename_tables(conn: sqlite3.Connection, renames: dict[str, str]) -> None:
    """Renomeia tabelas antigas (sem prefixo) se a nova ainda não existir."""
    with conn:
        for old, new in renames.items():
            if table_exists(conn, old) and not table_exists(conn, new):
                conn.execute(f"ALTER TABLE {old} RENAME TO {new}")


def add_columns(conn: sqlite3.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    """Adiciona colunas criadas depois da tabela: [(nome, definição)]."""
    existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    with conn:
        for name, definition in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

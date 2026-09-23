"""Gerenciamento de conexões curtas e transações SQLite."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from nfse_facil.domain.exceptions import PersistenciaError


def open_connection(db_path: Path, timeout: float = 10.0) -> sqlite3.Connection:
    """Abre uma nova conexão SQLite com PRAGMAs obrigatórios configurados."""
    try:
        # Garante diretório pai
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(db_path),
            timeout=timeout,
            isolation_level=None,  # Permite controle explícito e atômico de transações
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn
    except sqlite3.OperationalError as err:
        raise PersistenciaError(
            f"Não foi possível acessar o banco de dados local '{db_path.name}'. "
            "O arquivo pode estar bloqueado por outro processo ou inacessível."
        ) from err
    except Exception as err:
        raise PersistenciaError(
            f"Erro ao inicializar conexão com o banco de dados: {err}"
        ) from err


@contextmanager
def get_connection(db_path: Path, timeout: float = 10.0) -> Iterator[sqlite3.Connection]:
    """Gerenciador de contexto que garante ciclo de vida curto e fechamento da conexão."""
    conn = open_connection(db_path, timeout=timeout)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Gerenciador de contexto para transações atômicas com rollback em caso de falha."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise

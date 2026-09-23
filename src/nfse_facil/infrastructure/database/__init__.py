"""Módulo de persistência e gerenciamento do banco de dados SQLite."""

from nfse_facil.infrastructure.database.connection import (
    get_connection,
    open_connection,
    transaction,
)
from nfse_facil.infrastructure.database.migrations import (
    SCHEMA_VERSION,
    aplicar_migracoes,
    obter_versao_esquema,
    validar_esquema,
)

__all__ = [
    "SCHEMA_VERSION",
    "aplicar_migracoes",
    "get_connection",
    "obter_versao_esquema",
    "open_connection",
    "transaction",
    "validar_esquema",
]

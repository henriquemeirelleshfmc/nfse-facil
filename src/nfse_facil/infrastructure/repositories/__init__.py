"""Módulo de repositórios da aplicação."""

from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.infrastructure.repositories.in_memory import (
    InMemoryEmpresaRepository,
    carregar_dados_demonstracao_opcional,
)
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository

__all__ = [
    "EmpresaRepository",
    "InMemoryEmpresaRepository",
    "SqliteEmpresaRepository",
    "carregar_dados_demonstracao_opcional",
]

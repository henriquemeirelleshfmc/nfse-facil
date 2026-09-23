"""Migração v3 e persistência do cursor incremental do ADN."""

from pathlib import Path

from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.database.connection import get_connection
from nfse_facil.infrastructure.database.migrations import (
    aplicar_migracoes,
    obter_versao_esquema,
    validar_esquema_v3,
)
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository


def test_migracao_v2_para_v3_preserva_dados_e_inicia_nsu_zero(tmp_path: Path) -> None:
    banco = tmp_path / "legado_v2.db"
    with get_connection(banco) as conn:
        aplicar_migracoes(conn)
        conn.execute("PRAGMA user_version = 2")
        conn.execute("ALTER TABLE empresas DROP COLUMN ultimo_nsu_adn")
        conn.commit()

    with get_connection(banco) as conn:
        aplicar_migracoes(conn)
        assert obter_versao_esquema(conn) == 3
        validar_esquema_v3(conn)

    repo = SqliteEmpresaRepository(banco)
    empresa = Empresa("Empresa", "00000000000191", tmp_path / "docs")
    repo.salvar(empresa)
    recuperada = repo.obter_por_id(empresa.id)
    assert recuperada is not None
    assert recuperada.ultimo_nsu_adn == 0


def test_repositorio_preserva_ultimo_nsu(tmp_path: Path) -> None:
    repo = SqliteEmpresaRepository(tmp_path / "nsu.db")
    empresa = Empresa("Empresa", "00000000000191", tmp_path / "docs", ultimo_nsu_adn=987654)
    repo.salvar(empresa)
    recuperada = repo.obter_por_id(empresa.id)
    assert recuperada is not None
    assert recuperada.ultimo_nsu_adn == 987654

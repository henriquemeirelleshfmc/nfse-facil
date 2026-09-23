"""Testes para a migração sequencial do banco de dados SQLite v1 -> v2 e auditoria de segurança."""

from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import pytest

from nfse_facil.domain.certificate_models import CertificadoInfo
from nfse_facil.domain.exceptions import PersistenciaError, VersaoEsquemaIncompativelError
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.database.connection import get_connection, transaction
from nfse_facil.infrastructure.database.migrations import (
    COLUNAS_CERTIFICADO_V2,
    COLUNAS_OBRIGATORIAS_V1,
    COLUNAS_PROIBIDAS_SEGREDOS,
    SCHEMA_VERSION,
    aplicar_migracoes,
    obter_versao_esquema,
    validar_esquema,
    validar_esquema_v1,
    validar_esquema_v2,
    validar_esquema_v3,
)
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository


class TestMigrationV2AndSecurityAudit:
    """Validação das migrações sequenciais atômicas e auditoria rigorosa de ausência de segredos."""

    def test_migracao_v1_para_v2_preserva_empresas_existentes(self, tmp_path: Path) -> None:
        """Cria banco na versão 1 com empresa real e migra para a versão 2."""
        db_path = tmp_path / "banco_legado_v1.db"

        # 1. Cria banco v1 simulado com dados preexistentes
        with get_connection(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT PRIMARY KEY NOT NULL,
                    razao_social TEXT NOT NULL,
                    nome_fantasia TEXT NOT NULL DEFAULT '',
                    cnpj TEXT NOT NULL UNIQUE,
                    pasta_documentos TEXT NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX idx_empresas_razao ON empresas(razao_social)")
            conn.execute("PRAGMA user_version = 1")
            conn.execute(
                """
                INSERT INTO empresas (
                    id, razao_social, nome_fantasia, cnpj, pasta_documentos, ativo, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "emp-1",
                    "Comércio de Peças Modelo Ltda",
                    "Peças Modelo",
                    "00000000000191",
                    str(tmp_path / "docs_pecas"),
                    1,
                    "2026-01-01T00:00:00.000000+00:00",
                    "2026-01-01T00:00:00.000000+00:00",
                ),
            )
            conn.commit()

            # Valida que na versão 1 o esquema é válido e user_version == 1
            assert obter_versao_esquema(conn) == 1
            validar_esquema_v1(conn)

        # 2. Executa aplicar_migracoes para evoluir da v1 até a versão vigente
        with get_connection(db_path) as conn:
            aplicar_migracoes(conn)
            assert obter_versao_esquema(conn) == SCHEMA_VERSION
            validar_esquema_v3(conn)

        # 3. Comprova que os dados preexistentes foram 100% preservados
        repo = SqliteEmpresaRepository(db_path=db_path)
        empresa_recuperada = repo.obter_por_id("emp-1")
        assert empresa_recuperada is not None
        assert empresa_recuperada.razao_social == "Comércio de Peças Modelo Ltda"
        assert empresa_recuperada.cnpj == "00000000000191"
        assert empresa_recuperada.tem_certificado_associado is False
        assert empresa_recuperada.certificado_caminho is None

    def test_banco_novo_executa_migracoes_sequenciais_e_termina_na_v2(self, tmp_path: Path) -> None:
        """Banco recém-criado executa v0 -> v1 -> v2 e finaliza diretamente na versão 2."""
        db_path = tmp_path / "banco_novo.db"

        with get_connection(db_path) as conn:
            assert obter_versao_esquema(conn) == 0
            aplicar_migracoes(conn)
            assert obter_versao_esquema(conn) == SCHEMA_VERSION
            assert SCHEMA_VERSION == 3
            validar_esquema_v3(conn)

            # Confirma presença das colunas obrigatórias e de certificado
            colunas_rows = conn.execute("PRAGMA table_info(empresas)").fetchall()
            nomes_colunas = {row["name"] for row in colunas_rows}
            for col in COLUNAS_OBRIGATORIAS_V1 | COLUNAS_CERTIFICADO_V2:
                assert col in nomes_colunas

    def test_rollback_em_falha_de_migracao_v2_preserva_v1(self, tmp_path: Path) -> None:
        """Se a migração v1 -> v2 falhar antes da conclusão, user_version continua 1."""
        db_path = tmp_path / "banco_rollback_v2.db"

        # Inicializa banco na v1
        with get_connection(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT PRIMARY KEY NOT NULL,
                    razao_social TEXT NOT NULL,
                    nome_fantasia TEXT NOT NULL DEFAULT '',
                    cnpj TEXT NOT NULL UNIQUE,
                    pasta_documentos TEXT NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        # Tenta uma migração que provoca erro intencional
        with get_connection(db_path) as conn:
            with pytest.raises(Exception):
                with transaction(conn):
                    conn.execute("ALTER TABLE empresas ADD COLUMN certificado_caminho TEXT")
                    # Força erro
                    conn.execute("COMANDO SQL INVALIDO")
                    conn.execute("PRAGMA user_version = 2")

            # Verifica integridade: rollback desfez a alteração e manteve versão 1
            assert obter_versao_esquema(conn) == 1
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(empresas)").fetchall()}
            assert "certificado_caminho" not in cols

    def test_rejeicao_banco_versao_futura(self, tmp_path: Path) -> None:
        db_path = tmp_path / "banco_futuro.db"
        with get_connection(db_path) as conn:
            conn.execute("PRAGMA user_version = 4")

        with get_connection(db_path) as conn:
            with pytest.raises(VersaoEsquemaIncompativelError, match="mais recente"):
                aplicar_migracoes(conn)

    def test_auditoria_ausencia_de_colunas_de_segredos_no_banco(self, tmp_path: Path) -> None:
        """Auditoria obrigatória: comprova que nenhuma coluna como senha ou chave existe no banco."""
        db_path = tmp_path / "banco_auditoria.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        with get_connection(db_path) as conn:
            colunas_rows = conn.execute("PRAGMA table_info(empresas)").fetchall()
            nomes_colunas = [row["name"].lower() for row in colunas_rows]

            # Nenhum termo proibido pode estar presente
            for proibido in COLUNAS_PROIBIDAS_SEGREDOS:
                assert proibido not in nomes_colunas, f"Coluna proibida '{proibido}' detectada no banco!"

    def test_rejeicao_de_banco_com_coluna_proibida(self, tmp_path: Path) -> None:
        """Se um banco possuir uma coluna como 'senha', a validação deve rejeitá-lo."""
        db_path = tmp_path / "banco_com_senha.db"
        with get_connection(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT PRIMARY KEY NOT NULL,
                    razao_social TEXT NOT NULL,
                    cnpj TEXT NOT NULL UNIQUE,
                    pasta_documentos TEXT NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL,
                    senha TEXT -- Coluna proibida!
                )
                """
            )
            with pytest.raises(PersistenciaError, match="coluna proibida 'senha'"):
                validar_esquema(conn)

    def test_auditoria_ausencia_de_campos_de_segredo_nos_modelos(self) -> None:
        """Auditoria obrigatória: campos de Empresa e CertificadoInfo não contêm atributos de senha."""
        termos_segredo = {"senha", "password", "secret", "private_key", "pem", "conteudo_pfx"}

        campos_empresa = {f.name.lower() for f in fields(Empresa)}
        for termo in termos_segredo:
            assert termo not in campos_empresa, f"Campo de segredo '{termo}' presente em Empresa!"

        campos_cert = {f.name.lower() for f in fields(CertificadoInfo)}
        for termo in termos_segredo:
            assert termo not in campos_cert, f"Campo de segredo '{termo}' presente em CertificadoInfo!"

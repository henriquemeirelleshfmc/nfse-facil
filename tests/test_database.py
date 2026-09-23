"""Testes para o gerenciador de banco SQLite e migrações atômicas."""

from pathlib import Path
import sqlite3
import pytest

from nfse_facil.domain.exceptions import PersistenciaError, VersaoEsquemaIncompativelError
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


class TestDatabaseAndMigrations:
    """Validação da infraestrutura de banco SQLite e integridade do esquema."""

    def test_criacao_automatica_e_migracao_v1(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "teste_init.db"
        assert not db_path.exists()

        with get_connection(db_path) as conn:
            aplicar_migracoes(conn)
            versao = obter_versao_esquema(conn)
            assert versao == SCHEMA_VERSION

            # Confirma que a tabela e índice foram criados
            row_tab = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='empresas'"
            ).fetchone()
            assert row_tab is not None
            assert row_tab["name"] == "empresas"

            row_idx = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_empresas_razao'"
            ).fetchone()
            assert row_idx is not None

        # Arquivo deve ter sido criado no disco
        assert db_path.exists()

    def test_reabertura_e_idempotencia_migracao(self, tmp_path: Path) -> None:
        db_path = tmp_path / "teste_idempotente.db"

        # 1ª abertura: aplica migração
        with get_connection(db_path) as conn:
            aplicar_migracoes(conn)
            assert obter_versao_esquema(conn) == SCHEMA_VERSION

        # 2ª abertura: banco já na versão atual deve apenas validar sem erro
        with get_connection(db_path) as conn:
            aplicar_migracoes(conn)
            assert obter_versao_esquema(conn) == SCHEMA_VERSION

    def test_ativacao_foreign_keys_e_timeout(self, tmp_path: Path) -> None:
        db_path = tmp_path / "teste_pragmas.db"
        with get_connection(db_path) as conn:
            fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk_status == 1

            busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert busy_timeout >= 10000

    def test_rollback_atomico_em_falha_de_migracao(self, tmp_path: Path) -> None:
        db_path = tmp_path / "teste_rollback.db"

        with get_connection(db_path) as conn:
            assert obter_versao_esquema(conn) == 0

            # Simula falha proposital durante uma transação
            with pytest.raises(Exception):
                with transaction(conn):
                    conn.execute("CREATE TABLE tabela_teste_incompleta (id INT)")
                    conn.execute("PRAGMA user_version = 99")
                    # Provoca erro de sintaxe proposital
                    conn.execute("COMANDO SQL INVALIDO QUE FORCA ROLLBACK")

            # Verifica que a transação fez rollback completo
            assert obter_versao_esquema(conn) == 0
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE name='tabela_teste_incompleta'"
            ).fetchone()
            assert row is None

    def test_rejeicao_banco_com_versao_futura(self, tmp_path: Path) -> None:
        db_path = tmp_path / "teste_versao_futura.db"
        with get_connection(db_path) as conn:
            # Simula um banco gerado por uma versão futura (ex: versão 99)
            conn.execute("PRAGMA user_version = 99")

        with get_connection(db_path) as conn:
            with pytest.raises(VersaoEsquemaIncompativelError, match="mais recente"):
                aplicar_migracoes(conn)

    def test_validacao_esquema_incompleto_falha(self, tmp_path: Path) -> None:
        db_path = tmp_path / "teste_incompleto.db"
        with get_connection(db_path) as conn:
            # Cria tabela sem as colunas obrigatórias
            conn.execute("CREATE TABLE empresas (id TEXT PRIMARY KEY, razao_social TEXT)")
            with pytest.raises(PersistenciaError, match="colunas ausentes"):
                validar_esquema(conn)

    def test_migracao_v0_com_esquema_incompleto_faz_rollback_preserva_versao_zero_e_dados(
        self, tmp_path: Path
    ) -> None:
        """Comprova que se o banco v0 tiver tabela empresas incompleta:

        - aplicar_migracoes falha e levanta PersistenciaError;
        - user_version permanece 0;
        - nenhum dado pré-existente é corrompido ou apagado;
        - a estrutura incompleta não é aceita silenciosamente.
        """
        db_path = tmp_path / "banco_v0_incompleto.db"
        with get_connection(db_path) as conn:
            # Cria banco v0 com tabela empresas incompleta e insere linha com dados prévios
            conn.execute(
                "CREATE TABLE empresas (id TEXT PRIMARY KEY, razao_social TEXT, cnpj TEXT)"
            )
            conn.execute(
                "INSERT INTO empresas (id, razao_social, cnpj) VALUES (?, ?, ?)",
                ("emp-previa-1", "Empresa Legada Preexistente", "00000000000191"),
            )
            conn.commit()
            assert obter_versao_esquema(conn) == 0

        # Tenta aplicar migrações no banco com esquema defeituoso
        with get_connection(db_path) as conn:
            with pytest.raises(PersistenciaError, match="colunas ausentes|incompleta"):
                aplicar_migracoes(conn)

        # Confirma integridade após falha: user_version continua 0 e dados intactos
        with get_connection(db_path) as conn:
            assert obter_versao_esquema(conn) == 0
            row = conn.execute(
                "SELECT id, razao_social, cnpj FROM empresas WHERE id = 'emp-previa-1'"
            ).fetchone()
            assert row is not None
            assert row["razao_social"] == "Empresa Legada Preexistente"
            assert row["cnpj"] == "00000000000191"

    def test_validacao_esquema_falhas_especificas(self, tmp_path: Path) -> None:
        """Valida que a validação rejeita banco sem PK, sem NOT NULL ou sem unicidade em cnpj."""
        # 1. Tabela inexistente
        db1 = tmp_path / "db_sem_tabela.db"
        with get_connection(db1) as conn:
            with pytest.raises(PersistenciaError, match="tabela 'empresas'"):
                validar_esquema(conn)

        # 2. Ausência de Primary Key em 'id'
        db2 = tmp_path / "db_sem_pk.db"
        with get_connection(db2) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT,
                    razao_social TEXT NOT NULL,
                    nome_fantasia TEXT,
                    cnpj TEXT NOT NULL UNIQUE,
                    pasta_documentos TEXT NOT NULL,
                    certificado_caminho TEXT,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            with pytest.raises(PersistenciaError, match="chave prim|id"):
                validar_esquema(conn)

        # 3. Campo essencial sem NOT NULL (ex: razao_social anulável)
        db3 = tmp_path / "db_sem_not_null.db"
        with get_connection(db3) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT PRIMARY KEY,
                    razao_social TEXT,
                    nome_fantasia TEXT,
                    cnpj TEXT NOT NULL UNIQUE,
                    pasta_documentos TEXT NOT NULL,
                    certificado_caminho TEXT,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            with pytest.raises(PersistenciaError, match="NOT NULL"):
                validar_esquema(conn)

        # 4. CNPJ sem restrição de unicidade
        db4 = tmp_path / "db_cnpj_sem_unique.db"
        with get_connection(db4) as conn:
            conn.execute(
                """
                CREATE TABLE empresas (
                    id TEXT PRIMARY KEY,
                    razao_social TEXT NOT NULL,
                    nome_fantasia TEXT,
                    cnpj TEXT NOT NULL,
                    pasta_documentos TEXT NOT NULL,
                    certificado_caminho TEXT,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            with pytest.raises(PersistenciaError, match="unicidade|UNIQUE"):
                validar_esquema(conn)


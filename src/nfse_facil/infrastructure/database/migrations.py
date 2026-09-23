"""Gerenciador de migrações e evolução de esquema do SQLite."""

import sqlite3
from typing import Final

from nfse_facil.domain.exceptions import PersistenciaError, VersaoEsquemaIncompativelError
from nfse_facil.infrastructure.database.connection import transaction

SCHEMA_VERSION: Final[int] = 3

COLUNAS_OBRIGATORIAS_V1: Final[set[str]] = {
    "id",
    "razao_social",
    "nome_fantasia",
    "cnpj",
    "pasta_documentos",
    "ativo",
    "criado_em",
    "atualizado_em",
}

COLUNAS_CERTIFICADO_V2: Final[set[str]] = {
    "certificado_caminho",
    "certificado_cnpj",
    "certificado_fingerprint_sha256",
    "certificado_valido_de",
    "certificado_valido_ate",
    "certificado_verificado_em",
}

COLUNAS_OBRIGATORIAS_V2: Final[set[str]] = COLUNAS_OBRIGATORIAS_V1 | COLUNAS_CERTIFICADO_V2

COLUNAS_SINCRONIZACAO_V3: Final[set[str]] = {"ultimo_nsu_adn"}
COLUNAS_OBRIGATORIAS_V3: Final[set[str]] = COLUNAS_OBRIGATORIAS_V2 | COLUNAS_SINCRONIZACAO_V3

CAMPOS_ESSENCIAIS_NOT_NULL: Final[set[str]] = {
    "razao_social",
    "cnpj",
    "pasta_documentos",
    "ativo",
    "criado_em",
    "atualizado_em",
}

# Nomes de colunas terminantemente proibidos no esquema SQLite (Auditoria de Segurança)
COLUNAS_PROIBIDAS_SEGREDOS: Final[set[str]] = {
    "senha",
    "password",
    "secret",
    "segredo",
    "pin",
    "chave_privada",
    "private_key",
    "pem",
    "conteudo_pfx",
    "pfx",
    "pfx_data",
}


def obter_versao_esquema(conn: sqlite3.Connection) -> int:
    """Consulta a versão atual do esquema registrada em PRAGMA user_version."""
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0
    except Exception as err:
        raise PersistenciaError(f"Falha ao ler versão do esquema SQLite: {err}") from err


def _verificar_ausencia_segredos(colunas_dict: dict[str, sqlite3.Row]) -> None:
    """Garante que nenhuma coluna com nomes relacionados a segredos exista na tabela."""
    for nome_col in colunas_dict.keys():
        nome_normalizado = nome_col.strip().lower()
        if nome_normalizado in COLUNAS_PROIBIDAS_SEGREDOS:
            raise PersistenciaError(
                f"Violação de segurança do esquema: coluna proibida '{nome_col}' detectada no banco de dados."
            )


def validar_esquema_v1(conn: sqlite3.Connection) -> None:
    """Valida a existência e integridade estrita da tabela 'empresas' na versão 1."""
    try:
        tabela = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='empresas'"
        ).fetchone()
        if not tabela:
            raise PersistenciaError("Inconsistência de esquema: a tabela 'empresas' não foi encontrada.")

        colunas_rows = conn.execute("PRAGMA table_info(empresas)").fetchall()
        colunas_dict = {}
        for row in colunas_rows:
            if isinstance(row, sqlite3.Row) or hasattr(row, "keys"):
                colunas_dict[row["name"]] = {"pk": row["pk"], "notnull": row["notnull"]}
            else:
                colunas_dict[row[1]] = {"pk": row[5], "notnull": row[3]}

        # Auditoria de segurança contra colunas de senha/chaves
        _verificar_ausencia_segredos(colunas_dict)

        # 1. Colunas obrigatórias da v1
        colunas_existentes = set(colunas_dict.keys())
        colunas_ausentes = COLUNAS_OBRIGATORIAS_V1 - colunas_existentes
        if colunas_ausentes:
            raise PersistenciaError(
                f"Inconsistência de esquema v1: colunas ausentes na tabela 'empresas': {sorted(colunas_ausentes)}"
            )

        # 2. Chave primária em 'id'
        id_col = colunas_dict.get("id")
        if not id_col or id_col["pk"] < 1:
            raise PersistenciaError(
                "Inconsistência de esquema: a coluna 'id' deve ser a chave primária da tabela 'empresas'."
            )

        # 3. Campos essenciais marcados como NOT NULL
        for campo in CAMPOS_ESSENCIAIS_NOT_NULL:
            col_info = colunas_dict[campo]
            if col_info["notnull"] != 1:
                raise PersistenciaError(
                    f"Inconsistência de esquema: o campo essencial '{campo}' deve ser marcado como NOT NULL."
                )

        # 4. Restrição de unicidade efetiva para 'cnpj'
        indexes = conn.execute("PRAGMA index_list(empresas)").fetchall()
        cnpj_unique = False
        for idx in indexes:
            is_unique = idx["unique"] if (isinstance(idx, sqlite3.Row) or hasattr(idx, "keys")) else idx[2]
            idx_name = idx["name"] if (isinstance(idx, sqlite3.Row) or hasattr(idx, "keys")) else idx[1]
            if is_unique == 1:
                cols = conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
                col_names = [
                    c["name"] if (isinstance(c, sqlite3.Row) or hasattr(c, "keys")) else c[2]
                    for c in cols
                ]
                if col_names == ["cnpj"]:
                    cnpj_unique = True
                    break

        if not cnpj_unique:
            raise PersistenciaError(
                "Inconsistência de esquema: a coluna 'cnpj' deve possuir restrição efetiva de unicidade (UNIQUE)."
            )
    except PersistenciaError:
        raise
    except Exception as err:
        raise PersistenciaError(f"Erro ao validar integridade do esquema v1: {err}") from err


def validar_esquema_v2(conn: sqlite3.Connection) -> None:
    """Valida a existência e integridade estrita da tabela 'empresas' na versão 2."""
    try:
        # Executa todas as checagens base da v1
        validar_esquema_v1(conn)

        colunas_rows = conn.execute("PRAGMA table_info(empresas)").fetchall()
        colunas_dict = {}
        for row in colunas_rows:
            if isinstance(row, sqlite3.Row) or hasattr(row, "keys"):
                colunas_dict[row["name"]] = {"pk": row["pk"], "notnull": row["notnull"]}
            else:
                colunas_dict[row[1]] = {"pk": row[5], "notnull": row[3]}

        # Checa colunas de certificado da versão 2
        colunas_existentes = set(colunas_dict.keys())
        colunas_ausentes_v2 = COLUNAS_CERTIFICADO_V2 - colunas_existentes
        if colunas_ausentes_v2:
            raise PersistenciaError(
                f"Inconsistência de esquema v2: colunas de certificado ausentes: {sorted(colunas_ausentes_v2)}"
            )

        # Todas as colunas de certificado devem ser opcionais (NOT NULL = 0)
        for col_cert in COLUNAS_CERTIFICADO_V2:
            col_info = colunas_dict[col_cert]
            if col_info["notnull"] != 0:
                raise PersistenciaError(
                    f"Inconsistência de esquema v2: a coluna de certificado '{col_cert}' deve ser opcional (NULL)."
                )
    except PersistenciaError:
        raise
    except Exception as err:
        raise PersistenciaError(f"Erro ao validar integridade do esquema v2: {err}") from err


def validar_esquema_v3(conn: sqlite3.Connection) -> None:
    """Valida a coluna incremental do ADN adicionada na versão 3."""
    try:
        validar_esquema_v2(conn)
        colunas = {
            row["name"]: row
            for row in conn.execute("PRAGMA table_info(empresas)").fetchall()
        }
        if "ultimo_nsu_adn" not in colunas:
            raise PersistenciaError("Inconsistência de esquema v3: coluna ultimo_nsu_adn ausente.")
        info = colunas["ultimo_nsu_adn"]
        if info["notnull"] != 1 or str(info["dflt_value"]) not in {"0", "'0'", '"0"'}:
            raise PersistenciaError(
                "Inconsistência de esquema v3: ultimo_nsu_adn deve ser obrigatório e iniciar em zero."
            )
    except PersistenciaError:
        raise
    except Exception as err:
        raise PersistenciaError(f"Erro ao validar integridade do esquema v3: {err}") from err


def validar_esquema(conn: sqlite3.Connection, versao: int | None = None) -> None:
    """Valida a integridade do esquema com sensibilidade à versão informada."""
    ver = versao if versao is not None else obter_versao_esquema(conn)
    if ver == 1:
        validar_esquema_v1(conn)
    elif ver == 2:
        validar_esquema_v2(conn)
    else:
        validar_esquema_v3(conn)


def _migrar_v0_para_v1(conn: sqlite3.Connection) -> None:
    """Executa a migração atômica de v0 para v1."""
    try:
        with transaction(conn):
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS empresas (
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
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_empresas_razao ON empresas(razao_social)
                """
            )
            # Validação prévia da integridade da v1 DENTRO da mesma transação
            validar_esquema_v1(conn)
            conn.execute("PRAGMA user_version = 1")
    except Exception as err:
        if isinstance(err, PersistenciaError):
            raise
        raise PersistenciaError(f"Falha na migração atômica v0 -> v1: {err}") from err


def _migrar_v1_para_v2(conn: sqlite3.Connection) -> None:
    """Executa a migração atômica e incremental de v1 para v2 via ALTER TABLE."""
    try:
        with transaction(conn):
            # Garante que a estrutura v1 está válida antes de iniciar
            validar_esquema_v1(conn)

            # Adiciona colunas opcionais de certificado
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_caminho TEXT DEFAULT NULL")
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_cnpj TEXT DEFAULT NULL")
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_fingerprint_sha256 TEXT DEFAULT NULL")
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_valido_de TEXT DEFAULT NULL")
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_valido_ate TEXT DEFAULT NULL")
            conn.execute("ALTER TABLE empresas ADD COLUMN certificado_verificado_em TEXT DEFAULT NULL")

            # Validação estrita da integridade da v2 DENTRO da mesma transação
            validar_esquema_v2(conn)
            conn.execute("PRAGMA user_version = 2")
    except Exception as err:
        if isinstance(err, PersistenciaError):
            raise
        raise PersistenciaError(f"Falha na migração atômica v1 -> v2: {err}") from err


def _migrar_v2_para_v3(conn: sqlite3.Connection) -> None:
    """Adiciona o cursor público de sincronização do ADN sem armazenar segredos."""
    try:
        with transaction(conn):
            validar_esquema_v2(conn)
            conn.execute(
                "ALTER TABLE empresas ADD COLUMN ultimo_nsu_adn INTEGER NOT NULL DEFAULT 0"
            )
            validar_esquema_v3(conn)
            conn.execute("PRAGMA user_version = 3")
    except Exception as err:
        if isinstance(err, PersistenciaError):
            raise
        raise PersistenciaError(f"Falha na migração atômica v2 -> v3: {err}") from err


def aplicar_migracoes(conn: sqlite3.Connection) -> None:
    """Aplica migrações sequenciais de forma atômica e controlada (v0 -> v1 -> v2)."""
    versao_atual = obter_versao_esquema(conn)

    # 1. Rejeição explícita de bancos gerados por versões mais recentes do software
    if versao_atual > SCHEMA_VERSION:
        raise VersaoEsquemaIncompativelError(
            f"O banco de dados possui versão de esquema {versao_atual}, que é mais recente "
            f"do que a versão suportada por este aplicativo ({SCHEMA_VERSION}). "
            "Por favor, atualize o NFS-e Fácil para continuar."
        )

    # 2. Banco já na versão atual: apenas valida estrutura vigente
    if versao_atual == SCHEMA_VERSION:
        validar_esquema_v3(conn)
        return

    # 3. Execução sequencial controlada
    if versao_atual == 0:
        _migrar_v0_para_v1(conn)
        versao_atual = 1

    if versao_atual == 1:
        _migrar_v1_para_v2(conn)
        versao_atual = 2

    if versao_atual == 2:
        _migrar_v2_para_v3(conn)
        versao_atual = 3

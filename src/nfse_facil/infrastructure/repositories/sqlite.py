"""Implementação em SQLite do repositório de empresas."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from nfse_facil.config.settings import get_settings
from nfse_facil.domain.exceptions import (
    CNPJDuplicadoError,
    PersistenciaError,
    VersaoEsquemaIncompativelError,
)
from nfse_facil.domain.models import Empresa
from nfse_facil.domain.validators import normalizar_para_busca, sanitizar_cnpj
from nfse_facil.infrastructure.database.connection import get_connection, transaction
from nfse_facil.infrastructure.database.migrations import aplicar_migracoes
from nfse_facil.infrastructure.repositories.base import EmpresaRepository


def _chave_ordenacao_empresa(empresa: Empresa) -> tuple[str, str, str, str]:
    """Chave de ordenação determinística e natural para o português brasileiro.

    Usa a forma sem acento para ordem alfabética natural (ex: Álvaro antes de Beta),
    preserva o nome original para desempate, e utiliza CNPJ e ID como critérios finais.
    """
    sem_acento = normalizar_para_busca(empresa.nome_exibicao)
    return (sem_acento, empresa.nome_exibicao.casefold(), empresa.cnpj, empresa.id)


class SqliteEmpresaRepository(EmpresaRepository):
    """Repositório persistente de empresas utilizando SQLite com conexões curtas."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        # Inicializa o banco e executa migrações atômicas na primeira inicialização
        self._inicializar_esquema()

    def _inicializar_esquema(self) -> None:
        """Aplica as migrações necessárias garantindo que o esquema esteja atualizado."""
        try:
            with get_connection(self.db_path) as conn:
                aplicar_migracoes(conn)
        except (PersistenciaError, VersaoEsquemaIncompativelError):
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao inicializar o banco de dados SQLite: {err}") from err

    def _row_to_empresa(self, row: sqlite3.Row) -> Empresa:
        """Converte uma linha do SQLite para a entidade de domínio Empresa."""
        try:
            raw_criado = row["criado_em"]
            dt_criado = datetime.fromisoformat(raw_criado)
            if dt_criado.tzinfo is None:
                dt_criado = dt_criado.replace(tzinfo=timezone.utc)
            else:
                dt_criado = dt_criado.astimezone(timezone.utc)

            raw_atualizado = row["atualizado_em"]
            dt_atualizado = datetime.fromisoformat(raw_atualizado)
            if dt_atualizado.tzinfo is None:
                dt_atualizado = dt_atualizado.replace(tzinfo=timezone.utc)
            else:
                dt_atualizado = dt_atualizado.astimezone(timezone.utc)

            # Metadados opcionais de certificado digital (esquema v2)
            cert_caminho = None
            if "certificado_caminho" in row.keys() and row["certificado_caminho"]:
                cert_caminho = Path(row["certificado_caminho"])

            cert_cnpj = None
            if "certificado_cnpj" in row.keys() and row["certificado_cnpj"]:
                cert_cnpj = row["certificado_cnpj"]

            cert_fp = None
            if "certificado_fingerprint_sha256" in row.keys() and row["certificado_fingerprint_sha256"]:
                cert_fp = row["certificado_fingerprint_sha256"]

            cert_valido_de = None
            if "certificado_valido_de" in row.keys() and row["certificado_valido_de"]:
                dt_val_de = datetime.fromisoformat(row["certificado_valido_de"])
                cert_valido_de = dt_val_de.replace(tzinfo=timezone.utc) if dt_val_de.tzinfo is None else dt_val_de.astimezone(timezone.utc)

            cert_valido_ate = None
            if "certificado_valido_ate" in row.keys() and row["certificado_valido_ate"]:
                dt_val_ate = datetime.fromisoformat(row["certificado_valido_ate"])
                cert_valido_ate = dt_val_ate.replace(tzinfo=timezone.utc) if dt_val_ate.tzinfo is None else dt_val_ate.astimezone(timezone.utc)

            cert_verificado_em = None
            if "certificado_verificado_em" in row.keys() and row["certificado_verificado_em"]:
                dt_verif = datetime.fromisoformat(row["certificado_verificado_em"])
                cert_verificado_em = dt_verif.replace(tzinfo=timezone.utc) if dt_verif.tzinfo is None else dt_verif.astimezone(timezone.utc)

            return Empresa(
                id=row["id"],
                razao_social=row["razao_social"],
                nome_fantasia=row["nome_fantasia"] or "",
                cnpj=row["cnpj"],
                pasta_documentos=Path(row["pasta_documentos"]),
                ativo=bool(row["ativo"]),
                criado_em=dt_criado,
                atualizado_em=dt_atualizado,
                certificado_caminho=cert_caminho,
                certificado_cnpj=cert_cnpj,
                certificado_fingerprint_sha256=cert_fp,
                certificado_valido_de=cert_valido_de,
                certificado_valido_ate=cert_valido_ate,
                certificado_verificado_em=cert_verificado_em,
                ultimo_nsu_adn=row["ultimo_nsu_adn"] if "ultimo_nsu_adn" in row.keys() else 0,
            )
        except Exception as err:
            raise PersistenciaError(
                f"Erro ao converter dados da empresa do banco de dados (ID: {row['id']}): {err}"
            ) from err

    def listar_todas(self) -> list[Empresa]:
        """Retorna todas as empresas cadastradas ordenadas deterministicamente."""
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute("SELECT * FROM empresas").fetchall()
                empresas = [self._row_to_empresa(r) for r in rows]
            return sorted(empresas, key=_chave_ordenacao_empresa)
        except PersistenciaError:
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao listar empresas do banco de dados: {err}") from err

    def obter_por_id(self, empresa_id: str) -> Empresa | None:
        """Busca uma empresa pelo identificador único."""
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM empresas WHERE id = ?",
                    (empresa_id,),
                ).fetchone()
                return self._row_to_empresa(row) if row else None
        except PersistenciaError:
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao obter empresa por ID '{empresa_id}': {err}") from err

    def obter_por_cnpj(self, cnpj: str) -> Empresa | None:
        """Busca uma empresa pelo CNPJ (com ou sem máscara)."""
        cnpj_limpo = sanitizar_cnpj(cnpj)
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM empresas WHERE cnpj = ?",
                    (cnpj_limpo,),
                ).fetchone()
                return self._row_to_empresa(row) if row else None
        except PersistenciaError:
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao obter empresa por CNPJ '{cnpj}': {err}") from err

    def salvar(self, empresa: Empresa) -> None:
        """Insere ou atualiza uma empresa com controle de timestamps e unicidade de CNPJ."""
        agora_utc = datetime.now(timezone.utc)
        str_atualizado = agora_utc.isoformat(timespec="microseconds")
        novo_atualizado_em = datetime.fromisoformat(str_atualizado)
        novo_criado_em: datetime | None = None

        # Formatação de datas opcionais de certificado para ISO UTC
        str_cert_val_de = (
            empresa.certificado_valido_de.isoformat(timespec="microseconds")
            if empresa.certificado_valido_de
            else None
        )
        str_cert_val_ate = (
            empresa.certificado_valido_ate.isoformat(timespec="microseconds")
            if empresa.certificado_valido_ate
            else None
        )
        str_cert_verif = (
            empresa.certificado_verificado_em.isoformat(timespec="microseconds")
            if empresa.certificado_verificado_em
            else None
        )
        str_cert_caminho = str(empresa.certificado_caminho) if empresa.certificado_caminho else None

        try:
            with get_connection(self.db_path) as conn:
                try:
                    with transaction(conn):
                        # A verificação de existência ocorre DENTRO da transação de escrita (BEGIN IMMEDIATE)
                        existente = conn.execute(
                            "SELECT id, criado_em FROM empresas WHERE id = ?",
                            (empresa.id,),
                        ).fetchone()

                        if existente:
                            # ATUALIZAÇÃO: preserva criado_em original e atualiza atualizado_em
                            str_criado = existente["criado_em"]
                            dt_criado_preservado = datetime.fromisoformat(str_criado)
                            if dt_criado_preservado.tzinfo is None:
                                dt_criado_preservado = dt_criado_preservado.replace(tzinfo=timezone.utc)
                            else:
                                dt_criado_preservado = dt_criado_preservado.astimezone(timezone.utc)
                            novo_criado_em = dt_criado_preservado

                            conn.execute(
                                """
                                UPDATE empresas
                                SET razao_social = ?,
                                    nome_fantasia = ?,
                                    cnpj = ?,
                                    pasta_documentos = ?,
                                    ativo = ?,
                                    atualizado_em = ?,
                                    certificado_caminho = ?,
                                    certificado_cnpj = ?,
                                    certificado_fingerprint_sha256 = ?,
                                    certificado_valido_de = ?,
                                    certificado_valido_ate = ?,
                                    certificado_verificado_em = ?,
                                    ultimo_nsu_adn = ?
                                WHERE id = ?
                                """,
                                (
                                    empresa.razao_social,
                                    empresa.nome_fantasia,
                                    empresa.cnpj,
                                    str(empresa.pasta_documentos),
                                    1 if empresa.ativo else 0,
                                    str_atualizado,
                                    str_cert_caminho,
                                    empresa.certificado_cnpj,
                                    empresa.certificado_fingerprint_sha256,
                                    str_cert_val_de,
                                    str_cert_val_ate,
                                    str_cert_verif,
                                    empresa.ultimo_nsu_adn,
                                    empresa.id,
                                ),
                            )
                        else:
                            # INSERÇÃO: usa criado_em da entidade normalizado para UTC ou gera novo agora
                            dt_criado = empresa.criado_em if empresa.criado_em is not None else agora_utc
                            if dt_criado.tzinfo is None:
                                dt_criado = dt_criado.replace(tzinfo=timezone.utc)
                            else:
                                dt_criado = dt_criado.astimezone(timezone.utc)
                            str_criado = dt_criado.isoformat(timespec="microseconds")
                            novo_criado_em = datetime.fromisoformat(str_criado)

                            conn.execute(
                                """
                                INSERT INTO empresas (
                                    id, razao_social, nome_fantasia, cnpj,
                                    pasta_documentos, ativo, criado_em, atualizado_em,
                                    certificado_caminho, certificado_cnpj, certificado_fingerprint_sha256,
                                    certificado_valido_de, certificado_valido_ate, certificado_verificado_em,
                                    ultimo_nsu_adn
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    empresa.id,
                                    empresa.razao_social,
                                    empresa.nome_fantasia,
                                    empresa.cnpj,
                                    str(empresa.pasta_documentos),
                                    1 if empresa.ativo else 0,
                                    str_criado,
                                    str_atualizado,
                                    str_cert_caminho,
                                    empresa.certificado_cnpj,
                                    empresa.certificado_fingerprint_sha256,
                                    str_cert_val_de,
                                    str_cert_val_ate,
                                    str_cert_verif,
                                    empresa.ultimo_nsu_adn,
                                ),
                            )
                except sqlite3.IntegrityError as err:
                    msg = str(err).lower()
                    if "unique" in msg and "cnpj" in msg:
                        raise CNPJDuplicadoError(
                            f"Já existe uma empresa cadastrada com o CNPJ '{empresa.cnpj_formatado}'."
                        ) from err
                    raise PersistenciaError(f"Violação de integridade no banco de dados: {err}") from err
        except (CNPJDuplicadoError, PersistenciaError):
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao salvar empresa no banco de dados: {err}") from err

        # Apenas após o commit bem-sucedido da transação atualiza os timestamps no objeto em memória
        if novo_criado_em is not None:
            empresa.criado_em = novo_criado_em
        empresa.atualizado_em = novo_atualizado_em

    def remover(self, empresa_id: str) -> bool:
        """Remove o registro da empresa do SQLite (nunca remove arquivos ou pastas)."""
        try:
            with get_connection(self.db_path) as conn:
                with transaction(conn):
                    cursor = conn.execute(
                        "DELETE FROM empresas WHERE id = ?",
                        (empresa_id,),
                    )
                    return cursor.rowcount > 0
        except PersistenciaError:
            raise
        except Exception as err:
            raise PersistenciaError(f"Erro ao remover empresa '{empresa_id}': {err}") from err

    def pesquisar(self, termo: str) -> list[Empresa]:
        """Pesquisa empresas por nome, razão social ou CNPJ com suporte Unicode completo."""
        termo_limpo = termo.strip()
        if not termo_limpo:
            return self.listar_todas()

        # listar_todas() já faz tratamento de PersistenciaError
        todas = self.listar_todas()
        termo_norm = normalizar_para_busca(termo_limpo)

        try:
            termo_cnpj = sanitizar_cnpj(termo_limpo).casefold()
        except Exception:
            termo_cnpj = ""

        resultados: list[Empresa] = []
        for emp in todas:
            # Busca Unicode insensível a acentos e maiúsculas/minúsculas
            match_razao = termo_norm in normalizar_para_busca(emp.razao_social)
            match_fantasia = bool(
                emp.nome_fantasia and termo_norm in normalizar_para_busca(emp.nome_fantasia)
            )
            match_mascara = termo_norm in normalizar_para_busca(emp.cnpj_formatado)
            match_cnpj = bool(termo_cnpj and termo_cnpj in emp.cnpj.casefold())

            if match_razao or match_fantasia or match_mascara or match_cnpj:
                resultados.append(emp)

        return sorted(resultados, key=_chave_ordenacao_empresa)

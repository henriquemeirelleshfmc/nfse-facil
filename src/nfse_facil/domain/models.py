"""Modelos essenciais da camada de domínio da aplicação NFS-e Fácil.

REGRAS DE SEGURANÇA:
- Nenhuma senha ou segredo de certificado deve ser armazenado ou modelado aqui.
- O CNPJ é manipulado e persistido estritamente como string, preservando zeros à esquerda.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
import uuid

from nfse_facil.domain.exceptions import PeriodoInvalidoError, ValidacaoError
from nfse_facil.domain.validators import (
    formatar_cnpj,
    sanitizar_cnpj,
    validar_ou_falhar_cnpj,
)


class TipoPeriodo(str, Enum):
    """Opções rápidas de período de consulta."""

    ESTE_MES = "este_mes"
    MES_ANTERIOR = "mes_anterior"
    PERSONALIZADO = "personalizado"


@dataclass
class PeriodoConsulta:
    """Representa o intervalo de datas para consulta de notas fiscais.

    Garante integridade nas regras de transição de meses e anos,
    trabalhando internamente com objetos datetime.date.
    """

    tipo: TipoPeriodo
    data_inicio: date
    data_fim: date

    def __post_init__(self) -> None:
        if self.data_fim < self.data_inicio:
            raise PeriodoInvalidoError(
                f"A data final ({self.data_fim_formatada}) não pode ser anterior à "
                f"data inicial ({self.data_inicio_formatada})."
            )

    @property
    def data_inicio_formatada(self) -> str:
        """Data inicial no padrão brasileiro DD/MM/AAAA."""
        return self.data_inicio.strftime("%d/%m/%Y")

    @property
    def data_fim_formatada(self) -> str:
        """Data final no padrão brasileiro DD/MM/AAAA."""
        return self.data_fim.strftime("%d/%m/%Y")

    @property
    def rotulo_exibicao(self) -> str:
        """Texto legível do período para a interface."""
        if self.tipo == TipoPeriodo.ESTE_MES:
            return f"Este mês ({self.data_inicio_formatada} a {self.data_fim_formatada})"
        if self.tipo == TipoPeriodo.MES_ANTERIOR:
            return f"Mês anterior ({self.data_inicio_formatada} a {self.data_fim_formatada})"
        return f"Personalizado: {self.data_inicio_formatada} até {self.data_fim_formatada}"

    @classmethod
    def este_mes(cls, referencia: date | None = None) -> "PeriodoConsulta":
        """Calcula o período correspondente ao mês atual completo."""
        ref = referencia or date.today()
        primeiro_dia = date(ref.year, ref.month, 1)
        ultimo_dia_mes = calendar.monthrange(ref.year, ref.month)[1]
        ultimo_dia = date(ref.year, ref.month, ultimo_dia_mes)
        return cls(tipo=TipoPeriodo.ESTE_MES, data_inicio=primeiro_dia, data_fim=ultimo_dia)

    @classmethod
    def mes_anterior(cls, referencia: date | None = None) -> "PeriodoConsulta":
        """Calcula o período do mês anterior com suporte total à transição de ano (Jan -> Dez)."""
        ref = referencia or date.today()
        if ref.month == 1:
            ano = ref.year - 1
            mes = 12
        else:
            ano = ref.year
            mes = ref.month - 1

        primeiro_dia = date(ano, mes, 1)
        ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
        ultimo_dia = date(ano, mes, ultimo_dia_mes)
        return cls(tipo=TipoPeriodo.MES_ANTERIOR, data_inicio=primeiro_dia, data_fim=ultimo_dia)

    @classmethod
    def personalizado(cls, data_inicio: date, data_fim: date) -> "PeriodoConsulta":
        """Cria um período com datas customizadas definidas pelo usuário."""
        return cls(tipo=TipoPeriodo.PERSONALIZADO, data_inicio=data_inicio, data_fim=data_fim)


@dataclass
class PreferenciasDownload:
    """Opções de escopo e formatos de relatórios desejados pelo usuário."""

    baixar_emitidas: bool = True
    baixar_recebidas: bool = True
    gerar_excel: bool = True
    gerar_pdf: bool = True

    def tem_escopo_selecionado(self) -> bool:
        """Verifica se ao menos uma categoria de nota foi selecionada."""
        return self.baixar_emitidas or self.baixar_recebidas


@dataclass
class Empresa:
    """Entidade que representa uma empresa no sistema.

    NOTA DE SEGURANÇA:
    Esta entidade jamais contém ou armazena a senha do certificado A1 nem a chave privada.
    Apenas metadados públicos e não secretos do certificado são suportados.
    """

    razao_social: str
    cnpj: str
    pasta_documentos: Path
    nome_fantasia: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ativo: bool = True
    criado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadados opcionais do Certificado Digital A1 (Etapa 03)
    certificado_caminho: Path | None = None
    certificado_cnpj: str | None = None
    certificado_fingerprint_sha256: str | None = None
    certificado_valido_de: datetime | None = None
    certificado_valido_ate: datetime | None = None
    certificado_verificado_em: datetime | None = None
    ultimo_nsu_adn: int = 0

    def __post_init__(self) -> None:
        # Validação de Razão Social
        if not isinstance(self.razao_social, str) or not self.razao_social.strip():
            raise ValidacaoError("A Razão Social da empresa não pode ser vazia.")
        self.razao_social = self.razao_social.strip()

        # Validação do caminho de documentos
        if self.pasta_documentos is None:
            raise ValidacaoError("A pasta de documentos da empresa deve ser informada.")
        pasta_str = str(self.pasta_documentos).strip()
        if not pasta_str:
            raise ValidacaoError("A pasta de documentos da empresa não pode ser vazia.")
        self.pasta_documentos = Path(pasta_str)

        # Garante que o CNPJ seja validado e normalizado (14 caracteres maiúsculos)
        self.cnpj = validar_ou_falhar_cnpj(self.cnpj)
        self.nome_fantasia = self.nome_fantasia.strip() if isinstance(self.nome_fantasia, str) else ""

        # Validação e normalização dos metadados de certificado
        if self.certificado_caminho is not None and not isinstance(self.certificado_caminho, Path):
            caminho_str = str(self.certificado_caminho).strip()
            self.certificado_caminho = Path(caminho_str) if caminho_str else None

        if self.certificado_cnpj is not None:
            cnpj_cert_str = str(self.certificado_cnpj).strip()
            self.certificado_cnpj = validar_ou_falhar_cnpj(cnpj_cert_str) if cnpj_cert_str else None

        if self.certificado_fingerprint_sha256 is not None:
            fp_str = str(self.certificado_fingerprint_sha256).strip()
            self.certificado_fingerprint_sha256 = fp_str if fp_str else None

        # Normalização de timezone para UTC consciente
        if self.criado_em.tzinfo is None:
            self.criado_em = self.criado_em.replace(tzinfo=timezone.utc)
        else:
            self.criado_em = self.criado_em.astimezone(timezone.utc)

        if self.atualizado_em.tzinfo is None:
            self.atualizado_em = self.atualizado_em.replace(tzinfo=timezone.utc)
        else:
            self.atualizado_em = self.atualizado_em.astimezone(timezone.utc)

        if self.certificado_valido_de is not None:
            if self.certificado_valido_de.tzinfo is None:
                self.certificado_valido_de = self.certificado_valido_de.replace(tzinfo=timezone.utc)
            else:
                self.certificado_valido_de = self.certificado_valido_de.astimezone(timezone.utc)

        if self.certificado_valido_ate is not None:
            if self.certificado_valido_ate.tzinfo is None:
                self.certificado_valido_ate = self.certificado_valido_ate.replace(tzinfo=timezone.utc)
            else:
                self.certificado_valido_ate = self.certificado_valido_ate.astimezone(timezone.utc)

        if self.certificado_verificado_em is not None:
            if self.certificado_verificado_em.tzinfo is None:
                self.certificado_verificado_em = self.certificado_verificado_em.replace(tzinfo=timezone.utc)
            else:
                self.certificado_verificado_em = self.certificado_verificado_em.astimezone(timezone.utc)

        if not isinstance(self.ultimo_nsu_adn, int) or isinstance(self.ultimo_nsu_adn, bool) or self.ultimo_nsu_adn < 0:
            raise ValidacaoError("O último NSU do ADN deve ser um número inteiro não negativo.")

    @property
    def cnpj_formatado(self) -> str:
        """Retorna o CNPJ formatado com máscara visual (XX.XXX.XXX/XXXX-XX)."""
        return formatar_cnpj(self.cnpj)

    @property
    def nome_exibicao(self) -> str:
        """Nome preferencial para visualização pelo usuário na interface."""
        return self.nome_fantasia if self.nome_fantasia else self.razao_social

    @property
    def tem_certificado_associado(self) -> bool:
        """Indica se a empresa possui metadados de certificado A1 associados."""
        return bool(self.certificado_fingerprint_sha256 or self.certificado_cnpj)

    @property
    def certificado_cnpj_formatado(self) -> str:
        """Retorna o CNPJ do certificado formatado com máscara visual, se houver."""
        return formatar_cnpj(self.certificado_cnpj) if self.certificado_cnpj else ""

    @property
    def associacao_certificado_coerente(self) -> bool:
        """Verifica se o CNPJ da empresa confere com o CNPJ do certificado associado."""
        if not self.tem_certificado_associado or not self.certificado_cnpj:
            return True
        return self.cnpj == self.certificado_cnpj

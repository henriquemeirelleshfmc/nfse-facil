"""Modelos de domínio para representação pública de certificados digitais A1.

REGRAS CRÍTICAS DE SEGURANÇA:
- Nenhuma senha, chave privada, PEM, PIN ou binário PFX é modelado ou mantido aqui.
- Apenas metadados públicos e não sensíveis de inspeção e conferência.
- Todos os timestamps de validade são conscientes e normalizados para UTC.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Final

from nfse_facil.domain.validators import formatar_cnpj

# Limite para considerar que o certificado está próximo do vencimento (30 dias)
DIAS_AVISO_VENCIMENTO_CERTIFICADO: Final[int] = 30


class StatusCertificado(str, Enum):
    """Classificação do estado de validade temporal de um certificado digital."""

    AINDA_NAO_VALIDO = "ainda_nao_valido"
    VALIDO = "valido"
    PROXIMO_DO_VENCIMENTO = "proximo_do_vencimento"
    VENCIDO = "vencido"

    @property
    def rotulo_exibicao(self) -> str:
        """Rótulo em português amigável para exibição na interface."""
        rotulos = {
            StatusCertificado.AINDA_NAO_VALIDO: "Ainda não válido",
            StatusCertificado.VALIDO: "Válido",
            StatusCertificado.PROXIMO_DO_VENCIMENTO: "Próximo do vencimento",
            StatusCertificado.VENCIDO: "Vencido",
        }
        return rotulos.get(self, "Desconhecido")


@dataclass(frozen=True)
class CertificadoInfo:
    """Metadados públicos resultantes da inspeção local de um certificado A1.

    ATENÇÃO:
    Esta estrutura é imutável e contém exclusivamente dados não secretos.
    Nunca inclua senha, chave privada ou bytes brutos nesta classe.
    """

    cnpj: str
    nome_comum: str
    emissor: str
    numero_serie: str
    valido_de: datetime
    valido_ate: datetime
    fingerprint_sha256: str
    tipo_chave_publica: str
    tem_chave_privada: bool
    certificados_adicionais_qtd: int
    status_temporal: StatusCertificado
    dias_restantes: int
    caminho_origem: Path | None = None
    nome_empresarial: str | None = None

    def __post_init__(self) -> None:
        # Garante que as datas sejam conscientes e normalizadas em UTC
        if self.valido_de.tzinfo is None:
            object.__setattr__(self, "valido_de", self.valido_de.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "valido_de", self.valido_de.astimezone(timezone.utc))

        if self.valido_ate.tzinfo is None:
            object.__setattr__(self, "valido_ate", self.valido_ate.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "valido_ate", self.valido_ate.astimezone(timezone.utc))

    @property
    def cnpj_formatado(self) -> str:
        """Retorna o CNPJ formatado com máscara visual."""
        return formatar_cnpj(self.cnpj)

    @property
    def fingerprint_resumida(self) -> str:
        """Retorna fingerprint SHA-256 abreviada para conferência rápida pelo usuário."""
        if len(self.fingerprint_sha256) >= 16:
            return f"{self.fingerprint_sha256[:8]}...{self.fingerprint_sha256[-8:]}"
        return self.fingerprint_sha256

    @property
    def valido_de_formatado(self) -> str:
        """Data inicial de validade formatada no padrão brasileiro."""
        return self.valido_de.strftime("%d/%m/%Y %H:%M:%S UTC")

    @property
    def valido_ate_formatado(self) -> str:
        """Data final de validade formatada no padrão brasileiro."""
        return self.valido_ate.strftime("%d/%m/%Y %H:%M:%S UTC")

"""Modelos públicos e imutáveis da comunicação com o ADN da NFS-e."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class AmbienteADN(str, Enum):
    """Ambientes oficiais publicados para a API ADN de contribuintes."""

    PRODUCAO_RESTRITA = "producao_restrita"
    PRODUCAO = "producao"


BASES_ADN: Mapping[AmbienteADN, str] = MappingProxyType(
    {
        AmbienteADN.PRODUCAO_RESTRITA: "https://adn.producaorestrita.nfse.gov.br/contribuintes",
        AmbienteADN.PRODUCAO: "https://adn.nfse.gov.br/contribuintes",
    }
)


@dataclass(frozen=True)
class RespostaADN:
    """Resposta JSON ainda não persistida nem descompactada pela aplicação."""

    status_http: int
    dados: Mapping[str, Any]
    ambiente: AmbienteADN
    endpoint: str
    requisicao_id: str | None = None

    @property
    def status_processamento(self) -> str:
        valor = self.dados.get("StatusProcessamento", "")
        return str(valor).strip()

    @property
    def lote_dfe(self) -> tuple[Mapping[str, Any], ...]:
        lote = self.dados.get("LoteDFe", [])
        if not isinstance(lote, list):
            return ()
        return tuple(item for item in lote if isinstance(item, dict))

    def numero_resposta(self, *nomes: str) -> int | None:
        """Lê contadores públicos mesmo quando a API varia maiúsculas/minúsculas."""
        procurados = {nome.casefold() for nome in nomes}
        for chave, valor in self.dados.items():
            if str(chave).casefold() not in procurados:
                continue
            texto = str(valor).strip()
            if texto.isascii() and texto.isdigit():
                return int(texto)
        return None

    @property
    def ultimo_nsu(self) -> int | None:
        return self.numero_resposta("UltimoNSU", "ultNSU", "ultimo_nsu")

    @property
    def maior_nsu(self) -> int | None:
        return self.numero_resposta("MaxNSU", "MaiorNSU", "max_nsu")

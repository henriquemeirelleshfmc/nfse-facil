"""Modelos imutáveis de documentos fiscais recebidos do ADN."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path


class DirecaoDocumento(str, Enum):
    EMITIDA = "Emitidas"
    RECEBIDA = "Recebidas"
    OUTRA = "Outros"


@dataclass(frozen=True)
class DocumentoFiscal:
    nsu: str
    chave_acesso: str
    tipo_documento: str
    xml: bytes
    data_documento: date
    direcao: DirecaoDocumento


@dataclass(frozen=True)
class DocumentoSalvo:
    documento: DocumentoFiscal
    caminho: Path
    ja_existia: bool


@dataclass(frozen=True)
class ResultadoOrganizacao:
    documentos: tuple[DocumentoSalvo, ...]
    fora_do_filtro: int = 0
    arquivados_novos: int = 0

    @property
    def novos(self) -> int:
        return sum(not item.ja_existia for item in self.documentos)

    @property
    def existentes(self) -> int:
        return sum(item.ja_existia for item in self.documentos)

    @property
    def selecionados(self) -> int:
        return len(self.documentos)

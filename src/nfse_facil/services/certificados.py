"""Contrato abstrato para serviços de certificados digitais A1.

ETAPA 01: Contrato puro sem implementações falsas ou leitura real de certificados.
REQUISITO DE SEGURANÇA: Senhas de certificados jamais devem ser armazenadas em disco ou banco.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class CertificadoService(ABC):
    """Contrato abstrato para manipulação e validação de certificados digitais ICP-Brasil A1."""

    @abstractmethod
    def validar_arquivo(self, caminho: Path) -> bool:
        """Verifica se o arquivo existe e possui extensão compatível (.pfx ou .p12)."""

    @abstractmethod
    def verificar_validade(self, caminho: Path, senha: str) -> dict[str, str]:
        """Lê em memória os dados de validade e titularidade do certificado A1.

        NOTA DE SEGURANÇA:
        A senha é utilizada em memória estritamente durante a leitura e nunca é armazenada.
        """

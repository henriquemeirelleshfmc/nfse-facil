"""Contrato abstrato para o serviço de sincronização e download de NFS-e.

ETAPA 01: Contrato puro. Não implementa comunicação com a API ADN nem inventa endpoints.
"""

from abc import ABC, abstractmethod
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload


class NfseSyncService(ABC):
    """Contrato abstrato para a futura integração com o Portal Nacional da NFS-e."""

    @abstractmethod
    def sincronizar(
        self,
        empresa: Empresa,
        periodo: PeriodoConsulta,
        preferencias: PreferenciasDownload,
    ) -> int:
        """Sincroniza e baixa os documentos fiscais do período solicitado.

        Retorna a quantidade de notas fiscais processadas.
        A integração real com a API ADN e autenticação mTLS será implementada nas próximas etapas.
        """

"""Módulo de serviços da aplicação NFS-e Fácil.

Contém as interfaces abstratas que serão implementadas nas etapas futuras.
"""

from nfse_facil.services.certificados import CertificadoService
from nfse_facil.services.nfse import NfseSyncService
from nfse_facil.services.pasta_documentos import PastaDocumentosService
from nfse_facil.services.relatorios import GeradorRelatoriosService
from nfse_facil.services.relatorios import RelatorioService

__all__ = [
    "CertificadoService",
    "NfseSyncService",
    "PastaDocumentosService",
    "GeradorRelatoriosService",
    "RelatorioService",
]

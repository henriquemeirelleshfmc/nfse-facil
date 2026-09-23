"""Serviço de aplicação para associação segura de certificados A1 a empresas.

RESPONSABILIDADES:
- Isolar regras de negócio e persistência da interface gráfica.
- Validar compatibilidade de CNPJ e temporalidade antes de associar.
- Produzir cópias imutáveis de Empresa preservando o estado original em falha.
- Gerenciar remoção de metadados sem nunca apagar arquivos físicos.
"""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from nfse_facil.domain.certificate_models import CertificadoInfo, StatusCertificado
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService


class CertificadoAssociacaoService:
    """Serviço responsável pela associação e desassociação de certificados A1."""

    def __init__(
        self,
        repository: EmpresaRepository,
        cert_service: Pkcs12CertificadoService | None = None,
    ) -> None:
        self.repository = repository
        self.cert_service = cert_service or Pkcs12CertificadoService()

    def associar(
        self,
        empresa: Empresa,
        info: CertificadoInfo,
        lembrar_caminho: bool = True,
        data_referencia: datetime | None = None,
    ) -> Empresa:
        """Associa os metadados públicos do certificado à empresa após validação rigorosa.

        Garante atomicidade: constrói nova instância e persiste no repositório.
        Se a persistência falhar, a instância original permanece intacta.
        """
        # 1. Valida regras de negócio (CNPJ idêntico e período operacional permitido)
        self.cert_service.validar_para_associacao(info, empresa, data_referencia=data_referencia)

        # 2. Constrói cópia com os novos metadados públicos
        caminho_salvar: Path | None = info.caminho_origem if lembrar_caminho else None
        agora_utc = datetime.now(timezone.utc)

        empresa_atualizada = replace(
            empresa,
            certificado_caminho=caminho_salvar,
            certificado_cnpj=info.cnpj,
            certificado_fingerprint_sha256=info.fingerprint_sha256,
            certificado_valido_de=info.valido_de,
            certificado_valido_ate=info.valido_ate,
            certificado_verificado_em=agora_utc,
        )

        # 3. Persiste no repositório
        self.repository.salvar(empresa_atualizada)
        return empresa_atualizada

    def remover_associacao(self, empresa: Empresa) -> Empresa:
        """Remove exclusivamente os metadados de associação do certificado no banco.

        SEGURANÇA:
        O arquivo físico do certificado NUNCA é removido ou alterado no disco.
        """
        empresa_limpa = replace(
            empresa,
            certificado_caminho=None,
            certificado_cnpj=None,
            certificado_fingerprint_sha256=None,
            certificado_valido_de=None,
            certificado_valido_ate=None,
            certificado_verificado_em=None,
        )
        self.repository.salvar(empresa_limpa)
        return empresa_limpa

    def verificar_status_atual(
        self,
        empresa: Empresa,
        data_referencia: datetime | None = None,
    ) -> tuple[str, str]:
        """Avalia o estado atual do certificado associado para apresentação amigável.

        Retorna (codigo_status, rotulo_amigavel).
        Códigos:
        - 'nenhum': Nenhum certificado associado
        - 'arquivo_nao_encontrado': Caminho lembrado não existe no disco
        - 'valido': Certificado associado e válido
        - 'proximo_do_vencimento': Vence em 30 dias ou menos
        - 'vencido': Certificado expirado
        - 'ainda_nao_valido': Data de início futura
        """
        if not empresa.tem_certificado_associado:
            return "nenhum", "Nenhum certificado associado"

        # Se havia caminho lembrado, verifica se o arquivo continua existindo
        if empresa.certificado_caminho is not None:
            if not empresa.certificado_caminho.exists() or not empresa.certificado_caminho.is_file():
                return "arquivo_nao_encontrado", "Arquivo não encontrado no disco"

        # Avaliação temporal dos metadados gravados
        if empresa.certificado_valido_ate is not None:
            valido_de = empresa.certificado_valido_de or datetime.now(timezone.utc)
            status, _ = self.cert_service.classificar_validade_temporal(
                valido_de=valido_de,
                valido_ate=empresa.certificado_valido_ate,
                data_referencia=data_referencia,
            )
            return status.value, status.rotulo_exibicao

        return "valido", "Certificado associado"

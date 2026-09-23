"""Testes para o serviço de associação de certificados A1 e regras de negócio."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from nfse_facil.domain.certificate_models import CertificadoInfo, StatusCertificado
from nfse_facil.domain.exceptions import (
    CertificadoAindaNaoValidoError,
    CertificadoCNPJIncompativelError,
    CertificadoVencidoError,
    PersistenciaError,
)
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.in_memory import InMemoryEmpresaRepository
from nfse_facil.services.associacao_certificado import CertificadoAssociacaoService
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService
from tests.helpers_certificate import gerar_pkcs12_sintetico


@pytest.fixture
def repo() -> InMemoryEmpresaRepository:
    return InMemoryEmpresaRepository()


@pytest.fixture
def cert_service() -> Pkcs12CertificadoService:
    return Pkcs12CertificadoService()


@pytest.fixture
def associacao_service(repo: InMemoryEmpresaRepository, cert_service: Pkcs12CertificadoService) -> CertificadoAssociacaoService:
    return CertificadoAssociacaoService(repository=repo, cert_service=cert_service)


@pytest.fixture
def empresa_valida(repo: InMemoryEmpresaRepository, tmp_path: Path) -> Empresa:
    emp = Empresa(
        razao_social="Oficina Modelo Ltda",
        cnpj="00000000000191",
        pasta_documentos=tmp_path / "docs_oficina",
    )
    repo.salvar(emp)
    return emp


class TestCertificateAssociation:
    """Validação das regras de associação de certificado A1 à empresa."""

    def test_associacao_bem_sucedida_com_caminho_lembrado(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_oficina.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        info = cert_service.inspecionar(pfx_path, "123")
        empresa_atualizada = associacao_service.associar(
            empresa=empresa_valida,
            info=info,
            lembrar_caminho=True,
        )

        assert empresa_atualizada.tem_certificado_associado is True
        assert empresa_atualizada.certificado_cnpj == "00000000000191"
        assert empresa_atualizada.certificado_caminho == pfx_path
        assert empresa_atualizada.certificado_fingerprint_sha256 == info.fingerprint_sha256
        assert empresa_atualizada.certificado_valido_de == info.valido_de
        assert empresa_atualizada.certificado_valido_ate == info.valido_ate
        assert empresa_atualizada.certificado_verificado_em is not None

        # Confirma persistência no repositório
        salva = associacao_service.repository.obter_por_id(empresa_valida.id)
        assert salva is not None
        assert salva.certificado_caminho == pfx_path
        assert salva.certificado_cnpj == "00000000000191"

    def test_associacao_bem_sucedida_sem_lembrar_caminho(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_sem_caminho.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        info = cert_service.inspecionar(pfx_path, "123")
        empresa_atualizada = associacao_service.associar(
            empresa=empresa_valida,
            info=info,
            lembrar_caminho=False,
        )

        assert empresa_atualizada.tem_certificado_associado is True
        assert empresa_atualizada.certificado_caminho is None
        assert empresa_atualizada.certificado_cnpj == "00000000000191"
        assert empresa_atualizada.certificado_fingerprint_sha256 is not None

    def test_recusa_associacao_cnpj_incompativel(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_outro_cnpj.pfx"
        # Certificado com CNPJ diferente da empresa
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="12ABC345000188")

        info = cert_service.inspecionar(pfx_path, "123")

        with pytest.raises(CertificadoCNPJIncompativelError, match="não corresponde ao CNPJ da empresa"):
            associacao_service.associar(empresa_valida, info)

        # Confirma que a empresa no repositório permaneceu intacta
        empresa_banco = associacao_service.repository.obter_por_id(empresa_valida.id)
        assert empresa_banco is not None
        assert empresa_banco.tem_certificado_associado is False

    def test_recusa_associacao_certificado_vencido(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_vencido.pfx"
        inicio = datetime(2020, 1, 1, tzinfo=timezone.utc)
        fim = datetime(2021, 1, 1, tzinfo=timezone.utc)
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191", not_valid_before=inicio, not_valid_after=fim)

        # Inspeção funciona e traz os dados
        info = cert_service.inspecionar(pfx_path, "123")
        assert info.status_temporal == StatusCertificado.VENCIDO

        # Validação para associação deve recusar
        with pytest.raises(CertificadoVencidoError, match="expirou"):
            associacao_service.associar(empresa_valida, info)

    def test_recusa_associacao_certificado_ainda_nao_valido(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_futuro.pfx"
        inicio = datetime(2099, 1, 1, tzinfo=timezone.utc)
        fim = datetime(2100, 1, 1, tzinfo=timezone.utc)
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191", not_valid_before=inicio, not_valid_after=fim)

        info = cert_service.inspecionar(pfx_path, "123")
        assert info.status_temporal == StatusCertificado.AINDA_NAO_VALIDO

        with pytest.raises(CertificadoAindaNaoValidoError, match="ainda não é válido"):
            associacao_service.associar(empresa_valida, info)

    def test_permissao_associacao_certificado_proximo_do_vencimento(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        """Certificado prestes a vencer pode ser associado normalmente."""
        pfx_path = tmp_path / "cert_prestes_vencer.pfx"
        inicio = datetime.now(timezone.utc) - timedelta(days=335)
        fim = datetime.now(timezone.utc) + timedelta(days=20)  # 20 dias restantes (<= 30)
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191", not_valid_before=inicio, not_valid_after=fim)

        info = cert_service.inspecionar(pfx_path, "123")
        assert info.status_temporal == StatusCertificado.PROXIMO_DO_VENCIMENTO

        empresa_associada = associacao_service.associar(empresa_valida, info)
        assert empresa_associada.tem_certificado_associado is True

    def test_remocao_associacao_nao_apaga_arquivo_do_disco(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_para_remover.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        info = cert_service.inspecionar(pfx_path, "123")
        empresa_com_cert = associacao_service.associar(empresa_valida, info, lembrar_caminho=True)
        assert empresa_com_cert.tem_certificado_associado is True

        # Remove associação
        empresa_sem_cert = associacao_service.remover_associacao(empresa_com_cert)

        # Metadados limpos no modelo e no banco
        assert empresa_sem_cert.tem_certificado_associado is False
        assert empresa_sem_cert.certificado_caminho is None
        assert empresa_sem_cert.certificado_cnpj is None
        assert empresa_sem_cert.certificado_fingerprint_sha256 is None

        # ARQUIVO FÍSICO PERMANECE INTACTO NO DISCO
        assert pfx_path.exists() is True
        assert pfx_path.is_file() is True

    def test_status_quando_arquivo_lembrado_deixou_de_existir(
        self,
        tmp_path: Path,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        pfx_path = tmp_path / "cert_movido.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        info = cert_service.inspecionar(pfx_path, "123")
        empresa_associada = associacao_service.associar(empresa_valida, info, lembrar_caminho=True)

        # Remove o arquivo físico simulando que o usuário moveu ou apagou
        pfx_path.unlink()
        assert not pfx_path.exists()

        codigo, rotulo = associacao_service.verificar_status_atual(empresa_associada)
        assert codigo == "arquivo_nao_encontrado"
        assert "não encontrado" in rotulo.lower()

    def test_falha_na_persistencia_preserva_objeto_original(
        self,
        tmp_path: Path,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        """Comprova que se o repositório falhar, a instância original em memória não é corrompida."""
        repo_falho = MagicMock()
        repo_falho.salvar.side_effect = PersistenciaError("Erro de disco simulado")

        service_falho = CertificadoAssociacaoService(repository=repo_falho, cert_service=cert_service)

        pfx_path = tmp_path / "cert.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")
        info = cert_service.inspecionar(pfx_path, "123")

        with pytest.raises(PersistenciaError):
            service_falho.associar(empresa_valida, info)

        # Objeto original permanece com os valores originais intactos
        assert empresa_valida.certificado_caminho is None
        assert empresa_valida.certificado_cnpj is None
        assert empresa_valida.tem_certificado_associado is False

    def test_associacao_recalcula_sempre_validade_deterministica(
        self,
        associacao_service: CertificadoAssociacaoService,
        empresa_valida: Empresa,
        cert_service: Pkcs12CertificadoService,
    ) -> None:
        """Comprova que validar_para_associacao sempre recalcula a validade na data de referência."""
        # 1. Constrói CertificadoInfo inicialmente marcado como VÁLIDO no objeto
        info_inicialmente_valido = CertificadoInfo(
            cnpj="00000000000191",
            nome_comum="Oficina Modelo Ltda:00000000000191",
            emissor="Autoridade Certificadora Teste",
            numero_serie="1234567890",
            valido_de=datetime(2025, 1, 1, tzinfo=timezone.utc),
            valido_ate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            fingerprint_sha256="A" * 64,
            tipo_chave_publica="RSA 2048 bits",
            tem_chave_privada=True,
            certificados_adicionais_qtd=0,
            status_temporal=StatusCertificado.VALIDO,  # armazenado como válido
            dias_restantes=100,
            nome_empresarial="Oficina Modelo Ltda",
        )

        # 2. Referência na qual o certificado já expirou (2026-01-01)
        ref_expirada = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # 3. Confirma que a associação é recusada por CertificadoVencidoError (nunca confia no status_temporal)
        with pytest.raises(CertificadoVencidoError, match="vencido"):
            associacao_service.associar(
                empresa=empresa_valida,
                info=info_inicialmente_valido,
                data_referencia=ref_expirada,
            )

        # 4. Equivalente para "ainda não válido" (referência em 2024-12-01)
        ref_futura = datetime(2024, 12, 1, tzinfo=timezone.utc)
        with pytest.raises(CertificadoAindaNaoValidoError, match="ainda não é válido"):
            associacao_service.associar(
                empresa=empresa_valida,
                info=info_inicialmente_valido,
                data_referencia=ref_futura,
            )

        # 5. Confirma que próximo do vencimento (2025-12-20, restam 11 dias <= 30) continua permitido
        ref_proximo = datetime(2025, 12, 20, tzinfo=timezone.utc)
        empresa_associada = associacao_service.associar(
            empresa=empresa_valida,
            info=info_inicialmente_valido,
            data_referencia=ref_proximo,
        )
        assert empresa_associada.tem_certificado_associado is True


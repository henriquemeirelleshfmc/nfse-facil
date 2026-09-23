"""Testes automatizados da classe Pkcs12CertificadoService e leitura de certificados A1."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import pytest

import asn1crypto.core
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from nfse_facil.domain.certificate_models import StatusCertificado
from nfse_facil.domain.exceptions import (
    CertificadoAindaNaoValidoError,
    CertificadoArquivoGrandeError,
    CertificadoChaveIncompativelError,
    CertificadoChavePrivadaAusenteError,
    CertificadoCNPJAusenteError,
    CertificadoCNPJInvalidoError,
    CertificadoExtensaoInvalidaError,
    CertificadoNaoEncontradoError,
    CertificadoPrincipalAusenteError,
    CertificadoSenhaOuFormatoInvalidoError,
    CertificadoVencidoError,
)
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService, higienizar_texto_x509
from tests.helpers_certificate import gerar_certificado_x509_sintetico, gerar_pkcs12_sintetico


@pytest.fixture
def service() -> Pkcs12CertificadoService:
    return Pkcs12CertificadoService()


class TestPkcs12CertificadoService:
    """Suíte abrangente de testes locais de inspeção de certificados A1 sintéticos."""

    def test_inspecao_pfx_valido_com_senha(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx_path = tmp_path / "cert_valido.pfx"
        gerar_pkcs12_sintetico(
            caminho_arquivo=pfx_path,
            senha="minha_senha_secreta",
            cnpj="00000000000191",
            nome_empresarial="EMPRESA MODELO TESTE LTDA",
        )

        info = service.inspecionar(pfx_path, "minha_senha_secreta")

        assert info.cnpj == "00000000000191"
        assert info.cnpj_formatado == "00.000.000/0001-91"
        assert info.nome_empresarial == "EMPRESA MODELO TESTE LTDA"
        assert info.tem_chave_privada is True
        assert info.tipo_chave_publica == "RSA 2048 bits"
        assert info.status_temporal == StatusCertificado.VALIDO
        assert info.valido_de.tzinfo == timezone.utc
        assert info.valido_ate.tzinfo == timezone.utc
        assert len(info.fingerprint_sha256) == 64
        assert "..." in info.fingerprint_resumida

    def test_inspecao_p12_valido(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        p12_path = tmp_path / "cert_valido.p12"
        gerar_pkcs12_sintetico(
            caminho_arquivo=p12_path,
            senha="outra_senha",
            cnpj="12ABC345000188",
        )

        info = service.inspecionar(p12_path, "outra_senha")
        assert info.cnpj == "12ABC345000188"
        assert info.cnpj_formatado == "12.ABC.345/0001-88"
        assert info.status_temporal == StatusCertificado.VALIDO

    def test_extensao_em_maiusculas_pfx_e_p12(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx_upper = tmp_path / "CERT_UPPER.PFX"
        p12_upper = tmp_path / "CERT_UPPER.P12"

        gerar_pkcs12_sintetico(pfx_upper, senha="123")
        gerar_pkcs12_sintetico(p12_upper, senha="123")

        info1 = service.inspecionar(pfx_upper, "123")
        info2 = service.inspecionar(p12_upper, "123")
        assert info1.cnpj == "00000000000191"
        assert info2.cnpj == "00000000000191"

    def test_senha_incorreta_mensagem_amigavel_sem_vazar_segredo_ou_openssl(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        pfx_path = tmp_path / "cert_senha.pfx"
        senha_correta = "senha_correta_super_secreta"
        senha_errada = "senha_errada_digitada"
        gerar_pkcs12_sintetico(pfx_path, senha=senha_correta)

        with pytest.raises(CertificadoSenhaOuFormatoInvalidoError) as exc_info:
            service.inspecionar(pfx_path, senha_errada)

        msg = str(exc_info.value)
        # Deve ter a mensagem amigável padronizada
        assert "Não foi possível abrir o certificado. Verifique a senha e se o arquivo é um certificado A1 válido." in msg
        # NUNCA deve expor termos internos do OpenSSL ou as senhas
        assert senha_correta not in msg
        assert senha_errada not in msg
        assert "openssl" not in msg.lower()
        assert "pkcs12" not in msg.lower() or "certificado a1" in msg.lower()

    def test_arquivo_corrompido(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        corrompido_path = tmp_path / "corrompido.pfx"
        corrompido_path.write_bytes(b"ESTES_BYTES_NAO_SAO_UM_PKCS12_VALIDO_0123456789")

        with pytest.raises(CertificadoSenhaOuFormatoInvalidoError) as exc_info:
            service.inspecionar(corrompido_path, "senha_qualquer")

        assert "Não foi possível abrir o certificado." in str(exc_info.value)

    def test_arquivo_inexistente(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        inexistente = tmp_path / "nao_existe.pfx"
        with pytest.raises(CertificadoNaoEncontradoError, match="não foi encontrado"):
            service.inspecionar(inexistente, "123")

    def test_caminho_que_e_diretorio(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pasta = tmp_path / "pasta_teste.pfx"
        pasta.mkdir()

        with pytest.raises(CertificadoExtensaoInvalidaError, match="não é um arquivo"):
            service.inspecionar(pasta, "123")

    def test_extensao_nao_permitida(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        arq_txt = tmp_path / "certificado.txt"
        arq_txt.write_bytes(b"conteudo")

        with pytest.raises(CertificadoExtensaoInvalidaError, match="apenas arquivos .pfx ou .p12"):
            service.inspecionar(arq_txt, "123")

    def test_arquivo_acima_do_limite_de_tamanho(self, tmp_path: Path) -> None:
        # Cria serviço com limite reduzido de 100 KB para teste rápido sem alocar 5MB à toa
        service_limite = Pkcs12CertificadoService(limite_tamanho_bytes=100 * 1024)
        arq_grande = tmp_path / "arquivo_pesado.pfx"
        arq_grande.write_bytes(b"A" * (100 * 1024 + 50))

        with pytest.raises(CertificadoArquivoGrandeError, match="excede o limite máximo permitido"):
            service_limite.inspecionar(arq_grande, "123")

    def test_arquivo_truncado_ou_alterado_durante_leitura(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        arq = tmp_path / "alterado.pfx"
        gerar_pkcs12_sintetico(arq, senha="123")

        # Trunca propositalmente pela metade
        conteudo = arq.read_bytes()
        arq.write_bytes(conteudo[: len(conteudo) // 2])

        with pytest.raises(CertificadoSenhaOuFormatoInvalidoError):
            service.inspecionar(arq, "123")

    def test_pkcs12_sem_chave_privada(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        arq = tmp_path / "sem_chave.pfx"
        gerar_pkcs12_sintetico(arq, senha="123", omitir_chave_privada=True)

        with pytest.raises(
            (CertificadoChavePrivadaAusenteError, CertificadoPrincipalAusenteError)
        ):
            service.inspecionar(arq, "123")

    def test_chave_privada_incompativel_com_certificado(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Verifica a rejeição quando a chave privada não bate com a chave pública do certificado."""
        key1 = rsa.generate_private_key(65537, 2048)
        key2 = rsa.generate_private_key(65537, 2048)
        cert1 = gerar_certificado_x509_sintetico(chave_privada=key1)

        # Teste direto do método de correspondência criptográfica
        with pytest.raises(CertificadoChaveIncompativelError, match="não corresponde"):
            service._validar_correspondencia_chave(cert1, key2)

        # Teste via mock na inspeção
        pfx_path = tmp_path / "mismatch.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", chave_privada=key1, cert=cert1)

        with patch("cryptography.hazmat.primitives.serialization.pkcs12.load_key_and_certificates") as mock_load:
            mock_load.return_value = (key2, cert1, [])
            with pytest.raises(CertificadoChaveIncompativelError, match="não corresponde"):
                service.inspecionar(pfx_path, "123")

    def test_classificacao_temporal_e_fronteiras(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        """Testa todas as fronteiras temporais com injeção determinística de data_referencia."""
        pfx_path = tmp_path / "cert_temporal.pfx"
        inicio = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        fim = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        gerar_pkcs12_sintetico(
            pfx_path,
            senha="123",
            not_valid_before=inicio,
            not_valid_after=fim,
        )

        # 1. Antes do início: AINDA_NAO_VALIDO
        info_futuro = service.inspecionar(
            pfx_path, "123", data_referencia=datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        )
        assert info_futuro.status_temporal == StatusCertificado.AINDA_NAO_VALIDO

        # 2. Exatamente no início: VALIDO
        info_inicio = service.inspecionar(pfx_path, "123", data_referencia=inicio)
        assert info_inicio.status_temporal == StatusCertificado.VALIDO

        # 3. No meio (muito tempo restante): VALIDO
        info_meio = service.inspecionar(
            pfx_path, "123", data_referencia=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        )
        assert info_meio.status_temporal == StatusCertificado.VALIDO

        # 4. Exatamente 31 dias completos restantes: VALIDO
        ref_31_dias = fim - timedelta(days=31)
        info_31 = service.inspecionar(pfx_path, "123", data_referencia=ref_31_dias)
        assert info_31.dias_restantes == 31
        assert info_31.status_temporal == StatusCertificado.VALIDO

        # 5. Exatamente 30 dias completos restantes: PROXIMO_DO_VENCIMENTO
        ref_30_dias = fim - timedelta(days=30)
        info_30 = service.inspecionar(pfx_path, "123", data_referencia=ref_30_dias)
        assert info_30.dias_restantes == 30
        assert info_30.status_temporal == StatusCertificado.PROXIMO_DO_VENCIMENTO

        # 6. Exatamente no fim da validade (0 segundos restantes): PROXIMO_DO_VENCIMENTO
        info_fim = service.inspecionar(pfx_path, "123", data_referencia=fim)
        assert info_fim.status_temporal == StatusCertificado.PROXIMO_DO_VENCIMENTO
        assert info_fim.dias_restantes == 0

        # 7. Depois do fim: VENCIDO
        ref_vencido = fim + timedelta(seconds=1)
        info_vencido = service.inspecionar(pfx_path, "123", data_referencia=ref_vencido)
        assert info_vencido.status_temporal == StatusCertificado.VENCIDO
        assert info_vencido.dias_restantes == 0

    def test_ausencia_oid_cnpj_icp_brasil(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx_path = tmp_path / "sem_oid_cnpj.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj=None)

        with pytest.raises(CertificadoCNPJAusenteError, match="não possui a identificação de CNPJ"):
            service.inspecionar(pfx_path, "123")

    def test_tipos_asn1_outras_strings(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        """Verifica suporte aos formatos ASN.1 previstos e de interoperabilidade."""
        for tipo in [
            asn1crypto.core.OctetString,
            asn1crypto.core.PrintableString,
            asn1crypto.core.UTF8String,
            asn1crypto.core.IA5String,
        ]:
            pfx = tmp_path / f"tipo_{tipo.__name__}.pfx"
            gerar_pkcs12_sintetico(pfx, senha="123", cnpj="00000000000191", tipo_asn1_cnpj=tipo)
            info = service.inspecionar(pfx, "123")
            assert info.cnpj == "00000000000191"

    def test_asn1_com_dados_excedentes_rejeitado(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Verifica a rejeição de ASN.1 com bytes excedentes e tipo ASN.1 não string."""
        from nfse_facil.services.pkcs12 import _decodificar_valor_asn1

        # Teste direto de dados excedentes no DER
        der_valido = asn1crypto.core.OctetString(b"00000000000191").dump()
        der_com_lixo = der_valido + b"EXTRAS_RESIDUAIS"

        with pytest.raises(CertificadoCNPJInvalidoError, match="dados excedentes"):
            _decodificar_valor_asn1(der_com_lixo)

        # Teste com tipo ASN.1 inesperado (ex: Integer) dentro do certificado
        key = rsa.generate_private_key(65537, 2048)
        der_int = asn1crypto.core.Integer(12345).dump()
        on_invalido = x509.OtherName(x509.oid.ObjectIdentifier("2.16.76.1.3.3"), der_int)
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([]))
            .issuer_name(x509.Name([]))
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([on_invalido]), critical=False)
            .sign(key, hashes.SHA256())
        )
        pfx_path = tmp_path / "asn1_inteiro.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", chave_privada=key, cert=cert)

        with pytest.raises(CertificadoCNPJInvalidoError, match="Tipo de dado inesperado"):
            service.inspecionar(pfx_path, "123")

    def test_cnpj_extraido_invalido(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "cnpj_invalido.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123", cnpj="00000000000000")  # Dígito inválido

        with pytest.raises(CertificadoCNPJInvalidoError, match="inválido"):
            service.inspecionar(pfx, "123")

    def test_oid_cnpj_repetido_com_mesmo_valor_determinismo(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        pfx = tmp_path / "repetido_igual.pfx"
        gerar_pkcs12_sintetico(
            pfx,
            senha="123",
            cnpj="00000000000191",
            cnpjs_adicionais=[("00000000000191", asn1crypto.core.OctetString)],
        )

        info = service.inspecionar(pfx, "123")
        assert info.cnpj == "00000000000191"

    def test_oid_cnpj_repetido_com_valores_conflitantes_rejeitado(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        pfx = tmp_path / "repetido_conflitante.pfx"
        gerar_pkcs12_sintetico(
            pfx,
            senha="123",
            cnpj="00000000000191",
            cnpjs_adicionais=[("12ABC345000188", asn1crypto.core.OctetString)],
        )

        with pytest.raises(CertificadoCNPJInvalidoError, match="valores conflitantes"):
            service.inspecionar(pfx, "123")

    def test_nome_empresarial_com_caracteres_de_controle_higienizado(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        pfx = tmp_path / "nome_controle.pfx"
        nome_com_controle = "EMPRESA\x00\x07MODELO\r\nTESTE"
        gerar_pkcs12_sintetico(pfx, senha="123", nome_empresarial=nome_com_controle)

        info = service.inspecionar(pfx, "123")
        assert "\x00" not in info.nome_empresarial
        assert "\x07" not in info.nome_empresarial
        assert "\r" not in info.nome_empresarial
        assert "EMPRESA" in info.nome_empresarial

    def test_certificados_adicionais_em_cadeia(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        key_ca = rsa.generate_private_key(65537, 2048)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autoridade Certificadora")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autoridade Certificadora")]))
            .public_key(key_ca.public_key())
            .serial_number(999)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=10))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1000))
            .sign(key_ca, hashes.SHA256())
        )

        pfx = tmp_path / "com_ca.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123", cas=[ca_cert])

        info = service.inspecionar(pfx, "123")
        assert info.certificados_adicionais_qtd == 1

    def test_cnpj_mascarado_no_oid_rejeitado(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "cnpj_mascarado.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123", cnpj="00.000.000/0001-91")

        with pytest.raises(CertificadoCNPJInvalidoError) as exc:
            service.inspecionar(pfx, "123")
        assert "exatamente 14 caracteres" in str(exc.value)
        assert "sem máscara" in str(exc.value)
        assert "00.000.000/0001-91" not in str(exc.value)

    def test_cnpj_oid_excessivamente_longo(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "cnpj_longo.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123", cnpj="0" * 70)

        with pytest.raises(CertificadoCNPJInvalidoError) as exc:
            service.inspecionar(pfx, "123")
        assert "excede o limite" in str(exc.value)
        assert "0" * 70 not in str(exc.value)

    def test_cnpj_oid_com_controle_ou_quebra_de_linha(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "cnpj_quebra.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123", cnpj="00000000\n00019")

        with pytest.raises(CertificadoCNPJInvalidoError) as exc:
            service.inspecionar(pfx, "123")
        assert "\n" not in str(exc.value)
        assert "inválido" in str(exc.value).lower()

    def test_cn_com_quebra_de_linha_higienizado(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "cn_quebra.pfx"
        gerar_pkcs12_sintetico(
            pfx,
            senha="123",
            cnpj="00000000000191",
            nome_comum="EMPRESA MODELO\n\rTESTES:00000000000191",
        )

        info = service.inspecionar(pfx, "123")
        assert "\n" not in info.nome_comum
        assert "\r" not in info.nome_comum
        assert "EMPRESA MODELO TESTES:00000000000191" in info.nome_comum

    def test_emissor_com_tabulacao_higienizado(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "emissor_tab.pfx"
        gerar_pkcs12_sintetico(
            pfx,
            senha="123",
            cnpj="00000000000191",
            emissor="Autoridade\tCertificadora\t\tICP-Brasil",
        )

        info = service.inspecionar(pfx, "123")
        assert "\t" not in info.emissor
        assert "Autoridade Certificadora ICP-Brasil" in info.emissor

    def test_textos_muito_longos_truncados(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "texto_longo.pfx"
        nome_500 = "A" * 500
        gerar_pkcs12_sintetico(
            pfx,
            senha="123",
            cnpj="00000000000191",
            nome_empresarial=nome_500,
        )

        info = service.inspecionar(pfx, "123")
        # Nome empresarial tem limite defensivo ICP-Brasil de 200 caracteres
        assert len(info.nome_empresarial) == 200
        assert info.nome_empresarial == "A" * 200

        # Validação direta da função de higienização com diferentes limites
        assert len(higienizar_texto_x509("B" * 500, limite_tamanho=255)) == 255
        assert len(higienizar_texto_x509("C" * 500, limite_tamanho=100)) == 100

    def test_mensagem_erro_sem_conteudo_malicioso(self, tmp_path: Path, service: Pkcs12CertificadoService) -> None:
        pfx = tmp_path / "malicioso.pfx"
        payload_malicioso = "DROP_TABLE;SECRET_KEY_12345"
        gerar_pkcs12_sintetico(pfx, senha="123", cnpj=payload_malicioso)

        with pytest.raises(CertificadoCNPJInvalidoError) as exc:
            service.inspecionar(pfx, "123")
        msg = str(exc.value)
        assert "DROP_TABLE" not in msg
        assert "SECRET_KEY_12345" not in msg

    # =========================================================================
    # Testes individuais de ausência de vazamento técnico nas exceções públicas
    # =========================================================================

    def test_vazamento_excecao_stat_nao_revela_marcador(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Exceção em Path.stat não deve revelar detalhes internos na mensagem pública."""
        marcador = "OPENSSL_SECRET_MARKER"
        pfx = tmp_path / "cert_stat.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123")

        # exists() e is_file() chamam stat() internamente; precisamos deixá-los
        # passar e só falhar na chamada explícita de stat() dentro do try/except.
        stat_original = Path.stat
        chamadas = {"n": 0}

        def stat_condicional(self_path, *args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] <= 2:
                return stat_original(self_path, *args, **kwargs)
            raise OSError(marcador)

        with patch.object(Path, "stat", stat_condicional):
            with pytest.raises(CertificadoNaoEncontradoError) as exc:
                service.inspecionar(pfx, "123")
            msg_publica = str(exc.value)
            assert marcador not in msg_publica
            # A causa original permanece encadeada para depuração interna
            assert exc.value.__cause__ is not None
            assert marcador in str(exc.value.__cause__)

    def test_vazamento_excecao_leitura_nao_revela_marcador(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Exceção em open/read não deve revelar detalhes internos na mensagem pública."""
        marcador_perm = r"C:\Users\usuario\arquivo-secreto.pfx"
        marcador_gen = "ASN1_INTERNAL_MARKER"
        pfx = tmp_path / "cert_read.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123")

        # Cenário PermissionError
        with patch("builtins.open", side_effect=PermissionError(marcador_perm)):
            with pytest.raises(CertificadoNaoEncontradoError) as exc:
                service.inspecionar(pfx, "123")
            assert marcador_perm not in str(exc.value)
            assert exc.value.__cause__ is not None
            assert marcador_perm in str(exc.value.__cause__)

        # Cenário exceção genérica de leitura
        with patch("builtins.open", side_effect=IOError(marcador_gen)):
            with pytest.raises(CertificadoNaoEncontradoError) as exc:
                service.inspecionar(pfx, "123")
            assert marcador_gen not in str(exc.value)
            assert exc.value.__cause__ is not None
            assert marcador_gen in str(exc.value.__cause__)

    def test_vazamento_excecao_asn1_nao_revela_marcador(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Exceção no parser ASN.1 não deve revelar detalhes internos na mensagem pública."""
        marcador = "ASN1_INTERNAL_MARKER"
        pfx = tmp_path / "cert_asn1.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123")

        with patch("nfse_facil.services.pkcs12.asn1crypto.core.load", side_effect=ValueError(marcador)):
            with pytest.raises(CertificadoCNPJInvalidoError) as exc:
                service.inspecionar(pfx, "123")
            msg_publica = str(exc.value)
            assert marcador not in msg_publica
            assert exc.value.__cause__ is not None
            assert marcador in str(exc.value.__cause__)

    def test_vazamento_excecao_correspondencia_chave_nao_revela_marcador(
        self, service: Pkcs12CertificadoService
    ) -> None:
        """Exceção ao comparar chave privada/pública não deve revelar detalhes na mensagem.

        Chama o método real _validar_correspondencia_chave com mocks que provocam
        RuntimeError no public_bytes, exercitando o except genérico que antes
        interpolava {err} na mensagem pública.
        """
        from unittest.mock import MagicMock

        marcador = "OPENSSL_SECRET_MARKER"

        # Mock do certificado cujo public_key().public_bytes(...) levanta exceção
        cert_mock = MagicMock()
        cert_mock.public_key.return_value.public_bytes.side_effect = RuntimeError(marcador)

        chave_mock = MagicMock()

        with pytest.raises(CertificadoChaveIncompativelError) as exc:
            service._validar_correspondencia_chave(cert_mock, chave_mock)

        msg_publica = str(exc.value)
        assert marcador not in msg_publica
        assert exc.value.__cause__ is not None
        assert marcador in str(exc.value.__cause__)

    def test_vazamento_caminho_confidencial_nao_aparece_na_excecao(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Caminhos confidenciais não devem aparecer nas mensagens de exceção."""
        marcador_dir = "usuario-confidencial"
        marcador_cliente = "cliente-secreto"
        caminho_secreto = tmp_path / marcador_dir / marcador_cliente / "certificado.pfx"

        # Arquivo inexistente — deve levantar CertificadoNaoEncontradoError sem vazar o caminho
        with pytest.raises(CertificadoNaoEncontradoError) as exc:
            service.inspecionar(caminho_secreto, "123")
        msg = str(exc.value)
        assert marcador_dir not in msg
        assert marcador_cliente not in msg

    def test_vazamento_excecao_validador_cnpj_nao_revela_marcador(
        self, tmp_path: Path, service: Pkcs12CertificadoService
    ) -> None:
        """Exceção do validador de CNPJ não deve revelar detalhes na mensagem pública."""
        marcador = "senha-super-secreta"
        pfx = tmp_path / "cert_cnpj_val.pfx"
        gerar_pkcs12_sintetico(pfx, senha="123")

        from nfse_facil.domain.exceptions import CNPJInvalidoError

        with patch(
            "nfse_facil.services.pkcs12.validar_ou_falhar_cnpj",
            side_effect=CNPJInvalidoError(marcador),
        ):
            with pytest.raises(CertificadoCNPJInvalidoError) as exc:
                service.inspecionar(pfx, "123")
            msg_publica = str(exc.value)
            assert marcador not in msg_publica
            assert exc.value.__cause__ is not None
            assert marcador in str(exc.value.__cause__)

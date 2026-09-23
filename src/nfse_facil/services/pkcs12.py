"""Serviço de inspeção e validação local de certificados digitais A1 PKCS#12 (.pfx e .p12).

REGRAS DE SEGURANÇA E CONFORMIDADE:
- Exclusivamente local: sem requisições de rede, mTLS ou consulta externa.
- Segredo Zero: senhas e chaves privadas nunca são persistidas, logadas ou retornadas.
- Limite físico de leitura: impede sobrecarga de memória em arquivos manipulados.
- Tratamento de exceções: mensagens amigáveis sem expor internas do OpenSSL ou segredos.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Final
import unicodedata

import asn1crypto.core
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID, ObjectIdentifier

from nfse_facil.domain.certificate_models import (
    DIAS_AVISO_VENCIMENTO_CERTIFICADO,
    CertificadoInfo,
    StatusCertificado,
)
from nfse_facil.domain.exceptions import (
    CNPJInvalidoError,
    CertificadoAindaNaoValidoError,
    CertificadoArquivoGrandeError,
    CertificadoChaveIncompativelError,
    CertificadoChavePrivadaAusenteError,
    CertificadoCNPJAusenteError,
    CertificadoCNPJIncompativelError,
    CertificadoCNPJInvalidoError,
    CertificadoExtensaoInvalidaError,
    CertificadoNaoEncontradoError,
    CertificadoPrincipalAusenteError,
    CertificadoSenhaOuFormatoInvalidoError,
    CertificadoVencidoError,
)
from nfse_facil.domain.models import Empresa
from nfse_facil.domain.validators import sanitizar_cnpj, validar_ou_falhar_cnpj

# Limite máximo de leitura de arquivos de certificado: 5 MB
LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES: Final[int] = 5 * 1024 * 1024

# Extensões permitidas sem distinção de maiúsculas/minúsculas
EXTENSOES_PERMITIDAS: Final[set[str]] = {".pfx", ".p12"}

# OIDs ICP-Brasil Oficiais
OID_ICP_BRASIL_CNPJ: Final[ObjectIdentifier] = ObjectIdentifier("2.16.76.1.3.3")
OID_ICP_BRASIL_NOME_EMPRESARIAL: Final[ObjectIdentifier] = ObjectIdentifier("2.16.76.1.3.8")


def higienizar_texto_x509(texto: str | None, limite_tamanho: int = 200) -> str:
    """Higieniza textos públicos extraídos de certificados X.509.

    Regras obrigatórias:
    - Trata None ou valores não-string retornando string vazia;
    - Remove caracteres de controle (categoria Unicode 'C' como \\x00-\\x1f, \\x7f-\\x9f);
    - Substitui quebras de linha (\\r, \\n) e tabulações (\\t) por espaços;
    - Colapsa espaços contíguos em um único espaço e remove espaços nas pontas;
    - Trunca o resultado em limite_tamanho se limite_tamanho > 0;
    - Não modifica CNPJ, fingerprint ou número serial.
    """
    if not texto or not isinstance(texto, str):
        return ""

    caracteres_limpos = []
    for ch in texto:
        cat = unicodedata.category(ch)
        if cat.startswith("C") or ch in "\r\n\t":
            caracteres_limpos.append(" ")
        else:
            caracteres_limpos.append(ch)

    texto_limpo = "".join(caracteres_limpos)
    resultado = " ".join(texto_limpo.split())

    if limite_tamanho > 0 and len(resultado) > limite_tamanho:
        resultado = resultado[:limite_tamanho].strip()

    return resultado


def ler_arquivo_com_limite(caminho: Path, limite_bytes: int = LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES) -> bytes:
    """Lê o arquivo em modo binário com limite físico estrito de leitura.

    Garante o fechamento seguro do arquivo e rejeita se o conteúdo ultrapassar
    o limite configurado, mesmo que a consulta inicial de tamanho estivesse normal.
    """
    if not caminho.exists():
        raise CertificadoNaoEncontradoError("O arquivo de certificado não foi encontrado.")
    if not caminho.is_file():
        raise CertificadoExtensaoInvalidaError("O caminho informado não é um arquivo válido.")

    ext = caminho.suffix.lower()
    if ext not in EXTENSOES_PERMITIDAS:
        raise CertificadoExtensaoInvalidaError(
            f"Extensão de arquivo não permitida '{caminho.suffix}'. São aceitos apenas arquivos .pfx ou .p12."
        )

    # Verificação preliminar via stat
    try:
        tamanho_stat = caminho.stat().st_size
        if tamanho_stat > limite_bytes:
            raise CertificadoArquivoGrandeError(
                f"O arquivo excede o limite máximo permitido de {limite_bytes // (1024 * 1024)} MB."
            )
    except (CertificadoArquivoGrandeError, CertificadoExtensaoInvalidaError):
        raise
    except Exception as err:
        raise CertificadoNaoEncontradoError("Não foi possível acessar o arquivo de certificado.") from err

    # Leitura com limite físico estrito (limite_bytes + 1) para detectar alterações concorrentes
    try:
        with open(caminho, "rb") as f:
            conteudo = f.read(limite_bytes + 1)
    except FileNotFoundError:
        raise CertificadoNaoEncontradoError("O arquivo de certificado não foi encontrado ou foi removido.")
    except PermissionError as err:
        raise CertificadoNaoEncontradoError("Permissão negada ao ler o arquivo de certificado.") from err
    except Exception as err:
        raise CertificadoNaoEncontradoError("Erro ao ler o arquivo de certificado.") from err

    if len(conteudo) > limite_bytes:
        raise CertificadoArquivoGrandeError(
            f"O conteúdo do arquivo ultrapassa o limite máximo permitido de {limite_bytes // (1024 * 1024)} MB."
        )

    return conteudo


def _decodificar_valor_asn1(
    raw_der: bytes,
    permitir_strings_adicionais: bool = False,
) -> str:
    """Decodifica DER ASN.1 de OtherName validando ausência de dados excedentes.

    Aceita prioritariamente:
    - OctetString
    - PrintableString

    Quando permitir_strings_adicionais=True, tolera interoperabilidade defensiva com:
    - UTF8String
    - IA5String
    """
    try:
        obj = asn1crypto.core.load(raw_der)
    except Exception as err:
        raise CertificadoCNPJInvalidoError("Estrutura ASN.1 inválida no campo de identificação do certificado.") from err

    # Rejeita estruturas com dados excedentes (trailing bytes)
    dumped = obj.dump()
    if len(dumped) != len(raw_der):
        raise CertificadoCNPJInvalidoError("O conteúdo ASN.1 possui dados excedentes não conformes.")

    # Validação estrita de tipos
    tipos_validos = (asn1crypto.core.OctetString, asn1crypto.core.PrintableString)
    if permitir_strings_adicionais:
        tipos_validos += (asn1crypto.core.UTF8String, asn1crypto.core.IA5String)

    if not isinstance(obj, tipos_validos):
        raise CertificadoCNPJInvalidoError(
            "Tipo de dado inesperado no campo de identificação do certificado."
        )

    nativo = obj.native
    if isinstance(nativo, bytes):
        try:
            return nativo.decode("ascii").strip()
        except UnicodeDecodeError:
            try:
                return nativo.decode("utf-8").strip()
            except UnicodeDecodeError as err:
                raise CertificadoCNPJInvalidoError("Não foi possível decodificar o conteúdo ASN.1 em texto.") from err
    elif isinstance(nativo, str):
        return nativo.strip()

    return str(nativo).strip()


class Pkcs12CertificadoService:
    """Serviço responsável pela inspeção local e validação de certificados A1 PKCS#12."""

    def __init__(self, limite_tamanho_bytes: int = LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES) -> None:
        self.limite_tamanho_bytes = limite_tamanho_bytes

    def inspecionar(
        self,
        caminho_arquivo: Path | str,
        senha: str | bytes | None,
        data_referencia: datetime | None = None,
    ) -> CertificadoInfo:
        """Inspeciona o arquivo de certificado local e extrai seus metadados públicos.

        IMPORTANTE:
        A inspeção SEMPRE retorna CertificadoInfo com seu respectivo status_temporal,
        mesmo quando vencido, ainda não válido ou próximo do vencimento.
        Nunca levanta CertificadoVencidoError ou CertificadoAindaNaoValidoError aqui.
        """
        caminho = Path(caminho_arquivo)
        conteudo_binario = ler_arquivo_com_limite(caminho, self.limite_tamanho_bytes)

        # Preparação segura da senha
        senha_bytes: bytes | None = None
        if senha is not None:
            if isinstance(senha, str):
                senha_bytes = senha.encode("utf-8")
            else:
                senha_bytes = bytes(senha)
        del senha  # Reduz duração da referência ao segredo original

        # Carregamento do PKCS#12
        try:
            chave_privada, cert_principal, adicionais = pkcs12.load_key_and_certificates(
                conteudo_binario,
                senha_bytes,
            )
        except Exception as err:
            # Nunca inclui mensagens internas do OpenSSL ou tracebacks reveladores
            raise CertificadoSenhaOuFormatoInvalidoError() from err
        finally:
            # Redução imediata de ciclo de vida de dados sensíveis da memória
            del conteudo_binario
            del senha_bytes

        # Validação da presença dos componentes fundamentais do A1
        if cert_principal is None:
            raise CertificadoPrincipalAusenteError("O arquivo PKCS#12 não contém o certificado principal.")
        if chave_privada is None:
            raise CertificadoChavePrivadaAusenteError(
                "O arquivo PKCS#12 não contém a chave privada correspondente ao certificado A1."
            )

        # Validação da correspondência criptográfica entre chave privada e certificado público
        self._validar_correspondencia_chave(cert_principal, chave_privada)
        del chave_privada  # Reduz duração da referência à chave privada

        # Extração de CNPJ ICP-Brasil (OID 2.16.76.1.3.3)
        cnpj_extraido = self._extrair_cnpj_icp_brasil(cert_principal)

        # Extração de Nome Empresarial ICP-Brasil (OID 2.16.76.1.3.8) quando presente
        nome_empresarial = self._extrair_nome_empresarial_icp_brasil(cert_principal)

        # Extração dos demais metadados do certificado X.509
        nome_comum = self._extrair_nome_comum(cert_principal)
        emissor = self._extrair_emissor(cert_principal)
        numero_serie = format(cert_principal.serial_number, "X")
        valido_de = cert_principal.not_valid_before_utc
        valido_ate = cert_principal.not_valid_after_utc
        fingerprint_sha256 = cert_principal.fingerprint(hashes.SHA256()).hex().upper()
        tipo_chave_publica = self._identificar_tipo_chave(cert_principal)

        # Classificação temporal consciente em UTC
        status_temporal, dias_restantes = self.classificar_validade_temporal(
            valido_de=valido_de,
            valido_ate=valido_ate,
            data_referencia=data_referencia,
        )

        return CertificadoInfo(
            caminho_origem=caminho,
            cnpj=cnpj_extraido,
            nome_empresarial=nome_empresarial,
            nome_comum=nome_comum,
            emissor=emissor,
            numero_serie=numero_serie,
            valido_de=valido_de,
            valido_ate=valido_ate,
            fingerprint_sha256=fingerprint_sha256,
            tipo_chave_publica=tipo_chave_publica,
            tem_chave_privada=True,
            certificados_adicionais_qtd=len(adicionais) if adicionais else 0,
            status_temporal=status_temporal,
            dias_restantes=dias_restantes,
        )

    def validar_para_associacao(
        self,
        info: CertificadoInfo,
        empresa: Empresa,
        data_referencia: datetime | None = None,
    ) -> None:
        """Aplica as regras de negócio para permitir ou impedir a associação com uma empresa.

        Regras:
        - Certificado VENCIDO não pode ser associado operacionalmente.
        - Certificado AINDA NÃO VÁLIDO não pode ser associado.
        - O CNPJ do certificado deve ser estritamente igual ao CNPJ da empresa.
        - Certificado PRÓXIMO DO VENCIMENTO é permitido (a interface pode emitir aviso).
        """
        # SEMPRE recalcula o status temporal usando a data_referencia fornecida
        # ou datetime.now(timezone.utc). Nunca confia somente no status previamente armazenado.
        ref_utc = data_referencia if data_referencia is not None else datetime.now(timezone.utc)
        status, _ = self.classificar_validade_temporal(
            valido_de=info.valido_de,
            valido_ate=info.valido_ate,
            data_referencia=ref_utc,
        )

        if status == StatusCertificado.VENCIDO:
            raise CertificadoVencidoError(
                f"O certificado está vencido (expirou em {info.valido_ate_formatado}) e não pode ser associado como operacional."
            )
        if status == StatusCertificado.AINDA_NAO_VALIDO:
            raise CertificadoAindaNaoValidoError(
                f"O certificado ainda não é válido (início em {info.valido_de_formatado}) e não pode ser associado."
            )

        # Comparação normalizada de CNPJ
        cnpj_cert = sanitizar_cnpj(info.cnpj)
        cnpj_emp = sanitizar_cnpj(empresa.cnpj)
        if cnpj_cert != cnpj_emp:
            raise CertificadoCNPJIncompativelError(
                f"O CNPJ do certificado ({info.cnpj_formatado}) não corresponde ao CNPJ da empresa ({empresa.cnpj_formatado})."
            )

    @staticmethod
    def classificar_validade_temporal(
        valido_de: datetime,
        valido_ate: datetime,
        data_referencia: datetime | None = None,
    ) -> tuple[StatusCertificado, int]:
        """Classifica o estado de validade temporal de forma consciente e determinística em UTC.

        Fronteiras:
        - ref < valido_de: AINDA_NAO_VALIDO (dias_restantes = 0)
        - ref > valido_ate: VENCIDO (dias_restantes = 0)
        - valido_de <= ref <= valido_ate:
            - tempo_restante <= 30 dias completos (30 * 86400 s): PROXIMO_DO_VENCIMENTO
            - tempo_restante > 30 dias completos: VALIDO
        """
        ref_utc = data_referencia if data_referencia is not None else datetime.now(timezone.utc)
        if ref_utc.tzinfo is None:
            ref_utc = ref_utc.replace(tzinfo=timezone.utc)
        else:
            ref_utc = ref_utc.astimezone(timezone.utc)

        if ref_utc < valido_de:
            return StatusCertificado.AINDA_NAO_VALIDO, 0

        if ref_utc > valido_ate:
            return StatusCertificado.VENCIDO, 0

        # Dentro do intervalo válido: calcula tempo restante exato em segundos
        delta = valido_ate - ref_utc
        segundos_restantes = int(delta.total_seconds())
        dias_completos = segundos_restantes // 86400

        limite_segundos_aviso = DIAS_AVISO_VENCIMENTO_CERTIFICADO * 86400
        if segundos_restantes <= limite_segundos_aviso:
            return StatusCertificado.PROXIMO_DO_VENCIMENTO, dias_completos

        return StatusCertificado.VALIDO, dias_completos

    def _validar_correspondencia_chave(self, cert: x509.Certificate, chave_privada) -> None:
        """Confirma que a chave privada corresponde exatamente à chave pública do certificado.

        Utiliza a representação canônica DER SubjectPublicKeyInfo sem nunca serializar
        ou gravar a chave privada.
        """
        try:
            pub_cert_bytes = cert.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            pub_chave_bytes = chave_privada.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            if pub_cert_bytes != pub_chave_bytes:
                raise CertificadoChaveIncompativelError(
                    "A chave privada do contêiner PKCS#12 não corresponde à chave pública do certificado."
                )
        except CertificadoChaveIncompativelError:
            raise
        except Exception as err:
            raise CertificadoChaveIncompativelError(
                "Falha ao conferir correspondência da chave com o certificado."
            ) from err

    def _extrair_cnpj_icp_brasil(self, cert: x509.Certificate) -> str:
        """Extrai e valida o CNPJ da extensão SAN com OID ICP-Brasil 2.16.76.1.3.3.

        Garante:
        - Presença do OID;
        - Rejeição de múltiplos OIDs com valores conflitantes;
        - Tratamento determinístico se repetido com o mesmo valor;
        - Decodificação ASN.1 defensiva e validação estrita com o validador de CNPJ.
        """
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_value: x509.SubjectAlternativeName = san_ext.value
        except x509.ExtensionNotFound:
            raise CertificadoCNPJAusenteError(
                "O certificado não possui a extensão SubjectAlternativeName com o CNPJ ICP-Brasil."
            )

        cnpjs_encontrados: list[str] = []
        for general_name in san_value:
            if isinstance(general_name, x509.OtherName) and general_name.type_id == OID_ICP_BRASIL_CNPJ:
                # Decodifica DER ASN.1 permitindo UTF8String/IA5String por tolerância documentada
                texto_raw = _decodificar_valor_asn1(general_name.value, permitir_strings_adicionais=True)

                # 1. Limite pequeno antes de processar ou interpolar
                if len(texto_raw) > 64:
                    raise CertificadoCNPJInvalidoError(
                        "O valor de CNPJ no certificado excede o limite máximo permitido."
                    )

                # 2. Exige exatamente 14 caracteres ASCII (não aceita CNPJ mascarado ou com espaços/controles)
                if len(texto_raw) != 14 or not texto_raw.isascii():
                    raise CertificadoCNPJInvalidoError(
                        "O CNPJ contido no certificado deve possuir exatamente 14 caracteres alfanuméricos sem máscara."
                    )

                texto_upper = texto_raw.upper()

                # 3. Posições 1-12 (raiz e ordem de filial): somente 0-9 e A-Z
                if not all(c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in texto_upper[:12]):
                    raise CertificadoCNPJInvalidoError(
                        "O CNPJ contido no certificado contém caracteres inválidos na raiz ou ordem da filial."
                    )

                # 4. Posições 13-14 (dígitos verificadores): estritamente numéricos 0-9
                if not all(c in "0123456789" for c in texto_upper[12:14]):
                    raise CertificadoCNPJInvalidoError(
                        "Os dígitos verificadores do CNPJ contido no certificado devem ser numéricos."
                    )

                # 5. Aplicação do validador oficial de Módulo 11 (nunca interpola texto_raw malformado)
                try:
                    cnpj_validado = validar_ou_falhar_cnpj(texto_upper)
                    cnpjs_encontrados.append(cnpj_validado)
                except CNPJInvalidoError as err:
                    raise CertificadoCNPJInvalidoError(
                        "O CNPJ extraído do certificado é inválido perante as regras oficiais."
                    ) from err

        if not cnpjs_encontrados:
            raise CertificadoCNPJAusenteError(
                "O certificado não possui a identificação de CNPJ da ICP-Brasil (OID 2.16.76.1.3.3)."
            )

        # Verificação de múltiplos valores conflitantes
        valores_unicos = set(cnpjs_encontrados)
        if len(valores_unicos) > 1:
            raise CertificadoCNPJInvalidoError(
                f"O certificado contém múltiplos OIDs de CNPJ com valores conflitantes: {sorted(valores_unicos)}."
            )

        # Se houver repetições com o mesmo valor, toma deterministicamente o primeiro
        return cnpjs_encontrados[0]

    def _extrair_nome_empresarial_icp_brasil(self, cert: x509.Certificate) -> str | None:
        """Extrai o nome empresarial do OID ICP-Brasil 2.16.76.1.3.8 quando presente.

        Higieniza removendo caracteres de controle e limitando o tamanho a 200 caracteres.
        """
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_value: x509.SubjectAlternativeName = san_ext.value
        except x509.ExtensionNotFound:
            return None

        for general_name in san_value:
            if isinstance(general_name, x509.OtherName) and general_name.type_id == OID_ICP_BRASIL_NOME_EMPRESARIAL:
                try:
                    texto_raw = _decodificar_valor_asn1(general_name.value, permitir_strings_adicionais=True)
                    limpo = higienizar_texto_x509(texto_raw, limite_tamanho=200)
                    if limpo:
                        return limpo
                except Exception:
                    continue

        return None

    @staticmethod
    def _extrair_nome_comum(cert: x509.Certificate) -> str:
        """Extrai o Common Name (CN) do Subject do certificado higienizado."""
        attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        return higienizar_texto_x509(str(attrs[0].value), limite_tamanho=150) if attrs else ""

    @staticmethod
    def _extrair_emissor(cert: x509.Certificate) -> str:
        """Extrai identificação legível da autoridade emissora (CN ou O) higienizada."""
        cn_attrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            return higienizar_texto_x509(str(cn_attrs[0].value), limite_tamanho=200)
        o_attrs = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        if o_attrs:
            return higienizar_texto_x509(str(o_attrs[0].value), limite_tamanho=200)
        return higienizar_texto_x509(cert.issuer.rfc4514_string(), limite_tamanho=200)

    @staticmethod
    def _identificar_tipo_chave(cert: x509.Certificate) -> str:
        """Identifica de forma legível o tipo e tamanho da chave pública."""
        pub_key = cert.public_key()
        if isinstance(pub_key, rsa.RSAPublicKey):
            return f"RSA {pub_key.key_size} bits"
        return type(pub_key).__name__

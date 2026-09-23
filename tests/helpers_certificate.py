"""Utilitários para geração exclusiva de certificados e contêineres PKCS#12 sintéticos em testes.

REGRAS DE SEGURANÇA:
- NENHUM certificado real é utilizado.
- Todos os arquivos sintéticos são criados exclusivamente dentro de tmp_path nos testes.
- Nenhum arquivo .pfx, .p12, .pem ou .key deve ser persistido fora de tmp_path.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asn1crypto.core
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption, NoEncryption
from cryptography.x509.oid import ExtensionOID, NameOID, ObjectIdentifier

OID_CNPJ = ObjectIdentifier("2.16.76.1.3.3")
OID_NOME_EMPRESARIAL = ObjectIdentifier("2.16.76.1.3.8")


def gerar_certificado_x509_sintetico(
    chave_privada: rsa.RSAPrivateKey,
    cnpj: str | None = "00000000000191",
    nome_empresarial: str | None = "EMPRESA MODELO TESTES LTDA",
    nome_comum: str = "EMPRESA MODELO TESTES LTDA:00000000000191",
    emissor: str = "Autoridade Certificadora Testes ICP-Brasil",
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
    tipo_asn1_cnpj: type = asn1crypto.core.OctetString,
    trailing_bytes_cnpj: bytes | None = None,
    cnpjs_adicionais: list[tuple[str, type]] | None = None,
    incluir_san: bool = True,
) -> x509.Certificate:
    """Gera um certificado X.509 sintético em memória com extensões ICP-Brasil configuráveis."""
    agora = datetime.now(timezone.utc)
    nv_before = not_valid_before or (agora - timedelta(days=10))
    nv_after = not_valid_after or (agora + timedelta(days=365))

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome_comum)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emissor)])

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(chave_privada.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(nv_before)
        .not_valid_after(nv_after)
    )

    if incluir_san:
        general_names: list[Any] = []

        # 1. OID ICP-Brasil de CNPJ
        if cnpj is not None:
            if tipo_asn1_cnpj == asn1crypto.core.OctetString:
                der_cnpj = asn1crypto.core.OctetString(cnpj.encode("ascii")).dump()
            else:
                der_cnpj = tipo_asn1_cnpj(cnpj).dump()

            if trailing_bytes_cnpj:
                der_cnpj = der_cnpj + trailing_bytes_cnpj

            general_names.append(x509.OtherName(OID_CNPJ, der_cnpj))

        # OIDs de CNPJ adicionais (para testes de repetições ou conflitos)
        if cnpjs_adicionais:
            for c_val, c_tipo in cnpjs_adicionais:
                if c_tipo == asn1crypto.core.OctetString:
                    der_extra = asn1crypto.core.OctetString(c_val.encode("ascii")).dump()
                else:
                    der_extra = c_tipo(c_val).dump()
                general_names.append(x509.OtherName(OID_CNPJ, der_extra))

        # 2. OID ICP-Brasil de Nome Empresarial
        if nome_empresarial is not None:
            der_nome = asn1crypto.core.PrintableString(nome_empresarial).dump()
            general_names.append(x509.OtherName(OID_NOME_EMPRESARIAL, der_nome))

        if general_names:
            builder = builder.add_extension(
                x509.SubjectAlternativeName(general_names),
                critical=False,
            )

    return builder.sign(chave_privada, hashes.SHA256())


def gerar_pkcs12_sintetico(
    caminho_arquivo: Path,
    senha: str | bytes | None = "senha_teste_123",
    chave_privada: rsa.RSAPrivateKey | None = None,
    cert: x509.Certificate | None = None,
    cnpj: str | None = "00000000000191",
    nome_empresarial: str | None = "EMPRESA MODELO TESTES LTDA",
    nome_comum: str = "EMPRESA MODELO TESTES LTDA:00000000000191",
    emissor: str = "Autoridade Certificadora Testes ICP-Brasil",
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
    tipo_asn1_cnpj: type = asn1crypto.core.OctetString,
    trailing_bytes_cnpj: bytes | None = None,
    cnpjs_adicionais: list[tuple[str, type]] | None = None,
    cas: list[x509.Certificate] | None = None,
    omitir_chave_privada: bool = False,
    omitir_certificado: bool = False,
    incluir_san: bool = True,
) -> Path:
    """Gera um arquivo PKCS#12 (.pfx ou .p12) sintético em disco dentro de caminho_arquivo."""
    key = chave_privada or rsa.generate_private_key(public_exponent=65537, key_size=2048)

    if cert is None and not omitir_certificado:
        cert = gerar_certificado_x509_sintetico(
            chave_privada=key,
            cnpj=cnpj,
            nome_empresarial=nome_empresarial,
            nome_comum=nome_comum,
            emissor=emissor,
            not_valid_before=not_valid_before,
            not_valid_after=not_valid_after,
            tipo_asn1_cnpj=tipo_asn1_cnpj,
            trailing_bytes_cnpj=trailing_bytes_cnpj,
            cnpjs_adicionais=cnpjs_adicionais,
            incluir_san=incluir_san,
        )

    # Tratamento de encriptação
    if senha is not None:
        senha_bytes = senha.encode("utf-8") if isinstance(senha, str) else senha
        enc_alg = BestAvailableEncryption(senha_bytes)
    else:
        enc_alg = NoEncryption()

    chave_para_serializar = None if omitir_chave_privada else key
    cert_para_serializar = None if omitir_certificado else cert

    pfx_data = pkcs12.serialize_key_and_certificates(
        name=b"certificado_sintetico_a1",
        key=chave_para_serializar,
        cert=cert_para_serializar,
        cas=cas,
        encryption_algorithm=enc_alg,
    )

    caminho_arquivo.write_bytes(pfx_data)
    return caminho_arquivo

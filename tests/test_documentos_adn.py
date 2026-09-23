"""Testes da decodificação e organização segura de documentos do ADN."""

import base64
from datetime import date
import gzip
from pathlib import Path

import pytest

from nfse_facil.domain.adn_models import AmbienteADN, RespostaADN
from nfse_facil.domain.document_models import DirecaoDocumento
from nfse_facil.domain.exceptions import (
    DocumentoFiscalGravacaoError,
    DocumentoFiscalGrandeError,
    DocumentoFiscalInvalidoError,
)
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload
from nfse_facil.services.documentos_adn import OrganizadorDocumentosADN


CNPJ_EMPRESA = "00000000000191"
CNPJ_OUTRO = "11222333000181"


def xml_nfse(prestador=CNPJ_EMPRESA, tomador=CNPJ_OUTRO, data_emissao="2026-09-21T10:30:00-04:00") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
  <infNFSe Id="NFS123"><dhEmi>{data_emissao}</dhEmi>
    <prest><CNPJ>{prestador}</CNPJ></prest>
    <toma><CNPJ>{tomador}</CNPJ></toma>
  </infNFSe>
</NFSe>""".encode()


def resposta_com(arquivo_xml: str, **campos) -> RespostaADN:
    item = {
        "NSU": 7,
        "ChaveAcesso": "1" * 50,
        "TipoDocumento": "NFSE",
        "ArquivoXml": arquivo_xml,
        **campos,
    }
    return RespostaADN(200, {"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS", "LoteDFe": [item]}, AmbienteADN.PRODUCAO, "/DFe/0")


@pytest.fixture
def empresa(tmp_path: Path) -> Empresa:
    return Empresa("Empresa Teste", CNPJ_EMPRESA, tmp_path / "documentos")


@pytest.mark.parametrize("formato", ["direto", "base64", "gzip_base64"])
def test_decodifica_formatos_e_organiza_emitida(formato: str, empresa: Empresa) -> None:
    xml = xml_nfse()
    if formato == "direto":
        campo = xml.decode()
    elif formato == "base64":
        campo = base64.b64encode(xml).decode()
    else:
        campo = base64.b64encode(gzip.compress(xml)).decode()

    resultado = OrganizadorDocumentosADN().processar(resposta_com(campo), empresa)

    assert resultado.novos == 1
    salvo = resultado.documentos[0]
    assert salvo.documento.direcao == DirecaoDocumento.EMITIDA
    assert salvo.documento.data_documento == date(2026, 9, 21)
    pasta_empresa = empresa.pasta_documentos / f"Empresa Teste - {CNPJ_EMPRESA}"
    assert salvo.caminho == pasta_empresa / "2026" / "09" / "Emitidas" / f"NFSE_{'1' * 50}.xml"
    assert salvo.caminho.read_bytes() == xml


def test_classifica_recebida(empresa: Empresa) -> None:
    xml = xml_nfse(prestador=CNPJ_OUTRO, tomador=CNPJ_EMPRESA)
    resultado = OrganizadorDocumentosADN().processar(resposta_com(xml.decode()), empresa)
    assert resultado.documentos[0].documento.direcao == DirecaoDocumento.RECEBIDA
    assert "Recebidas" in resultado.documentos[0].caminho.parts


def test_classifica_outro_sem_inventar_direcao(empresa: Empresa) -> None:
    xml = xml_nfse(prestador=CNPJ_OUTRO, tomador="99888777000166")
    resultado = OrganizadorDocumentosADN().processar(resposta_com(xml.decode()), empresa)
    assert resultado.documentos[0].documento.direcao == DirecaoDocumento.OUTRA


def test_filtro_nao_descarta_documentos_necessarios_ao_avanco_do_nsu(empresa: Empresa) -> None:
    emitida_fora = resposta_com(xml_nfse(data_emissao="2026-08-31T23:59:59-04:00").decode()).lote_dfe[0]
    recebida_dentro = resposta_com(
        xml_nfse(prestador=CNPJ_OUTRO, tomador=CNPJ_EMPRESA).decode(), NSU=8, ChaveAcesso="2" * 50
    ).lote_dfe[0]
    emitida_dentro = resposta_com(
        xml_nfse().decode(), NSU=9, ChaveAcesso="3" * 50
    ).lote_dfe[0]
    resposta = RespostaADN(
        200,
        {"LoteDFe": [emitida_fora, recebida_dentro, emitida_dentro]},
        AmbienteADN.PRODUCAO,
        "/DFe/0",
    )

    resultado = OrganizadorDocumentosADN().processar(
        resposta,
        empresa,
        PeriodoConsulta.personalizado(date(2026, 9, 1), date(2026, 9, 30)),
        PreferenciasDownload(baixar_emitidas=False, baixar_recebidas=True),
    )

    assert resultado.novos == 1
    assert resultado.selecionados == 1
    assert resultado.fora_do_filtro == 2
    assert resultado.arquivados_novos == 3
    assert resultado.documentos[0].documento.direcao == DirecaoDocumento.RECEBIDA
    arquivo_interno = (
        OrganizadorDocumentosADN.pasta_da_empresa(empresa)
        / OrganizadorDocumentosADN.PASTA_ARQUIVO_INTERNO
    )
    assert len(list(arquivo_interno.rglob("*.xml"))) == 3
    arquivos_visiveis = [
        caminho
        for caminho in empresa.pasta_documentos.rglob("*.xml")
        if OrganizadorDocumentosADN.PASTA_ARQUIVO_INTERNO not in caminho.parts
    ]
    assert len(arquivos_visiveis) == 1


def test_cada_empresa_recebe_pasta_mae_exclusiva(tmp_path: Path) -> None:
    pasta_principal = tmp_path / "NFSe-Facil"
    empresa_a = Empresa("Empresa Alfa", CNPJ_EMPRESA, pasta_principal)
    empresa_b = Empresa("Empresa Beta", "11222333000181", pasta_principal)

    caminho_a = OrganizadorDocumentosADN.pasta_da_empresa(empresa_a)
    caminho_b = OrganizadorDocumentosADN.pasta_da_empresa(empresa_b)

    assert caminho_a == pasta_principal / f"Empresa Alfa - {CNPJ_EMPRESA}"
    assert caminho_b == pasta_principal / "Empresa Beta - 11222333000181"
    assert caminho_a != caminho_b


def test_nome_vindo_do_certificado_nao_repete_cnpj_na_pasta(tmp_path: Path) -> None:
    empresa_certificado = Empresa(
        f"Cooperativa Modelo:{CNPJ_EMPRESA}", CNPJ_EMPRESA, tmp_path
    )
    assert OrganizadorDocumentosADN.pasta_da_empresa(empresa_certificado).name == (
        f"Cooperativa Modelo - {CNPJ_EMPRESA}"
    )


def test_processamento_repetido_e_idempotente(empresa: Empresa) -> None:
    resposta = resposta_com(xml_nfse().decode())
    organizador = OrganizadorDocumentosADN()
    primeiro = organizador.processar(resposta, empresa)
    segundo = organizador.processar(resposta, empresa)
    assert primeiro.novos == 1
    assert segundo.novos == 0
    assert segundo.existentes == 1


def test_restaura_xml_visivel_apagado_a_partir_do_arquivo_interno(empresa: Empresa) -> None:
    organizador = OrganizadorDocumentosADN()
    periodo = PeriodoConsulta.personalizado(date(2026, 9, 1), date(2026, 9, 30))
    preferencias = PreferenciasDownload(baixar_emitidas=True, baixar_recebidas=False)
    resultado = organizador.processar(
        resposta_com(xml_nfse().decode()), empresa, periodo, preferencias
    )
    visivel = resultado.documentos[0].caminho
    conteudo_original = visivel.read_bytes()
    visivel.unlink()

    restaurados = organizador.restaurar_visiveis(empresa, periodo, preferencias)

    assert restaurados == 1
    assert visivel.read_bytes() == conteudo_original
    assert organizador.restaurar_visiveis(empresa, periodo, preferencias) == 0


def test_restauracao_respeita_periodo_e_direcao_selecionados(empresa: Empresa) -> None:
    organizador = OrganizadorDocumentosADN()
    resultado = organizador.processar(resposta_com(xml_nfse().decode()), empresa)
    visivel = resultado.documentos[0].caminho
    visivel.unlink()

    restaurados = organizador.restaurar_visiveis(
        empresa,
        PeriodoConsulta.personalizado(date(2026, 8, 1), date(2026, 8, 31)),
        PreferenciasDownload(baixar_emitidas=False, baixar_recebidas=True),
    )

    assert restaurados == 0
    assert not visivel.exists()


def test_nao_sobrescreve_mesmo_nome_com_conteudo_diferente(empresa: Empresa) -> None:
    organizador = OrganizadorDocumentosADN()
    organizador.processar(resposta_com(xml_nfse().decode()), empresa)
    alterado = xml_nfse(data_emissao="2026-09-22T10:30:00-04:00")
    with pytest.raises(DocumentoFiscalGravacaoError, match="conteúdo diferente"):
        organizador.processar(resposta_com(alterado.decode()), empresa)


@pytest.mark.parametrize("campo", ["", "%%%", base64.b64encode(b"nao xml").decode()])
def test_rejeita_conteudo_ausente_ou_invalido(campo: str, empresa: Empresa) -> None:
    with pytest.raises(DocumentoFiscalInvalidoError):
        OrganizadorDocumentosADN().processar(resposta_com(campo), empresa)


def test_rejeita_xml_malformado_e_doctype(empresa: Empresa) -> None:
    organizador = OrganizadorDocumentosADN()
    with pytest.raises(DocumentoFiscalInvalidoError):
        organizador.processar(resposta_com("<NFSe>"), empresa)
    perigoso = '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///segredo">]><NFSe>&e;</NFSe>'
    with pytest.raises(DocumentoFiscalInvalidoError, match="externas"):
        organizador.processar(resposta_com(perigoso), empresa)


def test_limita_descompactacao_de_gzip(empresa: Empresa) -> None:
    organizador = OrganizadorDocumentosADN()
    organizador.LIMITE_XML_BYTES = 100
    bomba = base64.b64encode(gzip.compress(b"<x>" + b"a" * 1000 + b"</x>")).decode()
    with pytest.raises(DocumentoFiscalGrandeError):
        organizador.processar(resposta_com(bomba), empresa)


def test_rejeita_data_ausente(empresa: Empresa) -> None:
    xml = f"<NFSe><prest><CNPJ>{CNPJ_EMPRESA}</CNPJ></prest></NFSe>"
    with pytest.raises(DocumentoFiscalInvalidoError, match="data válida"):
        OrganizadorDocumentosADN().processar(resposta_com(xml), empresa)


def test_evento_usa_dh_evento(empresa: Empresa) -> None:
    xml = (
        "<evento><infEvento><dhEvento>2026-08-15T14:30:00-04:00</dhEvento>"
        "<chNFSe>" + "4" * 50 + "</chNFSe></infEvento></evento>"
    )
    resultado = OrganizadorDocumentosADN().processar(
        resposta_com(xml, TipoDocumento="EVENTO", NSU=12, ChaveAcesso="4" * 50),
        empresa,
    )
    documento = resultado.documentos[0]
    assert documento.documento.data_documento == date(2026, 8, 15)
    assert documento.caminho.parent.parent.name == "08"


def test_documento_sem_data_interna_usa_data_do_envelope(empresa: Empresa) -> None:
    xml = "<evento><infEvento><chNFSe>" + "5" * 50 + "</chNFSe></infEvento></evento>"
    resultado = OrganizadorDocumentosADN().processar(
        resposta_com(
            xml,
            TipoDocumento="EVENTO",
            NSU=13,
            ChaveAcesso="5" * 50,
            DataHoraGeracao="2026-07-10T08:00:00Z",
        ),
        empresa,
    )
    assert resultado.documentos[0].documento.data_documento == date(2026, 7, 10)


@pytest.mark.parametrize("nsu", ["../../segredo", "１２", "", "1" * 21])
def test_nsu_malicioso_nao_vira_nome_de_arquivo(nsu, empresa: Empresa) -> None:
    with pytest.raises(DocumentoFiscalInvalidoError):
        OrganizadorDocumentosADN().processar(resposta_com(xml_nfse().decode(), NSU=nsu), empresa)


def test_tipo_e_chave_sao_higienizados(empresa: Empresa) -> None:
    resposta = resposta_com(
        xml_nfse().decode(),
        TipoDocumento="../../NFSe<script>",
        ChaveAcesso="../../fora",
    )
    resultado = OrganizadorDocumentosADN().processar(resposta, empresa)
    caminho = resultado.documentos[0].caminho
    assert caminho.parent.name == "Emitidas"
    assert caminho.resolve().is_relative_to(empresa.pasta_documentos.resolve())
    assert ".." not in caminho.name


def test_falha_de_gravacao_remove_temporario(monkeypatch, empresa: Empresa) -> None:
    def falhar_replace(*_args):
        raise OSError("CAMINHO_INTERNO_SECRETO")

    monkeypatch.setattr("nfse_facil.services.documentos_adn.os.replace", falhar_replace)
    with pytest.raises(DocumentoFiscalGravacaoError) as exc:
        OrganizadorDocumentosADN().processar(resposta_com(xml_nfse().decode()), empresa)
    assert "CAMINHO_INTERNO_SECRETO" not in str(exc.value)
    assert not list(empresa.pasta_documentos.rglob("*.tmp"))

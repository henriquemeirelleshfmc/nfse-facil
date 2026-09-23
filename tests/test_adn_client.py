"""Testes do cliente ADN sem realizar chamadas à rede oficial."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from nfse_facil.domain.adn_models import AmbienteADN, BASES_ADN
from nfse_facil.domain.exceptions import (
    ADNAutenticacaoError,
    ADNConfiguracaoError,
    ADNConexaoError,
    ADNIndisponivelError,
    ADNLimiteRequisicoesError,
    ADNRespostaInvalidaError,
    ADNTimeoutError,
)
from nfse_facil.infrastructure.http.adn_client import ADNClient


class RespostaFalsa:
    def __init__(self, status: int = 200, dados=None, headers=None, corpo: bytes | None = None):
        self.status_code = status
        self.headers = headers or {}
        self._corpo = corpo if corpo is not None else json.dumps(dados or {}).encode("utf-8")
        self.fechada = False

    def iter_content(self, chunk_size: int):
        for inicio in range(0, len(self._corpo), chunk_size):
            yield self._corpo[inicio : inicio + chunk_size]

    def close(self) -> None:
        self.fechada = True


@pytest.fixture
def pfx_minimo(tmp_path: Path) -> Path:
    caminho = tmp_path / "cliente.pfx"
    caminho.write_bytes(b"pkcs12-somente-para-mock-de-transporte")
    return caminho


def test_ambientes_usam_somente_hosts_oficiais() -> None:
    assert BASES_ADN[AmbienteADN.PRODUCAO] == "https://adn.nfse.gov.br/contribuintes"
    assert BASES_ADN[AmbienteADN.PRODUCAO_RESTRITA] == (
        "https://adn.producaorestrita.nfse.gov.br/contribuintes"
    )


def test_consulta_nsu_monta_requisicao_mtls_segura(pfx_minimo: Path) -> None:
    resposta_http = RespostaFalsa(
        dados={"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS", "LoteDFe": [{"NSU": 7}]},
        headers={"X-Request-ID": "req-123"},
    )
    transporte = MagicMock(return_value=resposta_http)
    cliente = ADNClient(AmbienteADN.PRODUCAO_RESTRITA, request_get=transporte)

    resposta = cliente.consultar_dfe_por_nsu(
        "000000000000007", pfx_minimo, "segredo", cnpj_consulta="00.000.000/0001-91"
    )

    assert resposta.status_processamento == "DOCUMENTOS_LOCALIZADOS"
    assert resposta.lote_dfe[0]["NSU"] == 7
    assert resposta.requisicao_id == "req-123"
    url, = transporte.call_args.args
    kwargs = transporte.call_args.kwargs
    assert url == f"{BASES_ADN[AmbienteADN.PRODUCAO_RESTRITA]}/DFe/000000000000007"
    assert kwargs["params"] == {"lote": "true", "cnpjConsulta": "00000000000191"}
    assert kwargs["verify"] is True
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["pkcs12_data"] == pfx_minimo.read_bytes()
    assert kwargs["pkcs12_password"] == "segredo"
    assert "segredo" not in repr(kwargs["headers"])
    assert resposta_http.fechada is True


def test_consulta_eventos_valida_chave_e_endpoint(pfx_minimo: Path) -> None:
    transporte = MagicMock(return_value=RespostaFalsa(dados={"eventos": []}))
    cliente = ADNClient(AmbienteADN.PRODUCAO, request_get=transporte)
    chave = "1" * 50

    resposta = cliente.consultar_eventos_por_chave(chave, pfx_minimo, b"senha")

    assert resposta.endpoint == f"/NFSe/{chave}/Eventos"
    assert transporte.call_args.args[0] == f"{BASES_ADN[AmbienteADN.PRODUCAO]}/NFSe/{chave}/Eventos"
    assert transporte.call_args.kwargs["params"] is None


@pytest.mark.parametrize("nsu", ["", "-1", "1.2", "１２", "A1", "1" * 16])
def test_nsu_invalido_e_rejeitado_sem_rede(nsu, pfx_minimo: Path) -> None:
    transporte = MagicMock()
    cliente = ADNClient(request_get=transporte)
    with pytest.raises(ADNConfiguracaoError):
        cliente.consultar_dfe_por_nsu(nsu, pfx_minimo, "senha")
    transporte.assert_not_called()


@pytest.mark.parametrize("chave", ["", "1" * 49, "1" * 51, "A" * 50, "１" * 50])
def test_chave_invalida_e_rejeitada_sem_rede(chave, pfx_minimo: Path) -> None:
    transporte = MagicMock()
    cliente = ADNClient(request_get=transporte)
    with pytest.raises(ADNConfiguracaoError):
        cliente.consultar_eventos_por_chave(chave, pfx_minimo, "senha")
    transporte.assert_not_called()


@pytest.mark.parametrize(
    ("erro_transporte", "erro_publico"),
    [
        (requests.exceptions.Timeout("SEGREDO_TIMEOUT"), ADNTimeoutError),
        (requests.exceptions.SSLError("SEGREDO_OPENSSL"), ADNAutenticacaoError),
        (requests.exceptions.ConnectionError("SEGREDO_REDE"), ADNConexaoError),
        (RuntimeError("SEGREDO_INTERNO"), ADNConexaoError),
    ],
)
def test_erros_de_transporte_sao_higienizados(
    erro_transporte, erro_publico, pfx_minimo: Path
) -> None:
    cliente = ADNClient(request_get=MagicMock(side_effect=erro_transporte))
    with pytest.raises(erro_publico) as exc:
        cliente.consultar_dfe_por_nsu(0, pfx_minimo, "senha-super-secreta")
    assert "SEGREDO" not in str(exc.value)
    assert "senha-super-secreta" not in str(exc.value)
    assert exc.value.__cause__ is erro_transporte


@pytest.mark.parametrize(
    ("status", "erro"),
    [
        (401, ADNAutenticacaoError),
        (403, ADNAutenticacaoError),
        (429, ADNLimiteRequisicoesError),
        (500, ADNIndisponivelError),
        (503, ADNIndisponivelError),
        (400, ADNRespostaInvalidaError),
    ],
)
def test_status_http_e_traduzido(status, erro, pfx_minimo: Path) -> None:
    cliente = ADNClient(request_get=MagicMock(return_value=RespostaFalsa(status=status)))
    with pytest.raises(erro):
        cliente.consultar_dfe_por_nsu(0, pfx_minimo, "senha")


def test_404_na_distribuicao_indica_que_nao_ha_novos_documentos(pfx_minimo: Path) -> None:
    resposta_http = RespostaFalsa(status=404, headers={"X-Request-ID": "fim-123"})
    cliente = ADNClient(request_get=MagicMock(return_value=resposta_http))

    resposta = cliente.consultar_dfe_por_nsu(100, pfx_minimo, "senha")

    assert resposta.status_http == 404
    assert resposta.status_processamento == "NENHUM_DOCUMENTO_LOCALIZADO"
    assert resposta.lote_dfe == ()
    assert resposta.requisicao_id == "fim-123"
    assert resposta_http.fechada is True


def test_404_em_consulta_de_eventos_continua_sendo_erro(pfx_minimo: Path) -> None:
    cliente = ADNClient(request_get=MagicMock(return_value=RespostaFalsa(status=404)))
    with pytest.raises(ADNRespostaInvalidaError, match="não encontrou"):
        cliente.consultar_eventos_por_chave("1" * 50, pfx_minimo, "senha")


def test_resposta_maior_que_limite_por_cabecalho(pfx_minimo: Path) -> None:
    resposta = RespostaFalsa(headers={"Content-Length": "11"}, corpo=b"{}")
    cliente = ADNClient(request_get=MagicMock(return_value=resposta), limite_resposta_bytes=10)
    with pytest.raises(ADNRespostaInvalidaError, match="excede"):
        cliente.consultar_dfe_por_nsu(0, pfx_minimo, "senha")


def test_resposta_maior_que_limite_durante_stream(pfx_minimo: Path) -> None:
    resposta = RespostaFalsa(corpo=b"{" + b" " * 20 + b"}")
    cliente = ADNClient(request_get=MagicMock(return_value=resposta), limite_resposta_bytes=10)
    with pytest.raises(ADNRespostaInvalidaError, match="excede"):
        cliente.consultar_dfe_por_nsu(0, pfx_minimo, "senha")


@pytest.mark.parametrize("corpo", [b"nao-json", b"\xff", b"[]"])
def test_resposta_invalida_e_rejeitada(corpo: bytes, pfx_minimo: Path) -> None:
    cliente = ADNClient(request_get=MagicMock(return_value=RespostaFalsa(corpo=corpo)))
    with pytest.raises(ADNRespostaInvalidaError):
        cliente.consultar_dfe_por_nsu(0, pfx_minimo, "senha")


def test_configuracao_de_timeout_e_limite_e_validada() -> None:
    with pytest.raises(ADNConfiguracaoError):
        ADNClient(timeout=(0, 10))
    with pytest.raises(ADNConfiguracaoError):
        ADNClient(limite_resposta_bytes=0)

"""Testes do avanço transacional lógico do cursor NSU."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nfse_facil.domain.adn_models import AmbienteADN, RespostaADN
from nfse_facil.domain.exceptions import ADNConfiguracaoError, DocumentoFiscalGravacaoError
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.in_memory import InMemoryEmpresaRepository
from nfse_facil.services.sincronizacao_adn import SincronizacaoADNService


def _resposta(*nsus: int, maior_nsu: int | None = None) -> RespostaADN:
    itens = [
        {
            "NSU": nsu,
            "ChaveAcesso": str(nsu).zfill(50),
            "TipoDocumento": "NFSE",
            "ArquivoXml": (
                "<NFSe><infNFSe><dhEmi>2026-09-21T10:00:00-04:00</dhEmi>"
                "<prest><CNPJ>00000000000191</CNPJ></prest>"
                "<toma><CNPJ>11222333000181</CNPJ></toma>"
                "</infNFSe></NFSe>"
            ),
        }
        for nsu in nsus
    ]
    dados = {"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS", "LoteDFe": itens}
    if maior_nsu is not None:
        dados["MaxNSU"] = maior_nsu
    return RespostaADN(
        200,
        dados,
        AmbienteADN.PRODUCAO_RESTRITA,
        "/DFe/0",
    )


def _empresa(tmp_path: Path, nsu: int = 0) -> Empresa:
    certificado = tmp_path / "certificado.pfx"
    certificado.write_bytes(b"simulado")
    return Empresa(
        "Empresa",
        "00000000000191",
        tmp_path / "docs",
        certificado_caminho=certificado,
        certificado_cnpj="00000000000191",
        ultimo_nsu_adn=nsu,
    )


def test_avanca_para_maior_nsu_somente_apos_organizar(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = _empresa(tmp_path, nsu=5)
    repo.salvar(empresa)
    cliente = MagicMock()
    cliente.consultar_dfe_por_nsu.return_value = _resposta(6, 8, 7)

    resultado = SincronizacaoADNService(repo, cliente).sincronizar_lote(empresa, "senha")

    assert resultado.nsu_anterior == 5
    assert resultado.ultimo_nsu == 8
    assert resultado.organizacao.novos == 3
    assert empresa.ultimo_nsu_adn == 8
    assert repo.obter_por_id(empresa.id).ultimo_nsu_adn == 8
    cliente.consultar_dfe_por_nsu.assert_called_once_with(
        5, empresa.certificado_caminho, "senha", cnpj_consulta=None, lote=True
    )


def test_informa_cnpj_consulta_apenas_para_outro_estabelecimento_da_raiz(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    certificado = tmp_path / "certificado.pfx"
    certificado.write_bytes(b"simulado")
    empresa = Empresa(
        "Filial",
        "00000000000272",
        tmp_path / "docs",
        certificado_caminho=certificado,
        certificado_cnpj="00000000000191",
    )
    repo.salvar(empresa)
    cliente = MagicMock()
    cliente.consultar_dfe_por_nsu.return_value = _resposta()

    SincronizacaoADNService(repo, cliente).sincronizar_lote(empresa, "senha")

    cliente.consultar_dfe_por_nsu.assert_called_once_with(
        0, certificado, "senha", cnpj_consulta=empresa.cnpj, lote=True
    )


def test_nao_avanca_nsu_quando_organizacao_falha(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = _empresa(tmp_path, nsu=10)
    repo.salvar(empresa)
    cliente = MagicMock()
    cliente.consultar_dfe_por_nsu.return_value = _resposta(11)
    organizador = MagicMock()
    organizador.processar.side_effect = DocumentoFiscalGravacaoError("falha segura")

    with pytest.raises(DocumentoFiscalGravacaoError):
        SincronizacaoADNService(repo, cliente, organizador).sincronizar_lote(empresa, "senha")

    assert empresa.ultimo_nsu_adn == 10
    assert repo.obter_por_id(empresa.id).ultimo_nsu_adn == 10
    repo_observado = repo.obter_por_id(empresa.id)
    assert repo_observado is empresa


def test_lote_vazio_preserva_cursor(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = _empresa(tmp_path, nsu=20)
    repo.salvar(empresa)
    cliente = MagicMock()
    cliente.consultar_dfe_por_nsu.return_value = _resposta()

    resultado = SincronizacaoADNService(repo, cliente).sincronizar_lote(empresa, "senha")

    assert resultado.nsu_anterior == 20
    assert resultado.ultimo_nsu == 20
    assert resultado.organizacao.novos == 0


def test_exige_certificado_associado_sem_chamar_rede(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = Empresa("Empresa", "00000000000191", tmp_path / "docs")
    cliente = MagicMock()
    with pytest.raises(ADNConfiguracaoError, match="certificado"):
        SincronizacaoADNService(repo, cliente).sincronizar_lote(empresa, "senha")
    cliente.consultar_dfe_por_nsu.assert_not_called()


def test_sincronizacao_completa_busca_lotes_automaticamente_com_uma_senha(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = _empresa(tmp_path)
    repo.salvar(empresa)
    cliente = MagicMock()
    primeiro = _resposta(*range(1, 51), maior_nsu=52)
    segundo = _resposta(51, 52, maior_nsu=52)
    cliente.consultar_dfe_por_nsu.side_effect = [primeiro, segundo]

    resultado = SincronizacaoADNService(repo, cliente).sincronizar_todos(
        empresa, "senha-unica"
    )

    assert resultado.concluida is True
    assert resultado.lotes_processados == 2
    assert resultado.ultimo_nsu == 52
    assert resultado.organizacao.novos == 52
    assert cliente.consultar_dfe_por_nsu.call_count == 2
    assert cliente.consultar_dfe_por_nsu.call_args_list[0].args[0] == 0
    assert cliente.consultar_dfe_por_nsu.call_args_list[1].args[0] == 50
    assert all(chamada.args[2] == "senha-unica" for chamada in cliente.consultar_dfe_por_nsu.call_args_list)


def test_lote_menor_que_cinquenta_indica_fim_disponivel(tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    empresa = _empresa(tmp_path)
    repo.salvar(empresa)
    cliente = MagicMock()
    cliente.consultar_dfe_por_nsu.return_value = _resposta(1, 2)

    resultado = SincronizacaoADNService(repo, cliente).sincronizar_todos(empresa, "senha")

    assert resultado.concluida is True
    assert resultado.lotes_processados == 1
    cliente.consultar_dfe_por_nsu.assert_called_once()

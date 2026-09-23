"""Testes de interface do fluxo de busca de notas sem rede real."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from nfse_facil.domain.document_models import ResultadoOrganizacao
from nfse_facil.domain.exceptions import ADNRespostaInvalidaError
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload
from nfse_facil.infrastructure.repositories.in_memory import InMemoryEmpresaRepository
from nfse_facil.services.sincronizacao_adn import ResultadoSincronizacao
from nfse_facil.ui.components.download_dialog import DownloadDialog


def _bombear(app, dialogo) -> None:
    for _ in range(200):
        time.sleep(0.01)
        app.update_idletasks()
        app.update()
        if not dialogo._processando:
            return


def test_download_dialog_limpa_senha_e_exibe_resultado(app, tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    certificado = tmp_path / "cert.pfx"
    certificado.write_bytes(b"mock")
    empresa = Empresa(
        "Empresa",
        "00000000000191",
        tmp_path / "docs",
        certificado_caminho=certificado,
    )
    repo.salvar(empresa)
    servico = MagicMock()
    servico.sincronizar_todos.return_value = ResultadoSincronizacao(
        ResultadoOrganizacao((), fora_do_filtro=0), 0, 15, "DOCUMENTOS_LOCALIZADOS", 2, True
    )
    sucesso = MagicMock()
    dlg = DownloadDialog(
        app,
        repo,
        empresa,
        PeriodoConsulta.este_mes(),
        PreferenciasDownload(),
        sucesso,
        servico,
    )
    dlg.txt_senha.insert(0, "senha-secreta")
    dlg._iniciar()
    assert dlg.txt_senha.get() == ""
    assert dlg.btn_buscar.cget("state") == "disabled"
    assert not hasattr(dlg, "senha")
    _bombear(app, dlg)
    assert "Consulta concluída" in dlg.lbl_status.cget("text")
    assert dlg.lbl_status_titulo.cget("text") == "Empresa atualizada"
    assert "2 lote(s)" in dlg.lbl_status.cget("text")
    assert "senha-secreta" not in dlg.lbl_status.cget("text")
    sucesso.assert_called_once_with(empresa)
    dlg.destroy()


def test_download_dialog_oculta_excecao_inesperada(app, tmp_path: Path) -> None:
    repo = InMemoryEmpresaRepository()
    certificado = tmp_path / "cert.pfx"
    certificado.write_bytes(b"mock")
    empresa = Empresa("Empresa", "00000000000191", tmp_path / "docs", certificado_caminho=certificado)
    servico = MagicMock()
    servico.sincronizar_todos.side_effect = RuntimeError("OPENSSL_SEGREDO_INTERNO")
    dlg = DownloadDialog(
        app,
        repo,
        empresa,
        PeriodoConsulta.este_mes(),
        PreferenciasDownload(),
        MagicMock(),
        servico,
    )
    dlg.txt_senha.insert(0, "senha")
    dlg._iniciar()
    _bombear(app, dlg)
    assert "OPENSSL_SEGREDO_INTERNO" not in dlg.lbl_status.cget("text")
    assert "Código de suporte: NFSE-" in dlg.lbl_status.cget("text")
    assert dlg.btn_copiar_diagnostico.winfo_manager() == "pack"
    assert dlg.btn_buscar.cget("state") == "normal"
    servico.sincronizar_todos.side_effect = ADNRespostaInvalidaError(
        "A NFS-e Nacional recusou os dados da consulta."
    )
    dlg.txt_senha.insert(0, "senha")
    dlg._iniciar()
    _bombear(app, dlg)
    assert "recusou os dados" in dlg.lbl_status.cget("text")
    assert "não confirma o fim" in dlg.lbl_status.cget("text")

    empresa.ultimo_nsu_adn = 10
    dlg._finalizar_sucesso(
        ResultadoSincronizacao(
            ResultadoOrganizacao((), fora_do_filtro=0),
            10,
            10,
            "NENHUM_DOCUMENTO_LOCALIZADO",
            1,
            True,
        )
    )
    assert dlg._reconstruir_historico is True
    assert dlg.btn_buscar.cget("text") == "Baixar histórico novamente"
    dlg.destroy()

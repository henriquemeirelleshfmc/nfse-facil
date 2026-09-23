"""Teste de fumaça (smoke test) da interface gráfica CustomTkinter."""

import pytest
import customtkinter as ctk

from nfse_facil.app import create_app
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.in_memory import InMemoryEmpresaRepository
from nfse_facil.ui.main_window import MainWindow
from nfse_facil.ui.messages import (
    MSG_SEGURANCA_CERTIFICADO,
    TITULO_AVISO_DOWNLOAD,
    obter_mensagem_aviso_download,
)


class TestUISmoke:
    """Valida a inicialização, presença de componentes e encerramento sem loop infinito."""

    def test_inicializacao_completa_e_componentes_essenciais(self, app: MainWindow) -> None:
        """Processa a inicialização gráfica, valida componentes e transições de tela."""
        repo = InMemoryEmpresaRepository()
        app.repository = repo
        app.company_list.repository = repo
        app.company_list.carregar_empresas()

        # Processa o ciclo de eventos da UI sem bloquear no mainloop
        app.update_idletasks()
        app.update()

        # 1. Confirma título e dimensões
        assert "NFS-e Fácil" in app.title()

        # 2. Confirma componentes da barra lateral e Minhas empresas
        assert hasattr(app, "sidebar_frame")
        assert hasattr(app, "btn_adicionar")
        assert hasattr(app, "company_list")
        assert "@henrique.meirelles_" in app.btn_contato.cget("text")
        assert app.btn_adicionar.cget("text") == "+ Adicionar empresa"
        assert app.company_list.txt_busca is not None

        # 3. Confirma estado inicial rigorosamente vazio do repositório
        assert len(repo.listar_todas()) == 0
        assert app._empresa_ativa is None
        assert app.company_list.empresa_selecionada_id is None

        # 4. Confirma frame de boas-vindas gerenciado e visível, e operacional oculto
        assert app.frame_boas_vindas.winfo_manager() == "pack"
        assert bool(app.frame_boas_vindas.winfo_ismapped()) is True
        # No CTkScrollableFrame, o contêiner efetivamente empacotado é _parent_frame
        assert app.frame_operacional._parent_frame.winfo_manager() == ""
        assert bool(app.frame_operacional._parent_frame.winfo_ismapped()) is False

        # 5. Confirma componentes operacionais de download e período
        assert hasattr(app, "period_selector")
        assert hasattr(app, "btn_baixar")
        assert app.btn_baixar.cget("text") == "Buscar e organizar notas"

        # 6. Confirma opções de download (checkboxes)
        assert app.var_emitidas.get() is True
        assert app.var_recebidas.get() is True
        assert app.var_excel.get() is True
        assert app.var_pdf.get() is True

        # 7. Simula adição de uma empresa e valida transição correta para painel operacional
        empresa_teste = Empresa(
            razao_social="Empresa Teste Interface Ltda",
            cnpj="12ABC345000188",  # Alfanumérico válido
            pasta_documentos="/tmp/teste",
        )
        repo.salvar(empresa_teste)
        app.company_list.carregar_empresas(selecionar_id=empresa_teste.id)
        app.update_idletasks()
        app.update()

        # Agora a empresa está ativa e o painel operacional está exibido
        assert app._empresa_ativa is not None
        assert app._empresa_ativa.id == empresa_teste.id
        assert app.lbl_card_nome.cget("text") == "Empresa Teste Interface Ltda"
        assert "12.ABC.345/0001-88" in app.lbl_card_cnpj.cget("text")

        # Valida transição dos frames (operacional visível e boas-vindas oculto)
        assert app.frame_boas_vindas.winfo_manager() == ""
        assert bool(app.frame_boas_vindas.winfo_ismapped()) is False
        assert app.frame_operacional._parent_frame.winfo_manager() == "pack"
        assert bool(app.frame_operacional._parent_frame.winfo_ismapped()) is True

        # 8. Valida retorno ao estado vazio quando a empresa é removida
        repo.remover(empresa_teste.id)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        assert len(repo.listar_todas()) == 0
        assert app._empresa_ativa is None
        assert app.frame_boas_vindas.winfo_manager() == "pack"
        assert bool(app.frame_boas_vindas.winfo_ismapped()) is True
        assert app.frame_operacional._parent_frame.winfo_manager() == ""
        assert bool(app.frame_operacional._parent_frame.winfo_ismapped()) is False

    def test_factory_create_app(self, app: MainWindow) -> None:
        """Testa o ponto de entrada da fábrica create_app()."""
        assert isinstance(app, MainWindow)
        assert "NFS-e Fácil" in app.title()

    def test_mensagens_interface_atemporais_e_sem_textos_obsoletos(self) -> None:
        """Comprova que os textos da interface não possuem termos obsoletos nem promessas ultrapassadas."""
        # 1. Mensagem de segurança do certificado
        assert "nunca será armazenada" in MSG_SEGURANCA_CERTIFICADO
        assert "solicitada somente quando necessária" in MSG_SEGURANCA_CERTIFICADO
        assert "nunca será solicitada" not in MSG_SEGURANCA_CERTIFICADO

        # 2. Mensagem de aviso de download
        msg = obter_mensagem_aviso_download("Empresa Modelo Ltda", "00.000.000/0001-91", "Janeiro/2026")
        assert "Empresa Modelo Ltda" in msg
        assert "00.000.000/0001-91" in msg
        assert "Janeiro/2026" in msg
        assert "Esta versão ainda não realiza downloads" in msg

        # Proibidos em mensagens de interface:
        termos_proibidos = [
            "Etapa 01",
            "Etapa 02",
            "próxima etapa",
            "nunca será solicitada",
        ]
        for termo in termos_proibidos:
            assert termo not in msg, f"Termo proibido '{termo}' encontrado na mensagem de download"
            assert termo not in MSG_SEGURANCA_CERTIFICADO, f"Termo proibido '{termo}' no aviso de certificado"

    def test_modal_aviso_downloads_utiliza_conteudo_centralizado(self, app: MainWindow, monkeypatch) -> None:
        """Comprova que a abertura do modal de download invoca e renderiza o conteúdo centralizado sem bloquear."""
        from datetime import date
        from unittest.mock import MagicMock
        from nfse_facil.domain.models import PeriodoConsulta, PreferenciasDownload, TipoPeriodo

        empresa_teste = Empresa(
            razao_social="Empresa Modal Teste",
            cnpj="00000000000191",
            pasta_documentos="/tmp/modal",
        )
        periodo = PeriodoConsulta(
            tipo=TipoPeriodo.ESTE_MES,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 1, 31),
        )
        prefs = PreferenciasDownload(baixar_emitidas=True)

        chamadas_toplevel = []

        # Evita abrir janela real bloqueante do CustomTkinter durante o teste
        class MockToplevel:
            def __init__(self, parent):
                self.parent = parent
                self._title = ""
                chamadas_toplevel.append(self)

            def title(self, val):
                self._title = val

            def geometry(self, val): pass
            def resizable(self, a, b): pass
            def transient(self, p): pass
            def grab_set(self): pass
            def destroy(self): pass

        monkeypatch.setattr(ctk, "CTkToplevel", MockToplevel)
        monkeypatch.setattr(ctk, "CTkFrame", MagicMock())
        monkeypatch.setattr(ctk, "CTkLabel", MagicMock())
        monkeypatch.setattr(ctk, "CTkButton", MagicMock())

        app._exibir_modal_aviso_downloads(empresa_teste, periodo, prefs)

        assert len(chamadas_toplevel) == 1
        assert chamadas_toplevel[0]._title == TITULO_AVISO_DOWNLOAD

"""Testes da interface gráfica para gestão de empresas (cadastro, edição e remoção segura)."""

from pathlib import Path
from typing import Generator
from unittest.mock import patch
import pytest

from nfse_facil.app import create_app
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository
from nfse_facil.ui.components.company_dialog import CompanyDialog
from nfse_facil.ui.main_window import MainWindow


class TestUICompanyManagement:
    """Validação do fluxo visual de cadastro, edição e remoção sem janelas bloqueantes."""

    def test_fluxo_adicionar_empresa_persiste_no_sqlite(self, app: MainWindow, tmp_path: Path) -> None:
        db_path = tmp_path / "ui_add.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        app.repository = repo
        app.company_list.repository = repo
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()
        assert app._empresa_ativa is None

        pasta_cliente = tmp_path / "docs_novo_cliente"

        # Simula abertura e salvamento no CompanyDialog
        dialog = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=app._on_empresa_cadastrada_ou_editada,
        )
        dialog.txt_razao.insert(0, "Nova Empresa Cadastrada Ltda")
        dialog.txt_fantasia.insert(0, "Nova Empresa")
        dialog.txt_cnpj.insert(0, "00.000.000/0001-91")
        dialog.txt_pasta.delete(0, "end")
        dialog.txt_pasta.insert(0, str(pasta_cliente))

        # Dispara salvamento
        dialog._salvar()
        app.update_idletasks()
        app.update()

        # Valida que foi persistido no banco
        todas = repo.listar_todas()
        assert len(todas) == 1
        assert todas[0].razao_social == "Nova Empresa Cadastrada Ltda"
        assert todas[0].cnpj == "00000000000191"

        # Valida que a pasta foi criada no disco
        assert pasta_cliente.exists()

        # Valida que a UI atualizou e selecionou a nova empresa
        assert app._empresa_ativa is not None
        assert app._empresa_ativa.razao_social == "Nova Empresa Cadastrada Ltda"
        assert app.lbl_card_nome.cget("text") == "Nova Empresa"
        assert "00.000.000/0001-91" in app.lbl_card_cnpj.cget("text")
        assert app.frame_boas_vindas.winfo_manager() == ""
        assert app.frame_operacional._parent_frame.winfo_manager() == "pack"

    def test_fluxo_editar_empresa_preserva_id_e_criacao(self, app: MainWindow, tmp_path: Path) -> None:
        db_path = tmp_path / "ui_edit.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        pasta_orig = tmp_path / "docs_orig"
        empresa_inicial = Empresa(
            razao_social="Nome Antigo Ltda",
            nome_fantasia="Fantasia Antiga",
            cnpj="00.000.000/0001-91",
            pasta_documentos=pasta_orig,
            ultimo_nsu_adn=42,
        )
        repo.salvar(empresa_inicial)
        id_original = empresa_inicial.id
        criado_em_original = empresa_inicial.criado_em

        app.repository = repo
        app.company_list.repository = repo
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()
        assert app._empresa_ativa is not None
        assert app._empresa_ativa.id == id_original

        pasta_nova = tmp_path / "docs_editados"

        # Abre o diálogo em modo de edição
        dialog = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=app._on_empresa_cadastrada_ou_editada,
            empresa_edicao=app._empresa_ativa,
        )

        # Modifica os campos
        dialog.txt_razao.delete(0, "end")
        dialog.txt_razao.insert(0, "Nome Atualizado Ltda")
        dialog.txt_fantasia.delete(0, "end")
        dialog.txt_fantasia.insert(0, "Fantasia Atualizada")
        dialog.txt_pasta.delete(0, "end")
        dialog.txt_pasta.insert(0, str(pasta_nova))

        # Salva a edição
        dialog._salvar()
        app.update_idletasks()
        app.update()

        empresa_salva = repo.obter_por_id(id_original)
        assert empresa_salva is not None
        assert empresa_salva.ultimo_nsu_adn == 42

        # Valida no banco
        empresa_db = repo.obter_por_id(id_original)
        assert empresa_db is not None
        assert empresa_db.razao_social == "Nome Atualizado Ltda"
        assert empresa_db.nome_fantasia == "Fantasia Atualizada"
        assert empresa_db.criado_em == criado_em_original
        assert empresa_db.atualizado_em > criado_em_original
        assert pasta_nova.exists()

        # Valida na UI
        assert app._empresa_ativa.razao_social == "Nome Atualizado Ltda"
        assert app.lbl_card_nome.cget("text") == "Fantasia Atualizada"

    def test_edicao_invalida_nao_altera_objeto_nem_interface(self, app: MainWindow, tmp_path: Path) -> None:
        db_path = tmp_path / "ui_edit_fail.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        empresa_inicial = Empresa(
            razao_social="Empresa Intacta Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "intacta",
        )
        repo.salvar(empresa_inicial)

        app.repository = repo
        app.company_list.repository = repo
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        dialog = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=app._on_empresa_cadastrada_ou_editada,
            empresa_edicao=app._empresa_ativa,
        )

        # Insere CNPJ inválido
        dialog.txt_cnpj.delete(0, "end")
        dialog.txt_cnpj.insert(0, "11.111.111/1111-11")  # Dígitos repetidos inválidos
        dialog._salvar()

        # Dialog permanece aberto com mensagem de erro
        assert dialog.lbl_erro.cget("text") != ""

        # Dados na janela principal permanecem estritamente intactos
        assert app._empresa_ativa.razao_social == "Empresa Intacta Ltda"
        assert app._empresa_ativa.cnpj == "00000000000191"
        assert app.lbl_card_nome.cget("text") == "Empresa Intacta Ltda"

        dialog.destroy()

    def test_fluxo_remover_empresa_segura_preserva_pasta(self, app: MainWindow, tmp_path: Path) -> None:
        db_path = tmp_path / "ui_delete.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        pasta_empresa = tmp_path / "docs_empresa_para_remover"
        pasta_empresa.mkdir()
        arquivo_cliente = pasta_empresa / "documento_antigo.xml"
        arquivo_cliente.write_text("<xml>conteudo</xml>", encoding="utf-8")

        empresa = Empresa(
            razao_social="Empresa Descartavel Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=pasta_empresa,
        )
        repo.salvar(empresa)

        app.repository = repo
        app.company_list.repository = repo
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()
        assert app._empresa_ativa is not None

        # 1. Simula usuário cancelando a exclusão
        with patch("tkinter.messagebox.askyesno", return_value=False):
            app._confirmar_remover_empresa()
            assert repo.obter_por_id(empresa.id) is not None
            assert app._empresa_ativa is not None

        # 2. Simula usuário confirmando a exclusão
        with patch("tkinter.messagebox.askyesno", return_value=True):
            app._confirmar_remover_empresa()
            app.update_idletasks()
            app.update()

        # Confirma que foi removida do banco
        assert repo.obter_por_id(empresa.id) is None
        assert len(repo.listar_todas()) == 0

        # CRÍTICO: Confirma que a pasta e seus arquivos no disco NÃO foram apagados
        assert pasta_empresa.exists()
        assert arquivo_cliente.exists()
        assert arquivo_cliente.read_text(encoding="utf-8") == "<xml>conteudo</xml>"

        # UI deve ter voltado ao estado vazio amigável
        assert app._empresa_ativa is None
        assert app.frame_boas_vindas.winfo_manager() == "pack"
        assert app.frame_operacional._parent_frame.winfo_manager() == ""

    def test_dialogo_cadastro_mantem_botao_salvar_visivel(self, app: MainWindow, tmp_path: Path) -> None:
        """O rodapé deve permanecer visível mesmo quando o formulário precisa rolar."""
        repo = SqliteEmpresaRepository(db_path=tmp_path / "ui_layout.db")
        dialog = CompanyDialog(parent=app, repository=repo, on_success=lambda _empresa: None)
        dialog.geometry("520x520")
        dialog.update_idletasks()
        dialog.update()

        assert dialog.form_scroll._parent_frame.winfo_manager() == "pack"
        assert dialog.footer_actions.winfo_manager() == "pack"
        assert dialog.btn_salvar.winfo_manager() == "pack"
        inferior_rodape = dialog.footer_actions.winfo_y() + dialog.footer_actions.winfo_height()
        assert inferior_rodape <= dialog.winfo_height()

        dialog.destroy()

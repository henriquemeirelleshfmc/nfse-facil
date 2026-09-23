"""Testes de interface gráfica para a gestão e inspeção de certificados digitais A1."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.in_memory import InMemoryEmpresaRepository
from nfse_facil.services.associacao_certificado import CertificadoAssociacaoService
from nfse_facil.ui.components.certificate_dialog import CertificateDialog, CertificateInfoDialog
from nfse_facil.ui.components.company_dialog import CompanyDialog
from nfse_facil.ui.main_window import MainWindow
from nfse_facil.ui.messages import MSG_ERRO_GENERICO_CERTIFICADO
from tests.helpers_certificate import gerar_pkcs12_sintetico


@pytest.fixture
def repo(tmp_path: Path) -> InMemoryEmpresaRepository:
    r = InMemoryEmpresaRepository()
    emp = Empresa(
        razao_social="Oficina Auto Modelo Ltda",
        nome_fantasia="Auto Modelo",
        cnpj="00000000000191",
        pasta_documentos=tmp_path / "docs_oficina",
    )
    r.salvar(emp)
    return r


class TestUICertificate:
    """Validação da interface gráfica para o ciclo de vida do certificado digital."""

    def test_estados_visuais_secao_certificado_no_cartao(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Verifica a exibição correta dos badges e botões de acordo com o estado do certificado."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        empresa = repo.listar_todas()[0]
        app._on_empresa_selecionada(empresa)
        app.update_idletasks()
        app.update()

        # 1. Estado Inicial: nenhum certificado associado
        assert "Nenhum certificado" in app.lbl_cert_status.cget("text")
        assert app.btn_selecionar_cert.cget("text") == "Selecionar certificado A1"
        assert not app.btn_info_cert.winfo_ismapped()
        assert not app.btn_remover_cert.winfo_ismapped()

        # 2. Estado: Certificado Válido Associado
        pfx_path = tmp_path / "cert.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")
        info = app.associacao_service.cert_service.inspecionar(pfx_path, "123")
        empresa_valida = app.associacao_service.associar(empresa, info, lembrar_caminho=True)

        app._on_empresa_selecionada(empresa_valida)
        app.update_idletasks()
        app.update()

        assert "✓ Certificado válido" in app.lbl_cert_status.cget("text")
        assert app.btn_selecionar_cert.cget("text") == "Trocar certificado"
        assert app.btn_info_cert.winfo_ismapped()
        assert app.btn_remover_cert.winfo_ismapped()

        # 3. Estado: Arquivo movido/removido do disco
        pfx_path.unlink()
        app._atualizar_secao_certificado(empresa_valida)
        assert "não encontrado" in app.lbl_cert_status.cget("text").lower()

        # 4. Estado: Vencido
        empresa_vencida = Empresa(
            id=empresa.id,
            razao_social=empresa.razao_social,
            cnpj=empresa.cnpj,
            pasta_documentos=empresa.pasta_documentos,
            certificado_caminho=None,
            certificado_cnpj=empresa.cnpj,
            certificado_fingerprint_sha256="DUMMYFP",
            certificado_valido_de=datetime(2020, 1, 1, tzinfo=timezone.utc),
            certificado_valido_ate=datetime(2021, 1, 1, tzinfo=timezone.utc),
            certificado_verificado_em=datetime.now(timezone.utc),
        )
        app._atualizar_secao_certificado(empresa_vencida)
        assert "❌ Certificado vencido" in app.lbl_cert_status.cget("text")

    def test_dialogo_inspecao_limpeza_senha_e_duplo_clique(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Comprova limpeza imediata da senha e proteção contra múltiplos cliques."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()
        empresa = repo.listar_todas()[0]

        pfx_path = tmp_path / "cert_dialog.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="senha_teste_123", cnpj="00000000000191")

        callback_sucesso = MagicMock()
        dlg = CertificateDialog(
            parent=app,
            empresa=empresa,
            associacao_service=app.associacao_service,
            on_success=callback_sucesso,
            caminho_inicial=pfx_path,
        )
        dlg.update_idletasks()
        dlg.update()

        # Digita senha no campo
        dlg.txt_senha.insert(0, "senha_teste_123")
        assert dlg.txt_senha.get() == "senha_teste_123"

        # Tenta alternar "Mostrar senha"
        dlg.var_mostrar_senha.set(True)
        dlg._alternar_mostrar_senha()
        assert dlg.txt_senha.cget("show") == ""
        dlg.var_mostrar_senha.set(False)
        dlg._alternar_mostrar_senha()
        assert dlg.txt_senha.cget("show") == "*"

        # Dispara inspeção
        dlg._iniciar_inspecao()

        # Senha visual deve ser apagada IMEDIATAMENTE após iniciar
        assert dlg.txt_senha.get() == ""
        # Botão deve estar desabilitado para impedir duplo clique
        assert dlg.btn_inspecionar.cget("state") == "disabled"

        # Simula duplo clique imediato enquanto processa
        dlg._iniciar_inspecao()

        # Aguarda término da thread no executor e processa callbacks do loop Tk
        dlg._executor.shutdown(wait=True)
        for _ in range(50):
            if not dlg._processando:
                break
            app.update_idletasks()
            app.update()

        # Inspeção concluída: resumo deve estar mapeado e confirmação habilitada
        assert dlg.card_resumo.winfo_ismapped()
        assert dlg.btn_confirmar.cget("state") == "normal"
        assert dlg.txt_senha.get() == ""  # Continua rigorosamente vazia

        # Confirma associação
        with patch("tkinter.messagebox.showinfo"):
            dlg._confirmar_associacao()

        callback_sucesso.assert_called_once()
        dlg.destroy()

    def test_fechamento_do_dialogo_durante_processamento(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Verifica que fechar a janela antes do término do worker não gera exceções no Tkinter."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()
        empresa = repo.listar_todas()[0]

        pfx_path = tmp_path / "cert_slow.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        dlg = CertificateDialog(
            parent=app,
            empresa=empresa,
            associacao_service=app.associacao_service,
            on_success=MagicMock(),
            caminho_inicial=pfx_path,
        )
        dlg.update_idletasks()
        dlg.update()
        dlg.txt_senha.insert(0, "123")

        # Inicia inspeção e fecha a janela imediatamente enquanto a thread roda
        dlg._iniciar_inspecao()
        dlg._on_fechar_janela()

        # O executor encerra limpo sem levantar erros de widget destruído
        dlg._executor.shutdown(wait=True)
        app.update_idletasks()
        app.update()

    def test_edicao_cnpj_com_certificado_solicita_confirmacao(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Testa o fluxo de editar o CNPJ de uma empresa que possui certificado associado."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        # Associa certificado à empresa
        pfx_path = tmp_path / "cert_edicao.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")
        info = app.associacao_service.cert_service.inspecionar(pfx_path, "123")
        empresa_associada = app.associacao_service.associar(repo.listar_todas()[0], info)

        # 1. Caso Cancelado: usuário muda CNPJ mas cancela na caixa de confirmação
        dlg_edicao = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=MagicMock(),
            empresa_edicao=empresa_associada,
        )
        dlg_edicao.txt_cnpj.delete(0, "end")
        dlg_edicao.txt_cnpj.insert(0, "12.ABC.345/0001-88")  # Novo CNPJ

        with patch("tkinter.messagebox.askyesno", return_value=False):
            dlg_edicao._salvar()

        # Não salvou: empresa no repositório permaneceu com CNPJ e certificado anteriores
        empresa_banco = repo.obter_por_id(empresa_associada.id)
        assert empresa_banco.cnpj == "00000000000191"
        assert empresa_banco.tem_certificado_associado is True
        dlg_edicao.destroy()

        # 2. Caso Confirmado: usuário confirma a alteração de CNPJ
        callback_edicao = MagicMock()
        dlg_edicao2 = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=callback_edicao,
            empresa_edicao=empresa_associada,
        )
        dlg_edicao2.txt_cnpj.delete(0, "end")
        dlg_edicao2.txt_cnpj.insert(0, "12.ABC.345/0001-88")

        with patch("tkinter.messagebox.askyesno", return_value=True):
            dlg_edicao2._salvar()

        # Salvou novo CNPJ e removeu os metadados do certificado anterior
        empresa_salva = repo.obter_por_id(empresa_associada.id)
        assert empresa_salva.cnpj == "12ABC345000188"
        assert empresa_salva.tem_certificado_associado is False
        assert empresa_salva.certificado_caminho is None
        assert empresa_salva.certificado_cnpj is None

        # Arquivo físico NÃO foi apagado
        assert pfx_path.exists() is True
        dlg_edicao2.destroy()

    def test_preenchimento_novo_cadastro_via_certificado(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Testa o botão 'Preencher dados via Certificado A1' no cadastro de nova empresa."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        pfx_path = tmp_path / "cert_novo.pfx"
        gerar_pkcs12_sintetico(
            pfx_path,
            senha="123",
            cnpj="12ABC345000188",
            nome_empresarial="NOVA EMPRESA IMPORTADA LTDA",
        )

        dlg = CompanyDialog(
            parent=app,
            repository=repo,
            on_success=MagicMock(),
        )

        with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
            with patch("tkinter.simpledialog.askstring", return_value="123"):
                dlg._importar_dados_de_certificado()

        # Aguarda término no executor determinístico e processa eventos do Tkinter
        dlg._executor.shutdown(wait=True)
        for _ in range(50):
            if not dlg._processando:
                break
            app.update_idletasks()
            app.update()

        assert dlg.txt_cnpj.get() == "12.ABC.345/0001-88"
        assert dlg.txt_razao.get() == "NOVA EMPRESA IMPORTADA LTDA"

        dlg.destroy()

    def test_company_dialog_processamento_assincrono_e_duplo_clique(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Comprova que CompanyDialog executa inspeção em background e bloqueia duplo clique."""
        pfx_path = tmp_path / "cert_async.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="12ABC345000188")

        dlg = CompanyDialog(parent=app, repository=repo, on_success=MagicMock())
        dlg.update_idletasks()
        dlg.update()

        with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
            with patch("tkinter.simpledialog.askstring", return_value="123"):
                dlg._importar_dados_de_certificado()

        # Durante o processamento
        assert dlg._processando is True
        assert dlg.btn_importar_cert.cget("state") == "disabled"
        assert "Inspecionando..." in dlg.btn_importar_cert.cget("text")
        # Garante ausência de atributo persistente de senha
        assert not hasattr(dlg, "senha")

        # Tenta disparar segundo clique imediatamente (deve ser ignorado)
        dlg._importar_dados_de_certificado()

        # Conclui execução da thread
        dlg._executor.shutdown(wait=True)
        for _ in range(50):
            if not dlg._processando:
                break
            app.update_idletasks()
            app.update()

        assert dlg._processando is False
        assert dlg.btn_importar_cert.cget("state") == "normal"
        assert "Preencher dados via Certificado A1..." in dlg.btn_importar_cert.cget("text")
        dlg.destroy()

    def test_company_dialog_fechamento_durante_processamento(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Comprova que fechar a janela durante o processamento do worker não quebra a UI."""
        pfx_path = tmp_path / "cert_fechamento.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="12ABC345000188")

        dlg = CompanyDialog(parent=app, repository=repo, on_success=MagicMock())
        dlg.update_idletasks()
        dlg.update()

        with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
            with patch("tkinter.simpledialog.askstring", return_value="123"):
                dlg._importar_dados_de_certificado()

        # Fecha janela imediatamente enquanto worker está em execução
        dlg.destroy()

        # Finaliza o worker
        dlg._executor.shutdown(wait=True)
        app.update_idletasks()
        app.update()

    def test_company_dialog_deteccao_empresa_existente(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Verifica que a detecção de CNPJ já existente funciona e pergunta antes de reutilizar."""
        empresa_existente = repo.listar_todas()[0]  # CNPJ: 00000000000191
        pfx_path = tmp_path / "cert_existente.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")

        callback_sucesso = MagicMock()
        dlg = CompanyDialog(parent=app, repository=repo, on_success=callback_sucesso)

        # 1. Usuário aceita selecionar empresa existente
        # O patch de askyesno deve cobrir todo o ciclo de vida: a chamada real acontece
        # em _processar_resultado_importacao (callback via Tk after), não durante
        # _importar_dados_de_certificado.
        with patch("tkinter.messagebox.askyesno", return_value=True):
            with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
                with patch("tkinter.simpledialog.askstring", return_value="123"):
                    dlg._importar_dados_de_certificado()

            dlg._executor.shutdown(wait=True)
            for _ in range(50):
                if not dlg._processando:
                    break
                app.update_idletasks()
                app.update()

        callback_sucesso.assert_called_once_with(empresa_existente)

    def test_excecao_com_texto_sensivel_simulado_nao_aparece_no_retorno_visual(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Comprova que falhas inesperadas com strings confidenciais/OpenSSL não vazam na UI."""
        import time

        texto_sensivel_secreto = "OPENSSL_CORE_DUMP_SECRET_KEY_SENHA_123456"

        # 1. Teste no CertificateDialog
        pfx_path = tmp_path / "cert_leak_test.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123")

        dlg_cert = CertificateDialog(
            parent=app,
            empresa=repo.listar_todas()[0],
            associacao_service=CertificadoAssociacaoService(repository=repo),
            on_success=MagicMock(),
            caminho_inicial=pfx_path,
        )
        dlg_cert.txt_senha.insert(0, "123")

        with patch.object(
            dlg_cert._inspector.cert_service,
            "inspecionar",
            side_effect=RuntimeError(texto_sensivel_secreto),
        ):
            dlg_cert._iniciar_inspecao()
            # Bombeamos o loop Tk sem shutdown(wait=True) para permitir que os
            # callbacks after() disparem naturalmente na thread principal.
            for _ in range(200):
                time.sleep(0.01)
                app.update_idletasks()
                app.update()
                if not dlg_cert._processando:
                    break

        texto_exibido_cert = dlg_cert.lbl_feedback.cget("text")
        assert texto_sensivel_secreto not in texto_exibido_cert
        assert texto_exibido_cert == MSG_ERRO_GENERICO_CERTIFICADO
        dlg_cert.destroy()

        # 2. Teste no CompanyDialog
        dlg_comp = CompanyDialog(parent=app, repository=repo, on_success=MagicMock())
        with patch.object(
            dlg_comp._inspector.cert_service,
            "inspecionar",
            side_effect=RuntimeError(texto_sensivel_secreto),
        ):
            with patch("tkinter.messagebox.showerror") as mock_msg:
                with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
                    with patch("tkinter.simpledialog.askstring", return_value="123"):
                        dlg_comp._importar_dados_de_certificado()

                # Bombeamos o loop Tk para que o callback after() dispare e
                # processe o resultado (incluindo a chamada a showerror).
                for _ in range(200):
                    time.sleep(0.01)
                    app.update_idletasks()
                    app.update()
                    if not dlg_comp._processando:
                        break

                assert mock_msg.called
                _, args_msg, _ = mock_msg.mock_calls[0]
                mensagem_popup = args_msg[1]
                assert texto_sensivel_secreto not in mensagem_popup
                assert mensagem_popup == MSG_ERRO_GENERICO_CERTIFICADO
                assert texto_sensivel_secreto not in dlg_comp.lbl_erro.cget("text")
        dlg_comp.destroy()

    def test_dialogo_info_exibe_metadados(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Verifica exibição do modal somente-leitura com informações do certificado."""
        app.repository = repo
        app.company_list.repository = repo
        app.associacao_service = CertificadoAssociacaoService(repository=repo)
        app.company_list.carregar_empresas()
        app.update_idletasks()
        app.update()

        pfx_path = tmp_path / "cert_info.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123", cnpj="00000000000191")
        info = app.associacao_service.cert_service.inspecionar(pfx_path, "123")
        empresa = app.associacao_service.associar(repo.listar_todas()[0], info)

        dlg = CertificateInfoDialog(parent=app, empresa=empresa)
        dlg.update_idletasks()
        dlg.update()
        assert "Informações do Certificado" in dlg.title()
        dlg.destroy()

    def test_certificado_error_higienizado_nao_vaza_causa_original_na_ui(
        self, app: MainWindow, repo: InMemoryEmpresaRepository, tmp_path: Path
    ) -> None:
        """Comprova que um CertificadoError já sanitizado chega ao callback visual sem
        revelar o marcador confidencial da exceção original encadeada em __cause__.

        Verifica ausência do marcador em:
        1. Texto retornado pelo AsyncCertificateInspector
        2. Label de feedback do CertificateDialog
        3. messagebox.showerror do CompanyDialog
        """
        import time
        from nfse_facil.domain.exceptions import CertificadoNaoEncontradoError

        marcador_confidencial = "OPENSSL_INTERNAL_SECRET_KEY_LEAK_12345"
        mensagem_publica = "Não foi possível acessar o arquivo de certificado."

        pfx_path = tmp_path / "cert_causa.pfx"
        gerar_pkcs12_sintetico(pfx_path, senha="123")

        # Cria a exceção higienizada com causa encadeada contendo o marcador
        def inspecionar_com_causa_encadeada(*_args, **_kwargs):
            try:
                raise OSError(marcador_confidencial)
            except OSError as causa:
                raise CertificadoNaoEncontradoError(mensagem_publica) from causa

        # --- 1. CertificateDialog: verifica label de feedback ---
        dlg_cert = CertificateDialog(
            parent=app,
            empresa=repo.listar_todas()[0],
            associacao_service=CertificadoAssociacaoService(repository=repo),
            on_success=MagicMock(),
            caminho_inicial=pfx_path,
        )
        dlg_cert.txt_senha.insert(0, "123")

        with patch.object(
            dlg_cert._inspector.cert_service,
            "inspecionar",
            side_effect=inspecionar_com_causa_encadeada,
        ):
            dlg_cert._iniciar_inspecao()
            for _ in range(200):
                time.sleep(0.01)
                app.update_idletasks()
                app.update()
                if not dlg_cert._processando:
                    break

        texto_feedback = dlg_cert.lbl_feedback.cget("text")
        # O texto público deve conter a mensagem sanitizada
        assert mensagem_publica in texto_feedback
        # O marcador confidencial NÃO deve aparecer na label
        assert marcador_confidencial not in texto_feedback
        dlg_cert.destroy()

        # --- 2. CompanyDialog: verifica showerror ---
        dlg_comp = CompanyDialog(parent=app, repository=repo, on_success=MagicMock())

        with patch.object(
            dlg_comp._inspector.cert_service,
            "inspecionar",
            side_effect=inspecionar_com_causa_encadeada,
        ):
            with patch("tkinter.messagebox.showerror") as mock_showerror:
                with patch("tkinter.filedialog.askopenfilename", return_value=str(pfx_path)):
                    with patch("tkinter.simpledialog.askstring", return_value="123"):
                        dlg_comp._importar_dados_de_certificado()

                for _ in range(200):
                    time.sleep(0.01)
                    app.update_idletasks()
                    app.update()
                    if not dlg_comp._processando:
                        break

                # Verifica que showerror foi chamado
                assert mock_showerror.called
                _, args_popup, _ = mock_showerror.mock_calls[0]
                texto_popup = args_popup[1]
                assert marcador_confidencial not in texto_popup
                assert mensagem_publica in texto_popup

                # O marcador também não deve aparecer na label de erro
                assert marcador_confidencial not in dlg_comp.lbl_erro.cget("text")
        dlg_comp.destroy()

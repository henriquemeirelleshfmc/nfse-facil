"""Janela principal da aplicação NFS-e Fácil desenvolvida em CustomTkinter."""

from pathlib import Path
from tkinter import messagebox
import webbrowser
import customtkinter as ctk

from nfse_facil.config.contact import SUPPORT_HANDLE, SUPPORT_URL
from nfse_facil.config.settings import get_settings
from nfse_facil.domain.models import Empresa, PreferenciasDownload
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.services.associacao_certificado import CertificadoAssociacaoService
from nfse_facil.ui.components.certificate_dialog import CertificateDialog, CertificateInfoDialog
from nfse_facil.ui.components.company_dialog import CompanyDialog
from nfse_facil.ui.components.company_list import CompanyList
from nfse_facil.ui.components.download_dialog import DownloadDialog
from nfse_facil.ui.components.period_selector import PeriodSelector
from nfse_facil.ui.messages import TITULO_AVISO_DOWNLOAD, obter_mensagem_aviso_download
from nfse_facil.ui.theme import (
    COLOR_BG_DARK,
    COLOR_BG_LIGHT,
    COLOR_CARD_DARK,
    COLOR_CARD_LIGHT,
    COLOR_DANGER,
    COLOR_NAV,
    COLOR_NAV_HOVER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_SOFT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_SOFT,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_DISPLAY,
    FONT_LARGE_BUTTON,
    FONT_SUBTITLE,
    FONT_TITLE,
)


class MainWindow(ctk.CTk):
    """Janela principal com navegação entre empresas, períodos e opções de download."""

    def __init__(self, repository: EmpresaRepository) -> None:
        super().__init__()
        self.repository = repository
        self.settings = get_settings()
        self.associacao_service = CertificadoAssociacaoService(repository=self.repository)

        self._empresa_ativa: Empresa | None = None

        # Configurações gerais da janela
        self.title("NFS-e Fácil")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))

        # Configuração do Grid principal (2 colunas: barra lateral e painel principal)
        self.grid_columnconfigure(0, weight=0, minsize=292)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_main_panel()
        self._build_sidebar()

    def _build_sidebar(self) -> None:
        """Constrói a barra lateral para gestão de empresas."""
        self.sidebar_frame = ctk.CTkFrame(
            self, corner_radius=0, width=292, fg_color=COLOR_NAV
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_propagate(False)

        # Cabeçalho do App
        lbl_logo = ctk.CTkLabel(
            self.sidebar_frame,
            text="▣  NFS-e Fácil",
            font=FONT_TITLE,
            anchor="w",
            text_color="#FFFFFF",
        )
        lbl_logo.pack(fill="x", padx=16, pady=(16, 4))

        lbl_sub = ctk.CTkLabel(
            self.sidebar_frame,
            text="Gestão simples de notas fiscais",
            font=FONT_CAPTION,
            text_color="#91A2C8",
            anchor="w",
        )
        lbl_sub.pack(fill="x", padx=16, pady=(0, 14))

        # Divisor
        divisor = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#294174")
        divisor.pack(fill="x", padx=16, pady=(0, 12))

        # Título da seção e botão Adicionar
        header_empresas = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        header_empresas.pack(fill="x", padx=16, pady=(0, 8))

        lbl_secao = ctk.CTkLabel(
            header_empresas,
            text="Minhas empresas",
            font=FONT_SUBTITLE,
            anchor="w",
            text_color="#DCE6FF",
        )
        lbl_secao.pack(side="left")

        self.btn_adicionar = ctk.CTkButton(
            self.sidebar_frame,
            text="+ Adicionar empresa",
            font=FONT_BODY_BOLD,
            height=36,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=10,
            command=self._abrir_dialogo_adicionar_empresa,
        )
        self.btn_adicionar.pack(fill="x", padx=16, pady=(0, 12))

        # Lista interativa de empresas
        self.company_list = CompanyList(
            self.sidebar_frame,
            repository=self.repository,
            on_company_selected=self._on_empresa_selecionada,
        )
        self.company_list.pack(fill="both", expand=True, padx=4, pady=(0, 12))

        contato = ctk.CTkFrame(
            self.sidebar_frame, corner_radius=10, fg_color="#101F43"
        )
        contato.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(
            contato, text="PRECISA DE AJUDA?", font=FONT_CAPTION,
            text_color="#91A2C8", anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 0))
        self.btn_contato = ctk.CTkButton(
            contato,
            text=f"Instagram  {SUPPORT_HANDLE}",
            font=FONT_CAPTION,
            height=30,
            anchor="w",
            fg_color="transparent",
            hover_color=COLOR_NAV_HOVER,
            text_color="#DCE6FF",
            command=lambda: webbrowser.open_new_tab(SUPPORT_URL),
        )
        self.btn_contato.pack(fill="x", padx=4, pady=(2, 5))

    def _build_main_panel(self) -> None:
        """Constrói o painel de conteúdo e ação principal."""
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)

        self.header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header.pack(fill="x", pady=(0, 18))
        self.lbl_header_titulo = ctk.CTkLabel(
            self.header, text="Visão geral", font=FONT_DISPLAY, anchor="w"
        )
        self.lbl_header_titulo.pack(anchor="w")
        self.lbl_header_subtitulo = ctk.CTkLabel(
            self.header,
            text="Selecione uma empresa e mantenha suas notas organizadas em poucos passos.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.lbl_header_subtitulo.pack(anchor="w", pady=(3, 0))

        # Mensagem de estado vazio quando nenhuma empresa estiver cadastrada
        self.frame_boas_vindas = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=("#E6ECF5", "#263653"),
        )

        lbl_bv_icone = ctk.CTkLabel(self.frame_boas_vindas, text="👋", font=("Segoe UI", 48))
        lbl_bv_icone.pack(pady=(40, 10))

        lbl_bv_titulo = ctk.CTkLabel(
            self.frame_boas_vindas,
            text="Bem-vindo ao NFS-e Fácil!",
            font=FONT_TITLE,
        )
        lbl_bv_titulo.pack(pady=(0, 8))

        lbl_bv_desc = ctk.CTkLabel(
            self.frame_boas_vindas,
            text="O aplicativo foi criado para tornar o download e a organização de notas\n"
            "fiscais de serviço uma tarefa simples, rápida e sem complicação.\n\n"
            "Para começar, clique no botão '+ Adicionar empresa' no menu à esquerda.",
            font=FONT_BODY,
            justify="center",
            text_color=("gray40", "gray70"),
        )
        lbl_bv_desc.pack(pady=(0, 24))

        btn_bv_add = ctk.CTkButton(
            self.frame_boas_vindas,
            text="+ Adicionar minha primeira empresa",
            font=FONT_BODY_BOLD,
            height=40,
            width=260,
            command=self._abrir_dialogo_adicionar_empresa,
        )
        btn_bv_add.pack(pady=(0, 40))

        # Container operacional (exibido quando uma empresa está selecionada)
        self.frame_operacional = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        # Cartão 1: Informações da Empresa Selecionada
        self.card_empresa = ctk.CTkFrame(
            self.frame_operacional,
            corner_radius=16,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=("#E6ECF5", "#263653"),
        )
        self.card_empresa.pack(fill="x", pady=(0, 16))

        self.lbl_card_titulo = ctk.CTkLabel(
            self.card_empresa,
            text="EMPRESA SELECIONADA",
            font=FONT_CAPTION,
            text_color=("gray50", "gray70"),
            anchor="w",
        )
        self.lbl_card_titulo.pack(fill="x", padx=16, pady=(12, 2))

        self.lbl_card_nome = ctk.CTkLabel(
            self.card_empresa,
            text="",
            font=FONT_TITLE,
            anchor="w",
        )
        self.lbl_card_nome.pack(fill="x", padx=16, pady=(0, 2))

        self.lbl_card_cnpj = ctk.CTkLabel(
            self.card_empresa,
            text="",
            font=FONT_BODY_BOLD,
            text_color=("gray30", "gray80"),
            anchor="w",
        )
        self.lbl_card_cnpj.pack(fill="x", padx=16, pady=(0, 4))

        self.lbl_card_pasta = ctk.CTkLabel(
            self.card_empresa,
            text="",
            font=FONT_CAPTION,
            text_color=("gray40", "gray60"),
            anchor="w",
        )
        self.lbl_card_pasta.pack(fill="x", padx=16, pady=(0, 10))

        self.frame_indicadores = ctk.CTkFrame(self.card_empresa, fg_color="transparent")
        self.frame_indicadores.pack(fill="x", padx=16, pady=(4, 12))
        self.frame_indicadores.grid_columnconfigure((0, 1), weight=1)

        self.card_indicador_sync = ctk.CTkFrame(
            self.frame_indicadores, corner_radius=12, fg_color=COLOR_PRIMARY_SOFT
        )
        self.card_indicador_sync.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(
            self.card_indicador_sync, text="SINCRONIZAÇÃO", font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED, anchor="w"
        ).pack(fill="x", padx=12, pady=(10, 1))
        self.lbl_indicador_sync = ctk.CTkLabel(
            self.card_indicador_sync, text="Pronta para começar", font=FONT_BODY_BOLD, anchor="w"
        )
        self.lbl_indicador_sync.pack(fill="x", padx=12, pady=(0, 10))

        self.card_indicador_cert = ctk.CTkFrame(
            self.frame_indicadores, corner_radius=12, fg_color=COLOR_SUCCESS_SOFT
        )
        self.card_indicador_cert.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            self.card_indicador_cert, text="CERTIFICADO", font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED, anchor="w"
        ).pack(fill="x", padx=12, pady=(10, 1))
        self.lbl_indicador_cert = ctk.CTkLabel(
            self.card_indicador_cert, text="Não configurado", font=FONT_BODY_BOLD, anchor="w"
        )
        self.lbl_indicador_cert.pack(fill="x", padx=12, pady=(0, 10))

        # Ações de Gestão da Empresa (Editar e Remover)
        self.frame_acoes_empresa = ctk.CTkFrame(self.card_empresa, fg_color="transparent")
        self.frame_acoes_empresa.pack(fill="x", padx=16, pady=(0, 12))

        self.btn_editar_empresa = ctk.CTkButton(
            self.frame_acoes_empresa,
            text="✏️ Editar empresa",
            font=FONT_BODY_BOLD,
            height=32,
            width=130,
            fg_color=("gray80", "gray30"),
            text_color=("gray10", "gray95"),
            hover_color=("gray70", "gray40"),
            command=self._abrir_dialogo_editar_empresa,
        )
        self.btn_editar_empresa.pack(side="left", padx=(0, 10))

        self.btn_remover_empresa = ctk.CTkButton(
            self.frame_acoes_empresa,
            text="🗑️ Remover cadastro",
            font=FONT_BODY_BOLD,
            height=32,
            width=140,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_DANGER,
            text_color=COLOR_DANGER,
            hover_color=("gray90", "gray25"),
            command=self._confirmar_remover_empresa,
        )
        self.btn_remover_empresa.pack(side="left")

        # Divisor interno
        ctk.CTkFrame(self.card_empresa, height=1, fg_color=("gray85", "gray30")).pack(
            fill="x", padx=16, pady=(10, 8)
        )

        # Seção de Certificado Digital A1
        self.lbl_cert_titulo = ctk.CTkLabel(
            self.card_empresa,
            text="CERTIFICADO DIGITAL A1",
            font=FONT_CAPTION,
            text_color=("gray50", "gray70"),
            anchor="w",
        )
        self.lbl_cert_titulo.pack(fill="x", padx=16, pady=(0, 2))

        self.lbl_cert_status = ctk.CTkLabel(
            self.card_empresa,
            text="Nenhum certificado associado",
            font=FONT_BODY_BOLD,
            anchor="w",
        )
        self.lbl_cert_status.pack(fill="x", padx=16, pady=(0, 8))

        self.frame_acoes_cert = ctk.CTkFrame(self.card_empresa, fg_color="transparent")
        self.frame_acoes_cert.pack(fill="x", padx=16, pady=(0, 12))

        self.btn_selecionar_cert = ctk.CTkButton(
            self.frame_acoes_cert,
            text="Selecionar certificado A1",
            font=FONT_BODY_BOLD,
            height=32,
            width=180,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._abrir_dialogo_selecionar_certificado,
        )
        self.btn_selecionar_cert.pack(side="left", padx=(0, 8))

        self.btn_info_cert = ctk.CTkButton(
            self.frame_acoes_cert,
            text="Ver informações",
            font=FONT_BODY_BOLD,
            height=32,
            width=130,
            fg_color=("gray80", "gray30"),
            text_color=("gray10", "gray95"),
            hover_color=("gray70", "gray40"),
            command=self._abrir_dialogo_info_certificado,
        )
        self.btn_info_cert.pack(side="left", padx=(0, 8))

        self.btn_remover_cert = ctk.CTkButton(
            self.frame_acoes_cert,
            text="Remover associação",
            font=FONT_BODY_BOLD,
            height=32,
            width=150,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_DANGER,
            text_color=COLOR_DANGER,
            hover_color=("gray90", "gray25"),
            command=self._confirmar_remover_certificado,
        )
        self.btn_remover_cert.pack(side="left")

        # Cartão 2: Seleção do Período
        self.card_periodo = ctk.CTkFrame(
            self.frame_operacional, corner_radius=16,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E6ECF5", "#263653")
        )
        self.card_periodo.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.card_periodo,
            text="1. ESCOLHA O PERÍODO",
            font=FONT_BODY_BOLD,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 10))

        self.period_selector = PeriodSelector(self.card_periodo)
        self.period_selector.pack(fill="x", padx=16, pady=(0, 14))

        # Cartão 3: Opções de Download e Relatórios
        self.card_opcoes = ctk.CTkFrame(
            self.frame_operacional, corner_radius=16,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E6ECF5", "#263653")
        )
        self.card_opcoes.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.card_opcoes,
            text="2. DOCUMENTOS E RELATÓRIOS DESEJADOS",
            font=FONT_BODY_BOLD,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 8))

        grid_chk = ctk.CTkFrame(self.card_opcoes, fg_color="transparent")
        grid_chk.pack(fill="x", padx=16, pady=(0, 14))

        self.var_emitidas = ctk.BooleanVar(value=True)
        self.chk_emitidas = ctk.CTkCheckBox(
            grid_chk,
            text="Notas emitidas (prestador)",
            variable=self.var_emitidas,
            font=FONT_BODY,
        )
        self.chk_emitidas.grid(row=0, column=0, sticky="w", padx=(0, 20), pady=6)

        self.var_recebidas = ctk.BooleanVar(value=True)
        self.chk_recebidas = ctk.CTkCheckBox(
            grid_chk,
            text="Notas recebidas (tomador)",
            variable=self.var_recebidas,
            font=FONT_BODY,
        )
        self.chk_recebidas.grid(row=0, column=1, sticky="w", pady=6)

        self.var_excel = ctk.BooleanVar(value=True)
        self.chk_excel = ctk.CTkCheckBox(
            grid_chk,
            text="Gerar relatório em Excel (.xlsx)",
            variable=self.var_excel,
            font=FONT_BODY,
        )
        self.chk_excel.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=6)

        self.var_pdf = ctk.BooleanVar(value=True)
        self.chk_pdf = ctk.CTkCheckBox(
            grid_chk,
            text="Gerar relatório em PDF (.pdf)",
            variable=self.var_pdf,
            font=FONT_BODY,
        )
        self.chk_pdf.grid(row=1, column=1, sticky="w", pady=6)

        # Cartão 4: Ação Principal
        self.card_acao = ctk.CTkFrame(
            self.frame_operacional, corner_radius=16,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E6ECF5", "#263653")
        )
        self.card_acao.pack(fill="x", pady=(0, 16))

        self.btn_baixar = ctk.CTkButton(
            self.card_acao,
            text="Buscar e organizar notas",
            font=FONT_LARGE_BUTTON,
            height=52,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=12,
            command=self._clicar_baixar_notas,
        )
        self.btn_baixar.pack(fill="x", padx=16, pady=(16, 8))

        self.lbl_status_acao = ctk.CTkLabel(
            self.card_acao,
            text="O programa organizará os arquivos e gerará os relatórios na pasta da empresa.",
            font=FONT_CAPTION,
            text_color=("gray50", "gray70"),
        )
        self.lbl_status_acao.pack(pady=(0, 16))

    def _abrir_dialogo_adicionar_empresa(self) -> None:
        """Abre o diálogo modal de cadastro de nova empresa."""
        CompanyDialog(
            parent=self,
            repository=self.repository,
            on_success=self._on_empresa_cadastrada_ou_editada,
        )

    def _abrir_dialogo_editar_empresa(self) -> None:
        """Abre o diálogo modal de edição da empresa atualmente selecionada."""
        if not self._empresa_ativa:
            return
        CompanyDialog(
            parent=self,
            repository=self.repository,
            on_success=self._on_empresa_cadastrada_ou_editada,
            empresa_edicao=self._empresa_ativa,
        )

    def _confirmar_remover_empresa(self) -> None:
        """Solicita confirmação explicativa e remove o cadastro da empresa no banco local."""
        if not self._empresa_ativa:
            return

        nome = self._empresa_ativa.nome_exibicao
        msg = (
            f"Tem certeza que deseja remover o cadastro da empresa '{nome}'?\n\n"
            "Apenas o cadastro no aplicativo será removido.\n"
            "A pasta e os arquivos de documentos da empresa NÃO serão apagados."
        )

        confirmado = messagebox.askyesno(
            title="Remover Cadastro de Empresa",
            message=msg,
            parent=self,
        )
        if not confirmado:
            return

        empresa_id = self._empresa_ativa.id
        try:
            self.repository.remover(empresa_id)
        except Exception as err:
            messagebox.showerror(
                title="Erro ao Remover Cadastro",
                message=f"Não foi possível remover o cadastro da empresa: {err}",
                parent=self,
            )
            return

        # Recarrega a lista de empresas (seleciona a próxima ou volta ao estado vazio)
        self.company_list.carregar_empresas()

    def _on_empresa_cadastrada_ou_editada(self, empresa: Empresa) -> None:
        """Callback acionado após cadastro ou edição bem-sucedida."""
        self.company_list.carregar_empresas(selecionar_id=empresa.id)

    def _on_empresa_selecionada(self, empresa: Empresa | None) -> None:
        """Atualiza o painel central de acordo com a empresa selecionada."""
        self._empresa_ativa = empresa
        if not hasattr(self, "frame_operacional") or not hasattr(self, "frame_boas_vindas"):
            return

        if empresa is None:
            self.lbl_header_titulo.configure(text="Visão geral")
            self.lbl_header_subtitulo.configure(
                text="Cadastre sua primeira empresa para começar com segurança."
            )
            self.frame_operacional.pack_forget()
            self.frame_boas_vindas.pack(fill="both", expand=True)
        else:
            self.frame_boas_vindas.pack_forget()
            self.lbl_header_titulo.configure(text="Olá! Vamos organizar suas notas?")
            self.lbl_header_subtitulo.configure(
                text=f"Você está trabalhando com {empresa.nome_exibicao}."
            )
            self.lbl_card_nome.configure(text=empresa.nome_exibicao)
            self.lbl_card_cnpj.configure(text=f"CNPJ: {empresa.cnpj_formatado}")
            self.lbl_card_pasta.configure(text=f"📁 Pasta: {empresa.pasta_documentos}")
            self.lbl_indicador_sync.configure(
                text=(
                    f"Último NSU: {empresa.ultimo_nsu_adn}"
                    if empresa.ultimo_nsu_adn
                    else "Ainda não sincronizada"
                )
            )
            self._atualizar_secao_certificado(empresa)
            self.frame_operacional.pack(fill="both", expand=True)

    def _atualizar_secao_certificado(self, empresa: Empresa) -> None:
        """Atualiza visualmente os badges e botões da seção de certificado digital."""
        codigo, rotulo = self.associacao_service.verificar_status_atual(empresa)

        if codigo == "nenhum":
            self.lbl_indicador_cert.configure(text="Não configurado", text_color=COLOR_WARNING)
            self.lbl_cert_status.configure(
                text="⚠️ Nenhum certificado digital associado",
                text_color=("gray40", "gray60"),
            )
            self.btn_selecionar_cert.configure(
                text="Selecionar certificado A1",
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER,
                text_color=("gray10", "gray95"),
            )
            self.btn_info_cert.pack_forget()
            self.btn_remover_cert.pack_forget()
        else:
            self.btn_selecionar_cert.configure(
                text="Trocar certificado",
                fg_color=("gray80", "gray30"),
                hover_color=("gray70", "gray40"),
                text_color=("gray10", "gray95"),
            )
            self.btn_info_cert.pack(side="left", padx=(0, 8))
            self.btn_remover_cert.pack(side="left")

            if codigo == "valido":
                self.lbl_indicador_cert.configure(text="Válido e pronto", text_color=COLOR_SUCCESS)
                data_fim = empresa.certificado_valido_ate.strftime("%d/%m/%Y") if empresa.certificado_valido_ate else ""
                self.lbl_cert_status.configure(
                    text=f"✓ Certificado válido (vence em {data_fim})",
                    text_color=COLOR_SUCCESS,
                )
            elif codigo == "proximo_do_vencimento":
                self.lbl_indicador_cert.configure(text="Vence em breve", text_color=COLOR_WARNING)
                data_fim = empresa.certificado_valido_ate.strftime("%d/%m/%Y") if empresa.certificado_valido_ate else ""
                self.lbl_cert_status.configure(
                    text=f"⚠️ Certificado vence em breve ({data_fim})",
                    text_color=COLOR_WARNING,
                )
            elif codigo == "vencido":
                self.lbl_indicador_cert.configure(text="Vencido", text_color=COLOR_DANGER)
                data_fim = empresa.certificado_valido_ate.strftime("%d/%m/%Y") if empresa.certificado_valido_ate else ""
                self.lbl_cert_status.configure(
                    text=f"❌ Certificado vencido em {data_fim}",
                    text_color=COLOR_DANGER,
                )
            elif codigo == "arquivo_nao_encontrado":
                self.lbl_indicador_cert.configure(text="Arquivo não encontrado", text_color=COLOR_DANGER)
                self.lbl_cert_status.configure(
                    text="⚠️ Arquivo do certificado não encontrado no caminho original",
                    text_color=COLOR_DANGER,
                )
            else:
                self.lbl_indicador_cert.configure(text=rotulo, text_color=COLOR_TEXT_MUTED)
                self.lbl_cert_status.configure(
                    text=f"ℹ️ {rotulo}",
                    text_color=("gray30", "gray70"),
                )

    def _abrir_dialogo_selecionar_certificado(self) -> None:
        """Abre o diálogo modal para seleção e inspeção de certificado A1."""
        if not self._empresa_ativa:
            return
        CertificateDialog(
            parent=self,
            empresa=self._empresa_ativa,
            associacao_service=self.associacao_service,
            on_success=self._on_certificado_atualizado,
        )

    def _abrir_dialogo_info_certificado(self) -> None:
        """Abre o modal com informações dos metadados gravados do certificado."""
        if not self._empresa_ativa:
            return
        CertificateInfoDialog(
            parent=self,
            empresa=self._empresa_ativa,
        )

    def _confirmar_remover_certificado(self) -> None:
        """Solicita confirmação do usuário e desassocia o certificado da empresa."""
        if not self._empresa_ativa:
            return

        nome = self._empresa_ativa.nome_exibicao
        msg = (
            f"Deseja remover a associação do certificado digital da empresa '{nome}'?\n\n"
            "Apenas os metadados de associação serão removidos do aplicativo.\n"
            "O arquivo físico do certificado (.pfx ou .p12) NÃO será apagado do seu computador."
        )
        confirmado = messagebox.askyesno(
            title="Remover Associação de Certificado",
            message=msg,
            parent=self,
        )
        if not confirmado:
            return

        try:
            empresa_atualizada = self.associacao_service.remover_associacao(self._empresa_ativa)
            self._on_certificado_atualizado(empresa_atualizada)
            messagebox.showinfo(
                "Associação Removida",
                "A associação do certificado com a empresa foi removida com sucesso.\n"
                "O arquivo original no disco permaneceu intacto.",
                parent=self,
            )
        except Exception as err:
            messagebox.showerror(
                "Erro ao Remover Associação",
                f"Não foi possível remover a associação do certificado: {err}",
                parent=self,
            )

    def _on_certificado_atualizado(self, empresa: Empresa) -> None:
        """Atualiza a empresa ativa e os componentes visuais após alteração de certificado."""
        self._empresa_ativa = empresa
        self._atualizar_secao_certificado(empresa)
        self.company_list.carregar_empresas(selecionar_id=empresa.id)

    def _clicar_baixar_notas(self) -> None:
        """Manipulador do botão Baixar Notas.

        CRÍTICO DA ETAPA 01:
        Não finge que baixou documentos. Informa com clareza a situação do projeto.
        """
        if not self._empresa_ativa:
            messagebox.showwarning(
                "Nenhuma Empresa Selecionada",
                "Selecione ou cadastre uma empresa antes de baixar notas.",
                parent=self,
            )
            return

        periodo = self.period_selector.obter_periodo()
        preferencias = PreferenciasDownload(
            baixar_emitidas=self.var_emitidas.get(),
            baixar_recebidas=self.var_recebidas.get(),
            gerar_excel=self.var_excel.get(),
            gerar_pdf=self.var_pdf.get(),
        )

        if not preferencias.tem_escopo_selecionado():
            messagebox.showwarning(
                "Opções de Download",
                "Por favor, selecione ao menos uma das opções: Notas emitidas ou Notas recebidas.",
                parent=self,
            )
            return

        if not self._empresa_ativa.certificado_caminho:
            messagebox.showwarning(
                "Certificado Necessário",
                "Selecione o certificado digital desta empresa antes de buscar notas.",
                parent=self,
            )
            return

        DownloadDialog(
            parent=self,
            repository=self.repository,
            empresa=self._empresa_ativa,
            periodo=periodo,
            preferencias=preferencias,
            on_success=self._on_sincronizacao_concluida,
        )

    def _on_sincronizacao_concluida(self, empresa: Empresa) -> None:
        """Atualiza a empresa ativa depois do avanço persistido do NSU."""
        self._empresa_ativa = empresa
        self.company_list.carregar_empresas(selecionar_id=empresa.id)

    def _exibir_modal_aviso_downloads(
        self,
        empresa: Empresa,
        periodo,
        preferencias: PreferenciasDownload,
    ) -> None:
        """Exibe modal informativo transparente comunicando o status do download."""
        janela_aviso = ctk.CTkToplevel(self)
        janela_aviso.title(TITULO_AVISO_DOWNLOAD)
        janela_aviso.geometry("520x380")
        janela_aviso.resizable(False, False)
        janela_aviso.transient(self)
        janela_aviso.grab_set()

        card = ctk.CTkFrame(janela_aviso, corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        lbl_icone = ctk.CTkLabel(card, text="ℹ️", font=("Segoe UI", 36))
        lbl_icone.pack(pady=(16, 4))

        lbl_titulo = ctk.CTkLabel(
            card,
            text=TITULO_AVISO_DOWNLOAD,
            font=FONT_SUBTITLE,
        )
        lbl_titulo.pack(pady=(0, 10))

        # Texto detalhado sem promessas obsoletas
        msg_texto = obter_mensagem_aviso_download(
            empresa.nome_exibicao,
            empresa.cnpj_formatado,
            periodo.rotulo_exibicao,
        )

        lbl_msg = ctk.CTkLabel(
            card,
            text=msg_texto,
            font=FONT_BODY,
            justify="left",
            wraplength=460,
        )
        lbl_msg.pack(padx=16, pady=(0, 20))

        btn_fechar = ctk.CTkButton(
            card,
            text="Entendido",
            font=FONT_BODY_BOLD,
            height=36,
            width=140,
            fg_color=COLOR_PRIMARY,
            command=janela_aviso.destroy,
        )
        btn_fechar.pack(pady=(0, 16))

    def destroy(self) -> None:
        """Libera callbacks e timers pendentes antes da destruição da janela principal."""
        try:
            for aid in list(self.tk.call("after", "info")):
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        except Exception:
            pass
        super().destroy()

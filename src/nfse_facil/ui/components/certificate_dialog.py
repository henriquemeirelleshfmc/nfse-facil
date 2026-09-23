"""Diálogos modais para inspeção e visualização de certificados digitais A1."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable
import customtkinter as ctk

from nfse_facil.domain.certificate_models import CertificadoInfo, StatusCertificado
from nfse_facil.domain.exceptions import CertificadoError, ValidacaoError
from nfse_facil.domain.models import Empresa
from nfse_facil.services.associacao_certificado import CertificadoAssociacaoService
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService
from nfse_facil.ui.components.async_certificate_inspector import AsyncCertificateInspector
from nfse_facil.ui.messages import MSG_ERRO_GENERICO_CERTIFICADO
from nfse_facil.ui.theme import (
    COLOR_BG_DARK,
    COLOR_BG_LIGHT,
    COLOR_CARD_DARK,
    COLOR_CARD_LIGHT,
    COLOR_DANGER,
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
    FONT_LARGE_BUTTON,
    FONT_SUBTITLE,
    FONT_TITLE,
)


class CertificateDialog(ctk.CTkToplevel):
    """Janela modal para seleção, inspeção e confirmação de associação de certificado A1."""

    def __init__(
        self,
        parent: ctk.CTk,
        empresa: Empresa,
        associacao_service: CertificadoAssociacaoService,
        on_success: Callable[[Empresa], None],
        cert_service: Pkcs12CertificadoService | None = None,
        caminho_inicial: Path | None = None,
    ) -> None:
        existing_afters = set()
        try:
            existing_afters = set(parent.tk.call("after", "info"))
        except Exception:
            pass

        super().__init__(parent)
        self.empresa = empresa
        self.associacao_service = associacao_service
        self.cert_service = cert_service or Pkcs12CertificadoService()
        self.on_success = on_success
        self.caminho_arquivo: Path | None = caminho_inicial

        try:
            self._my_after_ids = [
                aid for aid in self.tk.call("after", "info") if aid not in existing_afters
            ]
        except Exception:
            self._my_after_ids = []

        # Controlador de inspeção assíncrona em segundo plano
        self._inspector = AsyncCertificateInspector(self, self.cert_service)
        self._destruido = False
        self._abrir_seletor_id: str | None = None
        self._info_inspecionada: CertificadoInfo | None = None

        self.title("Certificado Digital A1 - NFS-e Fácil")
        self.geometry("620x700")
        self.minsize(540, 600)
        self.resizable(True, True)
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))

        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_fechar_janela)

        # Se nenhum caminho foi passado, abre o seletor logo após renderizar
        if self.caminho_arquivo is None:
            self._abrir_seletor_id = self.after(100, self._abrir_seletor_arquivo)

    @property
    def _processando(self) -> bool:
        """Compatibilidade para verificação do estado de processamento."""
        return self._inspector.processando

    @property
    def _executor(self):
        """Compatibilidade para acesso controlado ao executor em testes."""
        return self._inspector._executor

    def _on_fechar_janela(self) -> None:
        """Encerra com segurança o diálogo e o executor de tarefas."""
        self.destroy()

    def destroy(self) -> None:
        """Encerra o diálogo garantindo cancelamento de timers e liberação de recursos."""
        self._destruido = True
        try:
            self.grab_release()
        except Exception:
            pass
        if hasattr(self, "_my_after_ids"):
            for aid in self._my_after_ids:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        if getattr(self, "_abrir_seletor_id", None) is not None:
            try:
                self.after_cancel(self._abrir_seletor_id)
            except Exception:
                pass
            self._abrir_seletor_id = None
        if hasattr(self, "_inspector"):
            self._inspector.encerrar()
        super().destroy()

    def _build_ui(self) -> None:
        rodape = ctk.CTkFrame(
            self, corner_radius=14, fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E2E8F0", "#334155")
        )
        rodape.pack(fill="x", padx=20, pady=(10, 20), side="bottom")

        self.container = ctk.CTkScrollableFrame(
            self, corner_radius=18, fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E2E8F0", "#334155")
        )
        self.container.pack(fill="both", expand=True, padx=20, pady=(20, 0))

        # Cabeçalho
        ctk.CTkLabel(
            self.container, text="  CERTIFICADO DIGITAL  ", font=FONT_CAPTION,
            text_color=COLOR_PRIMARY, fg_color=COLOR_PRIMARY_SOFT,
            corner_radius=6, height=24,
        ).pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            self.container,
            text="Associar Certificado A1",
            font=FONT_TITLE,
        ).pack(anchor="w", padx=20, pady=(0, 4))

        ctk.CTkLabel(
            self.container,
            text=f"Empresa: {self.empresa.nome_exibicao} ({self.empresa.cnpj_formatado})",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 14))

        # Aviso de segurança explícito
        aviso_frame = ctk.CTkFrame(self.container, fg_color=COLOR_PRIMARY_SOFT, corner_radius=10)
        aviso_frame.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            aviso_frame,
            text="🔒 Segurança: A senha do certificado é usada apenas para esta inspeção\n"
            "e NUNCA será armazenada no banco de dados, em arquivos ou em registros.",
            font=FONT_CAPTION,
            justify="left",
        ).pack(padx=14, pady=10, anchor="w")

        # Seleção de Arquivo
        ctk.CTkLabel(self.container, text="Arquivo do Certificado (.pfx ou .p12) *", font=FONT_BODY_BOLD).pack(
            anchor="w", padx=20, pady=(0, 4)
        )

        frame_arq = ctk.CTkFrame(self.container, fg_color="transparent")
        frame_arq.pack(fill="x", padx=20, pady=(0, 14))

        self.txt_caminho = ctk.CTkEntry(
            frame_arq,
            placeholder_text="Selecione o arquivo .pfx ou .p12",
            height=42,
            state="readonly",
        )
        self.txt_caminho.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_procurar = ctk.CTkButton(
            frame_arq,
            text="Selecionar...",
            width=100,
            height=42,
            command=self._abrir_seletor_arquivo,
        )
        self.btn_procurar.pack(side="right")

        if self.caminho_arquivo:
            self._atualizar_caminho_visual(self.caminho_arquivo)

        # Campo de Senha
        ctk.CTkLabel(self.container, text="Senha do Certificado *", font=FONT_BODY_BOLD).pack(
            anchor="w", padx=20, pady=(0, 4)
        )

        self.txt_senha = ctk.CTkEntry(
            self.container,
            placeholder_text="Digite a senha do certificado",
            show="*",
            height=42,
        )
        self.txt_senha.pack(fill="x", padx=20, pady=(0, 6))

        # Checkboxes: Mostrar senha e Lembrar caminho
        frame_opcoes = ctk.CTkFrame(self.container, fg_color="transparent")
        frame_opcoes.pack(fill="x", padx=20, pady=(0, 14))

        self.var_mostrar_senha = ctk.BooleanVar(value=False)
        self.chk_mostrar_senha = ctk.CTkCheckBox(
            frame_opcoes,
            text="Mostrar senha",
            variable=self.var_mostrar_senha,
            command=self._alternar_mostrar_senha,
            font=FONT_CAPTION,
        )
        self.chk_mostrar_senha.pack(side="left", padx=(0, 16))

        self.var_lembrar_caminho = ctk.BooleanVar(value=True)
        self.chk_lembrar_caminho = ctk.CTkCheckBox(
            frame_opcoes,
            text="Lembrar caminho do arquivo (a senha NUNCA será salva)",
            variable=self.var_lembrar_caminho,
            font=FONT_CAPTION,
        )
        self.chk_lembrar_caminho.pack(side="left")

        # Botão Inspecionar
        self.btn_inspecionar = ctk.CTkButton(
            self.container,
            text="🔍 Inspecionar Certificado",
            font=FONT_BODY_BOLD,
            height=42,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._iniciar_inspecao,
        )
        self.btn_inspecionar.pack(fill="x", padx=20, pady=(0, 10))

        # Mensagem de status / erro
        self.lbl_feedback = ctk.CTkLabel(
            self.container,
            text="",
            font=FONT_CAPTION,
            wraplength=520,
            justify="left",
        )
        self.lbl_feedback.pack(fill="x", padx=20, pady=(0, 10))

        # Card de Resumo da Inspeção (oculto inicialmente)
        self.card_resumo = ctk.CTkFrame(self.container, fg_color=COLOR_SUCCESS_SOFT, corner_radius=10)

        self.lbl_resumo_cnpj = ctk.CTkLabel(self.card_resumo, text="", font=FONT_BODY_BOLD, anchor="w")
        self.lbl_resumo_cnpj.pack(fill="x", padx=14, pady=(10, 3))

        self.lbl_resumo_validade = ctk.CTkLabel(self.card_resumo, text="", font=FONT_CAPTION, anchor="w")
        self.lbl_resumo_validade.pack(fill="x", padx=14, pady=(0, 3))

        self.lbl_resumo_emissor = ctk.CTkLabel(self.card_resumo, text="", font=FONT_CAPTION, anchor="w")
        self.lbl_resumo_emissor.pack(fill="x", padx=14, pady=(0, 3))

        self.lbl_resumo_fp = ctk.CTkLabel(self.card_resumo, text="", font=FONT_CAPTION, anchor="w")
        self.lbl_resumo_fp.pack(fill="x", padx=14, pady=(0, 10))

        # Botão Confirmar Associação no rodapé
        self.btn_confirmar = ctk.CTkButton(
            rodape,
            text="✓ Confirmar e Associar",
            font=FONT_LARGE_BUTTON,
            height=42,
            fg_color=COLOR_SUCCESS,
            hover_color="#15803D",
            state="disabled",
            command=self._confirmar_associacao,
        )
        self.btn_confirmar.pack(side="right", fill="x", expand=True, padx=(8, 12), pady=12)
        ctk.CTkButton(
            rodape, text="Cancelar", width=110, height=42,
            fg_color="transparent", border_width=1,
            border_color=("#CBD5E1", "#475569"),
            text_color=("#334155", "#E2E8F0"), command=self.destroy,
        ).pack(side="left", padx=(12, 0), pady=12)

    def _alternar_mostrar_senha(self) -> None:
        """Alterna a máscara de exibição da senha digitada."""
        self.txt_senha.configure(show="" if self.var_mostrar_senha.get() else "*")

    def _abrir_seletor_arquivo(self) -> None:
        """Abre a caixa de diálogo para seleção de arquivo .pfx ou .p12."""
        caminho_escolhido = filedialog.askopenfilename(
            parent=self,
            title="Selecione o Certificado Digital A1",
            filetypes=[("Certificado Digital A1 (*.pfx; *.p12)", "*.pfx;*.p12"), ("Todos os arquivos", "*.*")],
        )
        if caminho_escolhido:
            self.caminho_arquivo = Path(caminho_escolhido)
            self._atualizar_caminho_visual(self.caminho_arquivo)
            self._ocultar_resumo()

    def _atualizar_caminho_visual(self, caminho: Path) -> None:
        """Atualiza o campo visual de caminho do arquivo."""
        self.txt_caminho.configure(state="normal")
        self.txt_caminho.delete(0, "end")
        self.txt_caminho.insert(0, str(caminho))
        self.txt_caminho.configure(state="readonly")

    def _ocultar_resumo(self) -> None:
        """Oculta o cartão de resumo e desativa a confirmação."""
        self.card_resumo.pack_forget()
        self.btn_confirmar.configure(state="disabled")
        self._info_inspecionada = None

    def _iniciar_inspecao(self) -> None:
        """Inicia a inspeção do certificado em segundo plano mantendo a interface responsiva."""
        if self._inspector.processando:
            return

        if not self.caminho_arquivo:
            self.lbl_feedback.configure(
                text="Por favor, selecione um arquivo de certificado (.pfx ou .p12).",
                text_color=COLOR_DANGER,
            )
            return

        senha_informada = self.txt_senha.get()

        # Limpeza visual imediata do campo de senha
        self.txt_senha.delete(0, "end")

        # Bloqueio de novos cliques e indicação de carregamento
        self.btn_inspecionar.configure(state="disabled", text="⏳ Inspecionando...")
        self.lbl_feedback.configure(text="Lendo e inspecionando certificado...", text_color=("gray40", "gray70"))
        self._ocultar_resumo()

        self._inspector.iniciar(
            caminho=self.caminho_arquivo,
            senha=senha_informada,
            on_resultado=self._processar_resultado_inspecao,
        )
        del senha_informada

    def _processar_resultado_inspecao(self, info: CertificadoInfo | None, erro: str | None) -> None:
        """Processa o resultado da inspeção exclusivamente na thread principal do CustomTkinter."""
        if self._destruido:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.btn_inspecionar.configure(state="normal", text="🔍 Inspecionar Certificado")

        # Garante limpeza adicional do campo de senha
        self.txt_senha.delete(0, "end")

        if erro or info is None:
            self.lbl_feedback.configure(text=erro or MSG_ERRO_GENERICO_CERTIFICADO, text_color=COLOR_DANGER)
            self._ocultar_resumo()
            return

        self._info_inspecionada = info

        # Exibe dados resumidos
        self.lbl_resumo_cnpj.configure(
            text=f"CNPJ do Titular: {info.cnpj_formatado}"
            + (f" ({info.nome_empresarial})" if info.nome_empresarial else "")
        )
        self.lbl_resumo_validade.configure(
            text=f"Validade: {info.valido_de_formatado} até {info.valido_ate_formatado}"
        )
        self.lbl_resumo_emissor.configure(text=f"Emissor: {info.emissor or 'Não identificado'}")
        self.lbl_resumo_fp.configure(text=f"Fingerprint SHA-256: {info.fingerprint_resumida}")

        self.card_resumo.pack(fill="x", padx=16, pady=(4, 10))

        # Avaliação de compatibilidade e regras para associação
        try:
            self.cert_service.validar_para_associacao(info, self.empresa)
            if info.status_temporal == StatusCertificado.PROXIMO_DO_VENCIMENTO:
                self.lbl_feedback.configure(
                    text=f"⚠️ Atenção: Certificado válido, mas próximo do vencimento ({info.dias_restantes} dias restantes).",
                    text_color=COLOR_WARNING,
                )
            else:
                self.lbl_feedback.configure(
                    text="✓ Certificado compatível e válido para uso.",
                    text_color=COLOR_SUCCESS,
                )
            self.btn_confirmar.configure(state="normal")
        except CertificadoError as valid_err:
            self.lbl_feedback.configure(text=str(valid_err), text_color=COLOR_DANGER)
            self.btn_confirmar.configure(state="disabled")

    def _confirmar_associacao(self) -> None:
        """Aplica a associação utilizando o CertificadoAssociacaoService."""
        if not self._info_inspecionada:
            return

        lembrar_caminho = self.var_lembrar_caminho.get()
        try:
            empresa_atualizada = self.associacao_service.associar(
                empresa=self.empresa,
                info=self._info_inspecionada,
                lembrar_caminho=lembrar_caminho,
            )
            messagebox.showinfo(
                "Certificado Associado",
                f"O certificado foi associado com sucesso à empresa '{empresa_atualizada.nome_exibicao}'.",
                parent=self,
            )
            self.on_success(empresa_atualizada)
            self._on_fechar_janela()
        except (CertificadoError, ValidacaoError) as err:
            messagebox.showerror(
                "Erro na Associação",
                str(err),
                parent=self,
            )
        except Exception:
            messagebox.showerror(
                "Erro na Associação",
                MSG_ERRO_GENERICO_CERTIFICADO,
                parent=self,
            )


class CertificateInfoDialog(ctk.CTkToplevel):
    """Janela modal para exibição dos metadados gravados do certificado de uma empresa."""

    def __init__(self, parent: ctk.CTk, empresa: Empresa) -> None:
        existing_afters = set()
        try:
            existing_afters = set(parent.tk.call("after", "info"))
        except Exception:
            pass

        super().__init__(parent)
        self.empresa = empresa

        try:
            self._my_after_ids = [
                aid for aid in self.tk.call("after", "info") if aid not in existing_afters
            ]
        except Exception:
            self._my_after_ids = []

        self.title("Informações do Certificado A1")
        self.geometry("600x590")
        self.minsize(540, 520)
        self.resizable(True, True)
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        self._build_ui()

    def destroy(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        if hasattr(self, "_my_after_ids"):
            for aid in self._my_after_ids:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        super().destroy()

    def _build_ui(self) -> None:
        rodape = ctk.CTkFrame(
            self, corner_radius=14, fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E2E8F0", "#334155")
        )
        rodape.pack(fill="x", padx=20, pady=(10, 20), side="bottom")
        container = ctk.CTkScrollableFrame(
            self, corner_radius=18, fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1, border_color=("#E2E8F0", "#334155")
        )
        container.pack(fill="both", expand=True, padx=20, pady=(20, 0))

        ctk.CTkLabel(
            container, text="  CERTIFICADO ASSOCIADO  ", font=FONT_CAPTION,
            text_color=COLOR_SUCCESS, fg_color=COLOR_SUCCESS_SOFT,
            corner_radius=6, height=24,
        ).pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            container,
            text="Metadados do Certificado A1",
            font=FONT_TITLE,
        ).pack(anchor="w", padx=20, pady=(0, 4))

        ctk.CTkLabel(
            container,
            text=f"Empresa: {self.empresa.nome_exibicao}",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            wraplength=510,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 16))

        card = ctk.CTkFrame(container, fg_color=("#F8FAFC", "#162033"), corner_radius=12)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        def add_item(rotulo: str, valor: str) -> None:
            ctk.CTkLabel(card, text=rotulo.upper(), font=FONT_CAPTION, text_color=COLOR_TEXT_MUTED).pack(
                anchor="w", padx=16, pady=(12, 1)
            )
            ctk.CTkLabel(
                card, text=valor, font=FONT_BODY_BOLD, anchor="w",
                justify="left", wraplength=490,
            ).pack(
                anchor="w", padx=16, pady=(0, 4)
            )

        add_item("CNPJ do Certificado:", self.empresa.certificado_cnpj_formatado or "Não registrado")

        fp = self.empresa.certificado_fingerprint_sha256
        add_item("Fingerprint SHA-256:", fp if fp else "Não registrada")

        val_de = (
            self.empresa.certificado_valido_de.strftime("%d/%m/%Y %H:%M:%S UTC")
            if self.empresa.certificado_valido_de
            else "Não registrado"
        )
        val_ate = (
            self.empresa.certificado_valido_ate.strftime("%d/%m/%Y %H:%M:%S UTC")
            if self.empresa.certificado_valido_ate
            else "Não registrado"
        )
        add_item("Validade:", f"{val_de} até {val_ate}")

        verif_em = (
            self.empresa.certificado_verificado_em.strftime("%d/%m/%Y %H:%M:%S UTC")
            if self.empresa.certificado_verificado_em
            else "Não registrado"
        )
        add_item("Verificado em:", verif_em)

        cam = (
            str(self.empresa.certificado_caminho)
            if self.empresa.certificado_caminho
            else "Caminho não lembrado pelo usuário"
        )
        add_item("Arquivo de Origem:", cam)

        ctk.CTkButton(
            rodape,
            text="Fechar",
            height=42,
            font=FONT_BODY_BOLD,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self.destroy,
        ).pack(fill="x", padx=12, pady=12)

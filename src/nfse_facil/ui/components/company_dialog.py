"""Diálogo para cadastro e edição de empresas na interface gráfica."""

from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Callable
import customtkinter as ctk

from nfse_facil.config.settings import get_settings
from nfse_facil.domain.exceptions import (
    CNPJDuplicadoError,
    CNPJInvalidoError,
    CertificadoError,
    PastaInvalidaError,
    PersistenciaError,
    ValidacaoError,
)
from nfse_facil.domain.certificate_models import CertificadoInfo
from nfse_facil.domain.models import Empresa
from nfse_facil.domain.validators import formatar_cnpj, validar_ou_falhar_cnpj
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.services.pasta_documentos import PastaDocumentosService
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService
from nfse_facil.ui.components.async_certificate_inspector import AsyncCertificateInspector
from nfse_facil.ui.messages import MSG_ERRO_GENERICO_CERTIFICADO, MSG_SEGURANCA_CERTIFICADO
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
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_LARGE_BUTTON,
    FONT_SUBTITLE,
    FONT_TITLE,
)


class CompanyDialog(ctk.CTkToplevel):
    """Janela modal para cadastro ou edição de empresa."""

    def __init__(
        self,
        parent: ctk.CTk,
        repository: EmpresaRepository,
        on_success: Callable[[Empresa], None],
        empresa_edicao: Empresa | None = None,
    ) -> None:
        existing_afters = set()
        try:
            existing_afters = set(parent.tk.call("after", "info"))
        except Exception:
            pass

        super().__init__(parent)
        self.repository = repository
        self.on_success = on_success
        self.empresa_edicao = empresa_edicao
        self.settings = get_settings()

        try:
            self._my_after_ids = [
                aid for aid in self.tk.call("after", "info") if aid not in existing_afters
            ]
        except Exception:
            self._my_after_ids = []

        modo_texto = "Editar Empresa" if empresa_edicao else "Adicionar Empresa"
        self.title(f"{modo_texto} - NFS-e Fácil")
        self.geometry("620x680")
        self.minsize(520, 520)
        self.resizable(True, True)
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))

        # Configura como janela modal
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        # Controlador assíncrono para leitura do certificado sem congelar a UI
        self._inspector = AsyncCertificateInspector(self)
        self._destruido = False

        self._build_ui()
        self.lift()
        self.focus_force()
        self.update_idletasks()

    @property
    def _processando(self) -> bool:
        """Indica se a importação assíncrona está em andamento."""
        return self._inspector.processando

    @property
    def _executor(self):
        """Acesso controlado ao executor para sincronização determinística em testes."""
        return self._inspector._executor

    def destroy(self) -> None:
        """Libera o foco modal e cancela timers pendentes antes da destruição da janela."""
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
        if hasattr(self, "_inspector"):
            self._inspector.encerrar()
        super().destroy()

    def _build_ui(self) -> None:
        # Rodapé fixo: permanece acessível mesmo com escala de tela ou fonte ampliada.
        botoes_frame = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        botoes_frame.pack(fill="x", padx=20, pady=(10, 20), side="bottom")
        self.footer_actions = botoes_frame

        # O formulário é rolável; apenas o conteúdo central se desloca.
        container = ctk.CTkScrollableFrame(
            self,
            corner_radius=18,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        container.pack(fill="both", expand=True, padx=20, pady=(20, 0))
        self.form_scroll = container

        # Cabeçalho
        titulo_texto = "Edição de Empresa" if self.empresa_edicao else "Cadastro de Empresa"
        subtitulo_texto = (
            "Atualize as informações da empresa selecionada."
            if self.empresa_edicao
            else "Preencha os dados da empresa para gerenciar suas notas fiscais."
        )

        ctk.CTkLabel(
            container,
            text="  EMPRESA  ",
            font=FONT_CAPTION,
            text_color=COLOR_PRIMARY,
            fg_color=COLOR_PRIMARY_SOFT,
            corner_radius=6,
            height=24,
        ).pack(anchor="w", padx=20, pady=(18, 8))

        titulo = ctk.CTkLabel(
            container,
            text=titulo_texto,
            font=FONT_TITLE,
        )
        titulo.pack(anchor="w", padx=20, pady=(0, 4))

        subtitulo = ctk.CTkLabel(
            container,
            text=subtitulo_texto,
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
        )
        subtitulo.pack(anchor="w", padx=20, pady=(0, 16))

        # Aviso explicativo da persistência segura
        aviso_frame = ctk.CTkFrame(container, fg_color=COLOR_PRIMARY_SOFT, corner_radius=10)
        aviso_frame.pack(fill="x", padx=20, pady=(0, 14))

        aviso_lbl = ctk.CTkLabel(
            aviso_frame,
            text=f"ℹ️ Os dados são salvos localmente de forma segura.\n{MSG_SEGURANCA_CERTIFICADO}",
            font=FONT_CAPTION,
            justify="left",
        )
        aviso_lbl.pack(padx=14, pady=10, anchor="w")

        # Botão opcional para iniciar cadastro a partir de Certificado A1
        if not self.empresa_edicao:
            self.btn_importar_cert = ctk.CTkButton(
                container,
                text="📂 Preencher dados via Certificado A1...",
                font=FONT_BODY_BOLD,
                height=40,
                fg_color="transparent",
                border_width=1,
                border_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_SOFT,
                text_color=COLOR_PRIMARY,
                command=self._importar_dados_de_certificado,
            )
            self.btn_importar_cert.pack(fill="x", padx=20, pady=(0, 18))

        ctk.CTkLabel(
            container, text="DADOS DA EMPRESA", font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 8))

        # Campo: Razão Social
        ctk.CTkLabel(container, text="Razão Social *", font=FONT_BODY_BOLD).pack(
            anchor="w", padx=20, pady=(0, 4)
        )
        self.txt_razao = ctk.CTkEntry(
            container,
            placeholder_text="Ex: Minha Empresa de Serviços Ltda",
            height=42,
        )
        self.txt_razao.pack(fill="x", padx=20, pady=(0, 14))

        # Campo: Nome Fantasia (Opcional)
        ctk.CTkLabel(container, text="Nome de Exibição / Fantasia", font=FONT_BODY_BOLD).pack(
            anchor="w", padx=20, pady=(0, 4)
        )
        self.txt_fantasia = ctk.CTkEntry(
            container,
            placeholder_text="Ex: Minha Empresa (opcional)",
            height=42,
        )
        self.txt_fantasia.pack(fill="x", padx=20, pady=(0, 14))

        # Campo: CNPJ (Suporta numérico e alfanumérico)
        ctk.CTkLabel(
            container,
            text="CNPJ *",
            font=FONT_BODY_BOLD,
        ).pack(anchor="w", padx=20, pady=(0, 4))
        self.txt_cnpj = ctk.CTkEntry(
            container,
            placeholder_text="Ex: 00.000.000/0001-91 ou 12.ABC.345/0001-88",
            height=42,
        )
        self.txt_cnpj.pack(fill="x", padx=20)
        ctk.CTkLabel(
            container,
            text="Aceita o CNPJ tradicional e o novo formato alfanumérico.",
            font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(4, 18))

        ctk.CTkLabel(
            container, text="ORGANIZAÇÃO DOS ARQUIVOS", font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 8))

        # Campo: Pasta de Documentos
        ctk.CTkLabel(container, text="Pasta principal para salvar os documentos *", font=FONT_BODY_BOLD).pack(
            anchor="w", padx=20, pady=(0, 4)
        )
        pasta_frame = ctk.CTkFrame(container, fg_color="transparent")
        pasta_frame.pack(fill="x", padx=20, pady=(0, 14))

        self.txt_pasta = ctk.CTkEntry(
            pasta_frame,
            height=42,
        )
        self.txt_pasta.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_pasta = ctk.CTkButton(
            pasta_frame,
            text="Selecionar...",
            width=100,
            height=42,
            command=self._selecionar_pasta,
        )
        btn_pasta.pack(side="right")

        # Preenchimento inicial dos campos
        if self.empresa_edicao:
            self.txt_razao.insert(0, self.empresa_edicao.razao_social)
            self.txt_fantasia.insert(0, self.empresa_edicao.nome_fantasia)
            self.txt_cnpj.insert(0, self.empresa_edicao.cnpj_formatado)
            self.txt_pasta.insert(0, str(self.empresa_edicao.pasta_documentos))
        else:
            self.txt_pasta.insert(0, str(self.settings.default_docs_dir))

        # Mensagem de erro de validação
        self.lbl_erro = ctk.CTkLabel(
            container,
            text="",
            font=FONT_BODY,
            text_color=COLOR_DANGER,
            wraplength=520,
        )
        self.lbl_erro.pack(padx=20, pady=(0, 12), anchor="w")

        btn_cancelar = ctk.CTkButton(
            botoes_frame,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            text_color=("gray10", "gray90"),
            height=42,
            width=110,
            command=self.destroy,
        )
        btn_cancelar.pack(side="left", padx=12, pady=12)

        rotulo_salvar = "Salvar Alterações" if self.empresa_edicao else "Salvar Empresa"
        self.btn_salvar = ctk.CTkButton(
            botoes_frame,
            text=rotulo_salvar,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            font=FONT_LARGE_BUTTON,
            height=42,
            width=180,
            command=self._salvar,
        )
        self.btn_salvar.pack(side="right", padx=12, pady=12)

    def _selecionar_pasta(self) -> None:
        """Abre caixa de diálogo para seleção de pasta no Windows."""
        caminho = filedialog.askdirectory(
            parent=self,
            title="Selecione a pasta principal (o programa criará a pasta da empresa)",
            initialdir=str(self.settings.default_docs_dir.parent),
        )
        if caminho:
            self.txt_pasta.delete(0, "end")
            self.txt_pasta.insert(0, caminho)

    def _salvar(self) -> None:
        """Valida os campos, prepara a pasta e persiste a empresa sem corromper estado anterior."""
        razao = self.txt_razao.get().strip()
        fantasia = self.txt_fantasia.get().strip()
        cnpj_bruto = self.txt_cnpj.get().strip()
        pasta_str = self.txt_pasta.get().strip()

        # 1. Validação dos campos textuais
        if not razao:
            self.lbl_erro.configure(text="Informe a Razão Social da empresa.")
            return

        if not cnpj_bruto:
            self.lbl_erro.configure(text="Informe o CNPJ da empresa.")
            return

        try:
            cnpj_validado = validar_ou_falhar_cnpj(cnpj_bruto)
        except CNPJInvalidoError as err:
            self.lbl_erro.configure(text=f"CNPJ inválido: {err}")
            return

        # 2. Verificação prévia de unicidade de CNPJ no repositório
        existente = self.repository.obter_por_cnpj(cnpj_validado)
        if existente:
            # Em edição, conflita se o ID for de outra empresa
            if not self.empresa_edicao or existente.id != self.empresa_edicao.id:
                self.lbl_erro.configure(
                    text=f"Já existe uma empresa cadastrada com este CNPJ ({formatar_cnpj(cnpj_validado)})."
                )
                return

        # 3. Validação e preparação da pasta de documentos no sistema de arquivos
        pasta_alvo = Path(pasta_str) if pasta_str else self.settings.default_docs_dir / razao
        try:
            pasta_garantida = PastaDocumentosService.validar_e_preparar_pasta(pasta_alvo)
        except PastaInvalidaError as err:
            self.lbl_erro.configure(text=str(err))
            return
        except Exception as err:
            self.lbl_erro.configure(text=f"Erro ao validar a pasta de documentos: {err}")
            return

        # 4. Construção da entidade e persistência
        try:
            if self.empresa_edicao:
                # Regra de Segurança da Etapa 03:
                # Se o CNPJ foi alterado em empresa que possui certificado associado,
                # não preservar silenciosamente uma associação incompatível.
                manter_certificado = True
                if self.empresa_edicao.tem_certificado_associado and self.empresa_edicao.certificado_cnpj:
                    if cnpj_validado != self.empresa_edicao.certificado_cnpj:
                        msg_aviso = (
                            f"O CNPJ da empresa foi alterado de '{self.empresa_edicao.cnpj_formatado}' "
                            f"para '{formatar_cnpj(cnpj_validado)}'.\n\n"
                            "Como o certificado digital atualmente associado possui o CNPJ anterior, "
                            "a associação do certificado SERÁ REMOVIDA desta empresa ao salvar.\n\n"
                            "O arquivo físico do certificado no disco NÃO será apagado.\n\n"
                            "Deseja confirmar a alteração do CNPJ e remover a associação do certificado?"
                        )
                        confirmar = messagebox.askyesno(
                            title="Confirmar Alteração de CNPJ",
                            message=msg_aviso,
                            parent=self,
                        )
                        if not confirmar:
                            # Usuário cancelou: preserva todos os dados e estado anterior intactos
                            return
                        manter_certificado = False

                cert_caminho = self.empresa_edicao.certificado_caminho if manter_certificado else None
                cert_cnpj = self.empresa_edicao.certificado_cnpj if manter_certificado else None
                cert_fp = self.empresa_edicao.certificado_fingerprint_sha256 if manter_certificado else None
                cert_val_de = self.empresa_edicao.certificado_valido_de if manter_certificado else None
                cert_val_ate = self.empresa_edicao.certificado_valido_ate if manter_certificado else None
                cert_verif = self.empresa_edicao.certificado_verificado_em if manter_certificado else None

                empresa_alvo = Empresa(
                    id=self.empresa_edicao.id,
                    razao_social=razao,
                    nome_fantasia=fantasia,
                    cnpj=cnpj_validado,
                    pasta_documentos=pasta_garantida,
                    ativo=self.empresa_edicao.ativo,
                    criado_em=self.empresa_edicao.criado_em,
                    certificado_caminho=cert_caminho,
                    certificado_cnpj=cert_cnpj,
                    certificado_fingerprint_sha256=cert_fp,
                    certificado_valido_de=cert_val_de,
                    certificado_valido_ate=cert_val_ate,
                    certificado_verificado_em=cert_verif,
                    ultimo_nsu_adn=self.empresa_edicao.ultimo_nsu_adn,
                )
            else:
                empresa_alvo = Empresa(
                    razao_social=razao,
                    nome_fantasia=fantasia,
                    cnpj=cnpj_validado,
                    pasta_documentos=pasta_garantida,
                )

            self.repository.salvar(empresa_alvo)
        except CNPJDuplicadoError as err:
            self.lbl_erro.configure(text=str(err))
            return
        except ValidacaoError as err:
            self.lbl_erro.configure(text=str(err))
            return
        except PersistenciaError:
            self.lbl_erro.configure(
                text="Erro ao salvar dados no banco local. Verifique se o arquivo não está bloqueado."
            )
            return
        except Exception:
            self.lbl_erro.configure(text="Ocorreu um erro inesperado ao salvar. Tente novamente.")
            return

        # 5. Sucesso: notifica callback com a empresa persistida e fecha modal
        self.on_success(empresa_alvo)
        self.destroy()

    def _importar_dados_de_certificado(self) -> None:
        """Inspeciona um arquivo A1 em segundo plano e preenche Razão Social e CNPJ automaticamente."""
        if self._inspector.processando:
            return

        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecione o Certificado Digital A1",
            filetypes=[("Certificado Digital A1 (*.pfx; *.p12)", "*.pfx;*.p12"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return

        senha = simpledialog.askstring(
            "Senha do Certificado",
            "Informe a senha do certificado para leitura dos dados:\n(A senha NÃO será salva)",
            show="*",
            parent=self,
        )
        if senha is None:
            return

        # Desabilita o botão para impedir duplo clique e sinaliza processamento
        if hasattr(self, "btn_importar_cert"):
            self.btn_importar_cert.configure(state="disabled", text="⏳ Inspecionando...")
        self.lbl_erro.configure(
            text="Inspecionando certificado em segundo plano...",
            text_color=("gray40", "gray70"),
        )

        iniciado = self._inspector.iniciar(
            caminho=Path(caminho),
            senha=senha,
            on_resultado=self._processar_resultado_importacao,
        )
        del senha  # descarta imediatamente da memória local

        if not iniciado and hasattr(self, "btn_importar_cert"):
            self.btn_importar_cert.configure(
                state="normal", text="📂 Preencher dados via Certificado A1..."
            )

    def _processar_resultado_importacao(self, info: CertificadoInfo | None, erro: str | None) -> None:
        """Processa o retorno da inspeção na thread principal do Tkinter."""
        if self._destruido:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if hasattr(self, "btn_importar_cert") and self.btn_importar_cert.winfo_exists():
            self.btn_importar_cert.configure(
                state="normal", text="📂 Preencher dados via Certificado A1..."
            )

        if erro or info is None:
            msg_erro = erro or MSG_ERRO_GENERICO_CERTIFICADO
            self.lbl_erro.configure(
                text=msg_erro,
                text_color=COLOR_DANGER,
            )
            messagebox.showerror(
                "Erro ao Ler Certificado",
                msg_erro,
                parent=self,
            )
            return

        # Verifica se o CNPJ já está cadastrado
        existente = self.repository.obter_por_cnpj(info.cnpj)
        if existente:
            confirmar = messagebox.askyesno(
                "Empresa Já Cadastrada",
                f"A empresa '{existente.nome_exibicao}' já está cadastrada com este CNPJ ({info.cnpj_formatado}).\n\n"
                "Deseja selecionar essa empresa existente em vez de criar um novo cadastro?",
                parent=self,
            )
            if confirmar:
                self.on_success(existente)
                self.destroy()
                return

        # Preenche os campos mantendo o usuário no controle
        self.txt_cnpj.delete(0, "end")
        self.txt_cnpj.insert(0, info.cnpj_formatado)

        nome_razao = info.nome_empresarial or info.nome_comum
        if nome_razao:
            self.txt_razao.delete(0, "end")
            self.txt_razao.insert(0, nome_razao)

        self.lbl_erro.configure(
            text=f"✓ Dados importados do certificado A1 ({info.cnpj_formatado}). Revise antes de salvar.",
            text_color=COLOR_SUCCESS,
        )

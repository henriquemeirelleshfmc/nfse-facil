"""Diálogo assíncrono para sincronizar todos os lotes disponíveis de NFS-e."""

from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Callable
import customtkinter as ctk

from nfse_facil.domain.adn_models import AmbienteADN
from nfse_facil.domain.exceptions import (
    ADNError,
    ADNLimiteRequisicoesError,
    ADNRespostaInvalidaError,
    CertificadoError,
    DocumentoFiscalError,
)
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload
from nfse_facil.infrastructure.http.adn_client import ADNClient
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.services.sincronizacao_adn import ResultadoSincronizacao, SincronizacaoADNService
from nfse_facil.services.documentos_adn import OrganizadorDocumentosADN
from nfse_facil.services.diagnostico import registrar_falha
from nfse_facil.ui.theme import (
    COLOR_BG_DARK,
    COLOR_BG_LIGHT,
    COLOR_CARD_DARK,
    COLOR_CARD_LIGHT,
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


class DownloadDialog(ctk.CTkToplevel):
    """Solicita a senha apenas em memória e mantém a interface responsiva."""

    def __init__(
        self,
        parent,
        repository: EmpresaRepository,
        empresa: Empresa,
        periodo: PeriodoConsulta,
        preferencias: PreferenciasDownload,
        on_success: Callable[[Empresa], None],
        sync_service: SincronizacaoADNService | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.empresa = empresa
        self.periodo = periodo
        self.preferencias = preferencias
        self.on_success = on_success
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nfse-download")
        self._future: Future | None = None
        self._after_id: str | None = None
        self._processando = False
        self._reconstruir_historico = False
        self._texto_diagnostico = ""
        self._sync_service = sync_service or SincronizacaoADNService(
            repository,
            ADNClient(AmbienteADN.PRODUCAO),
        )

        self.title("Buscar notas na NFS-e Nacional")
        self.geometry("620x650")
        self.minsize(620, 600)
        self.resizable(False, True)
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._construir()
        self.grab_set()

    def _construir(self) -> None:
        card = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
        )
        card.pack(fill="both", expand=True, padx=20, pady=20)

        cabecalho = ctk.CTkFrame(card, fg_color="transparent")
        cabecalho.pack(fill="x", padx=24, pady=(22, 14))
        ctk.CTkLabel(
            cabecalho,
            text="  NFS-e NACIONAL  ",
            font=FONT_CAPTION,
            text_color=COLOR_PRIMARY,
            fg_color=COLOR_PRIMARY_SOFT,
            corner_radius=6,
            height=24,
        ).pack(anchor="w")
        ctk.CTkLabel(
            cabecalho, text="Buscar e organizar notas", font=FONT_TITLE, anchor="w"
        ).pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(
            cabecalho,
            text="O aplicativo consultará todos os lotes disponíveis automaticamente.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        contexto = ctk.CTkFrame(card, corner_radius=12, fg_color=("#F8FAFC", "#162033"))
        contexto.pack(fill="x", padx=24, pady=(0, 14))
        ctk.CTkLabel(
            contexto, text="EMPRESA E PERÍODO", font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED, anchor="w"
        ).pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            contexto,
            text=self.empresa.nome_exibicao,
            font=FONT_SUBTITLE,
            anchor="w",
            justify="left",
            wraplength=500,
        ).pack(fill="x", padx=16)
        ctk.CTkLabel(
            contexto, text=self.periodo.rotulo_exibicao, font=FONT_BODY,
            text_color=COLOR_TEXT_MUTED, anchor="w"
        ).pack(fill="x", padx=16, pady=(2, 12))

        self.frame_credencial = ctk.CTkFrame(card, fg_color="transparent")
        self.frame_credencial.pack(fill="x", padx=24)
        ctk.CTkLabel(
            self.frame_credencial, text="Senha do certificado digital", font=FONT_BODY_BOLD, anchor="w"
        ).pack(fill="x", pady=(0, 6))
        linha_senha = ctk.CTkFrame(self.frame_credencial, fg_color="transparent")
        linha_senha.pack(fill="x")
        self.txt_senha = ctk.CTkEntry(
            linha_senha, placeholder_text="Digite a senha do certificado A1", show="*", height=42
        )
        self.txt_senha.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chk_mostrar_senha = ctk.CTkCheckBox(
            linha_senha, text="Mostrar", width=82, font=FONT_CAPTION,
            command=self._alternar_visibilidade_senha,
        )
        self.chk_mostrar_senha.pack(side="left")
        ctk.CTkLabel(
            self.frame_credencial,
            text="🔒 A senha é usada apenas nesta busca e não fica salva no computador.",
            font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

        self.frame_status = ctk.CTkFrame(card, corner_radius=10, fg_color=("#F8FAFC", "#162033"))
        self.frame_status.pack(fill="x", padx=24, pady=(14, 10))
        self.lbl_status_titulo = ctk.CTkLabel(
            self.frame_status, text="Pronto para começar", font=FONT_BODY_BOLD, anchor="w"
        )
        self.lbl_status_titulo.pack(fill="x", padx=14, pady=(10, 1))
        self.lbl_status = ctk.CTkLabel(
            self.frame_status,
            text="A conexão será feita com o ambiente oficial da NFS-e Nacional.",
            font=FONT_CAPTION,
            text_color=COLOR_TEXT_MUTED,
            wraplength=510,
            justify="left",
            anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=14, pady=(0, 10))
        self.btn_copiar_diagnostico = ctk.CTkButton(
            self.frame_status,
            text="Copiar informações para o suporte",
            height=30,
            font=FONT_CAPTION,
            fg_color="transparent",
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            text_color=("#334155", "#E2E8F0"),
            command=self._copiar_diagnostico,
        )
        self.barra_progresso = ctk.CTkFrame(
            self.frame_status, height=5, corner_radius=3, fg_color=COLOR_PRIMARY
        )

        botoes = ctk.CTkFrame(card, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 20))
        self.btn_fechar = ctk.CTkButton(
            botoes, text="Fechar", width=110, height=42,
            fg_color="transparent", border_width=1,
            border_color=("#CBD5E1", "#475569"),
            text_color=("#334155", "#E2E8F0"), command=self.destroy,
        )
        self.btn_fechar.pack(side="left")
        self.btn_buscar = ctk.CTkButton(
            botoes, text="Buscar notas agora", command=self._iniciar,
            font=FONT_LARGE_BUTTON, height=42, corner_radius=10,
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
        )
        self.btn_buscar.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _alternar_visibilidade_senha(self) -> None:
        self.txt_senha.configure(show="" if self.chk_mostrar_senha.get() else "*")

    def _iniciar(self) -> None:
        if self._processando:
            return
        senha = self.txt_senha.get()
        if not senha:
            self.lbl_status_titulo.configure(text="Senha necessária", text_color=COLOR_WARNING)
            self.lbl_status.configure(text="Digite a senha do certificado para continuar.")
            return
        if self._reconstruir_historico:
            try:
                self.empresa.ultimo_nsu_adn = 0
                self.repository.salvar(self.empresa)
            except Exception:
                self.lbl_status_titulo.configure(
                    text="Não foi possível preparar a recuperação", text_color=COLOR_WARNING
                )
                self.lbl_status.configure(
                    text="O histórico local não pôde ser reiniciado. Tente novamente."
                )
                return
            self._reconstruir_historico = False
        self.txt_senha.delete(0, "end")
        self._processando = True
        self._texto_diagnostico = ""
        self.btn_copiar_diagnostico.pack_forget()
        self.btn_buscar.configure(state="disabled", text="Buscando...")
        self.btn_fechar.configure(state="disabled")
        self.lbl_status_titulo.configure(text="Consulta em andamento", text_color=COLOR_PRIMARY)
        self.lbl_status.configure(text="Conectando com segurança à NFS-e Nacional...")
        self.barra_progresso.pack(fill="x", padx=14, pady=(0, 12))
        self._future = self._executor.submit(
            self._sync_service.sincronizar_todos,
            self.empresa,
            senha,
            self.periodo,
            self.preferencias,
        )
        del senha
        self._agendar_verificacao()

    def _agendar_verificacao(self) -> None:
        if self.winfo_exists():
            self._after_id = self.after(50, self._verificar_resultado)

    def _verificar_resultado(self) -> None:
        self._after_id = None
        if not self._future or not self._future.done():
            self._agendar_verificacao()
            return
        try:
            resultado = self._future.result()
        except ADNLimiteRequisicoesError as err:
            self._finalizar_erro(
                "O portal da NFS-e pausou temporariamente novas consultas.\n"
                "Tudo o que já foi recebido está salvo. Aguarde antes de tentar novamente.",
                err,
            )
        except ADNRespostaInvalidaError as err:
            self._finalizar_erro(
                f"{err}\n"
                "Isso não confirma o fim da importação. Tente novamente mais tarde.",
                err,
            )
        except (ADNError, CertificadoError, DocumentoFiscalError) as err:
            self._finalizar_erro(str(err), err)
        except Exception as err:
            self._finalizar_erro("Não foi possível concluir a busca. Tente novamente.", err)
        else:
            self._finalizar_sucesso(resultado)

    def _finalizar_sucesso(self, resultado: ResultadoSincronizacao) -> None:
        self._processando = False
        self._texto_diagnostico = ""
        self.btn_copiar_diagnostico.pack_forget()
        self.barra_progresso.pack_forget()
        self.btn_buscar.configure(state="normal", text="Verificar novas notas")
        self.btn_fechar.configure(state="normal")
        if resultado.concluida:
            if resultado.restaurados:
                titulo = (
                    f"Consulta concluída. {resultado.restaurados} arquivo(s) apagado(s) "
                    "foram restaurado(s) da cópia interna."
                )
                self.lbl_status_titulo.configure(text="Arquivos recuperados", text_color=COLOR_SUCCESS)
            elif resultado.organizacao.novos == 0 and self._arquivo_interno_ausente():
                titulo = (
                    "A cópia local do histórico não foi encontrada. Clique em "
                    "'Baixar histórico novamente' para reconstruir os arquivos pelo portal."
                )
                self._reconstruir_historico = True
                self.btn_buscar.configure(text="Baixar histórico novamente")
                self.lbl_status_titulo.configure(
                    text="Histórico local apagado", text_color=COLOR_WARNING
                )
                self.frame_status.configure(fg_color=("#FFF7ED", "#2E2108"))
            elif resultado.organizacao.novos == 0:
                titulo = "Consulta concluída. Não há novas notas disponíveis neste momento."
                self.lbl_status_titulo.configure(text="Empresa atualizada", text_color=COLOR_SUCCESS)
            else:
                titulo = "Importação concluída. Você já pode fechar esta janela."
                self.lbl_status_titulo.configure(text="Tudo certo", text_color=COLOR_SUCCESS)
            if not self._reconstruir_historico:
                self.frame_status.configure(fg_color=COLOR_SUCCESS_SOFT)
        else:
            titulo = "A busca foi pausada antes de chegar ao fim. Tente novamente mais tarde."
            self.lbl_status_titulo.configure(text="Busca pausada", text_color=COLOR_WARNING)
        if self._reconstruir_historico:
            texto_status = titulo
        else:
            texto_status = (
                f"{titulo}\n"
                f"{resultado.organizacao.novos} arquivo(s) novo(s), "
                f"{resultado.organizacao.existentes} já existente(s).\n"
                f"Notas do filtro escolhido: {resultado.organizacao.selecionados}. "
                f"Itens examinados no histórico: {resultado.organizacao.arquivados_novos}.\n"
                f"{resultado.lotes_processados} lote(s) processado(s). Último NSU: {resultado.ultimo_nsu}."
                + (
                    f"\n{len(resultado.relatorios)} relatório(s) criado(s) na pasta Relatórios."
                    if resultado.relatorios else ""
                )
            )
        self.lbl_status.configure(text=texto_status)
        self.on_success(self.empresa)

    def _arquivo_interno_ausente(self) -> bool:
        if self.empresa.ultimo_nsu_adn <= 0:
            return False
        pasta = (
            OrganizadorDocumentosADN.pasta_da_empresa(self.empresa)
            / OrganizadorDocumentosADN.PASTA_ARQUIVO_INTERNO
        )
        return not pasta.exists() or not next(pasta.rglob("*.xml"), None)

    def _finalizar_erro(self, mensagem: str, erro: BaseException | None = None) -> None:
        self._processando = False
        self.barra_progresso.pack_forget()
        self.btn_buscar.configure(state="normal", text="Tentar novamente")
        self.btn_fechar.configure(state="normal")
        self.lbl_status_titulo.configure(text="Não foi possível concluir", text_color=COLOR_WARNING)
        diagnostico = registrar_falha("consulta_adn", erro or RuntimeError("falha_publica"))
        self._texto_diagnostico = diagnostico.texto_para_copiar
        self.lbl_status.configure(text=f"{mensagem}\nCódigo de suporte: {diagnostico.codigo}")
        self.btn_copiar_diagnostico.pack(fill="x", padx=14, pady=(0, 10))

    def _copiar_diagnostico(self) -> None:
        if not self._texto_diagnostico:
            return
        self.clipboard_clear()
        self.clipboard_append(self._texto_diagnostico)
        self.lbl_status_titulo.configure(text="Informações copiadas", text_color=COLOR_SUCCESS)

    def destroy(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.grab_release()
        except Exception:
            pass
        super().destroy()

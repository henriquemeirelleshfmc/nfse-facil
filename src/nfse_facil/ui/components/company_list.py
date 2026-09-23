"""Componente de listagem e pesquisa de empresas para a barra lateral."""

from typing import Callable
import customtkinter as ctk

from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.ui.theme import (
    COLOR_NAV_CARD,
    COLOR_NAV_HOVER,
    COLOR_PRIMARY,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
)


class CompanyList(ctk.CTkFrame):
    """Lista interativa de empresas com barra de pesquisa e estado vazio amigável."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        repository: EmpresaRepository,
        on_company_selected: Callable[[Empresa | None], None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.repository = repository
        self.on_company_selected = on_company_selected

        self._empresa_selecionada_id: str | None = None
        self._itens_botoes: list[ctk.CTkButton] = []

        self._build_ui()
        self.carregar_empresas()

    def _build_ui(self) -> None:
        # Campo de Pesquisa em tempo real
        self.txt_busca = ctk.CTkEntry(
            self,
            placeholder_text="🔍 Buscar por nome ou CNPJ...",
            height=36,
            fg_color=COLOR_NAV_CARD,
            border_color="#294174",
            text_color="#FFFFFF",
            placeholder_text_color="#91A2C8",
        )
        self.txt_busca.pack(fill="x", padx=12, pady=(0, 10))
        self.txt_busca.bind("<KeyRelease>", lambda event: self.carregar_empresas())

        # Área de rolagem para os itens da lista
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=4, pady=0)

        # Container para estado vazio
        self.empty_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.lbl_vazio_icone = ctk.CTkLabel(
            self.empty_frame,
            text="🏢",
            font=("Segoe UI", 36),
        )
        self.lbl_vazio_icone.pack(pady=(20, 6))

        self.lbl_vazio_texto = ctk.CTkLabel(
            self.empty_frame,
            text="Nenhuma empresa cadastrada.\nClique em 'Adicionar empresa'\npara começar.",
            font=FONT_BODY,
            text_color="#91A2C8",
            justify="center",
        )
        self.lbl_vazio_texto.pack(pady=(0, 20))

    def carregar_empresas(self, selecionar_id: str | None = None) -> None:
        """Recarrega a lista de empresas a partir do repositório aplicando a busca."""
        termo = self.txt_busca.get().strip()
        empresas = self.repository.pesquisar(termo)

        # Limpa widgets anteriores
        for widget in self.scroll_frame.winfo_children():
            if widget != self.empty_frame:
                widget.destroy()

        if not empresas:
            self.empty_frame.pack(fill="both", expand=True, pady=10)
            if termo:
                self.lbl_vazio_texto.configure(
                    text=f"Nenhuma empresa encontrada para:\n'{termo}'"
                )
            else:
                self.lbl_vazio_texto.configure(
                    text="Nenhuma empresa cadastrada.\nClique em 'Adicionar empresa'\npara começar."
                )
            self._empresa_selecionada_id = None
            self.on_company_selected(None)
            return

        self.empty_frame.pack_forget()

        # Determina qual empresa manter selecionada
        alvo_id = selecionar_id or self._empresa_selecionada_id
        empresa_alvo = next((e for e in empresas if e.id == alvo_id), empresas[0])
        self._empresa_selecionada_id = empresa_alvo.id

        # Cria botões tipo cartão para cada empresa
        for emp in empresas:
            is_selecionada = emp.id == self._empresa_selecionada_id
            bg_color = COLOR_PRIMARY if is_selecionada else COLOR_NAV_CARD
            text_color = "#FFFFFF"
            hover_color = "#1D4ED8" if is_selecionada else COLOR_NAV_HOVER

            card = ctk.CTkButton(
                self.scroll_frame,
                text=f"{emp.nome_exibicao}\nCNPJ: {emp.cnpj_formatado}",
                font=FONT_BODY_BOLD if is_selecionada else FONT_BODY,
                fg_color=bg_color,
                text_color=text_color,
                hover_color=hover_color,
                anchor="w",
                height=58,
                corner_radius=10,
                command=lambda e=emp: self._selecionar(e),
            )
            card.pack(fill="x", pady=4, padx=6)

        self.on_company_selected(empresa_alvo)

    def _selecionar(self, empresa: Empresa) -> None:
        """Marca uma empresa como selecionada e atualiza a interface."""
        self._empresa_selecionada_id = empresa.id
        self.carregar_empresas(selecionar_id=empresa.id)

    @property
    def empresa_selecionada_id(self) -> str | None:
        """Retorna o ID da empresa selecionada."""
        return self._empresa_selecionada_id

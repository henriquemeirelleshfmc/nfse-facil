"""Componente de seleção de período para download de notas fiscais."""

from datetime import date, datetime
from typing import Callable
import customtkinter as ctk

from nfse_facil.domain.exceptions import PeriodoInvalidoError
from nfse_facil.domain.models import PeriodoConsulta, TipoPeriodo
from nfse_facil.ui.theme import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
)


class PeriodSelector(ctk.CTkFrame):
    """Componente visual com opções rápidas de período e datas personalizadas."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_period_changed: Callable[[PeriodoConsulta], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.on_period_changed = on_period_changed

        # Inicia padrão com "Este mês"
        self._periodo_atual = PeriodoConsulta.este_mes()
        self._modo_atual = TipoPeriodo.ESTE_MES

        self._build_ui()

    def _build_ui(self) -> None:
        # Seletor segmentado com as opções rápidas
        self.btn_segmentado = ctk.CTkSegmentedButton(
            self,
            values=["Este mês", "Mês anterior", "Personalizado"],
            command=self._on_segment_changed,
            height=36,
            font=FONT_BODY_BOLD,
            selected_color=COLOR_PRIMARY,
        )
        self.btn_segmentado.set("Este mês")
        self.btn_segmentado.pack(fill="x", pady=(0, 10))

        # Rótulo de exibição do período calculado
        self.lbl_detalhes = ctk.CTkLabel(
            self,
            text=f"📅 Período selecionado: {self._periodo_atual.rotulo_exibicao}",
            font=FONT_BODY,
            text_color=("gray30", "gray80"),
            anchor="w",
        )
        self.lbl_detalhes.pack(fill="x", pady=(0, 6))

        # Container para datas personalizadas (inicialmente oculto)
        self.frame_personalizado = ctk.CTkFrame(self, fg_color=("gray95", "gray15"), corner_radius=8)

        linha_datas = ctk.CTkFrame(self.frame_personalizado, fg_color="transparent")
        linha_datas.pack(fill="x", padx=12, pady=10)

        # Data Inicial
        ctk.CTkLabel(linha_datas, text="De:", font=FONT_BODY_BOLD).pack(side="left", padx=(0, 4))
        self.txt_data_inicio = ctk.CTkEntry(
            linha_datas,
            width=110,
            placeholder_text="DD/MM/AAAA",
            height=32,
        )
        self.txt_data_inicio.insert(0, self._periodo_atual.data_inicio_formatada)
        self.txt_data_inicio.pack(side="left", padx=(0, 12))

        # Data Final
        ctk.CTkLabel(linha_datas, text="Até:", font=FONT_BODY_BOLD).pack(side="left", padx=(0, 4))
        self.txt_data_fim = ctk.CTkEntry(
            linha_datas,
            width=110,
            placeholder_text="DD/MM/AAAA",
            height=32,
        )
        self.txt_data_fim.insert(0, self._periodo_atual.data_fim_formatada)
        self.txt_data_fim.pack(side="left", padx=(0, 12))

        # Botão Aplicar período personalizado
        btn_aplicar = ctk.CTkButton(
            linha_datas,
            text="Aplicar",
            width=80,
            height=32,
            command=self._aplicar_personalizado,
        )
        btn_aplicar.pack(side="left")

        # Rótulo de erro de data personalizada
        self.lbl_erro_data = ctk.CTkLabel(
            self.frame_personalizado,
            text="",
            font=FONT_CAPTION,
            text_color=COLOR_DANGER,
        )
        self.lbl_erro_data.pack(anchor="w", padx=12, pady=(0, 6))

    def _on_segment_changed(self, valor: str) -> None:
        """Manipula a troca rápida entre os modos de período."""
        self.lbl_erro_data.configure(text="")
        if valor == "Este mês":
            self.frame_personalizado.pack_forget()
            self._modo_atual = TipoPeriodo.ESTE_MES
            self._periodo_atual = PeriodoConsulta.este_mes()
            self._atualizar_exibicao()
        elif valor == "Mês anterior":
            self.frame_personalizado.pack_forget()
            self._modo_atual = TipoPeriodo.MES_ANTERIOR
            self._periodo_atual = PeriodoConsulta.mes_anterior()
            self._atualizar_exibicao()
        else:
            self._modo_atual = TipoPeriodo.PERSONALIZADO
            self.frame_personalizado.pack(fill="x", pady=(4, 6))
            self._aplicar_personalizado()

    def _aplicar_personalizado(self) -> None:
        """Valida e aplica as datas informadas nos campos de texto."""
        str_inicio = self.txt_data_inicio.get().strip()
        str_fim = self.txt_data_fim.get().strip()

        try:
            dt_inicio = datetime.strptime(str_inicio, "%d/%m/%Y").date()
        except ValueError:
            self.lbl_erro_data.configure(text="Data inicial inválida. Utilize o formato DD/MM/AAAA.")
            return

        try:
            dt_fim = datetime.strptime(str_fim, "%d/%m/%Y").date()
        except ValueError:
            self.lbl_erro_data.configure(text="Data final inválida. Utilize o formato DD/MM/AAAA.")
            return

        try:
            self._periodo_atual = PeriodoConsulta.personalizado(dt_inicio, dt_fim)
            self.lbl_erro_data.configure(text="")
            self._atualizar_exibicao()
        except PeriodoInvalidoError as err:
            self.lbl_erro_data.configure(text=str(err))

    def _atualizar_exibicao(self) -> None:
        """Atualiza o texto legível e notifica callbacks."""
        self.lbl_detalhes.configure(
            text=f"📅 Período selecionado: {self._periodo_atual.rotulo_exibicao}"
        )
        if self.on_period_changed:
            self.on_period_changed(self._periodo_atual)

    def obter_periodo(self) -> PeriodoConsulta:
        """Retorna o período atualmente selecionado."""
        return self._periodo_atual

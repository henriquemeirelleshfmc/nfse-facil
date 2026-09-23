"""Testes para o modelo PeriodoConsulta e regras de transição de datas."""

from datetime import date
import pytest

from nfse_facil.domain.exceptions import PeriodoInvalidoError
from nfse_facil.domain.models import PeriodoConsulta, PreferenciasDownload, TipoPeriodo


class TestPeriodoConsulta:
    """Validação de intervalos, cálculos de virada de mês/ano e formatação."""

    def test_este_mes_calculo_primeiro_e_ultimo_dia(self) -> None:
        # Teste com mês de 31 dias (Outubro/2024)
        ref_outubro = date(2024, 10, 15)
        periodo = PeriodoConsulta.este_mes(ref_outubro)
        assert periodo.tipo == TipoPeriodo.ESTE_MES
        assert periodo.data_inicio == date(2024, 10, 1)
        assert periodo.data_fim == date(2024, 10, 31)
        assert periodo.data_inicio_formatada == "01/10/2024"
        assert periodo.data_fim_formatada == "31/10/2024"

        # Teste com ano bissexto (Fevereiro/2024 - 29 dias)
        ref_fev_bissexto = date(2024, 2, 10)
        periodo_fev = PeriodoConsulta.este_mes(ref_fev_bissexto)
        assert periodo_fev.data_fim == date(2024, 2, 29)

        # Teste com ano não bissexto (Fevereiro/2025 - 28 dias)
        ref_fev_normal = date(2025, 2, 10)
        periodo_fev_normal = PeriodoConsulta.este_mes(ref_fev_normal)
        assert periodo_fev_normal.data_fim == date(2025, 2, 28)

    def test_mes_anterior_transicao_normal(self) -> None:
        # Março/2024 -> Mês anterior: Fevereiro/2024
        ref_marco = date(2024, 3, 20)
        periodo = PeriodoConsulta.mes_anterior(ref_marco)
        assert periodo.tipo == TipoPeriodo.MES_ANTERIOR
        assert periodo.data_inicio == date(2024, 2, 1)
        assert periodo.data_fim == date(2024, 2, 29)

    def test_mes_anterior_transicao_ano_janeiro_para_dezembro(self) -> None:
        # CRÍTICO: Janeiro/2025 -> Mês anterior: Dezembro/2024 (virada de ano)
        ref_janeiro = date(2025, 1, 10)
        periodo = PeriodoConsulta.mes_anterior(ref_janeiro)
        assert periodo.tipo == TipoPeriodo.MES_ANTERIOR
        assert periodo.data_inicio == date(2024, 12, 1)
        assert periodo.data_fim == date(2024, 12, 31)
        assert periodo.data_inicio_formatada == "01/12/2024"
        assert periodo.data_fim_formatada == "31/12/2024"

    def test_periodo_personalizado_valido(self) -> None:
        dt_ini = date(2024, 5, 10)
        dt_fim = date(2024, 5, 20)
        periodo = PeriodoConsulta.personalizado(dt_ini, dt_fim)
        assert periodo.tipo == TipoPeriodo.PERSONALIZADO
        assert periodo.data_inicio == dt_ini
        assert periodo.data_fim == dt_fim
        assert periodo.rotulo_exibicao == "Personalizado: 10/05/2024 até 20/05/2024"

    def test_periodo_personalizado_mesmo_dia_valido(self) -> None:
        # Data início igual a data fim é válido
        dia = date(2024, 8, 15)
        periodo = PeriodoConsulta.personalizado(dia, dia)
        assert periodo.data_inicio == periodo.data_fim

    def test_periodo_personalizado_rejeita_data_final_anterior_a_inicial(self) -> None:
        dt_ini = date(2024, 5, 20)
        dt_fim = date(2024, 5, 10)
        with pytest.raises(PeriodoInvalidoError, match="não pode ser anterior"):
            PeriodoConsulta.personalizado(dt_ini, dt_fim)


class TestPreferenciasDownload:
    """Testes para o modelo PreferenciasDownload."""

    def test_preferencias_padrao(self) -> None:
        prefs = PreferenciasDownload()
        assert prefs.baixar_emitidas is True
        assert prefs.baixar_recebidas is True
        assert prefs.gerar_excel is True
        assert prefs.gerar_pdf is True
        assert prefs.tem_escopo_selecionado() is True

    def test_sem_escopo_selecionado(self) -> None:
        prefs = PreferenciasDownload(baixar_emitidas=False, baixar_recebidas=False)
        assert prefs.tem_escopo_selecionado() is False

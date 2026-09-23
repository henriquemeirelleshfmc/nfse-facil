"""Testes automatizados para validação e formatação de CNPJ numérico e alfanumérico."""

import pytest
from nfse_facil.domain.exceptions import CNPJInvalidoError
from nfse_facil.domain.validators import (
    formatar_cnpj,
    sanitizar_cnpj,
    validar_cnpj,
    validar_ou_falhar_cnpj,
)


class TestCNPJLegadoNumerico:
    """Validações do padrão tradicional (puramente numérico)."""

    def test_cnpj_numerico_valido_sem_mascara(self) -> None:
        # Banco do Brasil (com zeros à esquerda)
        assert validar_cnpj("00000000000191") is True
        # Petrobras
        assert validar_cnpj("33000167000101") is True
        # Caixa Econômica Federal
        assert validar_cnpj("00360305000104") is True

    def test_cnpj_numerico_valido_com_mascara(self) -> None:
        assert validar_cnpj("00.000.000/0001-91") is True
        assert validar_cnpj("33.000.167/0001-01") is True
        assert validar_cnpj("00.360.305/0001-04") is True

    def test_cnpj_numerico_invalido_por_digito_verificador(self) -> None:
        # DV incorreto (esperado 91, informado 90)
        assert validar_cnpj("00000000000190") is False
        assert validar_cnpj("33.000.167/0001-99") is False

    def test_cnpj_numerico_digitos_iguais_invalido(self) -> None:
        # Todos os dígitos repetidos são inválidos pela regra fiscal
        assert validar_cnpj("00000000000000") is False
        assert validar_cnpj("11111111111111") is False
        assert validar_cnpj("99.999.999/9999-99") is False


class TestCNPJAlfanumerico:
    """Validações do padrão alfanumérico oficial (IN RFB nº 2.229/2024)."""

    def test_cnpj_alfanumerico_valido_sem_mascara(self) -> None:
        # Casos calculados rigorosamente pela fórmula Módulo 11 (ASCII - 48):
        # 12ABC3450001 -> DVs: 88
        assert validar_cnpj("12ABC345000188") is True
        # AB12CD340001 -> DVs: 84
        assert validar_cnpj("AB12CD34000184") is True
        # 00000000001A -> DVs: 78 (com zeros à esquerda e letra na raiz)
        assert validar_cnpj("00000000001A78") is True

    def test_cnpj_alfanumerico_valido_com_mascara(self) -> None:
        assert validar_cnpj("12.ABC.345/0001-88") is True
        assert validar_cnpj("AB.12C.D34/0001-84") is True
        assert validar_cnpj("00.000.000/001A-78") is True

    def test_cnpj_alfanumerico_normalizacao_minusculas(self) -> None:
        # Letras minúsculas devem ser aceitas e normalizadas para maiúsculas
        assert validar_cnpj("12abc345000188") is True
        assert validar_cnpj("ab.12c.d34/0001-84") is True

    def test_cnpj_alfanumerico_invalido_por_digito_verificador(self) -> None:
        # DV incorreto (esperado 88, informado 87)
        assert validar_cnpj("12ABC345000187") is False
        assert validar_cnpj("12.ABC.345/0001-00") is False

    def test_cnpj_alfanumerico_invalido_com_letras_nos_dvs(self) -> None:
        # Os dígitos verificadores (posições 13 e 14) DEVEM ser estritamente numéricos
        assert validar_cnpj("12ABC34500018A") is False
        assert validar_cnpj("12ABC3450001AA") is False


class TestCNPJCasosLimiteETratamentoString:
    """Testes de comprimento, caracteres proibidos e restrições de tipo."""

    def test_tamanho_incorreto(self) -> None:
        assert validar_cnpj("") is False
        assert validar_cnpj("12345") is False
        assert validar_cnpj("0000000000019") is False       # 13 caracteres
        assert validar_cnpj("000000000001910") is False     # 15 caracteres

    def test_caracteres_nao_permitidos(self) -> None:
        # Caracteres especiais não permitidos
        assert validar_cnpj("12.ABC.345/0001@88") is False
        assert validar_cnpj("12.ABC.345/0001#88") is False
        assert validar_cnpj("12.ABÇ.345/0001-88") is False  # Cedilha não é permitida
        assert validar_cnpj("12.AB*.345/0001-88") is False

    def test_rejeicao_estrita_caracteres_e_digitos_unicode(self) -> None:
        # 1. Dígitos arábicos Unicode (Eastern Arabic: ٠١٢٣٤٥٦٧٨٩)
        digitos_arabicos_14 = "٠١٢٣٤٥٦٧٨٩٠١٩١"
        assert len(digitos_arabicos_14) == 14
        assert validar_cnpj(digitos_arabicos_14) is False

        # Dígitos Devanagari Unicode (०१२३४५६७८९)
        digitos_devanagari_14 = "०१२३४५६७८९०१91"
        assert validar_cnpj(digitos_devanagari_14) is False

        # Dígitos Full-width Unicode (０１２３...)
        digitos_fullwidth_14 = "０００００００００００１９１"
        assert validar_cnpj(digitos_fullwidth_14) is False

        # 2. Letras acentuadas Unicode (Á, É, Í, Ó, Ú, Ç, etc.)
        assert validar_cnpj("Á2ABC345000188") is False
        assert validar_cnpj("12ÃBC345000188") is False
        assert validar_cnpj("12ABC34500018É") is False

        # 3. Letras ou símbolos nas posições dos dígitos verificadores (posições 13 e 14)
        assert validar_cnpj("12ABC3450001A8") is False
        assert validar_cnpj("12ABC34500018A") is False
        assert validar_cnpj("12ABC3450001AB") is False
        assert validar_cnpj("12ABC3450001!8") is False
        assert validar_cnpj("12ABC34500018?") is False

        # 4. Misturas Unicode que tenham exatamente 14 posições
        assert validar_cnpj("12ABC345000¹88") is False  # Sobrescrito ¹
        assert validar_cnpj("12ABC345000²88") is False  # Sobrescrito ²
        assert validar_cnpj("12ABC345000½88") is False  # Fração ½
        assert validar_cnpj("12ABC3450001✨8") is False  # Emoji

    def test_rejeicao_tipo_nao_string(self) -> None:
        # CNPJ nunca deve ser número int ou float
        assert validar_cnpj(12345678000195) is False  # type: ignore
        assert validar_cnpj(None) is False            # type: ignore

        with pytest.raises(TypeError):
            sanitizar_cnpj(12345678000195)  # type: ignore

    def test_validar_ou_falhar_cnpj(self) -> None:
        # Sucesso retorna a string normalizada
        assert validar_ou_falhar_cnpj("12.abc.345/0001-88") == "12ABC345000188"
        assert validar_ou_falhar_cnpj("00.000.000/0001-91") == "00000000000191"

        # Falha levanta CNPJInvalidoError
        with pytest.raises(CNPJInvalidoError, match="dígitos verificadores inválidos"):
            validar_ou_falhar_cnpj("00.000.000/0001-99")

        with pytest.raises(CNPJInvalidoError, match="exatamente 14 caracteres"):
            validar_ou_falhar_cnpj("123")


class TestFormatacaoCNPJ:
    """Testes para a aplicação da máscara visual."""

    def test_formatacao_numerico_preserva_zeros_a_esquerda(self) -> None:
        formatado = formatar_cnpj("00000000000191")
        assert formatado == "00.000.000/0001-91"

    def test_formatacao_alfanumerico(self) -> None:
        formatado = formatar_cnpj("12ABC345000188")
        assert formatado == "12.ABC.345/0001-88"

    def test_formatacao_entrada_minuscula(self) -> None:
        formatado = formatar_cnpj("ab12cd34000184")
        assert formatado == "AB.12C.D34/0001-84"

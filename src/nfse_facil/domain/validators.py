"""Módulo de validação e formatação de identificadores fiscais.

Implementa suporte a:
- CNPJ numérico tradicional (legado);
- CNPJ alfanumérico (conforme padrão oficial da Receita Federal do Brasil / IN RFB nº 2.229/2024);
- Tratamento estrito como string (zeros à esquerda preservados, sem conversão para int);
- Máscara visual padrão: XX.XXX.XXX/XXXX-XX.
"""

import re
from typing import Final
import unicodedata
from nfse_facil.domain.exceptions import CNPJInvalidoError

PESOS_DV1: Final[list[int]] = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
PESOS_DV2: Final[list[int]] = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

# Caracteres permitidos para máscara usual de entrada
RE_MASCARA_CARACTERES = re.compile(r"[\.\-\/\s]")


def sanitizar_cnpj(cnpj: str) -> str:
    """Remove caracteres de máscara e normaliza letras para maiúsculas.

    Preserva zeros à esquerda e mantém o CNPJ exclusivamente como string.
    """
    if not isinstance(cnpj, str):
        raise TypeError(f"CNPJ deve ser uma string, recebido: {type(cnpj).__name__}")
    limpo = RE_MASCARA_CARACTERES.sub("", cnpj.strip()).upper()
    return limpo


def calcular_digitos_verificadores(raiz_ordem_12: str) -> tuple[int, int]:
    """Calcula os dois dígitos verificadores (DVs) de um CNPJ (numérico ou alfanumérico).

    Utiliza o algoritmo oficial Módulo 11 com pesos de 2 a 9 e valor numérico
    baseado na tabela ASCII (ord(c) - 48), suportando '0'-'9' (0-9) e 'A'-'Z' (17-42).
    """
    if len(raiz_ordem_12) != 12:
        raise ValueError("A base para cálculo do DV de CNPJ deve conter exatamente 12 caracteres.")

    # 1º Dígito Verificador
    soma1 = sum((ord(char) - 48) * peso for char, peso in zip(raiz_ordem_12, PESOS_DV1))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 in (0, 1) else (11 - resto1)

    # 2º Dígito Verificador (inclui o 1º DV)
    base_dv2 = raiz_ordem_12 + str(dv1)
    soma2 = sum((ord(char) - 48) * peso for char, peso in zip(base_dv2, PESOS_DV2))
    resto2 = soma2 % 11
    dv2 = 0 if resto2 in (0, 1) else (11 - resto2)

    return dv1, dv2


ASCII_DIGITS: Final[set[str]] = set("0123456789")
ASCII_ALPHANUMERIC_UPPER: Final[set[str]] = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def validar_cnpj(cnpj: str) -> bool:
    """Valida um CNPJ numérico legado ou alfanumérico.

    Regras estritas:
    1. Deve ser do tipo string.
    2. Após remoção da máscara usual, deve conter exatamente 14 caracteres.
    3. As 12 primeiras posições aceitam exclusivamente dígitos ASCII (0-9) e letras ASCII (A-Z).
    4. As 2 últimas posições (DVs) aceitam exclusivamente dígitos ASCII (0-9).
    5. Nenhum caractere numérico ou alfabético Unicode não-ASCII é aceito.
    6. Não permite sequências com todos os 14 caracteres repetidos.
    7. Os dígitos verificadores calculados via Módulo 11 devem ser idênticos aos informados.
    """
    if not isinstance(cnpj, str):
        return False

    limpo = sanitizar_cnpj(cnpj)

    if len(limpo) != 14:
        return False

    # Não permite todos os caracteres repetidos (ex: "00000000000000", "AAAAAAAAAAAAAA")
    if len(set(limpo)) == 1:
        return False

    # As 12 primeiras posições devem ser estritamente ASCII 0-9 ou A-Z (sem caracteres Unicode)
    base = limpo[:12]
    if not all(c in ASCII_ALPHANUMERIC_UPPER for c in base):
        return False

    # Os 2 dígitos finais (DVs) devem ser estritamente dígitos ASCII 0-9
    dvs_informados = limpo[12:14]
    if not all(c in ASCII_DIGITS for c in dvs_informados):
        return False

    try:
        dv1, dv2 = calcular_digitos_verificadores(base)
    except ValueError:
        return False

    return f"{dv1}{dv2}" == dvs_informados


def validar_ou_falhar_cnpj(cnpj: str) -> str:
    """Valida o CNPJ e retorna a versão sanitizada de 14 caracteres.

    Levanta CNPJInvalidoError com mensagem amigável caso seja inválido.
    """
    if not isinstance(cnpj, str):
        raise CNPJInvalidoError("O CNPJ informado deve ser um texto.")

    limpo = sanitizar_cnpj(cnpj)

    if len(limpo) != 14:
        raise CNPJInvalidoError(
            f"O CNPJ deve conter exatamente 14 caracteres (recebido: {len(limpo)})."
        )

    if not validar_cnpj(limpo):
        raise CNPJInvalidoError(
            f"O CNPJ '{cnpj}' possui formato ou dígitos verificadores inválidos."
        )

    return limpo


def formatar_cnpj(cnpj: str) -> str:
    """Formata um CNPJ para o padrão visual XX.XXX.XXX/XXXX-XX.

    Preserva caracteres alfanuméricos e zeros à esquerda.
    """
    limpo = sanitizar_cnpj(cnpj)
    if len(limpo) != 14:
        return cnpj  # Retorna inalterado se o tamanho não for compatível com a máscara

    return f"{limpo[0:2]}.{limpo[2:5]}.{limpo[5:8]}/{limpo[8:12]}-{limpo[12:14]}"
 
 
def normalizar_para_busca(texto: str) -> str:
    """Normaliza uma string para pesquisa textual insensível a maiúsculas/minúsculas e acentos.

    Aplica casefold(), decompõe marcas diacríticas via NFKD e remove apenas caracteres de combinação.
    Não altera os dados originais armazenados ou exibidos.
    """
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


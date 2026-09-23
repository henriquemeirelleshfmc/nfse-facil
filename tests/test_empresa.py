"""Testes para o modelo Empresa e garantia de segurança de dados."""

from pathlib import Path
import pytest

from nfse_facil.domain.exceptions import CNPJInvalidoError, ValidacaoError
from nfse_facil.domain.models import Empresa


class TestEmpresaModel:
    """Validações da entidade Empresa."""

    def test_rejeicao_razao_social_vazia(self) -> None:
        with pytest.raises(ValidacaoError, match="Razão Social da empresa não pode ser vazia"):
            Empresa(
                razao_social="",
                cnpj="00.000.000/0001-91",
                pasta_documentos="/tmp/docs",
            )

    def test_rejeicao_razao_social_somente_espacos(self) -> None:
        with pytest.raises(ValidacaoError, match="Razão Social da empresa não pode ser vazia"):
            Empresa(
                razao_social="     ",
                cnpj="00.000.000/0001-91",
                pasta_documentos="/tmp/docs",
            )

    def test_rejeicao_pasta_documentos_vazia(self) -> None:
        with pytest.raises(ValidacaoError, match="pasta de documentos"):
            Empresa(
                razao_social="Empresa Valida Ltda",
                cnpj="00.000.000/0001-91",
                pasta_documentos="",
            )

        with pytest.raises(ValidacaoError, match="pasta de documentos"):
            Empresa(
                razao_social="Empresa Valida Ltda",
                cnpj="00.000.000/0001-91",
                pasta_documentos="   ",
            )

    def test_aceitacao_e_normalizacao_pasta_como_str_e_path(self) -> None:
        # Aceita str e normaliza para Path
        emp_str = Empresa(
            razao_social="Empresa Pasta Str Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos="C:\\Docs\\Empresa",
        )
        assert isinstance(emp_str.pasta_documentos, Path)

        # Aceita Path diretamente
        emp_path = Empresa(
            razao_social="Empresa Pasta Path Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=Path("C:\\Docs\\Empresa"),
        )
        assert isinstance(emp_path.pasta_documentos, Path)

    def test_criacao_empresa_com_cnpj_numerico(self) -> None:
        empresa = Empresa(
            razao_social="Empresa Modelo Contábil Ltda",
            nome_fantasia="Modelo Contábil",
            cnpj="00.000.000/0001-91",
            pasta_documentos=Path("/tmp/docs"),
        )
        assert empresa.razao_social == "Empresa Modelo Contábil Ltda"
        assert empresa.nome_fantasia == "Modelo Contábil"
        assert empresa.cnpj == "00000000000191"  # Normalizado e armazenado como string
        assert empresa.cnpj_formatado == "00.000.000/0001-91"
        assert empresa.nome_exibicao == "Modelo Contábil"
        assert isinstance(empresa.pasta_documentos, Path)
        assert empresa.ativo is True

    def test_criacao_empresa_com_cnpj_alfanumerico(self) -> None:
        empresa = Empresa(
            razao_social="Empresa Tech Alfa Ltda",
            cnpj="12.ABC.345/0001-88",
            pasta_documentos="/tmp/tech",
        )
        assert empresa.cnpj == "12ABC345000188"
        assert empresa.cnpj_formatado == "12.ABC.345/0001-88"
        assert empresa.nome_exibicao == "Empresa Tech Alfa Ltda"  # Sem fantasia usa a razão
        assert isinstance(empresa.pasta_documentos, Path)

    def test_rejeicao_empresa_com_cnpj_invalido(self) -> None:
        with pytest.raises(CNPJInvalidoError):
            Empresa(
                razao_social="Empresa Invalida Ltda",
                cnpj="12.345.678/0001-99",  # DV incorreto
                pasta_documentos=Path("/tmp/invalida"),
            )

    def test_garantia_de_seguranca_ausencia_de_campo_de_senha(self) -> None:
        """CRÍTICO: Garante que a entidade jamais possua atributos para armazenamento de senha."""
        empresa = Empresa(
            razao_social="Segurança Total Ltda",
            cnpj="33.000.167/0001-01",
            pasta_documentos=Path("/tmp/docs"),
        )
        # Nenhuma variação de campo de senha deve existir no modelo
        atributos_proibidos = [
            "senha",
            "password",
            "senha_certificado",
            "cert_password",
            "segredo",
            "secret",
        ]
        for attr in atributos_proibidos:
            assert not hasattr(empresa, attr), f"Atributo sensível '{attr}' não deve existir no modelo Empresa!"

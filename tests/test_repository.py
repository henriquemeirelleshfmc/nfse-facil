"""Testes para o repositório em memória InMemoryEmpresaRepository."""

from pathlib import Path
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.repositories.in_memory import (
    InMemoryEmpresaRepository,
    carregar_dados_demonstracao_opcional,
)


class TestInMemoryEmpresaRepository:
    """Valida o ciclo de vida do repositório em memória."""

    def test_repositorio_inicia_vazio_por_padrao(self) -> None:
        """Garante que a inicialização padrão não possua empresas pré-carregadas."""
        repo = InMemoryEmpresaRepository()
        assert len(repo.listar_todas()) == 0

    def test_salvar_e_obter_empresa(self) -> None:
        repo = InMemoryEmpresaRepository()
        empresa = Empresa(
            razao_social="Supermercado Alvorada Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=Path("/tmp/alvorada"),
        )
        repo.salvar(empresa)

        # Busca por ID
        encontrada = repo.obter_por_id(empresa.id)
        assert encontrada is not None
        assert encontrada.razao_social == "Supermercado Alvorada Ltda"

        # Busca por CNPJ formatado e não formatado
        assert repo.obter_por_cnpj("00000000000191") == empresa
        assert repo.obter_por_cnpj("00.000.000/0001-91") == empresa

    def test_pesquisa_por_nome_e_cnpj(self) -> None:
        repo = InMemoryEmpresaRepository()
        emp1 = Empresa(
            razao_social="Oficina Central",
            nome_fantasia="Auto Peças Central",
            cnpj="00.000.000/0001-91",
            pasta_documentos=Path("/tmp/1"),
        )
        emp2 = Empresa(
            razao_social="Padaria e Confeitaria Estrela",
            cnpj="12.ABC.345/0001-88",
            pasta_documentos=Path("/tmp/2"),
        )
        repo.salvar(emp1)
        repo.salvar(emp2)

        # Pesquisa por nome fantasia
        res_fantasia = repo.pesquisar("Auto Peças")
        assert len(res_fantasia) == 1
        assert res_fantasia[0] == emp1

        # Pesquisa por razão social
        res_razao = repo.pesquisar("Estrela")
        assert len(res_razao) == 1
        assert res_razao[0] == emp2

        # Pesquisa por CNPJ alfanumérico
        res_cnpj = repo.pesquisar("12ABC")
        assert len(res_cnpj) == 1
        assert res_cnpj[0] == emp2

        # Pesquisa vazia retorna todas
        assert len(repo.pesquisar("")) == 2

    def test_pesquisa_insensivel_a_acentos_alvaro(self) -> None:
        """Garante que no repositório em memória a busca por Álvaro ignore acentuação e caixa."""
        repo = InMemoryEmpresaRepository()
        emp = Empresa(
            razao_social="Álvaro Engenharia e Construções Ltda",
            nome_fantasia="Engenharia Álvaro",
            cnpj="00.000.000/0001-91",
            pasta_documentos=Path("/tmp/alvaro"),
        )
        repo.salvar(emp)

        for termo in ("Álvaro", "álvaro", "ÁLVARO", "alvaro", "alvar"):
            res = repo.pesquisar(termo)
            assert len(res) == 1, f"Falha na busca em memória por '{termo}'"
            assert res[0] == emp

    def test_remover_empresa(self) -> None:
        repo = InMemoryEmpresaRepository()
        emp = Empresa(
            razao_social="Empresa Temporaria",
            cnpj="33.000.167/0001-01",
            pasta_documentos=Path("/tmp/temp"),
        )
        repo.salvar(emp)
        assert len(repo.listar_todas()) == 1

        sucesso = repo.remover(emp.id)
        assert sucesso is True
        assert len(repo.listar_todas()) == 0

        # Tentativa de remover ID inexistente
        assert repo.remover("id-inexistente") is False

    def test_dados_demonstracao_apenas_quando_chamado_explicitamente(self) -> None:
        repo = InMemoryEmpresaRepository()
        assert len(repo.listar_todas()) == 0
        carregar_dados_demonstracao_opcional(repo, Path("/tmp"))
        assert len(repo.listar_todas()) == 2

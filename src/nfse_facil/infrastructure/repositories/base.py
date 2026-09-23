"""Contrato abstrato para o repositório de empresas."""

from abc import ABC, abstractmethod
from nfse_facil.domain.models import Empresa


class EmpresaRepository(ABC):
    """Interface abstrata definindo as operações de persistência de empresas.

    Na Etapa 01, este contrato é implementado em memória (InMemoryEmpresaRepository).
    Em etapas futuras, será implementado sobre SQLite sem quebrar o domínio ou a interface.
    """

    @abstractmethod
    def listar_todas(self) -> list[Empresa]:
        """Retorna todas as empresas cadastradas."""

    @abstractmethod
    def obter_por_id(self, empresa_id: str) -> Empresa | None:
        """Busca uma empresa pelo seu identificador único."""

    @abstractmethod
    def obter_por_cnpj(self, cnpj: str) -> Empresa | None:
        """Busca uma empresa pelo seu CNPJ."""

    @abstractmethod
    def salvar(self, empresa: Empresa) -> None:
        """Insere ou atualiza uma empresa no repositório."""

    @abstractmethod
    def remover(self, empresa_id: str) -> bool:
        """Remove uma empresa pelo seu identificador único. Retorna True se removida."""

    @abstractmethod
    def pesquisar(self, termo: str) -> list[Empresa]:
        """Pesquisa empresas que contenham o termo na Razão Social, Nome Fantasia ou CNPJ."""

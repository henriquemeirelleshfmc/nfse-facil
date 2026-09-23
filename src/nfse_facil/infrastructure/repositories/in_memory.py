"""Implementação em memória do repositório de empresas.

Inicia rigorosamente vazio por padrão para demonstrar o estado vazio real da interface.
"""

from pathlib import Path
from nfse_facil.domain.models import Empresa
from nfse_facil.domain.validators import normalizar_para_busca, sanitizar_cnpj
from nfse_facil.infrastructure.repositories.base import EmpresaRepository


class InMemoryEmpresaRepository(EmpresaRepository):
    """Repositório de empresas mantido em memória durante a execução."""

    def __init__(self) -> None:
        # Inicia rigorosamente vazio na execução normal da aplicação
        self._empresas: dict[str, Empresa] = {}

    def listar_todas(self) -> list[Empresa]:
        """Retorna todas as empresas cadastradas ordenadas por nome de exibição."""
        return sorted(self._empresas.values(), key=lambda e: normalizar_para_busca(e.nome_exibicao))

    def obter_por_id(self, empresa_id: str) -> Empresa | None:
        """Busca uma empresa pelo identificador único."""
        return self._empresas.get(empresa_id)

    def obter_por_cnpj(self, cnpj: str) -> Empresa | None:
        """Busca uma empresa pelo CNPJ (sanitizado)."""
        cnpj_limpo = sanitizar_cnpj(cnpj)
        for empresa in self._empresas.values():
            if empresa.cnpj == cnpj_limpo:
                return empresa
        return None

    def salvar(self, empresa: Empresa) -> None:
        """Insere ou atualiza uma empresa."""
        self._empresas[empresa.id] = empresa

    def remover(self, empresa_id: str) -> bool:
        """Remove a empresa caso exista. Retorna True em caso de sucesso."""
        if empresa_id in self._empresas:
            del self._empresas[empresa_id]
            return True
        return False

    def pesquisar(self, termo: str) -> list[Empresa]:
        """Filtra empresas por nome ou CNPJ com normalização Unicode consistente."""
        termo_limpo = termo.strip()
        if not termo_limpo:
            return self.listar_todas()

        termo_norm = normalizar_para_busca(termo_limpo)
        try:
            termo_cnpj = sanitizar_cnpj(termo_limpo).casefold()
        except Exception:
            termo_cnpj = ""

        resultados: list[Empresa] = []
        for empresa in self.listar_todas():
            # Casamento por nome, razão social ou CNPJ (com ou sem máscara)
            match_razao = termo_norm in normalizar_para_busca(empresa.razao_social)
            match_fantasia = bool(
                empresa.nome_fantasia and termo_norm in normalizar_para_busca(empresa.nome_fantasia)
            )
            match_mascara = termo_norm in normalizar_para_busca(empresa.cnpj_formatado)
            match_cnpj = bool(termo_cnpj and termo_cnpj in empresa.cnpj.casefold())

            if match_razao or match_fantasia or match_mascara or match_cnpj:
                resultados.append(empresa)

        return resultados


def carregar_dados_demonstracao_opcional(
    repo: InMemoryEmpresaRepository, pasta_base: Path
) -> None:
    """Função utilitária de demonstração EXPLICITAMENTE SEPARADA e DESATIVADA por padrão.

    Só deve ser chamada quando explicitamente solicitado em ambientes de teste manual.
    """
    empresa_demo_1 = Empresa(
        razao_social="Oficina Mecânica Modelo Ltda",
        nome_fantasia="Auto Mecânica Modelo",
        cnpj="00000000000191",  # CNPJ numérico válido com zeros à esquerda
        pasta_documentos=pasta_base / "Auto Mecanica Modelo",
    )
    empresa_demo_2 = Empresa(
        razao_social="Inovação e Tecnologia Alfa S/A",
        nome_fantasia="Alfa Tech",
        cnpj="12ABC345000188",  # CNPJ alfanumérico válido
        pasta_documentos=pasta_base / "Alfa Tech",
    )
    repo.salvar(empresa_demo_1)
    repo.salvar(empresa_demo_2)

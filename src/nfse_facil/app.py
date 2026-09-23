"""Ponto de entrada e ciclo de vida da aplicação NFS-e Fácil."""

import customtkinter as ctk

from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository
from nfse_facil.ui.main_window import MainWindow


def create_app(repository: EmpresaRepository | None = None) -> MainWindow:
    """Instancia e inicializa a aplicação desktop.

    Na execução normal da aplicação, utiliza SqliteEmpresaRepository com o caminho
    padrão do usuário (%LOCALAPPDATA%).
    Permite injeção de repositório alternativo para testes e demonstrações.
    """
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    repo_ativo = repository if repository is not None else SqliteEmpresaRepository()

    app = MainWindow(repository=repo_ativo)
    return app


def main() -> None:
    """Função principal executada pelo script de entrada ou linha de comando."""
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()

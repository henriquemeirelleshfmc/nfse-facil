"""Configurações centrais da aplicação NFS-e Fácil.

Todos os caminhos utilizam pathlib.Path e são portáteis entre ambientes,
evitando quaisquer caminhos fixos de máquina ou usuário.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Configurações imutáveis da aplicação."""

    app_name: str = "NFS-e Fácil"
    app_version: str = "0.6.0"
    app_description: str = "Gerenciador simplificado de NFS-e para contadores e empresas"

    # Diretório base do usuário para armazenamento de documentos
    base_user_dir: Path = field(default_factory=lambda: Path.home())

    # Caminho customizado para banco de dados (injetável em testes)
    custom_db_path: Path | None = None

    @property
    def default_docs_dir(self) -> Path:
        """Retorna o diretório padrão sugerido para documentos das empresas."""
        docs_pt = self.base_user_dir / "Documentos" / "NFSe-Facil"
        docs_en = self.base_user_dir / "Documents" / "NFSe-Facil"
        return docs_pt if (self.base_user_dir / "Documentos").exists() else docs_en

    @property
    def app_data_dir(self) -> Path:
        """Retorna o diretório padrão para dados locais da aplicação."""
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app and local_app.strip():
            return Path(local_app) / "NFSeFacil"
        return self.base_user_dir / ".nfse_facil"

    @property
    def default_db_path(self) -> Path:
        """Caminho do banco de dados SQLite oficial da aplicação."""
        return self.app_data_dir / "data" / "nfse_facil.db"

    @property
    def db_path(self) -> Path:
        """Retorna o caminho do banco de dados (customizado ou padrão)."""
        return self.custom_db_path if self.custom_db_path is not None else self.default_db_path

    def garantir_diretorios_banco(self) -> Path:
        """Garante que a estrutura de diretórios do banco exista no disco."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return self.db_path


_settings_instance: Settings | None = None


def get_settings(custom_db_path: Path | None = None) -> Settings:
    """Retorna a instância singleton de configurações ou uma nova com db customizado."""
    global _settings_instance
    if custom_db_path is not None:
        return Settings(custom_db_path=custom_db_path)
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

"""Validação da versão da aplicação e alinhamento com metadados do pacote."""

from pathlib import Path
import tomllib

from nfse_facil import __version__
from nfse_facil.config.settings import get_settings


def test_versao_aplicacao_consistente_e_alinhada() -> None:
    """Garante que __version__, Settings.app_version e pyproject.toml estejam rigorosamente em 0.6.0."""
    versao_esperada = "0.6.0"

    # 1. Versão do módulo raiz
    assert __version__ == versao_esperada

    # 2. Versão das configurações
    settings = get_settings()
    assert settings.app_version == versao_esperada
    assert settings.app_version == __version__

    # 3. Versão declarada no pyproject.toml
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml deve existir na raiz do projeto"

    with open(pyproject_path, "rb") as f:
        dados_toml = tomllib.load(f)

    versao_toml = dados_toml.get("project", {}).get("version")
    assert versao_toml == versao_esperada

"""Configuração global do pytest para testes de interface gráfica e ambiente."""

import os
import sys
from pathlib import Path
from typing import Generator
import pytest

# Garante localização correta das bibliotecas Tcl/Tk no Windows
tcl_path = Path(sys.prefix) / "tcl" / "tcl8.6"
tk_path = Path(sys.prefix) / "tcl" / "tk8.6"
if tcl_path.exists() and "TCL_LIBRARY" not in os.environ:
    os.environ["TCL_LIBRARY"] = str(tcl_path)
if tk_path.exists() and "TK_LIBRARY" not in os.environ:
    os.environ["TK_LIBRARY"] = str(tk_path)


@pytest.fixture(scope="session")
def app() -> Generator:
    """Instância única de MainWindow para toda a suite de testes, garantindo estabilidade no Windows."""
    from nfse_facil.app import create_app

    application = create_app()
    application.update_idletasks()
    application.update()
    yield application
    try:
        application.destroy()
    except Exception:
        pass

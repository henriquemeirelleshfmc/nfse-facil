"""Controlador assíncrono reutilizável para inspeção de certificados digitais A1."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable
import customtkinter as ctk

from nfse_facil.domain.certificate_models import CertificadoInfo
from nfse_facil.domain.exceptions import CertificadoError
from nfse_facil.services.pkcs12 import Pkcs12CertificadoService
from nfse_facil.ui.messages import MSG_ERRO_GENERICO_CERTIFICADO


class AsyncCertificateInspector:
    """Gerencia a inspeção assíncrona de certificados mantendo a UI responsiva e segura.

    Garantias:
    - Leitura e processamento criptográfico executados em ThreadPoolExecutor secundário;
    - Nenhuma operação Tkinter fora da thread principal;
    - Descarte imediato da senha da memória local do worker em bloco finally;
    - Mensagens de erro de exceções inesperadas substituídas por mensagem genérica amigável;
    - Monitoramento na thread principal via polling não bloqueante com after();
    - Encerramento limpo sem callbacks em widgets destruídos.
    """

    def __init__(
        self,
        widget: Any,
        cert_service: Pkcs12CertificadoService | None = None,
    ) -> None:
        self.widget = widget
        self.cert_service = cert_service or Pkcs12CertificadoService()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._processando = False
        self._destruido = False
        self._after_id: str | None = None

    @property
    def processando(self) -> bool:
        """Indica se há uma operação de inspeção em andamento."""
        return self._processando

    def iniciar(
        self,
        caminho: Path,
        senha: str,
        on_resultado: Callable[[CertificadoInfo | None, str | None], None],
    ) -> bool:
        """Inicia a inspeção assíncrona. Retorna False se já estiver processando ou destruído."""
        if self._processando or self._destruido:
            return False

        self._processando = True

        def worker(senha_op: str) -> tuple[CertificadoInfo | None, str | None]:
            """Worker executado na thread de fundo sem nenhum acesso ao Tkinter."""
            try:
                info = self.cert_service.inspecionar(caminho, senha_op)
                return info, None
            except CertificadoError as err:
                return None, str(err)
            except Exception:
                # Oculta detalhes técnicos internos e segredos da interface
                return None, MSG_ERRO_GENERICO_CERTIFICADO
            finally:
                del senha_op

        futuro = self._executor.submit(worker, senha)

        def _checar_conclusao() -> None:
            """Executado periodicamente na thread principal via after()."""
            if self._destruido:
                return
            try:
                if hasattr(self.widget, "winfo_exists") and not self.widget.winfo_exists():
                    return
            except Exception:
                return

            if futuro.done():
                self._after_id = None
                self._processando = False
                try:
                    info, erro = futuro.result()
                except Exception:
                    info, erro = None, MSG_ERRO_GENERICO_CERTIFICADO
                on_resultado(info, erro)
            else:
                self._after_id = self.widget.after(30, _checar_conclusao)

        self._after_id = self.widget.after(10, _checar_conclusao)
        return True

    def encerrar(self) -> None:
        """Cancela timers pendentes e desativa o executor com segurança."""
        self._destruido = True
        self._processando = False
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

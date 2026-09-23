"""Diagnóstico local sanitizado para facilitar atendimento ao usuário."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from threading import Lock

from nfse_facil.config.settings import get_settings


_LOCK = Lock()
_LIMITE_LOG_BYTES = 1024 * 1024


@dataclass(frozen=True)
class DiagnosticoPublico:
    codigo: str
    categoria: str
    ocorrido_em: datetime
    versao: str

    @property
    def texto_para_copiar(self) -> str:
        return (
            "NFS-e Fácil - informações de suporte\n"
            f"Código: {self.codigo}\n"
            f"Categoria: {self.categoria}\n"
            f"Data: {self.ocorrido_em.astimezone().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Versão: {self.versao}"
        )


def registrar_falha(categoria: str, erro: BaseException) -> DiagnosticoPublico:
    """Registra somente metadados seguros; nunca persiste a mensagem da exceção."""
    settings = get_settings()
    ocorrido_em = datetime.now(timezone.utc)
    diagnostico = DiagnosticoPublico(
        codigo=f"NFSE-{secrets.token_hex(3).upper()}",
        categoria=_categoria_segura(categoria),
        ocorrido_em=ocorrido_em,
        versao=settings.app_version,
    )
    registro = {
        "codigo": diagnostico.codigo,
        "categoria": diagnostico.categoria,
        "ocorrido_em_utc": ocorrido_em.isoformat(),
        "versao": diagnostico.versao,
        "tipo_erro": type(erro).__name__,
    }
    try:
        pasta = settings.app_data_dir / "logs"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / "diagnosticos.jsonl"
        with _LOCK:
            if caminho.exists() and caminho.stat().st_size >= _LIMITE_LOG_BYTES:
                anterior = pasta / "diagnosticos-anterior.jsonl"
                caminho.replace(anterior)
            with caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(registro, ensure_ascii=True) + "\n")
    except OSError:
        # O código continua útil na tela mesmo se o disco não aceitar o log.
        pass
    return diagnostico


def _categoria_segura(valor: str) -> str:
    permitido = "".join(c for c in str(valor) if c.isascii() and (c.isalnum() or c in "_-"))
    return permitido[:40] or "erro_aplicativo"

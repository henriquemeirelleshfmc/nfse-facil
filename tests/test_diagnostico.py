"""Testes do diagnóstico sanitizado usado no atendimento ao usuário."""

import json
from pathlib import Path

from nfse_facil.services.diagnostico import registrar_falha


def test_diagnostico_gera_codigo_e_nao_grava_mensagem_sensivel(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    segredo = "SENHA_CERTIFICADO_SUPER_SECRETA"

    diagnostico = registrar_falha("consulta_adn", RuntimeError(segredo))

    assert diagnostico.codigo.startswith("NFSE-")
    assert segredo not in diagnostico.texto_para_copiar
    caminho = tmp_path / "NFSeFacil" / "logs" / "diagnosticos.jsonl"
    conteudo = caminho.read_text(encoding="utf-8")
    assert segredo not in conteudo
    registro = json.loads(conteudo.splitlines()[-1])
    assert registro["tipo_erro"] == "RuntimeError"
    assert registro["categoria"] == "consulta_adn"


def test_categoria_do_diagnostico_e_restrita_a_ascii(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    diagnostico = registrar_falha("consulta/../../segredo ç", ValueError("interno"))
    assert diagnostico.categoria == "consultasegredo"

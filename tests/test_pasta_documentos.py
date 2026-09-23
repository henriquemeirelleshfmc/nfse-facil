"""Testes para o serviço PastaDocumentosService."""

from pathlib import Path
from unittest.mock import patch
import pytest

from nfse_facil.domain.exceptions import PastaInvalidaError
from nfse_facil.services.pasta_documentos import PastaDocumentosService


class TestPastaDocumentosService:
    """Validação de criação e integridade de diretórios de documentos."""

    def test_criacao_pasta_inexistente(self, tmp_path: Path) -> None:
        nova_pasta = tmp_path / "clientes" / "empresa_teste"
        assert not nova_pasta.exists()

        criada = PastaDocumentosService.validar_e_preparar_pasta(nova_pasta)
        assert criada.exists()
        assert criada.is_dir()

    def test_idempotencia_e_preservacao_conteudo_existente(self, tmp_path: Path) -> None:
        pasta_existente = tmp_path / "minha_empresa"
        pasta_existente.mkdir()

        # Cria um arquivo existente simulando arquivo prévio do usuário
        arquivo_usuario = pasta_existente / "nota_existente.txt"
        arquivo_usuario.write_text("conteudo importante do usuario", encoding="utf-8")

        # Chama a validação da pasta
        retorno = PastaDocumentosService.validar_e_preparar_pasta(pasta_existente)
        assert retorno == pasta_existente
        # Garante que o arquivo NÃO foi apagado nem modificado
        assert arquivo_usuario.exists()
        assert arquivo_usuario.read_text(encoding="utf-8") == "conteudo importante do usuario"

    def test_rejeicao_caminho_que_eh_arquivo_e_nao_diretorio(self, tmp_path: Path) -> None:
        arquivo_colisao = tmp_path / "nao_eh_pasta.txt"
        arquivo_colisao.write_text("arquivo", encoding="utf-8")

        with pytest.raises(PastaInvalidaError, match="é um arquivo, não uma pasta"):
            PastaDocumentosService.validar_e_preparar_pasta(arquivo_colisao)

    def test_rejeicao_caminho_vazio_ou_nulo(self) -> None:
        with pytest.raises(PastaInvalidaError, match="deve ser informada"):
            PastaDocumentosService.validar_e_preparar_pasta(None)  # type: ignore

        with pytest.raises(PastaInvalidaError, match="não pode ser vazio"):
            PastaDocumentosService.validar_e_preparar_pasta("")

        with pytest.raises(PastaInvalidaError, match="não pode ser vazio"):
            PastaDocumentosService.validar_e_preparar_pasta("   ")

    def test_tratamento_falha_de_permissao_simulada(self, tmp_path: Path) -> None:
        pasta_alvo = tmp_path / "pasta_sem_permissao"

        with patch.object(Path, "mkdir", side_effect=PermissionError("Acesso negado")):
            with pytest.raises(PastaInvalidaError, match="Sem permissão de acesso"):
                PastaDocumentosService.validar_e_preparar_pasta(pasta_alvo)

    def test_teste_gravacao_sucesso_nao_deixa_residuos(self, tmp_path: Path) -> None:
        """Garante que a execução com sucesso não deixa nenhum arquivo .perm_check_* no diretório."""
        pasta = tmp_path / "pasta_ok"
        PastaDocumentosService.validar_e_preparar_pasta(pasta)
        assert pasta.exists()
        residuos = list(pasta.glob(".perm_check_*"))
        assert len(residuos) == 0

    def test_falha_escrita_levanta_pastainvalidaerror_sem_residuos(self, tmp_path: Path) -> None:
        """Se o open exclusivo falhar por falta de permissão, levanta erro e não cria resíduos."""
        pasta = tmp_path / "pasta_escrita_bloqueada"
        pasta.mkdir()

        with patch("builtins.open", side_effect=PermissionError("Permissão negada")):
            with pytest.raises(PastaInvalidaError, match="Sem permissão de gravação"):
                PastaDocumentosService._testar_gravacao(pasta)

        residuos = list(pasta.glob(".perm_check_*"))
        assert len(residuos) == 0

    def test_escrita_sucesso_mas_falha_limpeza_levanta_erro(self, tmp_path: Path) -> None:
        """Se a escrita funcionar mas a remoção do arquivo de teste falhar,

        deve levantar PastaInvalidaError pois deixar resíduos não é sucesso.
        """
        pasta = tmp_path / "pasta_falha_limpeza"
        pasta.mkdir()

        arquivo_criado_ref: list[Path] = []
        real_unlink = Path.unlink

        def mock_unlink(self_path: Path, missing_ok: bool = False):
            if ".perm_check_" in self_path.name:
                arquivo_criado_ref.append(self_path)
                raise PermissionError("Falha simulada na remoção do arquivo temporário")
            return real_unlink(self_path, missing_ok=missing_ok)

        try:
            with patch.object(Path, "unlink", side_effect=mock_unlink):
                with pytest.raises(PastaInvalidaError, match="falhou ao remover o arquivo temporário"):
                    PastaDocumentosService._testar_gravacao(pasta)
        finally:
            import os
            for arq in pasta.glob(".perm_check_*"):
                try:
                    os.unlink(arq)
                except Exception:
                    pass

        residuos = list(pasta.glob(".perm_check_*"))
        assert len(residuos) == 0

    def test_falha_escrita_e_falha_limpeza_preserva_causa_original(self, tmp_path: Path) -> None:
        """Se ocorrer erro ao gravar e a limpeza também falhar,

        preserva a causa original na cadeia e registra a falha na mensagem.
        """
        pasta = tmp_path / "pasta_falha_dupla"
        pasta.mkdir()

        arquivo_criado_ref: list[Path] = []
        real_unlink = Path.unlink
        real_open = open

        def mock_unlink(self_path: Path, missing_ok: bool = False):
            if ".perm_check_" in self_path.name:
                raise OSError("Falha ao remover temporário")
            return real_unlink(self_path, missing_ok=missing_ok)

        class WrapperFile:
            def __init__(self, real_file):
                self.real_file = real_file

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.real_file.close()
                return False

            def write(self, data):
                raise OSError("Disco cheio ao escrever")

            def flush(self):
                pass

        def mock_open(path, *args, **kwargs):
            f = real_open(path, *args, **kwargs)
            arquivo_criado_ref.append(Path(path))
            return WrapperFile(f)

        try:
            with patch("builtins.open", side_effect=mock_open):
                with patch.object(Path, "unlink", side_effect=mock_unlink):
                    with pytest.raises(PastaInvalidaError, match="Falha na grava.*e na remo") as exc_info:
                        PastaDocumentosService._testar_gravacao(pasta)

            # Causa original é preservada
            assert isinstance(exc_info.value.__cause__, OSError)
            assert "Disco cheio" in str(exc_info.value.__cause__)
        finally:
            for arq in arquivo_criado_ref:
                if arq.exists():
                    real_unlink(arq)

        residuos = list(pasta.glob(".perm_check_*"))
        assert len(residuos) == 0


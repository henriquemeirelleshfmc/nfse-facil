"""Serviço para validação e criação segura da pasta de documentos de empresas."""

from pathlib import Path
import uuid
from nfse_facil.domain.exceptions import PastaInvalidaError


class PastaDocumentosService:
    """Serviço independente para gestão e integridade do diretório de documentos."""

    @staticmethod
    def _testar_gravacao(diretorio: Path) -> None:
        """Testa gravação real através de criação exclusiva e remoção imediata de arquivo temporário.

        Garante que nenhum resíduo permaneça no diretório e reporta falhas de escrita e limpeza.
        """
        nome_arquivo = f".perm_check_{uuid.uuid4().hex}"
        arquivo_teste = diretorio / nome_arquivo
        arquivo_criado = False
        erro_escrita: Exception | None = None

        try:
            with open(arquivo_teste, mode="x", encoding="utf-8") as f:
                arquivo_criado = True
                f.write("teste_permissao_nfse_facil")
                f.flush()
        except PermissionError as err:
            erro_escrita = err
            raise PastaInvalidaError(
                f"Sem permissão de gravação na pasta de documentos '{diretorio}'."
            ) from err
        except OSError as err:
            erro_escrita = err
            raise PastaInvalidaError(
                f"Não foi possível gravar arquivo de teste na pasta '{diretorio}': {err.strerror or err}"
            ) from err
        finally:
            if arquivo_criado:
                try:
                    if arquivo_teste.exists():
                        arquivo_teste.unlink()
                except Exception as err_limpeza:
                    if erro_escrita:
                        raise PastaInvalidaError(
                            f"Falha na gravação ({erro_escrita}) e na remoção do arquivo temporário ({err_limpeza}) em '{diretorio}'."
                        ) from erro_escrita
                    raise PastaInvalidaError(
                        f"O teste de escrita foi concluído, mas falhou ao remover o arquivo temporário de teste em '{diretorio}': {err_limpeza}"
                    ) from err_limpeza

    @classmethod
    def validar_e_preparar_pasta(cls, pasta: Path | str) -> Path:
        """Valida, cria e testa a capacidade de gravação da pasta no sistema de arquivos.

        Regras:
        1. O caminho não pode ser vazio ou nulo.
        2. Se já existir, deve ser um diretório (não um arquivo).
        3. Se não existir, é criado com tratamento de permissão e erros de SO.
        4. Conteúdo preexistente jamais é apagado ou sobrescrito.
        5. A capacidade de gravação é verificada na prática sem deixar resíduos.
        """
        if pasta is None:
            raise PastaInvalidaError("A pasta de documentos deve ser informada.")

        pasta_str = str(pasta).strip()
        if not pasta_str:
            raise PastaInvalidaError("O caminho da pasta de documentos não pode ser vazio.")

        try:
            caminho = Path(pasta_str)
        except Exception as err:
            raise PastaInvalidaError(
                f"O caminho informado para a pasta de documentos é inválido: '{pasta_str}'"
            ) from err

        # 1. Verifica colisão com arquivo existente que não seja diretório
        try:
            if caminho.exists() and not caminho.is_dir():
                raise PastaInvalidaError(
                    f"O caminho selecionado já existe e é um arquivo, não uma pasta: '{caminho}'"
                )
        except PermissionError as err:
            raise PastaInvalidaError(
                f"Sem permissão para verificar a pasta de documentos em '{caminho}'."
            ) from err

        # 2. Cria a pasta caso ainda não exista
        if not caminho.exists():
            try:
                caminho.mkdir(parents=True, exist_ok=True)
            except PermissionError as err:
                raise PastaInvalidaError(
                    f"Sem permissão de acesso para criar a pasta de documentos em '{caminho}'. "
                    "Verifique as permissões de usuário ou escolha outro local."
                ) from err
            except OSError as err:
                raise PastaInvalidaError(
                    f"Não foi possível criar a pasta de documentos em '{caminho}': {err.strerror or err}"
                ) from err

        # 3. Teste prático de escrita e limpeza estrita
        cls._testar_gravacao(caminho)

        return caminho

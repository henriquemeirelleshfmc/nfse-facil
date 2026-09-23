"""Cliente HTTPS/mTLS da API ADN destinada a contribuintes.

O transporte usa ``requests-pkcs12``. A biblioteca converte o PKCS#12 para um
PEM temporário criptografado com senha aleatória apenas para carregar o contexto
TLS do sistema operacional e remove o arquivo em bloco ``finally``. A aplicação
não conhece o caminho temporário e não persiste senha, PKCS#12 ou chave privada.
"""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import requests
import requests_pkcs12

from nfse_facil.domain.adn_models import AmbienteADN, BASES_ADN, RespostaADN
from nfse_facil.domain.exceptions import (
    ADNAutenticacaoError,
    ADNConfiguracaoError,
    ADNConexaoError,
    ADNIndisponivelError,
    ADNLimiteRequisicoesError,
    ADNRespostaInvalidaError,
    ADNTimeoutError,
)
from nfse_facil.domain.validators import validar_ou_falhar_cnpj
from nfse_facil.services.pkcs12 import (
    LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES,
    ler_arquivo_com_limite,
)

RequestCallable = Callable[..., Any]


class ADNClient:
    """Executa somente consultas GET oficiais, sem gravar documentos em disco."""

    LIMITE_RESPOSTA_BYTES = 50 * 1024 * 1024
    TIMEOUT_PADRAO = (10, 60)

    def __init__(
        self,
        ambiente: AmbienteADN = AmbienteADN.PRODUCAO_RESTRITA,
        *,
        request_get: RequestCallable | None = None,
        timeout: tuple[int, int] = TIMEOUT_PADRAO,
        limite_resposta_bytes: int = LIMITE_RESPOSTA_BYTES,
    ) -> None:
        if ambiente not in BASES_ADN:
            raise ADNConfiguracaoError("O ambiente selecionado para a NFS-e Nacional é inválido.")
        if len(timeout) != 2 or any(not isinstance(v, int) or v <= 0 for v in timeout):
            raise ADNConfiguracaoError("O tempo limite da comunicação deve possuir valores positivos.")
        if not isinstance(limite_resposta_bytes, int) or limite_resposta_bytes <= 0:
            raise ADNConfiguracaoError("O limite da resposta deve ser maior que zero.")
        self.ambiente = ambiente
        self.base_url = BASES_ADN[ambiente]
        self.timeout = timeout
        self.limite_resposta_bytes = limite_resposta_bytes
        self._request_get = request_get or requests_pkcs12.get

    def consultar_dfe_por_nsu(
        self,
        nsu: int | str,
        certificado: Path | str,
        senha: str | bytes | None,
        *,
        cnpj_consulta: str | None = None,
        lote: bool = True,
    ) -> RespostaADN:
        """Consulta documentos por NSU sem interpretar ou persistir os XMLs retornados."""
        nsu_normalizado = self._validar_nsu(nsu)
        params: dict[str, str] = {"lote": "true" if lote else "false"}
        if cnpj_consulta is not None:
            params["cnpjConsulta"] = validar_ou_falhar_cnpj(cnpj_consulta)
        endpoint = f"/DFe/{nsu_normalizado}"
        return self._get(endpoint, certificado, senha, params=params)

    def consultar_eventos_por_chave(
        self,
        chave_acesso: str,
        certificado: Path | str,
        senha: str | bytes | None,
    ) -> RespostaADN:
        """Consulta eventos vinculados a uma chave nacional de NFS-e."""
        chave = str(chave_acesso).strip()
        if len(chave) != 50 or not chave.isascii() or not chave.isdigit():
            raise ADNConfiguracaoError("A chave de acesso da NFS-e deve possuir 50 dígitos.")
        endpoint = f"/NFSe/{chave}/Eventos"
        return self._get(endpoint, certificado, senha, params=None)

    @staticmethod
    def _validar_nsu(nsu: int | str) -> str:
        texto = str(nsu).strip()
        if not texto or not texto.isascii() or not texto.isdigit() or len(texto) > 15:
            raise ADNConfiguracaoError("O NSU deve conter de 1 a 15 dígitos.")
        return texto

    def _get(
        self,
        endpoint: str,
        certificado: Path | str,
        senha: str | bytes | None,
        *,
        params: dict[str, str] | None,
    ) -> RespostaADN:
        conteudo_pkcs12 = ler_arquivo_com_limite(
            Path(certificado), LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES
        )
        senha_operacao = senha
        del senha
        url = f"{self.base_url}{endpoint}"
        try:
            resposta = self._request_get(
                url,
                params=params,
                headers={"Accept": "application/json", "User-Agent": "NFSe-Facil/0.5.0"},
                timeout=self.timeout,
                verify=True,
                allow_redirects=False,
                stream=True,
                pkcs12_data=conteudo_pkcs12,
                pkcs12_password=senha_operacao,
            )
        except requests.exceptions.Timeout as err:
            raise ADNTimeoutError("A NFS-e Nacional demorou demais para responder. Tente novamente.") from err
        except (requests.exceptions.SSLError, ValueError) as err:
            raise ADNAutenticacaoError(
                "Não foi possível autenticar com o certificado digital informado."
            ) from err
        except requests.exceptions.RequestException as err:
            raise ADNConexaoError(
                "Não foi possível conectar com segurança à NFS-e Nacional."
            ) from err
        except Exception as err:
            raise ADNConexaoError(
                "Não foi possível concluir a comunicação com a NFS-e Nacional."
            ) from err
        finally:
            del conteudo_pkcs12
            del senha_operacao

        try:
            return self._interpretar_resposta(resposta, endpoint)
        finally:
            fechar = getattr(resposta, "close", None)
            if callable(fechar):
                fechar()

    def _interpretar_resposta(self, resposta: Any, endpoint: str) -> RespostaADN:
        status = int(resposta.status_code)
        if status in (401, 403):
            raise ADNAutenticacaoError("O certificado não foi autorizado pela NFS-e Nacional.")
        if status == 429:
            raise ADNLimiteRequisicoesError(
                "Muitas consultas foram realizadas. Aguarde antes de tentar novamente."
            )
        if status >= 500:
            raise ADNIndisponivelError(
                "A NFS-e Nacional está temporariamente indisponível. Tente novamente mais tarde."
            )
        if status == 404 and endpoint.startswith("/DFe/"):
            # Na distribuição por NSU, a ausência do próximo recurso significa
            # que o contribuinte já alcançou o fim disponível naquele momento.
            return RespostaADN(
                status_http=status,
                dados={"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
                ambiente=self.ambiente,
                endpoint=endpoint,
                requisicao_id=(
                    resposta.headers.get("X-Request-ID")
                    or resposta.headers.get("Request-Id")
                ),
            )
        if status == 400:
            raise ADNRespostaInvalidaError(
                "A NFS-e Nacional recusou os dados da consulta. O aplicativo ajustará os parâmetros na próxima tentativa."
            )
        if status == 404:
            raise ADNRespostaInvalidaError(
                "A NFS-e Nacional não encontrou o recurso solicitado. Isso não confirma que a importação terminou."
            )
        if status < 200 or status >= 300:
            raise ADNRespostaInvalidaError(
                f"A NFS-e Nacional não aceitou a consulta realizada (código {status})."
            )

        cabecalho_tamanho = resposta.headers.get("Content-Length")
        if cabecalho_tamanho:
            try:
                if int(cabecalho_tamanho) > self.limite_resposta_bytes:
                    raise ADNRespostaInvalidaError("A resposta da NFS-e Nacional excede o limite seguro.")
            except ValueError:
                raise ADNRespostaInvalidaError(
                    "A NFS-e Nacional retornou um tamanho de resposta inválido."
                )

        corpo = bytearray()
        for bloco in resposta.iter_content(chunk_size=64 * 1024):
            if not bloco:
                continue
            corpo.extend(bloco)
            if len(corpo) > self.limite_resposta_bytes:
                raise ADNRespostaInvalidaError("A resposta da NFS-e Nacional excede o limite seguro.")
        try:
            dados = json.loads(bytes(corpo).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise ADNRespostaInvalidaError(
                "A NFS-e Nacional retornou uma resposta que não pôde ser compreendida."
            ) from err
        finally:
            del corpo
        if not isinstance(dados, dict):
            raise ADNRespostaInvalidaError("A NFS-e Nacional retornou uma estrutura inesperada.")
        requisicao_id = resposta.headers.get("X-Request-ID") or resposta.headers.get("Request-Id")
        return RespostaADN(
            status_http=status,
            dados=dados,
            ambiente=self.ambiente,
            endpoint=endpoint,
            requisicao_id=requisicao_id,
        )

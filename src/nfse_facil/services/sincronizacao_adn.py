"""Orquestra consulta, organização e avanço seguro do cursor NSU por empresa."""

from dataclasses import dataclass, replace
from pathlib import Path

from nfse_facil.domain.adn_models import RespostaADN
from nfse_facil.domain.document_models import ResultadoOrganizacao
from nfse_facil.domain.exceptions import ADNConfiguracaoError, DocumentoFiscalInvalidoError
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload
from nfse_facil.infrastructure.http.adn_client import ADNClient
from nfse_facil.infrastructure.repositories.base import EmpresaRepository
from nfse_facil.services.documentos_adn import OrganizadorDocumentosADN
from nfse_facil.services.relatorios import GeradorRelatoriosService


@dataclass(frozen=True)
class ResultadoSincronizacao:
    organizacao: ResultadoOrganizacao
    nsu_anterior: int
    ultimo_nsu: int
    status_processamento: str
    lotes_processados: int = 1
    concluida: bool = False
    relatorios: tuple[Path, ...] = ()
    restaurados: int = 0


class SincronizacaoADNService:
    """Executa um lote por vez e só avança o NSU após gravação integral bem-sucedida."""

    def __init__(
        self,
        repository: EmpresaRepository,
        cliente: ADNClient,
        organizador: OrganizadorDocumentosADN | None = None,
        gerador_relatorios: GeradorRelatoriosService | None = None,
    ) -> None:
        self.repository = repository
        self.cliente = cliente
        self.organizador = organizador or OrganizadorDocumentosADN()
        self.gerador_relatorios = gerador_relatorios or GeradorRelatoriosService()

    def sincronizar_lote(
        self,
        empresa: Empresa,
        senha: str | bytes | None,
        periodo: PeriodoConsulta | None = None,
        preferencias: PreferenciasDownload | None = None,
    ) -> ResultadoSincronizacao:
        if not empresa.certificado_caminho:
            raise ADNConfiguracaoError("Selecione um certificado digital antes de buscar notas.")
        nsu_anterior = empresa.ultimo_nsu_adn
        resposta = self.cliente.consultar_dfe_por_nsu(
            nsu_anterior,
            empresa.certificado_caminho,
            senha,
            # O parâmetro cnpjConsulta existe para consultar outro estabelecimento
            # da mesma raiz. Quando certificado e empresa são o mesmo CNPJ, o ADN
            # identifica o contribuinte diretamente pelo certificado mTLS.
            cnpj_consulta=(
                empresa.cnpj
                if empresa.certificado_cnpj and empresa.certificado_cnpj != empresa.cnpj
                else None
            ),
            lote=True,
        )
        del senha
        organizacao = self.organizador.processar(resposta, empresa, periodo, preferencias)
        novo_nsu = self._maior_nsu_confirmado(resposta, nsu_anterior)
        if novo_nsu > nsu_anterior:
            atualizada = replace(empresa, ultimo_nsu_adn=novo_nsu)
            self.repository.salvar(atualizada)
            empresa.ultimo_nsu_adn = atualizada.ultimo_nsu_adn
            empresa.atualizado_em = atualizada.atualizado_em
        return ResultadoSincronizacao(
            organizacao=organizacao,
            nsu_anterior=nsu_anterior,
            ultimo_nsu=novo_nsu,
            status_processamento=resposta.status_processamento,
            concluida=self._resposta_indica_fim(resposta, novo_nsu),
        )

    def sincronizar_todos(
        self,
        empresa: Empresa,
        senha: str | bytes | None,
        periodo: PeriodoConsulta | None = None,
        preferencias: PreferenciasDownload | None = None,
        limite_lotes: int = 1000,
    ) -> ResultadoSincronizacao:
        """Busca lotes consecutivos usando a senha uma única vez durante a operação."""
        if limite_lotes < 1:
            raise ADNConfiguracaoError("O limite de lotes da sincronização é inválido.")
        restaurados = self.organizador.restaurar_visiveis(empresa, periodo, preferencias)
        nsu_inicial = empresa.ultimo_nsu_adn
        resultados = []
        concluida = False
        try:
            for _ in range(limite_lotes):
                resultado = self.sincronizar_lote(empresa, senha, periodo, preferencias)
                resultados.append(resultado)
                if resultado.concluida:
                    concluida = True
                    break
        finally:
            del senha
        consolidado = self._consolidar(resultados, nsu_inicial, concluida=concluida)
        consolidado = replace(consolidado, restaurados=restaurados)
        if periodo is not None and preferencias is not None:
            relatorios = self.gerador_relatorios.gerar(empresa, periodo, preferencias)
            consolidado = replace(consolidado, relatorios=relatorios)
        return consolidado

    @staticmethod
    def _consolidar(
        resultados: list[ResultadoSincronizacao], nsu_inicial: int, *, concluida: bool
    ) -> ResultadoSincronizacao:
        documentos = tuple(
            documento
            for resultado in resultados
            for documento in resultado.organizacao.documentos
        )
        organizacao = ResultadoOrganizacao(
            documentos=documentos,
            fora_do_filtro=sum(r.organizacao.fora_do_filtro for r in resultados),
            arquivados_novos=sum(r.organizacao.arquivados_novos for r in resultados),
        )
        ultimo = resultados[-1]
        return ResultadoSincronizacao(
            organizacao=organizacao,
            nsu_anterior=nsu_inicial,
            ultimo_nsu=ultimo.ultimo_nsu,
            status_processamento=ultimo.status_processamento,
            lotes_processados=len(resultados),
            concluida=concluida,
        )

    @staticmethod
    def _resposta_indica_fim(resposta: RespostaADN, novo_nsu: int) -> bool:
        status = resposta.status_processamento.casefold()
        if not resposta.lote_dfe or "nenhum" in status or "nao_localizado" in status or "não_localizado" in status:
            return True
        if resposta.maior_nsu is not None and novo_nsu >= resposta.maior_nsu:
            return True
        # A distribuição entrega no máximo 50 itens. Um lote menor indica que
        # o cursor alcançou o fim disponível naquele momento.
        return len(resposta.lote_dfe) < 50

    @staticmethod
    def _maior_nsu_confirmado(resposta: RespostaADN, atual: int) -> int:
        maior = atual
        for item in resposta.lote_dfe:
            texto = str(item.get("NSU", "")).strip()
            if not texto.isascii() or not texto.isdigit() or len(texto) > 20:
                raise DocumentoFiscalInvalidoError("O ADN retornou um NSU inválido.")
            maior = max(maior, int(texto))
        return maior

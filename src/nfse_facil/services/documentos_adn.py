"""Decodificação e organização segura dos XMLs distribuídos pelo ADN."""

import base64
import binascii
from datetime import date, datetime
import gzip
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile
import sys
from xml.etree import ElementTree

from nfse_facil.domain.adn_models import RespostaADN
from nfse_facil.domain.document_models import (
    DirecaoDocumento,
    DocumentoFiscal,
    DocumentoSalvo,
    ResultadoOrganizacao,
)
from nfse_facil.domain.exceptions import (
    DocumentoFiscalGravacaoError,
    DocumentoFiscalGrandeError,
    DocumentoFiscalInvalidoError,
)
from nfse_facil.domain.models import Empresa, PeriodoConsulta, PreferenciasDownload
from nfse_facil.domain.validators import sanitizar_cnpj


class OrganizadorDocumentosADN:
    """Transforma lotes ADN em XMLs validados e arquivos organizados."""

    LIMITE_XML_BYTES = 10 * 1024 * 1024
    LIMITE_CAMPO_CODIFICADO = 15 * 1024 * 1024
    PASTA_ARQUIVO_INTERNO = ".nfse-facil-arquivo-adn"

    def processar(
        self,
        resposta: RespostaADN,
        empresa: Empresa,
        periodo: PeriodoConsulta | None = None,
        preferencias: PreferenciasDownload | None = None,
    ) -> ResultadoOrganizacao:
        documentos = tuple(self._converter_item(item, empresa) for item in resposta.lote_dfe)
        pasta_empresa = self.pasta_da_empresa(empresa)
        pasta_arquivo = pasta_empresa / self.PASTA_ARQUIVO_INTERNO
        pasta_arquivo.mkdir(parents=True, exist_ok=True)
        self._marcar_oculto_windows(pasta_arquivo)
        arquivados = tuple(
            self._salvar_atomico(documento, pasta_arquivo)
            for documento in documentos
        )
        selecionados = tuple(
            documento
            for documento in documentos
            if self._esta_selecionado(documento, periodo, preferencias)
        )
        salvos_visiveis = tuple(
            self._salvar_atomico(documento, pasta_empresa)
            for documento in selecionados
        )
        return ResultadoOrganizacao(
            documentos=salvos_visiveis,
            fora_do_filtro=len(documentos) - len(selecionados),
            arquivados_novos=sum(not item.ja_existia for item in arquivados),
        )

    def restaurar_visiveis(
        self,
        empresa: Empresa,
        periodo: PeriodoConsulta | None,
        preferencias: PreferenciasDownload | None,
    ) -> int:
        """Restaura XMLs visíveis apagados usando o arquivo interno local."""
        pasta_empresa = self.pasta_da_empresa(empresa)
        pasta_arquivo = pasta_empresa / self.PASTA_ARQUIVO_INTERNO
        if not pasta_arquivo.exists():
            return 0

        restaurados = 0
        for origem in pasta_arquivo.rglob("*.xml"):
            try:
                relativo = origem.relative_to(pasta_arquivo)
                if len(relativo.parts) != 4:
                    continue
                ano, mes, direcao_texto, _nome = relativo.parts
                if not (ano.isascii() and ano.isdigit() and mes.isascii() and mes.isdigit()):
                    continue
                direcao = DirecaoDocumento(direcao_texto)
                xml = origem.read_bytes()
                if len(xml) > self.LIMITE_XML_BYTES:
                    continue
                raiz = self._validar_xml(xml)
                documento = DocumentoFiscal(
                    nsu="0",
                    chave_acesso="RESTAURADO",
                    tipo_documento="Documento",
                    xml=xml,
                    data_documento=self._extrair_data(raiz),
                    direcao=direcao,
                )
                if not self._esta_selecionado(documento, periodo, preferencias):
                    continue
                destino = pasta_empresa / relativo
                if self._copiar_atomico_se_ausente(origem, destino):
                    restaurados += 1
            except (OSError, ValueError, DocumentoFiscalInvalidoError):
                continue
        return restaurados

    @staticmethod
    def _copiar_atomico_se_ausente(origem: Path, destino: Path) -> bool:
        destino.parent.mkdir(parents=True, exist_ok=True)
        conteudo = origem.read_bytes()
        if destino.exists():
            if hashlib.sha256(destino.read_bytes()).digest() != hashlib.sha256(conteudo).digest():
                raise DocumentoFiscalGravacaoError(
                    "Já existe um documento visível com o mesmo nome e conteúdo diferente."
                )
            return False
        descritor, temporario = tempfile.mkstemp(prefix=".nfse_restore_", suffix=".tmp", dir=destino.parent)
        try:
            with os.fdopen(descritor, "wb") as arquivo:
                arquivo.write(conteudo)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, destino)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)
        return True

    @classmethod
    def pasta_da_empresa(cls, empresa: Empresa) -> Path:
        """Retorna uma pasta exclusiva e segura dentro da pasta principal escolhida."""
        nome = empresa.nome_fantasia or empresa.razao_social
        # Alguns certificados trazem a razão social no formato "NOME:CNPJ".
        nome = re.sub(rf"[\s:–—-]*{re.escape(empresa.cnpj)}$", "", nome).strip()
        nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome)
        nome = re.sub(r"\s+", " ", nome).strip(" .")
        nome = nome[:100].rstrip(" .") or "Empresa"
        return empresa.pasta_documentos / f"{nome} - {empresa.cnpj}"

    @staticmethod
    def _marcar_oculto_windows(pasta: Path) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            atributos = ctypes.windll.kernel32.GetFileAttributesW(str(pasta))
            if atributos != -1:
                ctypes.windll.kernel32.SetFileAttributesW(str(pasta), atributos | 0x02)
        except Exception:
            # A ocultação é apenas visual; falhar nela não compromete os arquivos.
            pass

    @staticmethod
    def _esta_selecionado(
        documento: DocumentoFiscal,
        periodo: PeriodoConsulta | None,
        preferencias: PreferenciasDownload | None,
    ) -> bool:
        if periodo and not (periodo.data_inicio <= documento.data_documento <= periodo.data_fim):
            return False
        if preferencias:
            if documento.direcao == DirecaoDocumento.EMITIDA and not preferencias.baixar_emitidas:
                return False
            if documento.direcao == DirecaoDocumento.RECEBIDA and not preferencias.baixar_recebidas:
                return False
            if documento.direcao == DirecaoDocumento.OUTRA:
                return False
        return True

    def _converter_item(self, item: dict, empresa: Empresa) -> DocumentoFiscal:
        nsu = self._identificador_numerico(item.get("NSU"), "NSU")
        chave = self._chave_segura(item.get("ChaveAcesso"), nsu)
        tipo = self._texto_seguro(item.get("TipoDocumento"), "Documento")
        campo_xml = item.get("ArquivoXml")
        if not isinstance(campo_xml, str) or not campo_xml.strip():
            raise DocumentoFiscalInvalidoError("O ADN retornou um documento fiscal sem conteúdo XML.")
        xml = self._decodificar_xml(campo_xml)
        raiz = self._validar_xml(xml)
        data_doc = self._extrair_data(raiz, item.get("DataHoraGeracao"))
        direcao = self._classificar_direcao(raiz, empresa.cnpj)
        return DocumentoFiscal(nsu, chave, tipo, xml, data_doc, direcao)

    def _decodificar_xml(self, valor: str) -> bytes:
        texto = valor.strip()
        if len(texto.encode("utf-8")) > self.LIMITE_CAMPO_CODIFICADO:
            raise DocumentoFiscalGrandeError("O documento recebido excede o limite seguro.")
        if texto.startswith("<"):
            xml = texto.encode("utf-8")
        else:
            try:
                bruto = base64.b64decode(texto, validate=True)
            except (binascii.Error, ValueError) as err:
                raise DocumentoFiscalInvalidoError(
                    "O ADN retornou um documento com codificação inválida."
                ) from err
            if bruto.startswith(b"\x1f\x8b"):
                try:
                    with gzip.GzipFile(fileobj=BytesIO(bruto), mode="rb") as arquivo_gzip:
                        xml = arquivo_gzip.read(self.LIMITE_XML_BYTES + 1)
                except (gzip.BadGzipFile, EOFError, OSError) as err:
                    raise DocumentoFiscalInvalidoError(
                        "O ADN retornou um documento compactado inválido."
                    ) from err
            else:
                xml = bruto
        if len(xml) > self.LIMITE_XML_BYTES:
            raise DocumentoFiscalGrandeError("O XML descompactado excede o limite seguro.")
        if not xml.lstrip().startswith(b"<"):
            raise DocumentoFiscalInvalidoError("O conteúdo retornado pelo ADN não é um XML válido.")
        return xml

    @staticmethod
    def _validar_xml(xml: bytes) -> ElementTree.Element:
        texto_inicial = xml[:2048].upper()
        if b"<!DOCTYPE" in texto_inicial or b"<!ENTITY" in texto_inicial:
            raise DocumentoFiscalInvalidoError("O XML contém declarações externas não permitidas.")
        try:
            return ElementTree.fromstring(xml)
        except ElementTree.ParseError as err:
            raise DocumentoFiscalInvalidoError("O documento retornado contém XML inválido.") from err

    def _extrair_data(self, raiz: ElementTree.Element, data_envelope=None) -> date:
        # NFS-e/DPS usam dhEmi ou dCompet; eventos usam dhEvento. Alguns
        # retornos do ADN informam a data somente no envelope LoteDFe.
        for nome in (
            "dhEmi",
            "dCompet",
            "dhEvento",
            "dhRegEvento",
            "dhPedRegEvento",
            "dPedRegEvento",
            "dhProcessamento",
        ):
            valor = self._primeiro_texto(raiz, nome)
            if valor:
                data_convertida = self._converter_data(valor)
                if data_convertida:
                    return data_convertida
        if data_envelope is not None:
            data_convertida = self._converter_data(str(data_envelope).strip())
            if data_convertida:
                return data_convertida
        raise DocumentoFiscalInvalidoError("O documento não possui uma data válida para organização.")

    @staticmethod
    def _converter_data(valor: str) -> date | None:
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(valor[:10])
            except ValueError:
                return None

    def _classificar_direcao(self, raiz: ElementTree.Element, cnpj_empresa: str) -> DirecaoDocumento:
        prestador = self._cnpj_no_grupo(raiz, {"prest", "prestador"})
        tomador = self._cnpj_no_grupo(raiz, {"toma", "tomador"})
        alvo = sanitizar_cnpj(cnpj_empresa)
        if prestador == alvo:
            return DirecaoDocumento.EMITIDA
        if tomador == alvo:
            return DirecaoDocumento.RECEBIDA
        return DirecaoDocumento.OUTRA

    def _cnpj_no_grupo(self, raiz: ElementTree.Element, nomes: set[str]) -> str | None:
        for elemento in raiz.iter():
            if self._nome_local(elemento.tag).casefold() in nomes:
                for filho in elemento.iter():
                    if self._nome_local(filho.tag).casefold() == "cnpj" and filho.text:
                        try:
                            return sanitizar_cnpj(filho.text)
                        except Exception:
                            return None
        return None

    @staticmethod
    def _primeiro_texto(raiz: ElementTree.Element, nome: str) -> str | None:
        for elemento in raiz.iter():
            if OrganizadorDocumentosADN._nome_local(elemento.tag) == nome and elemento.text:
                return elemento.text.strip()
        return None

    @staticmethod
    def _nome_local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _identificador_numerico(valor, campo: str) -> str:
        texto = str(valor).strip()
        if not texto or not texto.isascii() or not texto.isdigit() or len(texto) > 20:
            raise DocumentoFiscalInvalidoError(f"O {campo} retornado pelo ADN é inválido.")
        return texto

    @staticmethod
    def _chave_segura(valor, nsu: str) -> str:
        texto = str(valor or "").strip()
        if texto and texto.isascii() and texto.isalnum() and len(texto) <= 60:
            return texto
        return f"NSU{nsu}"

    @staticmethod
    def _texto_seguro(valor, padrao: str) -> str:
        texto = str(valor or "").strip()
        texto = re.sub(r"[^0-9A-Za-z_-]", "_", texto)[:40]
        return texto or padrao

    def _salvar_atomico(self, documento: DocumentoFiscal, raiz: Path) -> DocumentoSalvo:
        pasta = raiz / str(documento.data_documento.year) / f"{documento.data_documento.month:02d}" / documento.direcao.value
        nome = f"{documento.tipo_documento}_{documento.chave_acesso}.xml"
        destino = pasta / nome
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                existente = destino.read_bytes()
                if hashlib.sha256(existente).digest() != hashlib.sha256(documento.xml).digest():
                    raise DocumentoFiscalGravacaoError(
                        "Já existe um documento com o mesmo identificador e conteúdo diferente."
                    )
                return DocumentoSalvo(documento, destino, True)
            descritor, temporario = tempfile.mkstemp(prefix=".nfse_", suffix=".tmp", dir=pasta)
            try:
                with os.fdopen(descritor, "wb") as arquivo:
                    arquivo.write(documento.xml)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                os.replace(temporario, destino)
            finally:
                if os.path.exists(temporario):
                    os.unlink(temporario)
            return DocumentoSalvo(documento, destino, False)
        except DocumentoFiscalGravacaoError:
            raise
        except OSError as err:
            raise DocumentoFiscalGravacaoError(
                "Não foi possível salvar o documento fiscal na pasta da empresa."
            ) from err

"""Exceções customizadas da camada de domínio da aplicação."""


class NFSeFacilError(Exception):
    """Exceção base para erros da aplicação NFS-e Fácil."""


class ValidacaoError(NFSeFacilError):
    """Exceção levantada quando alguma regra de validação de domínio falha."""


class CNPJInvalidoError(ValidacaoError):
    """Exceção levantada quando um CNPJ numérico ou alfanumérico é inválido."""


class PeriodoInvalidoError(ValidacaoError):
    """Exceção levantada quando um intervalo de datas é inconsistente."""


class EmpresaNaoEncontradaError(NFSeFacilError):
    """Exceção levantada quando uma empresa pesquisada não é encontrada."""


class CNPJDuplicadoError(ValidacaoError):
    """Exceção levantada quando uma tentativa de cadastro/edição conflita com CNPJ já existente."""


class PastaInvalidaError(ValidacaoError):
    """Exceção levantada quando a pasta de documentos é inválida ou inacessível."""


class PersistenciaError(NFSeFacilError):
    """Exceção levantada em falhas operacionais da camada de persistência/banco de dados."""


class VersaoEsquemaIncompativelError(PersistenciaError):
    """Exceção levantada quando o banco de dados possui versão superior à suportada pelo aplicativo."""


# =====================================================================
# EXCEÇÕES DE CERTIFICADO DIGITAL A1 (ETAPA 03)
# =====================================================================


class CertificadoError(NFSeFacilError):
    """Exceção base para erros relacionados a certificados digitais A1."""


class CertificadoNaoEncontradoError(CertificadoError):
    """Exceção levantada quando o arquivo de certificado não é encontrado no caminho especificado."""


class CertificadoExtensaoInvalidaError(CertificadoError):
    """Exceção levantada quando o arquivo não possui extensão .pfx ou .p12."""


class CertificadoArquivoGrandeError(CertificadoError):
    """Exceção levantada quando o arquivo ultrapassa o limite seguro de tamanho."""


class CertificadoSenhaOuFormatoInvalidoError(CertificadoError):
    """Exceção levantada quando a senha está incorreta ou o arquivo PKCS#12 é inválido.

    NOTA DE SEGURANÇA:
    Não expõe mensagens internas do OpenSSL e nunca interpola ou registra senhas.
    """

    MENSAGEM_PADRAO = (
        "Não foi possível abrir o certificado. Verifique a senha e se o arquivo é um certificado A1 válido."
    )

    def __init__(self, mensagem: str | None = None) -> None:
        super().__init__(mensagem or self.MENSAGEM_PADRAO)


class CertificadoAlgoritmoNaoSuportadoError(CertificadoError):
    """Exceção levantada quando o certificado utiliza algoritmo não suportado."""


class CertificadoPrincipalAusenteError(CertificadoError):
    """Exceção levantada quando o contêiner PKCS#12 não contém o certificado principal."""


class CertificadoChavePrivadaAusenteError(CertificadoError):
    """Exceção levantada quando o contêiner PKCS#12 não contém a chave privada correspondente."""


class CertificadoChaveIncompativelError(CertificadoError):
    """Exceção levantada quando a chave privada não corresponde à chave pública do certificado."""


class CertificadoCNPJAusenteError(CertificadoError):
    """Exceção levantada quando o certificado não contém a extensão ICP-Brasil de CNPJ (OID 2.16.76.1.3.3)."""


class CertificadoCNPJInvalidoError(CertificadoError, ValidacaoError):
    """Exceção levantada quando o CNPJ extraído do certificado é inválido segundo as regras oficiais."""


class CertificadoAindaNaoValidoError(CertificadoError):
    """Exceção levantada na validação para associação quando a data atual é anterior ao início da validade."""


class CertificadoVencidoError(CertificadoError):
    """Exceção levantada na validação para associação quando o certificado já expirou."""


class CertificadoCNPJIncompativelError(CertificadoError, ValidacaoError):
    """Exceção levantada quando o CNPJ do certificado difere do CNPJ da empresa."""


# =====================================================================
# EXCEÇÕES DE COMUNICAÇÃO COM O ADN (ETAPA 04)
# =====================================================================


class ADNError(NFSeFacilError):
    """Erro público e sanitizado durante comunicação com o ADN."""


class ADNConfiguracaoError(ADNError, ValidacaoError):
    """Parâmetros locais inválidos para uma consulta ao ADN."""


class ADNConexaoError(ADNError):
    """Não foi possível estabelecer uma conexão segura com o ADN."""


class ADNTimeoutError(ADNConexaoError):
    """O ADN não respondeu dentro do tempo limite configurado."""


class ADNAutenticacaoError(ADNError):
    """O certificado não foi aceito para autenticação mTLS."""


class ADNLimiteRequisicoesError(ADNError):
    """O ADN limitou temporariamente novas consultas."""


class ADNRespostaInvalidaError(ADNError):
    """O ADN retornou conteúdo ausente, excessivo ou fora do formato esperado."""


class ADNIndisponivelError(ADNError):
    """O serviço oficial está temporariamente indisponível."""


class DocumentoFiscalError(NFSeFacilError):
    """Erro público durante validação ou organização de um documento fiscal."""


class DocumentoFiscalInvalidoError(DocumentoFiscalError):
    """O documento retornado pelo ADN não possui formato seguro reconhecido."""


class DocumentoFiscalGrandeError(DocumentoFiscalError):
    """O documento excede o limite de segurança após a descompactação."""


class DocumentoFiscalGravacaoError(DocumentoFiscalError):
    """Não foi possível gravar o documento de forma atômica."""

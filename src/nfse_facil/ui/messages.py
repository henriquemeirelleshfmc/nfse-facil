"""Textos centralizados, atemporais e auditáveis da interface gráfica."""

from typing import Final

MSG_SEGURANCA_CERTIFICADO: Final[str] = (
    "A senha do certificado nunca será armazenada. "
    "Ela será solicitada somente quando necessária para acessar o certificado."
)

MSG_ERRO_GENERICO_CERTIFICADO: Final[str] = (
    "Não foi possível concluir a leitura do certificado. Tente novamente ou selecione outro arquivo."
)

TITULO_AVISO_DOWNLOAD: Final[str] = "Comunicação com a NFS-e Nacional"


def formatar_erro_certificado(err: Exception) -> str:
    """Retorna mensagem de erro sanitizada e amigável para apresentação ao usuário."""
    from nfse_facil.domain.exceptions import CertificadoError, ValidacaoError

    if isinstance(err, (CertificadoError, ValidacaoError)):
        return str(err)
    return MSG_ERRO_GENERICO_CERTIFICADO


def obter_mensagem_aviso_download(
    empresa_nome: str, cnpj_formatado: str, periodo_rotulo: str
) -> str:
    """Gera o texto informativo atemporal exibido ao clicar em Baixar notas."""
    return (
        f"Você selecionou a empresa:\n"
        f"• {empresa_nome} ({cnpj_formatado})\n"
        f"• Período: {periodo_rotulo}\n\n"
        "Esta versão ainda não realiza downloads. "
        "A conexão segura com a NFS-e Nacional já está preparada; o salvamento e a organização "
        "das notas ainda não estão disponíveis nesta versão.\n\n"
        f"{MSG_SEGURANCA_CERTIFICADO}"
    )

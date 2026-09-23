# Relatório — ETAPA 07: Aplicativo e Instalador para Windows

## Resumo

A versão 0.6.0 do NFS-e Fácil foi empacotada como aplicativo desktop para Windows 64 bits e como instalador em português do Brasil. O usuário final não precisa instalar Python nem dependências separadamente.

## Entregáveis

- Aplicativo: `dist\NFSeFacil\NFSeFacil.exe`
- Instalador: `dist\installer\NFSeFacil-Setup-0.6.0.exe`
- Configuração do empacotamento: `packaging\nfse_facil.spec`
- Configuração do instalador: `packaging\installer.iss`
- Metadados de versão: `packaging\version_info.txt`
- Automação de compilação: `scripts\build_windows.ps1`

## Características do instalador

- interface em português do Brasil;
- instalação por usuário, sem exigir privilégios de administrador;
- destino padrão em `%LOCALAPPDATA%\Programs\NFSeFacil`;
- atalho no menu Iniciar;
- atalho opcional na área de trabalho;
- desinstalador próprio;
- nome, versão, responsável e endereço de suporte incorporados aos metadados.

## Validações realizadas

1. Suite automatizada: **213 testes aprovados**.
2. Empacotamento com PyInstaller 6.18.0 concluído.
3. Compilação com Inno Setup 7.1.0 concluída.
4. Instalação silenciosa em pasta isolada concluída com código 0.
5. Aplicativo instalado permaneceu aberto no teste de inicialização.
6. Encerramento e desinstalação concluídos com código 0.
7. Arquivo principal removido corretamente após a desinstalação.

## Resultado final

- Instalador: **33,54 MB**
- Versão: **0.6.0.0**
- Produto: **NFS-e Fácil**
- SHA-256: `D03413EE8BFB5FA665DDEF4BF0C86183EC9C11ED7C9629841CB78D64EA9605C3`

## Observação sobre assinatura do produto

O instalador ainda não possui assinatura de código do responsável pelo NFS-e Fácil. Em computadores sem reputação prévia, o Windows pode exibir um aviso de proteção. A distribuição pública ideal deverá usar um certificado de assinatura de código válido e assinar tanto o aplicativo quanto o instalador.

## Estado

A ETAPA 07 está concluída. O instalador está pronto para testes controlados em outros computadores Windows 64 bits.

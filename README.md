# NFS-e Fácil

> Aplicativo desktop simplificado para gestão e download de Notas Fiscais de Serviço Eletrônicas (NFS-e), desenvolvido em Python com interface CustomTkinter e persistência local SQLite.

---

## 1. Objetivo do Produto

O **NFS-e Fácil** tem como objetivo simplificar radicalmente a rotina contábil e fiscal de escritórios e empresas. Em vez de navegar por portais complexos ou sistemas fiscais de difícil compreensão, o usuário realiza todo o fluxo em quatro etapas diretas:

1. **Selecionar a empresa**.
2. **Escolher o período** desejado (mês atual, mês anterior ou intervalo personalizado).
3. **Clicar em "Baixar notas"**.
4. O programa organiza os documentos XML/PDF em pastas próprias e gera relatórios consolidados em Excel e PDF automaticamente.

---

## 2. Público-Alvo

- **Contadores e auxiliares contábeis** que precisam coletar e conferir notas de dezenas ou centenas de clientes todos os meses.
- **Empresários e operadores de backoffice** com pouca ou nenhuma familiaridade técnica com informática, APIs fiscais ou arquivos de parametrização.

---

## 3. Estado Atual do Projeto

**ETAPA 06 — Relatórios fiscais e renovação visual** (concluída).

- Cliente HTTPS para os ambientes oficiais de produção restrita e produção.
- Consultas `GET /DFe/{NSU}` e `GET /NFSe/{ChaveAcesso}/Eventos`.
- Autenticação mTLS com certificado A1, validação TLS obrigatória, redirects desativados, timeouts e limite de resposta.
- Erros de rede, autenticação, indisponibilidade e excesso de requisições traduzidos para mensagens seguras.
- Decodificação defensiva de XML direto, Base64 e Base64+GZip retornados pelo ADN.
- Proteção contra expansão GZip excessiva, XML externo, nomes maliciosos e sobrescrita silenciosa.
- Organização separada por empresa em `pasta principal/nome da empresa - CNPJ/ano/mês/Emitidas`, `Recebidas` ou `Outros`.
- Sincronização contínua de todos os lotes disponíveis com uma única digitação da senha; a tela diferencia conclusão, bloqueio temporário e rejeição.
- Relatórios fiscais completos em Excel e PDF a partir dos XMLs arquivados, com resumo de emitidas/recebidas, valores de serviço e líquidos, ISS, retenções federais, IBS/CBS e detalhamento nota a nota.
- Gravação atômica, reprocessamento idempotente e cursor NSU individual por empresa.
- O cursor só avança depois que o lote inteiro foi validado e salvo; falhas mantêm a retomada segura.
- Documentos fora do filtro visual ficam em um arquivo interno oculto para permitir o avanço seguro do NSU; somente o período e as direções selecionadas aparecem nas pastas normais.
- Botão principal conectado ao ambiente oficial de produção, com senha efêmera e execução em segundo plano.

### Base concluída nas etapas anteriores

- **Inspeção e Gestão de Certificados Digitais A1 (.pfx / .p12)**:
  - Leitura física limitada a 5 MB (`limite + 1`), com tratamento rigoroso contra truncamento ou alteração do arquivo.
  - Decodificação ASN.1 defensiva e determinística para extensões ICP-Brasil: OID `2.16.76.1.3.3` (CNPJ do titular) aceitando `OCTET STRING` e `PrintableString` (com tolerância documentada para `UTF8String`/`IA5String`) e OID `2.16.76.1.3.8` (nome empresarial higienizado).
  - Validação de correspondência criptográfica estrita entre a chave privada e a chave pública do certificado (`public_bytes`), sem persistir ou serializar chaves privadas.
  - Avaliação temporal consciente em UTC (`not_valid_before_utc`, `not_valid_after_utc`), classificando em: `AINDA_NAO_VALIDO`, `VALIDO`, `PROXIMO_DO_VENCIMENTO` (30 dias ou menos) e `VENCIDO`.
- **Diferenciação Estrita entre Inspeção e Associação**:
  - `inspecionar()`: Abre, interpreta e exibe metadados mesmo para certificados vencidos ou ainda não válidos, sem transformar estados temporais em falha de leitura.
  - `validar_para_associacao()`: Impede associar certificados vencidos ou futuros como operacionais (`CertificadoVencidoError`, `CertificadoAindaNaoValidoError`), permitindo certificados próximos do vencimento com aviso explícito.
- **Serviço de Associação Desacoplado (`CertificadoAssociacaoService`)**:
  - Validação de correspondência exata entre o CNPJ da empresa e o CNPJ do titular do certificado (suportando formatos numéricos e alfanuméricos).
  - Atualização imutável via `dataclasses.replace` e persistência atômica no repositório.
  - Remoção segura de metadados sem exclusão física do arquivo `.pfx`/`.p12` do usuário.
- **Persistência SQLite e Evolução do Esquema (Migração v2)**:
  - Migração sequencial atômica v0 → v1 → v2 controlada por `PRAGMA user_version = 2`.
  - Novos campos na tabela `empresas`: `certificado_caminho`, `certificado_cnpj`, `certificado_fingerprint_sha256`, `certificado_valido_de`, `certificado_valido_ate`, `certificado_verificado_em`.
  - Auditoria de segurança automática no esquema SQLite impedindo colunas para senhas ou dados binários sensíveis.
- **Interface Gráfica Responsiva e Segura**:
  - Processamento em segundo plano com `ThreadPoolExecutor` isolado, garantindo 100% de responsividade visual.
  - Campo de senha com máscara `*`, alternância de visibilidade e **limpeza visual imediata** logo após iniciar a inspeção.
  - Proteção contra duplo clique e encerramento seguro de janela sem callbacks em widgets destruídos.
  - Exibição de metadados detalhados em modal somente-leitura e fluxo de importação automática de dados para novos cadastros.
  - Confirmação explícita ao editar o CNPJ de uma empresa que já possua certificado associado.
- **Cobertura de Testes**: 213 testes automatizados cobrindo domínio, repositórios, migrações, criptografia PKCS#12, cliente ADN, documentos fiscais, relatórios, diagnóstico seguro e UI gráfica.

> [!IMPORTANT]
> **AVISO DE ESCOPO:**
> A comunicação real somente ocorre quando o usuário fornecer a senha do certificado e iniciar uma consulta. Os testes automatizados não acessam a rede oficial. Os documentos retornados são salvos dentro da pasta exclusiva da empresa.

---

## 4. Política de Segurança de Dados e Segredos

| Categoria | Detalhe | Armazenado? |
| :--- | :--- | :--- |
| **Identificador da Empresa** | UUID v4 único | **SIM** (SQLite) |
| **Razão Social / Nome Fantasia** | Nomes cadastrais para identificação | **SIM** (SQLite) |
| **CNPJ da Empresa** | 14 posições (numérico legado ou alfanumérico) | **SIM** (SQLite) |
| **Pasta de Documentos** | Caminho no sistema de arquivos para salvar notas | **SIM** (SQLite) |
| **Metadados do Certificado** | Fingerprint SHA-256, CNPJ titular, validade UTC, caminho (opcional) | **SIM** (SQLite) |
| **Senha do Certificado Digital** | Senhas de arquivos `.pfx` ou `.p12` | ❌ **NUNCA ARMAZENADA** (solicitada apenas temporariamente para a operação em memória) |
| **Chave Privada / Conteúdo Bruto** | Dados binários ou chaves criptográficas | ❌ **NUNCA ARMAZENADOS** |
| **PEM temporário do mTLS** | Criado internamente pela biblioteca HTTP, criptografado com senha aleatória e removido imediatamente após carregar o contexto TLS | ⚠️ **TEMPORÁRIO, SOMENTE DURANTE A CONEXÃO** |

### Transparência sobre o PEM temporário

Para permitir que o Windows/Python estabeleça a conexão mTLS a partir de um `.pfx`/`.p12`, a biblioteca `requests-pkcs12` converte o certificado e a chave para um arquivo PEM temporário. Esse PEM é protegido com uma senha aleatória, utilizado apenas para carregar o contexto TLS e apagado em um bloco de limpeza da própria biblioteca. A senha original do certificado não é gravada no banco, em configurações ou em logs. Ainda assim, como qualquer arquivo temporário, existe uma pequena janela de existência no disco durante a preparação da conexão; essa é uma decisão técnica assumida e documentada pelo projeto.

> [!NOTE]
> **Limitação Técnica de Gerenciamento de Memória em Python:**
> Strings em Python são objetos imutáveis e gerenciados pelo coletor de lixo do CPython. A aplicação adota as melhores práticas de segurança (eliminação imediata de referências com `del`, limpeza imediata dos campos visuais do Tkinter e escopo mínimo), contudo não é tecnicamente possível prometer sobrescrita garantida de memória física (`zeroization`) no interpretador Python.

---

## 5. Como Redefinir Dados de Desenvolvimento com Segurança

Caso deseje limpar ou redefinir o banco de dados local de desenvolvimento/testes, basta excluir o arquivo de banco específico:

```powershell
# PowerShell: excluir exclusivamente o banco de desenvolvimento local:
Remove-Item "$env:LOCALAPPDATA\NFSeFacil\data\nfse_facil.db" -ErrorAction SilentlyContinue
```

Na próxima inicialização, o sistema recriará o banco vazio e aplicará automaticamente as migrações sequenciais v0 → v1 → v2.

---

## 6. Roadmap do Projeto

- [x] **Etapa 01**: Fundação da aplicação, regras de negócio de CNPJ, contratos abstratos e UI demonstrativa.
- [x] **Etapa 02**: Persistência local em SQLite, migrações atômicas, gestão completa de empresas e validação de pastas.
- [x] **Etapa 03**: Gestão e inspeção de Certificados Digitais A1 em memória (sem armazenamento de senha).
- [x] **Etapa 04**: Comunicação e autenticação mTLS com o Portal Nacional da NFS-e via API ADN.
- [x] **Etapa 05**: Download, descompactação e organização segura dos XMLs em pastas por ano/mês.
- [x] **Etapa 06**: Relatórios fiscais separados em Excel/PDF, recuperação de histórico, renovação visual e diagnóstico seguro para suporte.
- [x] **Etapa 07**: Empacotamento em aplicativo e instalador executável Windows (.exe).

---

## 7. Requisitos de Sistema

- **Sistema Operacional**: Windows 10, Windows 11 ou superior (64-bit).
- **Uso do instalador**: não requer Python instalado.
- **Desenvolvimento**: Python 3.12 ou superior.

---

## 8. Instalação e Execução

Abra o terminal (PowerShell ou Prompt de Comando) na pasta raiz do projeto:

```powershell
# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar em modo editável com ferramentas de desenvolvimento
python -m pip install -e ".[dev]"

# 3. Executar o aplicativo
python -m nfse_facil
```

### Gerar o aplicativo e o instalador para Windows

O aplicativo portátil é criado com PyInstaller. O instalador é gerado com o Inno Setup 7, que deve estar instalado no computador de desenvolvimento.

```powershell
# Instalar as dependências de desenvolvimento e empacotamento
python -m pip install -e ".[dev,build]"

# Executar todos os testes e gerar o aplicativo portátil
.\scripts\build_windows.ps1

# Executar os testes e gerar também o instalador
.\scripts\build_windows.ps1 -Installer
```

Os resultados ficam em `dist\NFSeFacil\NFSeFacil.exe` e `dist\installer\NFSeFacil-Setup-0.6.0.exe`.

---

## 9. Execução dos Testes Automatizados

Para executar toda a suíte de 213 testes automatizados:

```powershell
python -m pytest tests -v
```

---

## 10. Licença

Este projeto é distribuído sob os termos da licença MIT. Para mais detalhes, consulte o arquivo [LICENSE](LICENSE).

## 11. Contato e Suporte

Para dúvidas e contato com o responsável pelo projeto, acesse o Instagram [@henrique.meirelles_](https://www.instagram.com/henrique.meirelles_/).

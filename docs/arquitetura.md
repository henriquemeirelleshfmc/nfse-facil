# Arquitetura do Sistema - NFS-e Fácil

Este documento detalha a arquitetura técnica, divisão de responsabilidades, decisões de design, persistência e segurança do projeto **NFS-e Fácil**.

---

## 1. Visão Geral das Camadas

A aplicação segue uma arquitetura em camadas desacopladas (Clean / Hexagonal Architecture), garantindo que as regras fiscais, a manipulação de certificados digitais e o domínio permaneçam isolados da infraestrutura de banco de dados e da interface gráfica.

```text
┌──────────────────────────────────────────────────────────┐
│                   Apresentação (UI)                      │
│        CustomTkinter: MainWindow, CompanyDialog,         │
│     CertificateDialog, CertificateInfoDialog,            │
│             CompanyList, PeriodSelector                  │
└────────────────────────────┬─────────────────────────────┘
                             │ consome
┌────────────────────────────▼─────────────────────────────┐
│                 Serviços de Aplicação                    │
│   Pkcs12CertificadoService (leitura e criptografia PKCS12)│
│   CertificadoAssociacaoService (regras e persistência)   │
│   PastaDocumentosService (validação segura de pastas)    │
│ ADNClient, SincronizacaoADNService, OrganizadorDocumentos│
└────────────────────────────┬─────────────────────────────┘
                             │ orquestra
┌────────────────────────────▼─────────────────────────────┐
│                   Núcleo de Domínio                      │
│   Entidades: Empresa, CertificadoInfo, PeriodoConsulta   │
│   Enums: StatusCertificado, TipoPeriodo                  │
│   Validadores: Módulo 11 (numérico e alfanumérico)       │
│   Exceções: CertificadoError, CNPJInvalidoError, etc.    │
└────────────────────────────▲─────────────────────────────┘
                             │ persiste / consulta
┌────────────────────────────┴─────────────────────────────┐
│                     Infraestrutura                       │
│   connection.py: Conexões curtas, pragmas e transações   │
│   migrations.py: Esquema v2, PRAGMA user_version e audit │
│   SqliteEmpresaRepository: CRUD, busca, ordenação        │
│   ADNClient: HTTPS/mTLS com Portal Nacional              │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Responsabilidade dos Módulos

### 2.1. `src/nfse_facil/config/`
- **`settings.py`**:
  - Resolução dinâmica do caminho do banco SQLite: `%LOCALAPPDATA%\NFSeFacil\data\nfse_facil.db` com fallback seguro para `~/.nfse_facil/data/nfse_facil.db`.
  - Parâmetro `custom_db_path` para permitir injeção de banco isolado por teste ou temporário.
  - Diretório padrão de documentos com criação sob demanda.

### 2.2. `src/nfse_facil/domain/`
- **`models.py`**:
  - `Empresa`: Entidade central. Contém identificação cadastral, pasta de documentos, timestamps UTC e colunas opcionais de metadados de certificado:
    - `certificado_caminho`: Path opcional (apenas se o usuário optar por lembrar).
    - `certificado_cnpj`: CNPJ normalizado como string de 14 caracteres (numérico ou alfanumérico) para conferência estrita.
    - `certificado_fingerprint_sha256`: Hash canônico em hexadecimal maiúsculo.
    - `certificado_valido_de` e `certificado_valido_ate`: Intervalo temporal consciente em UTC.
    - `certificado_verificado_em`: Timestamp UTC da última validação local.
    - Propriedades auxiliares: `tem_certificado_associado`, `certificado_cnpj_formatado`, `associacao_certificado_coerente`.
- **`certificate_models.py`**:
  - `StatusCertificado` (Enum): `AINDA_NAO_VALIDO`, `VALIDO`, `PROXIMO_DO_VENCIMENTO`, `VENCIDO`.
  - `CertificadoInfo`: Dataclass imutável representando metadados públicos do certificado extraídos em memória. **Sem campos de senha ou dados binários de chaves privadas**.
- **`validators.py`**:
  - Validação estrita do Módulo 11 para CNPJ numérico legado e alfanumérico oficial.
  - Normalização para busca insensível a acentos e caixa com `normalizar_para_busca()`.
  - Sanitização de strings e formatação visual `XX.XXX.XXX/XXXX-XX`.
- **`exceptions.py`**:
  - Hierarquia de certificados: `CertificadoError`, `CertificadoNaoEncontradoError`, `CertificadoExtensaoInvalidaError`, `CertificadoArquivoGrandeError`, `CertificadoSenhaOuFormatoInvalidoError`, `CertificadoAlgoritmoNaoSuportadoError`, `CertificadoPrincipalAusenteError`, `CertificadoChavePrivadaAusenteError`, `CertificadoChaveIncompativelError`, `CertificadoCNPJAusenteError`, `CertificadoCNPJInvalidoError`, `CertificadoAindaNaoValidoError`, `CertificadoVencidoError`, `CertificadoCNPJIncompativelError`.

### 2.3. `src/nfse_facil/services/`
- **`pkcs12.py` (`Pkcs12CertificadoService`)**:
  - **Leitura física limitada**: Leitura binária em bloco de até `limite + 1` (5 MB + 1 byte), protegendo contra estouro de memória e arquivos modificados durante a operação.
  - **Criptografia PKCS#12**: Utiliza `cryptography.hazmat.primitives.serialization.pkcs12.load_key_and_certificates`.
  - **Correspondência de Chave**: Compara a representação canônica da chave pública derivada da chave privada com a chave pública do certificado X.509 (`public_bytes`), garantindo integridade criptográfica sem expor ou serializar a chave privada.
  - **Decodificação ASN.1 ICP-Brasil**:
    - OID `2.16.76.1.3.3`: Extração do CNPJ com aceitação prioritária de `OCTET STRING` e `PrintableString` (e tolerância documentada para `UTF8String`/`IA5String`). Rejeita estruturas ASN.1 compostas, dados aninhados inesperados ou dados excedentes (`trailing data`).
    - OID `2.16.76.1.3.8`: Extração e higienização do nome empresarial (remoção de caracteres de controle e truncamento defensivo a 200 caracteres).
  - **Classificação Temporal Precisa**: Avalia datas conscientes em UTC (`not_valid_before_utc`, `not_valid_after_utc`). Define fronteiras exatas: antes do início é ainda não válido, exatamente no início/fim é válido, até 30 dias restantes é próximo do vencimento, após o fim é vencido.
  - **Desacoplamento Inspeção vs Associação**: `inspecionar()` apenas extrai e classifica; `validar_para_associacao()` bloqueia certificados vencidos ou ainda não válidos, permitindo certificados próximos do vencimento com alerta.
- **`associacao_certificado.py` (`CertificadoAssociacaoService`)**:
  - Orquestra o ciclo de vida da associação entre empresa e certificado.
  - Valida correspondência de CNPJ e estado temporal.
  - Constrói nova instância com `dataclasses.replace` e persiste atômica e exclusivamente após validação completa.
  - Fornece desassociação segura limpando todos os metadados do certificado no banco sem apagar o arquivo físico do usuário.
- **`documentos_adn.py` (`OrganizadorDocumentosADN`)**:
  - Aceita XML direto, Base64 e Base64+GZip com limites antes e durante a expansão.
  - Rejeita DTD/entidades externas, XML malformado, identificadores inseguros e colisões de conteúdo.
  - Classifica documentos por participação da empresa e grava atomicamente por ano/mês/direção.
- **`sincronizacao_adn.py` (`SincronizacaoADNService`)**:
  - Consulta um lote, organiza todos os documentos e avança o cursor NSU somente após sucesso integral.
  - Mantém retomada idempotente quando a gravação ou persistência falha.

### 2.4. `src/nfse_facil/infrastructure/database/`
- **`connection.py`**:
  - Gerenciamento de conexões curtas com context managers (`open_connection`, `get_connection`, `transaction`).
  - `PRAGMA foreign_keys = ON;` e `PRAGMA busy_timeout = 10000;`.
- **`migrations.py`**:
  - Migrações sequenciais atômicas: v0 → v1 → v2 → v3.
  - Cada migração valida sua estrutura dentro da própria transação e somente atualiza `PRAGMA user_version` após a confirmação integral.
  - Validação sensível à versão: `validar_esquema_v1` aceita bancos v1 sem exigir colunas de certificado; `validar_esquema_v2` checa a presença das novas colunas `NULL`.
  - **Auditoria de Segurança Integrada**: `_verificar_ausencia_segredos` impede colunas proibidas (`senha`, `password`, `secret`, `chave_privada`, `pem`, `pfx_data`, etc.).
- **`sqlite.py` (`SqliteEmpresaRepository`)**:
  - Mapeamento completo dos campos cadastrais e de certificado.
  - Validação de integridade na leitura do banco (garante que `certificado_cnpj` normalizado seja compatível com `empresa.cnpj`).
  - Preservação estrita de timestamps e rollback seguro em falha.
  - Persistência do cursor público `ultimo_nsu_adn`, separado por empresa e iniciado em zero.

### 2.5. `src/nfse_facil/ui/`
- **`components/certificate_dialog.py` (`CertificateDialog`)**:
  - Janela modal para inspeção e associação de certificado A1.
  - **Execução em Segundo Plano**: `ThreadPoolExecutor` executa leitura e decodificação em worker isolado, sem qualquer chamada a métodos do Tkinter fora da thread principal.
  - **Proteção Visual e de Segredos**:
    - Campo de senha com máscara `*` e opção de visualização.
    - Limpeza imediata do campo visual de senha logo após o clique em "Inspecionar".
    - Desativação do botão durante a operação para impedir duplo clique.
    - Cancelamento seguro de timers `after` e liberação de grab em `destroy()`.
    - Eliminação imediata de referências da senha em variáveis locais (`del`).
- **`components/certificate_dialog.py` (`CertificateInfoDialog`)**:
  - Modal somente-leitura exibindo metadados persistidos (CNPJ, validade UTC, emissor, fingerprint SHA-256 e caminho de origem).
- **`components/company_dialog.py` (`CompanyDialog`)**:
  - Botão "Preencher via Certificado A1..." para agilizar o cadastro de nova empresa.
  - Ao editar o CNPJ de uma empresa que possui certificado associado: exibe diálogo de confirmação claro antes de salvar. Se cancelado, preserva todos os dados intactos; se confirmado, atualiza o CNPJ e limpa a associação anterior sem tocar no arquivo físico.
- **`main_window.py`**:
  - Seção "Certificado digital" integrada ao cartão de detalhes da empresa com badges de status ("Nenhum certificado associado", "✓ Certificado válido", "⚠️ Próximo do vencimento", "❌ Certificado vencido", "⚠️ Arquivo do certificado não encontrado").
  - Botões para selecionar/trocar certificado, visualizar detalhes e remover associação com confirmação.

### 2.6. `src/nfse_facil/infrastructure/http/`
- **`adn_client.py` (`ADNClient`)**:
  - Ambientes oficiais isolados por enum: produção restrita e produção.
  - Consultas de contribuinte por NSU e de eventos por chave de acesso.
  - TLS do servidor sempre validado; redirecionamentos desativados para impedir encaminhamento do certificado a outro host.
  - Timeouts de conexão/leitura, leitura em fluxo e limite máximo de 50 MB por resposta.
  - Tradução de erros HTTP/rede para mensagens públicas sem conteúdo técnico interno.
  - Transporte injetável para testes completos sem conexão com os serviços governamentais.
  - Uso de `requests-pkcs12`: a biblioteca gera internamente um PEM temporário criptografado com senha aleatória, carrega o contexto TLS e remove o arquivo imediatamente. Nenhum caminho temporário é conhecido ou persistido pela aplicação.

---

## 3. Diretrizes de Segurança de Dados e Segredos

1. **Zero Persistência Permanente de Segredos**: Nenhuma senha ou chave privada é gravada no SQLite, configurações ou logs. Durante o mTLS, a biblioteca HTTP utiliza um PEM temporário criptografado e o remove após carregar o contexto TLS.
2. **Ciclo de Vida Mínimo em Memória**: A senha é coletada temporariamente, utilizada no worker para a chamada OpenSSL em memória e descartada imediatamente.
3. **Impossibilidade de Zeroization Garantida em Python**: Documentado explicitamente que o interpretador CPython gerencia strings como objetos imutáveis; adotam-se as melhores práticas possíveis (escopo estreito, `del`, limpeza do widget de tela).
4. **Mensagens Sanitizadas**: Exceções criptográficas da OpenSSL são capturadas e traduzidas em mensagens claras e amigáveis ao usuário ("Senha incorreta ou certificado inválido", "Arquivo de certificado corrompido", etc.), sem vazamento de detalhes internos da stack.

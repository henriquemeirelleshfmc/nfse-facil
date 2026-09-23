# Relatório de Conclusão - ETAPA 02

**Projeto**: NFS-e Fácil  
**Etapa**: 02 — Persistência Local e Gestão de Empresas  
**Local do Projeto**: `<pasta-do-projeto>`  
**Data de Conclusão**: 21/09/2026  
**Status**: Concluída e Aprovada com 100% dos testes aprovados  

---

## 1. Resumo Executivo

A **Etapa 02 — Persistência Local e Gestão de Empresas** foi concluída com êxito. O sistema evoluiu a fundação arquitetural da Etapa 01, substituindo o repositório volátil em memória por um mecanismo robusto, seguro e atômico de persistência em banco de dados SQLite local, sem utilização de ORM pesado e utilizando exclusivamente os recursos da biblioteca padrão `sqlite3` do Python.

Ao fechar e abrir novamente a aplicação, todas as empresas cadastradas e suas configurações permanecem preservadas. Além disso, a gestão visual de empresas agora oferece fluxo completo de **Adição**, **Edição** (preservando o identificador e a data original de criação) e **Remoção Segura de Cadastro** (que exclui o registro do banco sem jamais tocar nos arquivos ou pastas no disco).

---

## 2. Detalhamento da Persistência Local (SQLite)

### 2.1. Localização e Resolução de Caminhos
- **Caminho Padrão no Windows**: `%LOCALAPPDATA%\NFSeFacil\data\nfse_facil.db`.
- **Resolução Dinâmica**: Implementada no módulo `settings.py` por meio da verificação de `os.getenv("LOCALAPPDATA")`.
- **Mecanismo de Fallback**: Caso a variável de ambiente não esteja presente ou o sistema não seja Windows, o caminho recai automaticamente para `~/.nfse_facil/data/nfse_facil.db`.
- **Injeção de Caminho Customizado**: As funções de conexão (`open_connection`, `get_connection`), o módulo `Settings` e a classe `SqliteEmpresaRepository` aceitam o parâmetro opcional `custom_db_path` / `db_path`, viabilizando o isolamento absoluto dos testes automatizados em diretórios temporários (`tmp_path`) sem afetar os dados reais do usuário.

### 2.2. Política de Conexões
- **Ciclo de Vida de Curta Duração**: Cada operação do repositório abre, executa e fecha a conexão imediatamente utilizando o context manager `get_connection()`. Essa abordagem elimina bloqueios prolongados de arquivo no Windows e previne travamentos de concorrência.
- **Configuração Obrigatória de Pragmas**:
  - `PRAGMA foreign_keys = ON;` (garantia de integridade referencial).
  - `PRAGMA busy_timeout = 10000;` (timeout de 10 segundos para espera ativa em concorrência transitória).
  - `sqlite3.Row` ativado como `row_factory` para permitir acesso aos campos por nome de coluna e por índice.
- **Transações Atômicas**: As operações de escrita utilizam explicitamente o context manager `transaction()`, aplicando `BEGIN IMMEDIATE` para garantia de lock de escrita imediato e prevenção de deadlocks.

### 2.3. Esquema e Migrações Atômicas
- **Controle de Versão via `PRAGMA user_version`**: O controle do esquema é gerenciado pelas funções `aplicar_migracoes` e `validar_esquema` em `migrations.py`.
- **Migração v1**:
  ```sql
  CREATE TABLE IF NOT EXISTS empresas (
      id TEXT PRIMARY KEY,
      razao_social TEXT NOT NULL,
      nome_fantasia TEXT NOT NULL DEFAULT '',
      cnpj TEXT NOT NULL,
      pasta_documentos TEXT NOT NULL,
      certificado_caminho TEXT,
      ativo INTEGER NOT NULL DEFAULT 1,
      criado_em TEXT NOT NULL,
      atualizado_em TEXT NOT NULL,
      CONSTRAINT uq_empresas_cnpj UNIQUE (cnpj)
  );
  ```
  *(Nota técnica: A cláusula `CONSTRAINT uq_empresas_cnpj UNIQUE (cnpj)` cria internamente no SQLite o índice exclusivo para a coluna CNPJ, dispensando comandos redundantes de criação de índice).*
- **Atomicidade e Rollback Integral**: A aplicação da migração, a validação estrutural profunda e a alteração de `PRAGMA user_version` ocorrem sob uma única transação lógica. Se qualquer instrução falhar ou o esquema for considerado incompleto, ocorre rollback integral: `user_version` permanece `0` e nenhum dado existente é modificado ou apagado.
- **Proteção Contra Versões Futuras**: Caso o banco local apresente `user_version > 1` (criado por versão mais nova do aplicativo), o sistema rejeita a inicialização com a exceção `VersaoEsquemaIncompativelError`, protegendo os dados do usuário contra corrupção.

### 2.4. Formato e Normalização de Timestamps
- Todos os registros gravam datas e horários no formato textual **ISO-8601 UTC consciente com microsegundos**:
  `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (obtido via `datetime.isoformat(timespec="microseconds")`).
- **Normalização Real para UTC**: Datas conscientes com outro fuso horário (ex: deslocamento `-04:00` de Manaus) são convertidas via `astimezone(timezone.utc)`, garantindo que todos os timestamps persistidos terminem estritamente em `+00:00`.
- Na leitura, o parser converte a string de volta para objetos `datetime` com fuso horário UTC (`timezone.utc`), permitindo ordenações e cálculos temporais precisos e padronizados.
- **Atribuição Pós-Commit**: No modelo e no repositório, `empresa.criado_em` e `empresa.atualizado_em` recebem os valores efetivamente persistidos somente após o commit da transação. Em caso de falha de persistência, os timestamps do objeto em memória são preservados intactos.

---

## 3. Repositório SQLite de Empresas (`SqliteEmpresaRepository`)

O repositório implementa integralmente o contrato abstrato `EmpresaRepository`, oferecendo:
1. **`salvar(empresa)`**:
   - Insere uma nova empresa ou atualiza uma preexistente caso o `id` já conste na base.
   - A consulta e a gravação ocorrem dentro do mesmo bloco transacional `transaction(conn)`.
   - Em caso de conflito de CNPJ com outra empresa cadastrada, captura o `sqlite3.IntegrityError` e traduz com precisão para a exceção de domínio `CNPJDuplicadoError`.
   - Na edição, permite que a empresa mantenha seu próprio CNPJ sem conflito.
2. **`obter_por_id(id)` e `obter_por_cnpj(cnpj)`**:
   - Localização direta com conversão de `sqlite3.Row` para a entidade de domínio `Empresa`.
   - Erros de SQLite são traduzidos para `PersistenciaError` com chaining (`from err`).
3. **`listar_todas()`**:
   - Retorna todas as empresas ativas com ordenação amigável e determinística.
4. **`pesquisar(termo)`**:
   - Implementa busca textual insensível a maiúsculas/minúsculas e marcas diacríticas (acentos) através da função de domínio `normalizar_para_busca()`.
   - Garante que a busca por termos como "Álvaro", "álvaro", "alvaro" ou "alvar" localize empresas como "Álvaro Engenharia Ltda", superando limitações do collation `NOCASE` nativo do SQLite (que em builds padrão do Windows opera apenas sobre ASCII).
   - Delega para `listar_todas()`, propagando `PersistenciaError` sem reempacotamento repetitivo.
5. **`remover(id)`**:
   - Executa `DELETE FROM empresas WHERE id = ?` em transação atômica.
6. **Ordenação Natural em Português**:
   - A ordenação utiliza `normalizar_para_busca()` para extrair caracteres base desprovidos de acentos via NFKD. Desta forma, "Álvaro" é ordenado antes de "Beta" e "Zélia", com desempate determinístico pelo nome em minúsculas, CNPJ e ID.

---

## 4. Serviço de Gestão de Pastas (`PastaDocumentosService`)

O serviço `PastaDocumentosService` foi projetado de forma desacoplada da interface gráfica:
- **Criação Segura**: Cria a pasta e diretórios pais caso não existam (`parents=True, exist_ok=True`).
- **Validação de Permissão de Escrita com Limpeza Estrita**: Realiza um teste prático com nome imprevisível (`.perm_check_{uuid.uuid4().hex}`) e criação em modo exclusivo (`mode='x'`).
- **Segurança contra Resíduos**: O arquivo temporário é removido em bloco `finally`. Se a gravação funcionar mas a exclusão falhar, dispara `PastaInvalidaError`, pois resíduos não são tratados como sucesso. Se ambos falharem, a causa original é preservada no encadeamento (`from err_escrita`) e ambas as falhas constam na mensagem.
- **Idempotência Estrita**: Se a pasta já existir previamente no disco, o serviço apenas valida a permissão sem remover, renomear ou modificar qualquer arquivo preexistente do cliente.
- **Tratamento de Exceções**: Lança `PastaInvalidaError` caso o caminho seja vazio, aponte para um arquivo regular em vez de pasta, ou ocorra negação de permissão pelo sistema operacional.

---

## 5. Aprimoramentos na Interface Gráfica (CustomTkinter)

1. **Janela Principal (`MainWindow`)**:
   - **Cartão de Empresa Selecionada**: Apresenta Razão Social, Nome Fantasia, CNPJ formatado e caminho da pasta.
   - **Botões Operacionais**:
     - `✏️ Editar empresa`: Abre o diálogo modal populado com os dados da empresa ativa.
     - `🗑️ Remover cadastro`: Solicita confirmação explícita ao usuário com mensagem clara informando que apenas o cadastro no aplicativo será removido e que os arquivos de documentos na pasta do cliente NÃO serão apagados.
   - **Retorno ao Estado Vazio**: Ao remover a última empresa, a aplicação oculta o painel operacional e exibe imediatamente o painel de boas-vindas com o botão para cadastrar uma nova empresa.
   - **Destruição Limpa**: O método `destroy()` cancela todos os timers pendentes do Tkinter no Windows, evitando erros e vazamentos de recursos.
2. **Centralização de Mensagens (`src/nfse_facil/ui/messages.py`)**:
   - Mensagens atemporais centralizadas em constantes e funções testáveis sem bloqueio de tela:
     - `MSG_SEGURANCA_CERTIFICADO`: "A senha do certificado nunca será armazenada. Em uma versão futura, ela será solicitada somente quando necessária para acessar o certificado."
     - `TITULO_AVISO_DOWNLOAD`: "Comunicação com a NFS-e Nacional".
     - `obter_mensagem_aviso_download()`: texto transparente explicando o status sem promessas da Etapa 02.
3. **Diálogo de Empresa (`CompanyDialog`)**:
   - Opera nos modos de **Adição** e **Edição**.
   - Preserva estritamente o `id` e a data de criação `criado_em` da empresa ao editar.
   - Em caso de dados inválidos (ex: CNPJ incorreto ou pasta sem permissão), exibe alerta visual em vermelho e não fecha a janela, mantendo o estado da aplicação principal rigorosamente intacto.
   - Sincroniza tarefas ociosas de layout (`update_idletasks()`) e cancela timers agendados do `CTkToplevel` em `destroy()`, eliminando violações de acesso no Windows.
4. **Ponto de Entrada Flexível (`create_app`)**:
   - `create_app(repository: EmpresaRepository | None = None)` permite a execução normal do aplicativo instanciando o repositório SQLite padrão, bem como a injeção de repositórios em memória ou temporários nos testes automatizados.

---

## 6. Dados Armazenados vs. Dados NUNCA Armazenados

| Dado | Onde é Salvo | Justificativa |
| :--- | :--- | :--- |
| **ID da Empresa** | Banco SQLite local | Identificador primário UUID v4 |
| **Razão Social e Nome Fantasia** | Banco SQLite local | Identificação visual do cliente |
| **CNPJ** | Banco SQLite local | 14 posições alfanuméricas ou numéricas sem máscara |
| **Pasta de Documentos** | Banco SQLite local | Caminho de destino para downloads |
| **Ativo / Timestamps** | Banco SQLite local | Controle de ciclo de vida e auditoria (ISO-8601 UTC) |
| **Senha do Certificado Digital** | ❌ **NUNCA ARMAZENADA** | Solicitada apenas em memória no momento do acesso futuro |
| **Chaves Privadas / PINs** | ❌ **NUNCA ARMAZENADAS** | O sistema nunca armazenará chaves ou credenciais |

---

## 7. Verificação de Arquivos Residuais no Repositório

Foi realizada uma auditoria completa no diretório de trabalho do projeto:
- **Arquivos `.db`, `.sqlite`, `.sqlite3`**: 0 encontrados na árvore do projeto.
- **Arquivos de journal/WAL (`-journal`, `-wal`, `-shm`)**: 0 encontrados.
- **Arquivos de teste de permissão (`.perm_check_*`)**: 0 encontrados.
- **Configuração do `.gitignore`**: Atualizado para ignorar ativamente arquivos de banco locais e de concorrência (`*.db*`, `*.sqlite*`, `*.sqlite3*`, `*.db-journal`, `*.db-wal`, `*.db-shm`).
- **Comportamento dos Testes**: 100% dos testes que utilizam SQLite operam em diretórios temporários gerenciados pelo pytest (`tmp_path`), garantindo que nenhum arquivo de teste permaneça em disco após a execução.

---

## 8. Resultados da Suite de Testes Automatizados

A suite conta com **76 testes automatizados**, todos aprovados com 100% dos testes aprovados:

| Módulo de Teste | Quantidade | Foco dos Testes | Status |
| :--- | :---: | :--- | :---: |
| `test_cnpj.py` | 17 | CNPJ numérico, alfanumérico, Módulo 11, sanitização e formatação | **Aprovado** |
| `test_database.py` | 8 | Conexão SQLite, Pragmas, migração atômica, rollback v0 incompleto e validação de esquema | **Aprovado** |
| `test_empresa.py` | 8 | Entidade Empresa, validação de campos, garantia de ausência de senha e normalização UTC | **Aprovado** |
| `test_pasta_documentos.py` | 9 | Criação de pasta, idempotência, caminhos inválidos, gravação real e limpeza estrita | **Aprovado** |
| `test_periodo.py` | 8 | Período de consulta, virada de ano, validações de data e preferências | **Aprovado** |
| `test_repository.py` | 6 | Repositório InMemory e busca insensível a acentos com Álvaro | **Aprovado** |
| `test_sqlite_repository.py` | 12 | CRUD SQLite, persistência ao reabrir, unicidade, busca Álvaro, erro SQLite e UTC `-04:00` | **Aprovado** |
| `test_ui_company_management.py` | 4 | Fluxos de UI: Adicionar, Editar, Falha de Edição e Remoção Segura | **Aprovado** |
| `test_ui_smoke.py` | 4 | Fumaça de UI, componentes, fábrica `create_app()`, mensagens atemporais e modal | **Aprovado** |
| **TOTAL** | **76** | **Testes Automatizados (Etapas 01 e 02)** | **100% PASS** |

### Saída da Execução dos Testes:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-8.0.0, pluggy-1.6.0
rootdir: <pasta-do-projeto>
configfile: pyproject.toml
collected 76 items

tests/test_cnpj.py .................                             [ 22%]
tests/test_database.py ........                                  [ 32%]
tests/test_empresa.py ........                                   [ 43%]
tests/test_pasta_documentos.py .........                         [ 55%]
tests/test_periodo.py ........                                   [ 65%]
tests/test_repository.py ......                                  [ 73%]
tests/test_sqlite_repository.py ............                     [ 89%]
tests/test_ui_company_management.py ....                         [ 94%]
tests/test_ui_smoke.py ....                                      [100%]

============================= 76 passed in 1.50s ==============================
```

---

## 9. Comandos Executados Durante a Validação

```powershell
# 1. Execução de toda a suite de testes automatizados
python -m pytest tests -v

# 2. Compilação de bytecode para garantia de ausência de erros de sintaxe
python -m compileall src tests

# 3. Verificação de ausência de arquivos residuais de banco de dados e testes de permissão
python -c "from pathlib import Path; print('DB:', list(Path('.').glob('**/*.db*'))); print('PERM:', list(Path('.').glob('**/.perm_check_*')))"

# 4. Checagem de status de controle de versão (sem commit ou push)
git status
git remote -v
git log --oneline --all
```

---

## 10. Declaração de Escopo e Próximos Passos

- [x] **ETAPA 01 — Fundação do Projeto**: Concluída e auditada.
- [x] **ETAPA 02 — Persistência Local e Gestão de Empresas**: Concluída e auditada.
- [ ] **ETAPA 03 — Certificados Digitais A1**: **NÃO INICIADA**. Nenhuma leitura de arquivo `.pfx`/`.p12`, requisição de senha ou rotina mTLS foi antecipada nesta etapa.

---

## 11. Correções Pós-Auditoria da Etapa 02

Em atendimento rigoroso à revisão pós-auditoria da Etapa 02, foram executados os seguintes ajustes arquiteturais e correções:

### 1. Migração Atômica de Banco v0 Incompleto
- A função `aplicar_migracoes(conn)` passou a executar `validar_esquema(conn)` **dentro da mesma transação atômica** (`with transaction(conn):`) antes de executar `PRAGMA user_version = 1`.
- Caso um banco versão 0 possua tabela `empresas` com estrutura deficiente ou incompleta, a validação dispara `PersistenciaError`, desfazendo integralmente qualquer alteração na transação.
- O banco permanece com `user_version == 0` e todos os dados pré-existentes são preservados sem exclusões silenciosas.
- Testado e comprovado no teste automatizado `test_migracao_v0_com_esquema_incompleto_faz_rollback_preserva_versao_zero_e_dados`.

### 2. Validação Rigorosa e Estrita de Esquema
- A função `validar_esquema(conn)` realiza auditoria profunda da estrutura da tabela `empresas`:
  1. Existência da tabela `empresas` no catálogo SQLite (`sqlite_master`).
  2. Presença de todas as colunas obrigatórias (`id`, `razao_social`, `nome_fantasia`, `cnpj`, `pasta_documentos`, `certificado_caminho`, `ativo`, `criado_em`, `atualizado_em`).
  3. Validação de Chave Primária em `id` (`pk >= 1` em `PRAGMA table_info`).
  4. Validação de campos essenciais marcados como `NOT NULL` (`notnull == 1` para `razao_social`, `cnpj`, `pasta_documentos`, `criado_em`, `atualizado_em`, `ativo`).
  5. Validação de restrição efetiva de unicidade em `cnpj` através da inspeção de `PRAGMA index_list('empresas')` e `PRAGMA index_info(index_name)`.
- Testado e comprovado no teste automatizado `test_validacao_esquema_falhas_especificas`.

### 3. Timestamps sem Testes Frágeis
- A persistência dos campos `criado_em` e `atualizado_em` agora invoca explicitamente `datetime.isoformat(timespec="microseconds")`, assegurando exatamente 6 casas decimais de precisão mesmo quando o microsegundo for zero.
- Os testes não presumem `microsecond > 0`, conferem diretamente o texto bruto persistido no SQLite e validam a expressão regular `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$`.
- Para aferir a mudança em `atualizado_em`, utiliza-se uma data fixa conhecida no passado (`2020-01-01T12:00:00.000000+00:00`), sem nenhuma utilização de chamadas a `sleep`.
- Comprova-se que a entidade em memória recebe exatamente a mesma string ISO-8601 persistida.
- Testado em `test_atualizacao_preserva_id_e_criado_em_e_atualiza_timestamp`.

### 4. Normalização Real para UTC e Preservação de Timestamps em Falha
- No modelo `Empresa` e no repositório `SqliteEmpresaRepository`:
  - Datas ingênuas (sem fuso) são interpretadas como UTC via `replace(tzinfo=timezone.utc)`.
  - Datas conscientes em qualquer outro fuso (ex: `America/Manaus` ou `timezone(timedelta(hours=-4))`) são convertidas para UTC via `astimezone(timezone.utc)`.
  - Todos os timestamps gravados no SQLite terminam obrigatoriamente em `+00:00` com `timespec="microseconds"`.
  - O instante cronológico permanece rigorosamente equivalente.
  - Na atualização, `criado_em` é lido do banco e atribuído ao objeto de domínio apenas após o commit bem-sucedido.
  - Se a transação falhar (ex: colisão de CNPJ), os atributos `criado_em` e `atualizado_em` do objeto em memória são preservados sem modificação.
- Testado e comprovado em `test_normalizacao_real_para_utc_e_preservacao_em_falha`.

### 5. Isolamento Transacional na Persistência de Empresas
- No método `SqliteEmpresaRepository.salvar()`, a leitura prévia de `criado_em` (para empresas existentes) foi movida para dentro do bloco transacional `with transaction(conn):`.
- Isso elimina race conditions e garante isolamento ACID integral entre a consulta e a instrução `INSERT OR REPLACE`.

### 6. Tradução Consistente de Erros do SQLite sem Reempacotamento
- Todas as operações do repositório SQLite capturam exceções técnicas `sqlite3.Error` nas fronteiras apropriadas e as convertem para `PersistenciaError` com chaining (`from err`).
- Exceções de domínio preexistentes (`PersistenciaError`, `CNPJDuplicadoError`, `VersaoEsquemaIncompativelError`) propagam-se livremente sem reempacotamento.
- O método `pesquisar()` delega para `listar_todas()` sem adicionar camadas repetitivas de try/except.
- Testado em `test_erros_leitura_sqlite_sao_traduzidos_para_persistencia_error` e `test_pesquisar_propaga_persistencia_error_sem_reempacotar`.

### 7. Busca Textual e Ordenação Insensíveis a Acentos
- Criada a função `normalizar_para_busca(texto: str) -> str` em `src/nfse_facil/domain/validators.py` e exportada na camada de domínio.
- Utiliza decomposição canônica `unicodedata.normalize("NFKD", texto)`, remoção de marcas diacríticas (`unicodedata.combining(c)`) e `casefold()`.
- Aplicada em `SqliteEmpresaRepository.pesquisar()` e `InMemoryEmpresaRepository.pesquisar()`, bem como nas funções de ordenação alfabética natural.
- Testada extensivamente para a palavra "Álvaro": buscas por "Álvaro", "álvaro", "ÁLVARO", "alvaro" e "alvar" localizam a empresa com 100% de precisão tanto no SQLite quanto no repositório em memória.

### 8. Teste de Gravação Real de Diretórios e Limpeza Estrita
- Implementado em `PastaDocumentosService._testar_gravacao()`:
  - Criação exclusiva com modo `x` e nome imprevisível (`.perm_check_{uuid.uuid4().hex}`).
  - Variável de estado `arquivo_criado` registrando o momento exato da criação.
  - Tentativa de remoção condicionada a `arquivo_criado` e à verificação de existência do arquivo.
  - Se a gravação tiver sucesso mas a limpeza falhar, levanta `PastaInvalidaError` (resíduos não são tratados como sucesso).
  - Se a gravação e a limpeza falharem conjuntamente, a causa original é preservada no chaining (`from err_escrita`) e a falha de limpeza é informada na mensagem.
  - Nenhum arquivo fora do escopo desta execução é excluído.
  - Confirmado que nenhum arquivo `.perm_check_*` permanece no disco após a execução.
- Testado em `test_teste_gravacao_sucesso_nao_deixa_residuos`, `test_falha_escrita_levanta_pastainvalidaerror_sem_residuos`, `test_escrita_sucesso_mas_falha_limpeza_levanta_erro` e `test_falha_escrita_e_falha_limpeza_preserva_causa_original`.

### 9. Centralização e Limpeza de Textos da Interface
- Criado o módulo `src/nfse_facil/ui/messages.py` contendo:
  - `MSG_SEGURANCA_CERTIFICADO`: "A senha do certificado nunca será armazenada. Em uma versão futura, ela será solicitada somente quando necessária para acessar o certificado."
  - `TITULO_AVISO_DOWNLOAD`: "Comunicação com a NFS-e Nacional".
  - `obter_mensagem_aviso_download(empresa_nome, cnpj_formatado, periodo_rotulo)`: texto atemporal sem promessas da Etapa 02.
- O método `_clicar_baixar_notas` foi atualizado para invocar `_exibir_modal_aviso_downloads()`, utilizando o conteúdo centralizado.
- Os testes de fumaça da UI auditam as mensagens diretamente sem abertura de diálogos bloqueantes e validam que o modal utiliza as constantes e funções centralizadas.

### 10. Alinhamento de Documentação Arquitetural
- `docs/arquitetura.md` foi atualizado para remover menções a classes não existentes, refletindo a arquitetura real baseada em funções e context managers em `connection.py` e `migrations.py`.
- `README.md` foi alinhado quanto à segurança de certificados, número total de testes (76 testes) e função `normalizar_para_busca()`.

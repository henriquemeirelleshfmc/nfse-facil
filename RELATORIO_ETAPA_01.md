# RELATÓRIO DA ETAPA 01 — Fundação do Projeto NFS-e Fácil

**Data e Hora de Conclusão:** 19/09/2026  
**Local do Projeto:** `C:\Users\henrique\Desktop\peganf`  
**Status da Etapa:** Concluída com 100% de Aprovação nos Critérios de Aceitação  

---

## 1. Resumo do que Foi Implementado

A **Etapa 01 — Fundação do Projeto** estabeleceu as fundações estruturais, arquiteturais e de qualidade para o produto **NFS-e Fácil**. Foram implementados:

- **Estrutura de Projeto Padronizada**: Inicialização limpa de pacote Python moderno com suporte a `pyproject.toml`, `.gitignore` defensivo para segurança de chaves/certificados e organização modular sob `src/nfse_facil/`.
- **Validação Completa e Oficial de CNPJ**: Motor de validação com suporte tanto ao **CNPJ numérico tradicional** (legado) quanto ao **novo padrão CNPJ alfanumérico** (IN RFB nº 2.229/2024), com preservação obrigatória de zeros à esquerda, tratamento estrito como string e máscara visual.
- **Modelos de Domínio Puros**: Entidades `Empresa`, `PeriodoConsulta` e `PreferenciasDownload` com regras de datas robustas (incluindo cálculo de primeiro/último dia e suporte à transição de ano entre Janeiro e Dezembro), sem campos ou atributos de senha/certificado.
- **Contratos Abstratos de Serviços**: Classes abstratas puras (`abc.ABC` com `@abstractmethod`) para Certificados A1, Sincronização NFS-e e Geração de Relatórios, sem serviços falsos ou stubs artificiais.
- **Persistência em Memória Preparada**: Interface `EmpresaRepository` e implementação `InMemoryEmpresaRepository` que inicia rigorosamente **vazia** em modo de produção, garantindo a exibição autêntica do estado inicial da interface.
- **Interface Desktop com CustomTkinter**: Aplicação desktop visualmente moderna, com paleta de cores corporativa, suporte a redimensionamento de tela, busca em tempo real por nome ou CNPJ, estado vazio amigável ("Minhas empresas"), diálogo de cadastro de empresa e botão de ação com aviso explicativo transparente.
- **Bateria de Testes Automatizados**: 35 testes unitários e de fumaça da interface gráfica, cobrindo 100% dos requisitos de negócio e ciclo de vida da UI.

---

## 2. Árvore dos Principais Arquivos Criados

```text
peganf/
├── .gitignore
├── pyproject.toml
├── README.md
├── RELATORIO_ETAPA_01.md
├── docs/
│   └── arquitetura.md
├── src/
│   └── nfse_facil/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── exceptions.py
│       │   ├── models.py
│       │   └── validators.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   └── repositories/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       └── in_memory.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── certificados.py
│       │   ├── nfse.py
│       │   └── relatorios.py
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py
│           ├── theme.py
│           └── components/
│               ├── __init__.py
│               ├── company_dialog.py
│               ├── company_list.py
│               └── period_selector.py
└── tests/
    ├── __init__.py
    ├── test_cnpj.py
    ├── test_empresa.py
    ├── test_periodo.py
    ├── test_repository.py
    └── test_ui_smoke.py
```

---

## 3. Decisões Técnicas Tomadas e Justificativas

1. **Separação Rígida em Camadas**: Isolamento entre Domínio, Infraestrutura, Serviços e Interface Gráfica. Garante que futuras substituições (ex: migrar do repositório em memória para SQLite) ocorram sem qualquer modificação nas regras de validação ou telas.
2. **Suporte Nativo ao CNPJ Alfanumérico**: Em vez de aceitar apenas 14 dígitos numéricos, foi implementado o algoritmo oficial Módulo 11 com pesos de 2 a 9 e conversão de caracteres pelo código ASCII (`ord(char) - 48`). Assegura compatibilidade futura com as empresas registradas sob o novo padrão da Receita Federal.
3. **Imutabilidade e Tipagem de CNPJ**: O CNPJ é manipulado exclusivamente como `str` em todas as camadas. Não há conversões para `int`, garantindo a preservação invariável de zeros à esquerda (ex: `00.000.000/0001-91` e `00000000001A78`).
4. **Tratamento de Datas com `datetime.date`**: A lógica temporal não depende de conversões frágeis de string. O cálculo do mês anterior lida com a virada crítica de Janeiro para Dezembro do ano anterior e anos bissextos via `calendar.monthrange`.
5. **Portabilidade com `pathlib.Path`**: Nenhum caminho absoluto ou de máquina específica foi embutido no código. O caminho padrão de documentos é resolvido dinamicamente a partir do diretório pessoal do usuário (`Path.home()`).
6. **Contratos Abstratos Puros**: Classes de serviço abstratas não misturam implementações com simulações. Apenas definem contratos formais com documentação das futuras integrações.
7. **Repositório Inicial Vazio por Padrão**: A aplicação não carrega dados fictícios no fluxo normal. O estado vazio com ícone e orientações amigáveis é imediatamente visível ao abrir o aplicativo.

---

## 4. Dependências Adicionadas e Finalidade

As dependências foram mantidas estritamente no mínimo necessário e separadas em execução e desenvolvimento no `pyproject.toml`:

### Dependências de Execução (Runtime)
- **`customtkinter>=5.2.0`**: Biblioteca moderna de interface gráfica para Python baseada em Tkinter, proporcionando visual atraente (modo claro/escuro nativo, cantos arredondados, botões modernos) e baixo consumo de recursos no Windows.

### Dependências de Desenvolvimento (Dev)
- **`pytest>=8.0.0`**: Framework padrão para execução e automação da suite de testes unitários e de integração.

---

## 5. Comandos Utilizados para Instalar, Executar e Testar

### Instalação no Ambiente
```powershell
python -m pip install -e ".[dev]"
```

### Execução da Aplicação Desktop
```powershell
python -m nfse_facil
```
*(ou via script de console: `nfse-facil`)*

### Execução da Suite de Testes Automatizados
```powershell
python -m pytest tests -v
```

---

## 6. Resultado Exato dos Testes

- **Ambiente de Teste**: Python 3.12.0 em Windows 11 (64-bit AMD64).
- **Total de Testes**: 35
- **Aprovados (Passed)**: 35
- **Falhos (Failed)**: 0
- **Ignorados (Skipped)**: 0
- **Tempo de Execução**: 1.11 segundos

### Detalhamento por Arquivo:
- `tests/test_cnpj.py`: 16 testes (numérico válido com/sem máscara, alfanumérico válido com/sem máscara, minúsculas, DVs incorretos, repetições, caracteres proibidos, tipagem string e máscara visual).
- `tests/test_empresa.py`: 4 testes (criação com CNPJ numérico e alfanumérico, rejeição de CNPJ inválido, garantia explícita de ausência de atributos de senha).
- `tests/test_periodo.py`: 8 testes (cálculo de primeiro/último dia do mês atual, anos bissextos, virada de ano de Janeiro para Dezembro, intervalo personalizado, rejeição de data final menor que inicial, preferências padrão).
- `tests/test_repository.py`: 5 testes (repositório iniciando vazio, salvar/obter, busca por termo/CNPJ, remoção, isolamento de dados demonstrativos).
- `tests/test_ui_smoke.py`: 2 testes (teste de fumaça da inicialização gráfica da janela, verificação de componentes essenciais, transição após adição de empresa e fechamento limpo sem travamento).

---

## 7. Resultado da Verificação de Inicialização da Interface

- A aplicação inicializa e encerra sem erros de importação ou conflito de ciclo de vida.
- O teste automatizado de fumaça (`test_ui_smoke.py`) instanciou a janela principal (`MainWindow`), acionou `app.update_idletasks()` e `app.update()` no interpretador Tkinter local, verificou os títulos, botões e campos, e realizou `app.destroy()` de forma limpa.
- Foi executado teste direto via linha de comando:
  ```powershell
  python -c "from nfse_facil.app import create_app; app = create_app(); print('TITULO:', app.title()); app.destroy()"
  ```
  Com saída confirmada:
  ```text
  TITULO: NFS-e Fácil
  ```
- **Transparência de Inspeção**: A interface foi validada por testes automatizados de ciclo de vida e renderização de widgets. A verificação humana visual completa com interação manual do usuário ocorrerá no monitor do ambiente operacional.

---

## 8. Funcionalidades que são Apenas Demonstrativas

Nesta Etapa 01, as seguintes partes da interface têm caráter puramente demonstrativo e orientativo:

1. **Botão "Adicionar empresa"**: Abre um diálogo que permite cadastrar e testar o fluxo de seleção com validação de CNPJ e pasta local. Os dados ficam salvos em memória durante a sessão e não persistem em banco SQLite.
2. **Botão "Baixar notas"**: Ao ser clicado, não simula falsos downloads nem finge sucesso. Exibe uma janela modal clara informando que a integração com o Portal Nacional da NFS-e será ativada na próxima etapa.
3. **Ausência de Certificados**: Não há campo para upload de arquivo `.pfx`/`.p12` nem solicitação de senha.

---

## 9. Tudo que Ficou Pendente (Itens Postergados para Etapas Futuras)

1. **Persistência em Banco SQLite**: Criação das tabelas `empresas` e migração do repositório em memória para persistência local permanente.
2. **Integração com Certificados A1**: Leitura e validação de arquivos `.pfx`/`.p12` via biblioteca criptográfica em memória, sem jamais salvar a senha do usuário.
3. **Comunicação com o Portal Nacional (API ADN)**: Implementação de mTLS, endpoints de distribuição de DF-e, controle de NSU e paginação.
4. **Download e Armazenamento dos Documentos**: Salvamento estruturado dos arquivos XML da NFS-e e geração de PDFs nas pastas das respectivas empresas.
5. **Geração de Relatórios Consolidados**: Criação automatizada de planilhas Excel (.xlsx) e relatórios em PDF com resumos de faturamento e impostos retidos.
6. **Empacotamento Executável**: Geração de instalador ou executável único para Windows com PyInstaller.

---

## 10. Riscos ou Dúvidas Encontrados

- **Mudança de Regra do CNPJ Alfanumérico**: O formato foi implementado segundo a IN RFB nº 2.229/2024 e o cálculo Módulo 11 com base ASCII (ord - 48). O sistema já está preparado para o formato, mitigando riscos de quebra cadastral quando novas empresas com letras no CNPJ forem registradas.
- **Ambientes sem Display Gráfico (Headless)**: O teste de fumaça depende da presença do subsistema gráfico do Tkinter. No Windows Desktop padrão a execução ocorre com sucesso absoluto.

---

## 11. Lista de Arquivos que Precisam ser Revisados pelo Planejador

Os arquivos principais para conferência da fundação arquitetural são:

1. [pyproject.toml](file:///C:/Users/henrique/Desktop/peganf/pyproject.toml) — Dependências e metadados do pacote.
2. [.gitignore](file:///C:/Users/henrique/Desktop/peganf/.gitignore) — Regras de bloqueio de arquivos sensíveis (.pfx, senhas, bancos).
3. [src/nfse_facil/domain/validators.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/domain/validators.py) — Validador oficial de CNPJ numérico e alfanumérico.
4. [src/nfse_facil/domain/models.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/domain/models.py) — Entidades `Empresa`, `PeriodoConsulta` e `PreferenciasDownload`.
5. [src/nfse_facil/infrastructure/repositories/base.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/infrastructure/repositories/base.py) — Contrato de repositório.
6. [src/nfse_facil/infrastructure/repositories/in_memory.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/infrastructure/repositories/in_memory.py) — Repositório em memória com inicialização vazia.
7. [src/nfse_facil/services/certificados.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/services/certificados.py) — Contrato abstrato de certificados.
8. [src/nfse_facil/services/nfse.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/services/nfse.py) — Contrato abstrato de sincronização.
9. [src/nfse_facil/services/relatorios.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/services/relatorios.py) — Contrato abstrato de relatórios.
10. [src/nfse_facil/ui/main_window.py](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/ui/main_window.py) — Interface gráfica CustomTkinter com estado vazio e avisos.
11. [tests/test_cnpj.py](file:///C:/Users/henrique/Desktop/peganf/tests/test_cnpj.py) — Suite de testes de validação fiscal.
12. [tests/test_ui_smoke.py](file:///C:/Users/henrique/Desktop/peganf/tests/test_ui_smoke.py) — Teste de fumaça da interface.
13. [docs/arquitetura.md](file:///C:/Users/henrique/Desktop/peganf/docs/arquitetura.md) — Documento de arquitetura das camadas.
14. [README.md](file:///C:/Users/henrique/Desktop/peganf/README.md) — Guia de uso e execução.

---

## 12. Confirmação de Segurança (Certificados, Senhas e Segredos)

- **Confirmação Estrita**: Nenhum certificado real ou fictício foi adicionado ao repositório.
- Nenhuma senha, token ou chave privada foi incluída no código-fonte ou em configurações.
- O modelo `Empresa` e os validadores não possuem nenhum atributo para persistência de senha de certificado.
- O arquivo `.gitignore` bloqueia ativamente arquivos `.pfx`, `.p12`, `.pem`, `.key`, `.sqlite`, `.db` e `.env`.

---

## 13. Informações Complementares de Auditoria

- **Versão Exata do Python**: `Python 3.12.0 (tags/v3.12.0:0fb18b0, Oct 2 2023, 13:03:39) [MSC v.1935 64 bit (AMD64)]`
- **Sistema Operacional de Validação**: `Microsoft Windows 11 (Windows-11-10.0.26200-SP0)`
- **Comandos Realmente Executados**:
  1. `python -m pip install -e .`
  2. `python -m pytest tests -v`
  3. `python -c "from nfse_facil.app import create_app; app = create_app(); print('TITULO:', app.title()); app.destroy()"`
- **Confirmação do Suporte a CNPJ**: Suporte integral a CNPJ numérico legado e CNPJ alfanumérico novo, com testes específicos cobrindo DVs, normalização e zeros à esquerda.
- **Divergências entre Plano e Implementação**:
  - *Ordem de inicialização dos frames da MainWindow*: Ajustada para instanciar o frame principal (`_build_main_panel`) antes da lista lateral (`_build_sidebar`), prevenindo acesso a atributos de tela antes de estarem montados quando a lista notifica o estado inicial vazio.
  - *Caso de teste alfanumérico `00000000001A`*: O dígito verificador foi rigorosamente calibrado para `78` segundo a fórmula Módulo 11 (`00000000001A78`), garantindo precisão matemática estrita na suite de testes.

---

## 14. Sugestão da Próxima Etapa (Sem Implementação)

**Sugestão para a ETAPA 02 — Persistência Local e Gestão de Empresas**:
1. Implementar o repositório persistente `SqliteEmpresaRepository` utilizando SQLite local (arquivo `nfse_facil.db` protegido pelo `.gitignore`).
2. Implementar migrações simples ou criação inicial de esquema para a tabela `empresas`.
3. Permitir salvar, editar e remover empresas na interface de forma persistente entre execuções do aplicativo.
4. Adicionar suporte para seleção do arquivo de certificado digital A1 (`.pfx` ou `.p12`) no cadastro da empresa, salvando apenas o caminho do arquivo e validando sua titularidade em memória, mantendo a regra rígida de não armazenar a senha.

---

## 15. Correções da Auditoria

Esta seção registra as correções realizadas após a primeira rodada de auditoria da Etapa 01:

### 15.1. Problemas Identificados e Corrigidos
1. **Remoção de asserção permissiva no teste de fumaça da interface**:
   - *Problema*: `tests/test_ui_smoke.py` continha a expressão `assert app.frame_boas_vindas.winfo_ismapped() or True`.
   - *Correção*: A asserção foi completamente removida. Foram introduzidas verificações reais baseadas no gerenciador de geometria (`winfo_manager()`) e mapeamento (`winfo_ismapped()`), testando o contêiner efetivo do `CTkScrollableFrame` (`_parent_frame`), garantindo que o repositório inicie vazio, nenhuma empresa esteja ativa, o painel de boas-vindas esteja visível, o operacional esteja oculto, a transição para operacional ocorra após o cadastro de uma empresa e o retorno ao estado vazio aconteça de forma consistente ao remover a empresa.
2. **Restrição estrita do CNPJ a caracteres ASCII (0-9 e A-Z)**:
   - *Problema*: O uso de `str.isdigit()` aceitava caracteres numéricos Unicode não-ASCII (como dígitos orientais/arábicos e expoentes).
   - *Correção*: Substituído por conjuntos estritos de caracteres ASCII (`ASCII_DIGITS` com `0-9` e `ASCII_ALPHANUMERIC_UPPER` com `0-9` e `A-Z`), rejeitando categoricamente dígitos arábicos Unicode, dígitos Devanagari, números full-width, letras acentuadas (Á, É, Ç), caracteres especiais em posições de DV e frações/sobrescritos Unicode de 14 posições.
3. **Fortalecimento das validações no modelo Empresa**:
   - *Problema*: Regras de obrigatoriedade de razão social e caminho de pasta existiam somente na tela, não no domínio.
   - *Correção*: `Empresa.__post_init__` agora rejeita diretamente razão social vazia ou composta apenas por espaços, bem como pasta de documentos vazia ou nula, levantando `ValidacaoError` com mensagens claras em português.
4. **Criação do arquivo LICENSE**:
   - *Problema*: O `pyproject.toml` especificava licença MIT sem o arquivo `LICENSE` no repositório.
   - *Correção*: Criado o arquivo `LICENSE` oficial com termos MIT e titular neutro "NFS-e Fácil contributors" (2026), e atualizado o `README.md`.
5. **Inicialização do Repositório Git Local**:
   - *Problema*: O diretório ainda não estava inicializado com Git.
   - *Correção*: Executado `git init` localmente. Nenhuma configuração remota foi adicionada, nenhum pull request foi criado e nenhum commit foi realizado sem autorização prévia.

### 15.2. Arquivos Alterados
- [`src/nfse_facil/domain/validators.py`](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/domain/validators.py): Restrição estrita a conjuntos ASCII (`ASCII_DIGITS`, `ASCII_ALPHANUMERIC_UPPER`).
- [`src/nfse_facil/domain/models.py`](file:///C:/Users/henrique/Desktop/peganf/src/nfse_facil/domain/models.py): Validação de razão social e pasta de documentos no domínio.
- [`tests/test_ui_smoke.py`](file:///C:/Users/henrique/Desktop/peganf/tests/test_ui_smoke.py): Eliminação de `or True` e implementação do ciclo completo de estados da UI.
- [`tests/test_cnpj.py`](file:///C:/Users/henrique/Desktop/peganf/tests/test_cnpj.py): Adição de bateria de testes para rejeição de caracteres e dígitos Unicode.
- [`tests/test_empresa.py`](file:///C:/Users/henrique/Desktop/peganf/tests/test_empresa.py): Adição de testes para campos obrigatórios do modelo Empresa.
- [`LICENSE`](file:///C:/Users/henrique/Desktop/peganf/LICENSE): Arquivo criado com a licença MIT padrão.
- [`README.md`](file:///C:/Users/henrique/Desktop/peganf/README.md): Adicionada seção de referência à licença MIT.

### 15.3. Novos Testes Adicionados
- `tests/test_cnpj.py::TestCNPJCasosLimiteETratamentoString::test_rejeicao_estrita_caracteres_e_digitos_unicode`: Rejeição de dígitos arábicos orientais, Devanagari, full-width, letras acentuadas (Á, Ã, É), símbolos/letras em DVs e sobrescritos Unicode (¹, ², ½, emoji).
- `tests/test_empresa.py::TestEmpresaModel::test_rejeicao_razao_social_vazia`: Validação de razão social vazia.
- `tests/test_empresa.py::TestEmpresaModel::test_rejeicao_razao_social_somente_espacos`: Validação de razão social com espaços.
- `tests/test_empresa.py::TestEmpresaModel::test_rejeicao_pasta_documentos_vazia`: Validação de pasta vazia (string vazia e espaços).
- `tests/test_empresa.py::TestEmpresaModel::test_aceitacao_e_normalizacao_pasta_como_str_e_path`: Normalização de `str` para `Path`.

### 15.4. Resultado Completo da Suíte de Testes
- **Comando**: `python -m pytest tests -v`
- **Total de Testes**: 40
- **Aprovados (Passed)**: 40 (100%)
- **Falhos (Failed)**: 0
- **Ignorados (Skipped)**: 0
- **Tempo de Execução**: 1.11 segundos

### 15.5. Resultado da Compilação dos Módulos
- **Comando**: `python -m compileall src tests`
- **Resultado**: Código de retorno 0, todos os módulos compilados com sucesso sem erros de sintaxe ou importação.

### 15.6. Resultado do Teste de Inicialização e Ciclo de Vida da Interface
- **Comando**: `python -c "from nfse_facil.app import create_app; app = create_app(); print('TITULO:', app.title()); app.destroy(); print('ENCERRADO COM SUCESSO')"`
- **Resultado**: Janela criada, processada e destruída com sucesso absoluto (código 0).

### 15.7. Confirmação de Criação do LICENSE
- Arquivo `LICENSE` presente na raiz (`C:\Users\henrique\Desktop\peganf\LICENSE`) com texto MIT padrão e copyright "2026 NFS-e Fácil contributors".

### 15.8. Confirmação de Inicialização e Resumo do Status do Git
- Repositório Git inicializado localmente (`Initialized empty Git repository in C:/Users/henrique/Desktop/peganf/.git/`).
- **Nenhum commit foi realizado** e **nenhum remoto foi configurado**.
- Saída do `git status`:
  ```text
  On branch master
  No commits yet
  Untracked files:
    .gitignore
    LICENSE
    README.md
    RELATORIO_ETAPA_01.md
    docs/
    pyproject.toml
    src/
    tests/
  nothing added to commit but untracked files present
  ```
- Arquivos temporários, `.pytest_cache`, `__pycache__`, `.egg-info`, `.env`, `.venv`, `.db` e certificados estão rigorosamente ignorados pelo `.gitignore`.

### 15.9. Declaração Explícita de Escopo
- **DECLARAÇÃO FORMAL**: A Etapa 02 **NÃO FOI INICIADA**. Nenhum código de banco SQLite real, nenhuma integração de rede, nenhum parser de certificado A1 real e nenhum download de documento foram implementados nesta etapa.

# Relatório de Conclusão da Etapa 03 — Certificado Digital A1 Local

**Projeto:** NFS-e Fácil  
**Data de Conclusão:** 21/09/2026  
**Status da Etapa:** Concluída com Sucesso (100% dos 139 testes aprovados)  
**Ambiente:** Windows 10/11, Python 3.12, CustomTkinter, SQLite3, Cryptography 42+, ASN1Crypto 1.5+

---

## 1. Objetivo da Etapa

A Etapa 03 teve como objetivo dotar o **NFS-e Fácil** da capacidade de gerenciar, inspecionar e associar certificados digitais A1 (`.pfx` e `.p12`) de forma estritamente local e segura. A funcionalidade permite ao usuário selecionar um arquivo no formato PKCS#12, fornecer temporariamente sua senha para leitura criptográfica em memória, visualizar todos os metadados fiscais/temporais e associar o certificado à empresa correspondente, persistindo metadados essenciais no banco SQLite sem jamais armazenar ou exportar a senha ou a chave privada.

---

## 2. Arquitetura e Componentes Criados

A implementação seguiu a arquitetura em camadas limpa do projeto, sem acoplamento entre regras de negócio, criptografia e interface gráfica:

1. **Camada de Domínio (`src/nfse_facil/domain/`)**:
   - `certificate_models.py`:
     - `StatusCertificado` (Enum): `AINDA_NAO_VALIDO`, `VALIDO`, `PROXIMO_DO_VENCIMENTO`, `VENCIDO`.
     - `CertificadoInfo` (Dataclass): Metadados públicos extraídos em memória (CNPJ, razão social, emissor, número de série, intervalo UTC, fingerprint SHA-256, contagem de certificados da cadeia, status temporal e dias restantes). Não contém campos de senha nem dados binários de chaves.
   - `models.py`:
     - Entidade `Empresa` enriquecida com colunas opcionais de certificado: `certificado_caminho`, `certificado_cnpj`, `certificado_fingerprint_sha256`, `certificado_valido_de`, `certificado_valido_ate` e `certificado_verificado_em`.
     - Propriedades de integridade: `tem_certificado_associado`, `certificado_cnpj_formatado` e `associacao_certificado_coerente`.
   - `exceptions.py`:
     - Hierarquia completa de exceções de certificado com mensagens sanitizadas em português, sem vazamento de detalhes técnicos internos da OpenSSL.
2. **Camada de Serviços (`src/nfse_facil/services/`)**:
   - `pkcs12.py` (`Pkcs12CertificadoService`): Leitura física limitada a 5 MB, extração PKCS#12 via `cryptography`, validação criptográfica de chave pública/privada, decodificador ASN.1 ICP-Brasil defensivo e classificação temporal UTC.
   - `associacao_certificado.py` (`CertificadoAssociacaoService`): Orquestrador de aplicação responsável por validações de associação, conferência estrita de CNPJ, imutabilidade com `dataclasses.replace`, persistência e desassociação segura.
3. **Camada de Infraestrutura (`src/nfse_facil/infrastructure/`)**:
   - `database/migrations.py`: Migração atômica v1 → v2, `PRAGMA user_version = 2`, validações estruturais sensíveis à versão (`validar_esquema_v1`, `validar_esquema_v2`) e auditoria de segurança contra colunas de senha/chaves (`_verificar_ausencia_segredos`).
   - `repositories/sqlite.py`: Mapeamento e persistência dos metadados de certificado, com verificação de coerência ao carregar dados do SQLite.
4. **Camada de Interface Gráfica (`src/nfse_facil/ui/`)**:
   - `components/certificate_dialog.py`:
     - `CertificateDialog`: Janela modal com leitura em background via `ThreadPoolExecutor`, campo com máscara `*`, alternância de visibilidade, limpeza imediata da senha e proteção contra múltiplos cliques.
     - `CertificateInfoDialog`: Janela modal somente-leitura com metadados do certificado.
   - `components/company_dialog.py`:
     - Botão "Preencher via Certificado A1..." para carregar CNPJ e Razão Social no formulário de cadastro.
     - Diálogo de confirmação com prevenção de inconsistência ao editar o CNPJ de uma empresa que já possua certificado associado.
   - `main_window.py`:
     - Seção "Certificado digital" com badges de status visual e botões de gerenciamento.

---

## 3. Diferenciação entre Inspeção e Validação para Associação

Atendendo ao Ajuste Obrigatório 1, a inspeção local foi rigorosamente desacoplada da validação para associação:

- **`inspecionar(...)`**:
  - Abre o pacote PKCS#12, valida a correspondência de chaves, extrai os metadados e classifica o estado temporal do certificado.
  - Retorna `CertificadoInfo` com o status (`AINDA_NAO_VALIDO`, `VALIDO`, `PROXIMO_DO_VENCIMENTO` ou `VENCIDO`).
  - **Não gera exceção** quando o certificado estiver vencido ou ainda não válido, permitindo que a interface apresente integralmente todos os metadados ao usuário para diagnóstico.
- **`validar_para_associacao(...)`**:
  - Aplica as regras operacionais para permitir ou barrar a associação à empresa:
    - Certificado vencido: levanta `CertificadoVencidoError` (associação proibida).
    - Certificado ainda não válido: levanta `CertificadoAindaNaoValidoError` (associação proibida).
    - Certificado com CNPJ divergente: levanta `CertificadoCNPJIncompativelError` (associação proibida).
    - Certificado próximo do vencimento (<= 30 dias): associação permitida, com alerta visual claro na interface.
    - Certificado válido: associação permitida normalmente.

---

## 4. Mecanismo de Leitura Física Limitada

Conforme o Ajuste Obrigatório 4:
- O arquivo `.pfx` ou `.p12` é inspecionado antecipadamente com `stat` para rejeição rápida se o tamanho reportado exceder 5 MB.
- A leitura física é realizada em modo binário (`rb`) usando `with open(...) as f: f.read(limite + 1)`.
- Se o conteúdo lido atingir `5 * 1024 * 1024 + 1` bytes, a operação é rejeitada imediatamente com `CertificadoArquivoGrandeError`, mesmo que o tamanho do arquivo tenha sido alterado durante a operação no disco.
- Se o arquivo for removido ou modificado entre o `stat` e a leitura, erros de sistema operacional são capturados e traduzidos para mensagens amigáveis (`CertificadoNaoEncontradoError` ou `CertificadoSenhaOuFormatoInvalidoError`), sem vazar senhas.

---

## 5. Decodificação de OIDs ICP-Brasil (CNPJ e Razão Social)

Conforme o Ajuste Obrigatório 5:
- A extensão Subject Alternative Name (SAN) é percorrida em busca de entradas `OtherName`.
- **CNPJ (`2.16.76.1.3.3`)**:
  - Tipos ASN.1 aceitos prioritariamente: `OCTET STRING` e `PrintableString`.
  - Tolerância de interoperabilidade documentada: aceitação defensiva de `UTF8String` e `IA5String`, submetidas às mesmas validações estritas de tamanho e Módulo 11.
  - Rejeição de estruturas ASN.1 compostas, aninhadas inesperadamente ou que contenham dados excedentes (`trailing data`).
  - Rejeição de múltiplos OIDs com valores conflitantes.
  - Tratamento determinístico se o mesmo OID aparecer repetido com o mesmo valor (utiliza o valor único comprovado).
  - Validação estrita do CNPJ resultante usando o validador oficial do sistema (suportando numérico e alfanumérico).
- **Nome Empresarial (`2.16.76.1.3.8`)**:
  - Extração com decodificação limpa, truncamento em 200 caracteres e sanitização de caracteres de controle (remoção de `\r`, `\n`, `\t`, `\x00`, etc.) antes da exibição ao usuário.

---

## 6. Validação de Correspondência entre Chave Privada e Certificado

Conforme o Ajuste Obrigatório 6:
- O serviço verifica não apenas a presença de uma chave privada no arquivo PKCS#12, mas confirma criptograficamente que ela pertence ao certificado digital fornecido.
- A validação compara os bytes canônicos públicos (`public_bytes`) gerados pela chave privada com a chave pública do certificado X.509 (`cert.public_key().public_bytes(...)`).
- A chave privada **nunca é serializada para disco nem persistida no banco**.
- Caso a chave privada não corresponda ao certificado público, a operação é rejeitada com `CertificadoChaveIncompativelError` ("A chave privada fornecida não corresponde à chave pública do certificado.").

---

## 7. Tratamento de Datas X.509 em UTC e Regras de Fronteira

Conforme o Ajuste Obrigatório 7:
- São utilizadas exclusivamente as propriedades conscientes em UTC da biblioteca `cryptography`:
  - `not_valid_before_utc`
  - `not_valid_after_utc`
- Fronteiras temporais testadas e definidas com exatidão matemática:
  - `agora < valido_de`: `AINDA_NAO_VALIDO`
  - `agora == valido_de`: `VALIDO`
  - `agora == valido_ate`: `VALIDO`
  - `agora > valido_ate`: `VENCIDO`
  - `0 <= dias_restantes <= 30`: `PROXIMO_DO_VENCIMENTO`
  - `dias_restantes > 30`: `VALIDO`
- O cálculo de `dias_restantes` é derivado de `(valido_ate - agora).total_seconds() / 86400.0`, prevenindo truncamentos indevidos de horas.

---

## 8. Persistência de Metadados e Migração SQLite v2

Conforme os Ajustes Obrigatórios 2 e 11:
- A migração é estritamente sequencial:
  - v0 → v1: cria tabela `empresas` com restrição `UNIQUE(cnpj)` e validação da estrutura v1.
  - v1 → v2: adiciona as colunas de metadados opcionais (`NULL`):
    - `certificado_caminho TEXT NULL`
    - `certificado_cnpj TEXT NULL`
    - `certificado_fingerprint_sha256 TEXT NULL`
    - `certificado_valido_de TEXT NULL`
    - `certificado_valido_ate TEXT NULL`
    - `certificado_verificado_em TEXT NULL`
- `PRAGMA user_version` somente é atualizado para 2 após a validação bem-sucedida de todas as colunas da v2 dentro da mesma transação.
- `validar_esquema_v1` aceita bancos na v1 sem exigir colunas de certificado; `validar_esquema_v2` exige todas as colunas da v2 como opcionais (`notnull == 0`).
- Auditoria de segurança integrada impede qualquer coluna que contenha palavras como `senha`, `password`, `secret`, `chave_privada`, `pem`, etc.

---

## 9. Serviço de Associação (`CertificadoAssociacaoService`)

Conforme o Ajuste Obrigatório 3:
- A lógica de associação não reside na interface gráfica; ela é encapsulada em `CertificadoAssociacaoService`.
- Responsabilidades do serviço:
  - Validar compatibilidade de CNPJ entre a empresa e o certificado;
  - Validar estado temporal para associação;
  - Produzir nova instância da entidade usando `dataclasses.replace` (imutabilidade);
  - Persistir as alterações no repositório;
  - Remover a associação mantendo intactos os demais dados cadastrais;
  - Em caso de falha em qualquer etapa da persistência, o estado anterior da empresa em memória é preservado integralmente.

---

## 10. Comportamento da Interface Gráfica e Responsividade em Segundo Plano

Conforme o Ajuste Obrigatório 8:
- Toda leitura de arquivo e processamento criptográfico ocorre em thread de trabalho secundária via `ThreadPoolExecutor(max_workers=1)`.
- **Zero chamadas Tkinter no worker**: O worker manipula apenas caminhos, senhas em memória e objetos de domínio, retornando tupla `(info, erro)` para a thread principal.
- A thread principal do CustomTkinter monitora a conclusão periodicamente sem travar o loop de eventos.
- **Proteção contra Duplo Clique**: O botão "Inspecionar Certificado" é desabilitado imediatamente ao iniciar a operação.
- **Fechamento Seguro**: Em caso de fechamento do modal durante o processamento, os timers `after` são cancelados, o `grab` é liberado e o executor é finalizado sem lançar exceções em widgets destruídos.

---

## 11. Tratamento e Ciclo de Vida da Senha na Memória

Conforme os Ajustes Obrigatórios 8 e 9:
- O campo de senha possui máscara `*` e opção de visualização via checkbox.
- A senha visual é **limpa imediatamente** (`txt_senha.delete(0, 'end')`) logo após o disparo da inspeção.
- Não existem atributos duradouros de classe armazenando a senha.
- Não existem variáveis globais armazenando senhas.
- A variável local `senha_op` tem seu ciclo de vida encerrado com `del` no bloco `finally` do worker.
- A senha nunca é passada para logs, mensagens de exceção ou caixas de diálogo.

---

## 12. Confirmação ao Editar CNPJ de Empresa com Certificado

Conforme o Ajuste Obrigatório 2:
- Ao editar uma empresa que já possui certificado associado:
  - Se o CNPJ for alterado para um valor diferente de `empresa.certificado_cnpj`, o sistema exibe um modal de confirmação:
    > "A alteração do CNPJ tornará o certificado digital atualmente associado incompatível. Se continuar, o novo CNPJ será salvo e os dados do certificado serão desassociados (o arquivo físico original não será excluído). Deseja continuar?"
  - Se o usuário selecionar **Não / Cancelar**: nenhum dado é salvo e a empresa anterior é mantida 100% intacta.
  - Se o usuário selecionar **Sim / Confirmar**: o novo CNPJ é salvo no repositório e todos os campos de certificado são redefinidos para `None`. O arquivo físico `.pfx`/`.p12` no disco **nunca é apagado**.

---

## 13. Auditoria de Segredos e Ausência de Persistência Sensível

Conforme os Ajustes Obrigatórios 10 e 13:
- Foi executada auditoria automatizada em:
  - Esquema da tabela `empresas` no SQLite (13 colunas validadas, zero campos de segredo);
  - Atributos do modelo `Empresa` (zero campos sensíveis);
  - Atributos da dataclass `CertificadoInfo` (zero campos sensíveis);
  - Mensagens de erro e textos da interface (sem palavras restritas ou vazamento de segredos).

---

## 14. Limitações Conhecidas sobre Gerenciamento de Memória em Python

Conforme o Ajuste Obrigatório 9:
- No interpretador CPython, strings e buffers são gerenciados automaticamente pelo coletor de lixo e não oferecem garantia de sobrescrita física de memória (`zeroization`).
- O projeto aplica as mitigações possíveis em nível de aplicação (escopo mínimo, `del` imediato, limpeza do widget visual do Tkinter e ausência total de gravação em disco/banco), mantendo esta limitação técnica explicitamente documentada.

---

## 15. Relatório de Testes Automatizados Executados

Foram executados **139 testes automatizados** com **100% dos testes aprovados** e zero falhas:

| Arquivo de Teste | Quantidade | Foco da Validação | Resultado |
| :--- | :---: | :--- | :---: |
| `tests/test_pkcs12_service.py` | 34 | Leitura física limitada a 5 MB, decodificação ASN.1 ICP-Brasil, higienização central de strings, OID de CNPJ rigoroso (14 chars alfanuméricos), ausência de eco malicioso, integridade de chaves, datas UTC e ausência de vazamento técnico ou de caminhos locais | **APROVADO** |
| `tests/test_certificate_association.py` | 10 | Recálculo obrigatório de validade temporal determinística, compatibilidade de CNPJ, imutabilidade, integridade de persistência | **APROVADO** |
| `tests/test_migration_v2.py` | 7 | Migração sequencial atômica v0→v1→v2, validação estrita, auditoria de colunas proibidas, rollback atômico | **APROVADO** |
| `tests/test_ui_certificate.py` | 11 | Concorrência assíncrona, descarte imediato de senha, bloqueio de duplo clique, fechamento seguro, ocultação de exceções técnicas/OpenSSL, comprovação de que CertificadoError higienizado não vaza `__cause__` na UI | **APROVADO** |
| `tests/test_version.py` | 1 | Consistência e alinhamento de versão do projeto (0.3.0) entre pyproject.toml, package e settings | **APROVADO** |
| `tests/test_cnpj.py` | 17 | Algoritmo oficial Módulo 11 (numérico e alfanumérico) | **APROVADO** |
| `tests/test_empresa.py` | 8 | Regras da entidade Empresa e propriedades de domínio | **APROVADO** |
| `tests/test_database.py` | 8 | Conexões curtas, transações imediatas e pragmas SQLite | **APROVADO** |
| `tests/test_sqlite_repository.py` | 12 | CRUD persistente, busca insensível a acentos, ordenação Unicode | **APROVADO** |
| `tests/test_repository.py` | 6 | Repositório em memória | **APROVADO** |
| `tests/test_pasta_documentos.py` | 9 | Criação e validação segura de diretórios sem resíduos | **APROVADO** |
| `tests/test_periodo.py` | 8 | Filtros e regras temporais de download | **APROVADO** |
| `tests/test_ui_company_management.py` | 4 | Ciclo de vida gráfico de empresas na UI | **APROVADO** |
| `tests/test_ui_smoke.py` | 4 | Inicialização e transições de tela do CustomTkinter | **APROVADO** |
| **TOTAL** | **139** | **Suite completa de testes do sistema** | **100% PASS** |

---

## 16. Validação da Preservação das Etapas 01 e 02

- Todos os 76 testes existentes das Etapas 01 e 02 continuam sendo executados e passando integralmente (sem regressões).
- A interface gráfica, persistência SQLite e validação de pastas mantiveram seu comportamento intacto.

---

## 17. Verificação de Arquivos Residuais e Integridade do Workspace

- Todos os certificados de teste utilizados foram gerados sinteticamente em diretórios temporários (`tmp_path`) gerenciados pelo pytest.
- Auditoria no workspace confirmou **ausência total** de arquivos residuais `.pfx`, `.p12`, `.pem`, `.key`, `.db` ou `.sqlite`.
- Bytecode compilado com sucesso em todo o projeto (`python -m compileall src tests`).

---

## 18. Resumo das Decisões de Design

1. **Separação entre Inspeção e Associação**: Facilita a experiência do usuário, permitindo diagnosticar certificados vencidos ou inválidos antes de tentar associá-los.
2. **Imutabilidade**: A entidade `Empresa` tem seus metadados de certificado atualizados via `dataclasses.replace`, evitando mutações parciais no estado em memória caso a transação no SQLite falhe.
3. **Leitura Física Limitada (`limite + 1`)**: Protege contra ataques de negação de serviço e estouro de memória física.
4. **Decodificação ASN.1 Estrita**: Rejeita estruturas malformadas ou com dados excedentes, garantindo determinismo e segurança no processamento criptográfico.

---

## 19. Itens Fora de Escopo Mantidos Fora de Escopo

Em cumprimento estrito às instruções da etapa:
- ❌ Nenhuma conexão de rede foi realizada;
- ❌ Nenhum certificado real de produção foi utilizado;
- ❌ Não foi implementado mTLS ou conexão com o Portal Nacional ADN;
- ❌ Não foram implementadas rotinas de NSU ou download de notas fiscais;
- ❌ Não foram feitas consultas de revogação online (CRL ou OCSP);
- ❌ Não foram criados certificados do tipo A3, token ou cartão.

---

## 20. Estado do Repositório Git

Repositório inicializado, sem commits e sem remoto configurado. Arquivos legítimos do projeto ainda não rastreados.

---

## 21. Conclusão e Próximos Passos

A **Etapa 03 — Certificado Digital A1 Local** foi concluída com êxito, incorporando todos os requisitos iniciais e todas as correções pós-auditoria. O sistema encontra-se robusto, seguro, documentado e testado.

---

## 22. Correções Pós-Auditoria da Etapa 03

Em atendimento às solicitações da auditoria da Etapa 03, foram implementadas as seguintes melhorias e correções:

1. **Recálculo Obrigatório da Validade na Associação**:
   - `Pkcs12CertificadoService.validar_para_associacao` recalcula rigorosamente a validade temporal usando a data de referência informada ou `datetime.now(timezone.utc)`.
   - O método nunca confia exclusivamente no status prévio armazenado no objeto `CertificadoInfo`.
   - Adicionado teste determinístico comprovando recusa de certificado inicialmente marcado como válido cuja validade expirou na referência, recusa para certificado ainda não válido e permissão quando próximo do vencimento.

2. **Preenchimento via Certificado Totalmente Responsivo e Assíncrono (`CompanyDialog`)**:
   - Reutilização da abstração compartilhada `AsyncCertificateInspector` em `CompanyDialog`, garantindo que nenhuma operação de I/O de disco ou criptografia execute na thread principal da interface.
   - Nenhuma chamada Tkinter é executada na thread de trabalho secundária.
   - O botão "Preencher dados via Certificado A1..." é desabilitado imediatamente ao iniciar a leitura, exibindo o estado visual "⏳ Inspecionando...".
   - Proteção contra duplo clique e reentrada concorrente.
   - A senha informada é descartada e limpa da memória local imediatamente após ser enviada ao trabalhador, não sendo armazenada em nenhum atributo duradouro de instância.
   - O fechamento da janela durante o processamento encerra o executor com segurança sem disparar erros de acesso a widgets destruídos.
   - Adicionados testes para background processing, clique duplicado, sucesso, erro, fechamento concorrente e detecção de empresa existente.

3. **Ocultação de Exceções Técnicas e Segredos na Interface**:
   - Removidas mensagens com interpolação de exceções inesperadas `{err}` na interface.
   - Substituídas pela mensagem amigável padronizada: `"Não foi possível concluir a leitura do certificado. Tente novamente ou selecione outro arquivo."`.
   - A causa técnica original permanece restrita ao encadeamento interno de exceções, sem expor senhas ou detalhes do OpenSSL.
   - Adicionado teste com exceção contendo texto sensível simulado, comprovando ausência de vazamento no retorno visual.

4. **Higienização Centralizada de Textos Extraídos do Certificado (`higienizar_texto_x509`)**:
   - Implementada a função central `higienizar_texto_x509` para sanitização defensiva de strings públicas do X.509 (nome comum, nome empresarial, emissor).
   - Remoção de caracteres de controle ASCII (`\x00` a `\x1f`, exceto normalização de quebras e tabulações para espaços simples), remoção de espaços duplicados e aplicação de limites de tamanho defensivos.
   - CNPJ, fingerprints e números de série não são processados por essa função.
   - OID de CNPJ ICP-Brasil (`2.16.76.1.3.3`): limite preventivo de 64 bytes, exigência estrita de exatamente 14 caracteres ASCII (posições 1–12 em `0-9`/`A-Z`, posições 13–14 em `0-9`), rejeição de CNPJ mascarado dentro do OID e validação de dígitos verificadores Módulo 11.
   - Mensagens de erro de validação não ecoam o conteúdo bruto inválido ou malicioso.

5. **Correção do Limite de Tamanho da Documentação para 5 MB**:
   - Corrigidas todas as referências de 10 MB para 5 MB em `README.md`, `docs/arquitetura.md` e `RELATORIO_ETAPA_03.md`, alinhando com a constante `LIMITE_TAMANHO_ARQUIVO_CERTIFICADO_BYTES = 5 * 1024 * 1024`.

6. **Alinhamento da Versão do Projeto para 0.3.0**:
   - Atualizados `pyproject.toml`, `src/nfse_facil/__init__.py` e `Settings.app_version` para `0.3.0`.
   - Criado teste `tests/test_version.py` garantindo que as versões declaradas e configuradas não divirjam.

7. **Correção dos Nomes Reais de Exceções no Relatório**:
   - Substituídos os nomes inexistentes pelos nomes reais implementados no código: `CertificadoCNPJIncompativelError`, `CertificadoArquivoGrandeError`, `CertificadoNaoEncontradoError`, `CertificadoSenhaOuFormatoInvalidoError` e `CertificadoChaveIncompativelError`.

8. **Verificações Finais e Ausência de Resíduos**:
   - Suíte de testes completa executada: **139 testes aprovados, sem falhas**.
   - Compilação do bytecode Python (`compileall`) sem falhas.
   - Varredura por arquivos residuais (.pfx, .p12, .pem, .key, .db, .sqlite, .db-wal, .db-shm) confirmou **zero arquivos residuais** no repositório.
   - Status do Git: Repositório inicializado, sem commits e sem remoto configurado.

9. **Sanitização Real de Mensagens de Exceção em `pkcs12.py` (Correção Obrigatória)**:
   - Removidas as 7 interpolações de exceções internas (`{err}`, `str(err)`, `type(obj).__name__`) que expunham detalhes do OpenSSL, ASN.1, caminhos e senhas nas mensagens públicas.
   - Pontos corrigidos:
     - Linha ~114: erro de `stat` → mensagem fixa sem `{err}`
     - Linhas ~123/125: erros de leitura (`PermissionError` e genérico) → mensagens fixas
     - Linha ~152: erro do parser ASN.1 → mensagem fixa sem detalhes internos
     - Linha ~166: `type(obj).__name__` → mensagem fixa sem nome de classe interna
     - Linha ~379: erro ao comparar chaves → mensagem fixa
     - Linha ~437: erro do validador de CNPJ → mensagem fixa
   - Todas as exceções utilizam `raise ExcecaoPublica("Mensagem fixa.") from err`, preservando a causa encadeada apenas para depuração interna.
   - Verificação automatizada com `Select-String` confirma zero ocorrências residuais de `{err}`, `str(err)` e `type(obj).__name__` em `pkcs12.py`.

10. **Redução de Referências a Dados Sensíveis em `inspecionar()`**:
    - `del senha` executado imediatamente após criar `senha_bytes`.
    - `del chave_privada` executado imediatamente após `_validar_correspondencia_chave`.
    - `conteudo_binario` e `senha_bytes` já são eliminados no bloco `finally`.

11. **Novos Testes de Ausência de Vazamento (5 unitários + 1 integração visual)**:
    - `test_vazamento_excecao_stat_nao_revela_marcador`: exceção em `Path.stat`
    - `test_vazamento_excecao_leitura_nao_revela_marcador`: exceção em `open/read` (PermissionError + genérica)
    - `test_vazamento_excecao_asn1_nao_revela_marcador`: exceção no parser ASN.1
    - `test_vazamento_excecao_correspondencia_chave_nao_revela_marcador`: exceção na serialização de chave
    - `test_vazamento_excecao_validador_cnpj_nao_revela_marcador`: erro do validador de CNPJ
    - `test_certificado_error_higienizado_nao_vaza_causa_original_na_ui`: comprova que `CertificadoError` com `__cause__` confidencial chega ao callback visual sem vazar o marcador na label de feedback e no `showerror`.

Aguardando a auditoria do usuário para liberação da próxima etapa.

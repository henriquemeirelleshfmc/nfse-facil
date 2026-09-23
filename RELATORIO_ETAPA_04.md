# Relatório da Etapa 04 — Comunicação mTLS com o ADN

**Projeto:** NFS-e Fácil  
**Versão:** 0.4.0  
**Data:** 21/09/2026  

## Escopo entregue

- Cliente desacoplado para a API ADN de contribuintes.
- Ambientes oficiais de produção restrita e produção.
- Consulta de DF-e por NSU com `lote` e `cnpjConsulta` opcionais.
- Consulta de eventos de NFS-e por chave de acesso.
- Autenticação mTLS com PKCS#12 por `requests-pkcs12`.
- TLS obrigatório, redirecionamentos desativados, timeouts e limite de 50 MB.
- Respostas JSON estruturadas sem persistência ou descompactação de documentos.
- Tratamento sanitizado de autenticação, timeout, conexão, HTTP 429 e indisponibilidade.

## Decisão sobre PEM temporário

O proprietário do projeto autorizou o uso documentado de PEM temporário. A biblioteca `requests-pkcs12` cria internamente um PEM criptografado com senha aleatória, utiliza-o para carregar o contexto TLS e o remove em bloco de limpeza. A aplicação não recebe o caminho temporário e não persiste senha, PKCS#12, PEM ou chave privada.

## Limites da etapa

- Nenhuma chamada real é feita automaticamente.
- Nenhum XML, PDF ou conteúdo fiscal é salvo em disco.
- Nenhuma resposta é descompactada ou organizada.
- A interface de download continua reservada à Etapa 05.
- A validação automatizada utiliza transporte simulado e não depende da disponibilidade do governo.

## Referências oficiais consultadas

- Documentação atual do Sistema Nacional NFS-e: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual
- Endereços oficiais das APIs: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
- Manual dos Contribuintes — APIs do ADN, versão 1.0 de 12/02/2026.

## Ajuste de compatibilidade da consulta oficial

- Quando o CNPJ da empresa é o mesmo do certificado, a identificação é feita diretamente pelo certificado mTLS e o parâmetro opcional `cnpjConsulta` não é enviado.
- O parâmetro `cnpjConsulta` fica reservado para a consulta de outro estabelecimento, conforme a finalidade descrita no manual oficial do ADN.
- Respostas HTTP 400, 404, 401/403, 429 e 5xx apresentam orientações diferentes, evitando classificar todas como uma rejeição genérica.
- Na rota de distribuição `/DFe/{NSU}`, uma resposta 404 após o último NSU salvo é tratada como fim momentâneo da distribuição: a consulta termina normalmente com a indicação de que não há novas notas.

## Validação

- `python -m compileall -q src tests`: concluído sem erros.
- `python -m pytest tests -q`: **170 testes aprovados**, zero falhas, em 8,96 segundos.
- Varredura de resíduos: nenhum `.pfx`, `.p12`, `.pem`, `.key`, `.db`, `.sqlite`, `.db-wal` ou `.db-shm` encontrado no projeto.
- Nenhuma configuração `verify=False` ou `allow_redirects=True` encontrada.
- Repositório Git inicializado, ainda sem commits e sem remoto; arquivos legítimos permanecem não rastreados.

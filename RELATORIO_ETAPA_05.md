# Relatório da Etapa 05 — Download e Organização de XMLs

**Versão:** 0.5.0  
**Data:** 21/09/2026  

## Entregas

- Decodificação de `ArquivoXml` como XML direto, Base64 ou Base64+GZip.
- Limite de 15 MB para o campo codificado e 10 MB para cada XML expandido.
- Leitura limitada do GZip para impedir expansão descontrolada.
- Rejeição de DTD, entidades externas, XML malformado e datas inválidas.
- Identificadores higienizados e confinamento dos arquivos dentro da pasta da empresa.
- Organização isolada por empresa em `Nome da empresa - CNPJ/AAAA/MM/Emitidas`, `Recebidas` e `Outros`.
- Busca automática de lotes consecutivos com senha digitada uma única vez e identificação explícita do término da importação.
- Relatórios fiscais completos na pasta `Relatórios`: resumo por direção, bases, ISS, retenções, IBS/CBS, valores líquidos e 44 campos de detalhamento por NFS-e.
- PDF dividido em seções independentes: resumo e detalhamento de notas emitidas, seguidos do resumo e detalhamento de notas recebidas, sem misturar categorias na mesma listagem.
- Excel organizado em quatro abas quando há movimentação nos dois sentidos: `Resumo emitidas`, `Notas emitidas`, `Resumo recebidas` e `Notas recebidas`.
- Escrita atômica com arquivo temporário no mesmo volume, `fsync` e `os.replace`.
- Idempotência por conteúdo e recusa de sobrescrita quando houver colisão divergente.
- Migração SQLite v3 com `ultimo_nsu_adn INTEGER NOT NULL DEFAULT 0`.
- Serviço de sincronização que avança o NSU somente depois da gravação integral do lote.
- Filtros de período e direção não eliminam o arquivo fiscal: documentos fora do filtro ficam no diretório interno oculto `.nfse-facil-arquivo-adn`, enquanto somente os selecionados são materializados nas pastas visíveis.
- XMLs visíveis apagados são restaurados automaticamente a partir do arquivo interno, respeitando o período e as direções selecionadas.
- Se a pasta da empresa e o arquivo interno também tiverem sido apagados, a interface oferece `Baixar histórico novamente`, reinicia somente o cursor daquela empresa e reconstrói o histórico pelo ADN.
- Diálogo assíncrono ligado ao botão principal, com senha limpa imediatamente da tela, ambiente de produção identificado e resumo do lote.
- Compatibilidade com datas de NFS-e, DPS e eventos (`dhEmi`, `dCompet`, `dhEvento`, campos de registro/processamento e `DataHoraGeracao` do envelope ADN).

## PDF/DANFSe

A API DANFSe versão 1.0 foi desativada no ambiente nacional em 03/08/2026. Por isso, esta etapa não chama endpoint obsoleto nem apresenta PDF inexistente como concluído. Uma representação PDF local poderá ser estudada junto da geração de relatórios, usando o XML oficialmente recebido como fonte.

## Limites atuais

- A camada de domínio, infraestrutura e interface está concluída e testada sem rede real.
- Uma única busca processa automaticamente os lotes consecutivos disponíveis no ADN.
- Nenhum certificado ou documento fiscal real foi usado nos testes.

## Validação

- `python -m compileall -q src tests`: concluído sem erros.
- `python -m pytest tests -q`: **211 testes aprovados**, zero falhas, incluindo recuperação de arquivos e relatórios Excel e PDF válidos.
- Nenhuma chamada aos ambientes oficiais foi realizada pela suíte.
- Nenhum `.pfx`, `.p12`, `.pem`, `.key`, `.db`, `.sqlite` ou `.tmp` residual foi encontrado no projeto.

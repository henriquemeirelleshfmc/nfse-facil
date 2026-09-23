# ETAPA 06 — Renovação visual da interface

## Objetivo

Modernizar a experiência do NFS-e Fácil sem alterar as regras fiscais, a persistência ou a segurança do certificado digital.

## Alterações realizadas

- Identidade visual profissional em azul profundo, com suporte aos modos claro e escuro.
- Barra lateral mais compacta, pesquisa destacada e cartões de empresa com seleção clara.
- Cabeçalho contextual que informa qual empresa está em uso.
- Cartões principais com maior espaçamento, bordas suaves e hierarquia tipográfica consistente.
- Indicadores rápidos do estado da sincronização e do certificado digital.
- Ação principal renomeada para `Buscar e organizar notas`, descrevendo o resultado real da operação.
- Ampliação da janela padrão e manutenção de dimensões mínimas compatíveis com telas menores.
- Janela de busca redesenhada com identificação clara da empresa e do período, campo de senha com opção de visualização, indicador de processamento e estados visuais distintos para sucesso, pausa e erro.
- Informação explícita de que todos os lotes disponíveis são consultados automaticamente e de que a senha não permanece salva.
- Cadastro e edição de empresa reorganizados em seções de dados e arquivos, com campos maiores, ajuda contextual para o CNPJ e importação por certificado destacada.
- Rodapé do cadastro transformado em uma barra fixa de ações, mantendo `Cancelar` e `Salvar empresa` sempre acessíveis mesmo em janelas menores.
- Associação do certificado A1 redesenhada com cabeçalho contextual, aviso de segurança destacado, campos maiores, resultado da inspeção em cartão próprio e rodapé fixo para cancelar ou confirmar.
- Tela de informações do certificado padronizada com a identidade visual, conteúdo rolável e tratamento adequado para caminhos e metadados longos.
- Cartão de contato e suporte adicionado à barra lateral, direcionando para o Instagram `@henrique.meirelles_`.
- Contato incluído nos rodapés clicáveis do PDF e nas planilhas Excel.
- Diagnóstico sanitizado com código de suporte, cópia pela interface e registro local sem mensagens internas, senhas, certificados, CNPJ ou conteúdo fiscal.
- Versão do produto atualizada para `0.6.0` após a conclusão da etapa.

## Princípios preservados

- Linguagem simples e sem termos técnicos desnecessários.
- Nenhuma senha armazenada.
- Nenhuma alteração na comunicação oficial com o ADN.
- Todos os componentes críticos mantêm navegação e estados testáveis.

## Validação

- Compilação integral de `src` e `tests`.
- Testes específicos de interface, cadastro, certificado e download.
- Suíte automatizada completa.
- 213 testes aprovados, incluindo os fluxos de conclusão, erro e diagnóstico seguro da nova janela de busca.

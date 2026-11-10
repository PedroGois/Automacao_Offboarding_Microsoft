# Guia Operacional — Offboarding M365

Este guia explica como operar o painel com segurança. Ele descreve o comportamento atual do sistema; não substitui a política de desligamento aprovada pela empresa.

## 1. Finalidade

O painel identifica colaboradores inativos no SIGO, procura a conta correspondente no Microsoft Entra ID e prepara uma lista para o processo de offboarding. As ações administrativas só acontecem após revisão e confirmação manual no painel.

## 2. Antes de começar

Confirme os seguintes itens antes de cada execução:

- O arquivo `.env` está configurado e não foi compartilhado nem enviado ao repositório.
- O aplicativo no Entra ID tem autorização para consultar usuários e licenças, bloquear contas, revogar sessões e remover licenças.
- Para converter caixas, o certificado do aplicativo está instalado neste computador, com a chave privada acessível ao usuário que executará o painel.
- O módulo PowerShell `ExchangeOnlineManagement` está instalado.
- Há uma pessoa responsável para validar casos ambíguos e autorizar as ações.

## 3. Execução normal

1. Abra um PowerShell na pasta do projeto.
2. Inicie o painel com `python -m streamlit run app.py`.
3. No painel, selecione **Buscar e Cruzar Dados**.
4. Confira as duas listas geradas:
   - **Prontos para Bloqueio:** contas encontradas com uma correspondência única e que estão habilitadas ou ainda têm licença.
   - **Para Verificação Manual:** casos sem conta correspondente, com correspondência ambígua ou sem UPN/e-mail adequado para ação.
5. Resolva os casos manuais fora do painel. Use **Ignorar nas próximas** somente quando a chapa realmente não deve voltar a ser analisada; essa escolha fica gravada em `data/chapas_ignoradas.json`.
6. Revise a lista aprovada, principalmente nome, chapa e UPN.
7. Se a regra interna determinar a preservação do e-mail, execute **Converter para Caixa Compartilhada** e confirme os resultados mostrados pelo painel.
8. Somente após essa confirmação, execute **Revogar, Bloquear e Remover Licenças**.
9. Guarde o registro da execução e trate individualmente qualquer falha indicada no resultado.

## 4. O que cada ação faz

| Ação | Efeito | Confirmação esperada |
|---|---|---|
| Buscar e Cruzar Dados | Consulta SIGO e Entra ID; atualiza os CSVs de trabalho. | Quantidades de registros consultados, aprovados e manuais. |
| Converter para Caixa Compartilhada | Executa a conversão no Exchange Online. | Cada caixa deve retornar como `SharedMailbox`. |
| Revogar, Bloquear e Remover Licenças | Desabilita o login, revoga sessões ativas e remove as licenças atribuídas. | Resultado de sucesso por usuário e quantidade de licenças processadas. |

## 5. Como o sistema decide os casos

Somente colaboradores inativos no SIGO entram na análise. A tentativa de encontrar a conta no Entra ID segue esta ordem:

1. Chapa (`employeeId`);
2. E-mail, UPN, aliases ou endereços proxy;
3. Nome normalizado.

Quando houver mais de uma possibilidade, a conta não é processada automaticamente. Ela vai para a lista de verificação manual. Contas já bloqueadas e sem licenças são descartadas da lista de trabalho.

## 6. Registros e evidências

| Arquivo | Uso |
|---|---|
| `data/desligados_para_powershell.csv` | Lista aprovada que alimenta as ações administrativas. |
| `data/para_verificar_manual.csv` | Casos que precisam de decisão humana. |
| `data/chapas_ignoradas.json` | Exceções persistentes criadas no painel. |
| `logs/pipeline_offboarding.log` | Histórico técnico da busca, cruzamento e chamadas das ações. |

Os CSVs são arquivos de trabalho, não um histórico imutável. Caso seja necessária evidência para auditoria, salve uma cópia datada da lista aprovada e do log antes de uma nova execução.

## 7. Tratamento de falhas

- **Falha de autenticação:** verifique a validade das credenciais no `.env`, o certificado e as autorizações do aplicativo.
- **Falha em uma caixa:** não execute novamente a lista inteira sem revisar o resultado; confirme se a caixa já foi convertida antes de repetir a operação.
- **Falha no bloqueio ou licenças:** consulte a mensagem por usuário, confirme se o UPN ainda existe e valide as permissões do aplicativo.
- **Caso ambíguo:** não altere a conta por suposição. Confirme a identidade com RH, gestor ou a fonte oficial de cadastro.

## 8. Decisões que precisam ser formalizadas

O sistema atual não remove grupos, listas de distribuição ou equipes do Teams. Também não agenda execuções nem exclui/arquiva caixas após um período. Essas etapas devem continuar manuais até serem aprovadas e implementadas.

### Retenção planejada: 90 dias

A caixa compartilhada deverá permanecer disponível por até 90 dias após o desligamento. A automação para controlar esse prazo e executar o arquivamento ou a exclusão ao final ainda **não está implementada**. Até a implementação, a equipe responsável deve controlar o prazo manualmente e confirmar as exigências de backup, retenção e LGPD antes de qualquer exclusão.

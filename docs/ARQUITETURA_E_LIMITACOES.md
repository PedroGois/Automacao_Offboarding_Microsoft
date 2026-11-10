# Arquitetura e Limitações Atuais

## Visão geral

O projeto é um painel Streamlit que orquestra uma consulta ao SIGO, uma consulta ao Microsoft Graph e dois comandos administrativos em PowerShell.

```text
SIGO ──> coleta Python ─┐
                        ├──> cruzamento ──> CSVs de trabalho ──> painel Streamlit
Entra ID / Graph ──────┘                              │
                                                       ├──> Exchange Online: converter caixa
                                                       └──> Microsoft Graph: bloquear, revogar, remover licenças
```

## Componentes

| Componente | Responsabilidade |
|---|---|
| `app.py` | Interface do painel, revisão das listas e disparo das ações. |
| `scripts/python/collect_data.py` | Autenticação, coleta, cruzamento, geração de CSV e registro em log. |
| `scripts/powershell/offboarding.ps1` | Conversão da caixa pelo Exchange Online e ações de conta/licença pelo Graph. |
| `.env` | Credenciais do SIGO, aplicativo Entra ID e configuração do certificado do Exchange. |
| `data/` | Dados de trabalho e lista persistente de exceções. |
| `logs/` | Registro técnico do pipeline. |

## Limitações conhecidas

- Não há agendamento: o painel precisa ser iniciado e operado manualmente.
- Não há etapa implementada para remover grupos de segurança, distribuição ou Teams.
- Não existe retenção, arquivamento ou exclusão automatizada de caixas compartilhadas. A retenção de 90 dias está planejada, mas ainda precisa ser implementada.
- A lista de exceções é persistente e não há tela para revisá-la ou removê-la; qualquer revisão hoje é feita diretamente no JSON.
- O processo não possui modo de simulação nem aprovação em duas etapas.
- O log é técnico e não substitui uma evidência formal de auditoria por colaborador.

## Cuidados de manutenção

- Não registre senhas, segredos, tokens, certificados ou conteúdo do `.env` em tickets, logs ou commits.
- Antes de alterar a regra de cruzamento, valide com uma amostra de dados reais e casos de homônimos.
- Mudanças no CSV devem preservar o separador `;`, pois ele é consumido pelo PowerShell.
- Qualquer automação de exclusão deve passar por validação de segurança, LGPD, retenção e backup antes de ser adicionada ao projeto.

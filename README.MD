# M365 Offboarding

Painel interno para apoiar o desligamento de colaboradores no Microsoft 365. O sistema consulta o SIGO e o Microsoft Entra ID, cruza os registros e apresenta listas para revisão antes de executar ações no Exchange Online e no Microsoft Graph.

> **Uso interno e administrativo:** este projeto altera contas, sessões, licenças e caixas de correio no tenant. Toda execução deve ser revisada e autorizada pela equipe responsável.

## Documentação

| Documento | Finalidade | Caminho |
|---|---|---|
| Guia operacional | Passo a passo de execução, revisão e tratamento de falhas. | [docs/GUIA_OPERACIONAL.md](docs/GUIA_OPERACIONAL.md) |
| Arquitetura e limitações | Componentes, integrações e limites atuais da solução. | [docs/ARQUITETURA_E_LIMITACOES.md](docs/ARQUITETURA_E_LIMITACOES.md) |
| Política de desligamento | Diretrizes organizacionais para o ciclo de offboarding. | [docs/POLITICA_OFFBOARDING.MD](docs/POLITICA_OFFBOARDING.MD) |

## Funcionalidades

- Consulta de colaboradores e situação de atividade no SIGO.
- Consulta paginada de usuários, licenças atribuídas e estado da conta no Microsoft Graph.
- Cruzamento por matrícula, e-mail/UPN/aliases e, quando a correspondência é única, nome normalizado.
- Geração de uma lista de processamento e outra de verificação manual.
- Conversão de caixas postais em caixas compartilhadas por meio do Exchange Online PowerShell.
- Bloqueio de login, revogação de sessões e remoção das licenças atribuídas pelo Microsoft Graph.
- Registro de chapas ignoradas em JSON e histórico do pipeline.

## Requisitos

- Windows com Python e PowerShell disponíveis.
- Acesso à API do SIGO e credenciais válidas.
- Aplicativo do Microsoft Entra ID com autenticação de aplicativo, segredo válido e permissões administrativas para as operações realizadas pelo Graph.
- Para conversão de caixas: módulo `ExchangeOnlineManagement`, certificado instalado com chave privada acessível ao usuário do painel e associado ao aplicativo do Entra ID.
- Acesso ao Exchange Online com autorização para conexão app-only e gerenciamento das caixas postais.

## Instalação e configuração

1. Abra um terminal na pasta raiz do projeto e instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Crie `.env` na raiz do projeto, usando `.env-example` como referência:

   ```dotenv
   SIGO_DOCUMENT=seu-documento
   SIGO_PASSWORD=sua-senha

   AZURE_TENANT_ID=id-do-tenant
   AZURE_CLIENT_ID=id-do-aplicativo
   AZURE_CLIENT_SECRET=segredo-do-aplicativo

   EXCHANGE_ORGANIZATION=seu-tenant.onmicrosoft.com
   AZURE_CERTIFICATE_THUMBPRINT=impressao-digital-do-certificado
   ```

   **Variáveis necessárias por operação:**

   | Variáveis | Uso |
   |---|---|
   | `SIGO_DOCUMENT`, `SIGO_PASSWORD` | Autenticação e consulta ao SIGO |
   | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Consulta e ações no Microsoft Graph |
   | `AZURE_CLIENT_ID`, `EXCHANGE_ORGANIZATION`, `AZURE_CERTIFICATE_THUMBPRINT` | Conexão app-only ao Exchange Online para conversão |

3. Configure o aplicativo no Entra ID com as permissões de aplicativo exigidas pelas operações de leitura de usuários/licenças, atualização de contas, revogação de sessões e atribuição de licenças. Conceda consentimento administrativo conforme as políticas da organização.

4. Para a conversão de caixas, instale o certificado no repositório do Windows acessível à identidade que executa o Streamlit, confirme que a chave privada está disponível e autorize o aplicativo no Exchange Online. O segredo do Graph não substitui o certificado do Exchange.

Não compartilhe nem versione `.env`, segredos ou chaves privadas. Valide as permissões e credenciais com o administrador responsável pelo tenant.

## Execução

Na raiz do repositório, inicie o painel:

```powershell
python -m streamlit run app.py
```

O endereço local do painel será exibido no terminal.

## Fluxo operacional

1. **Buscar e Cruzar Dados** — consulta o SIGO e o Entra ID, faz o cruzamento e grava os CSVs de resultado.
2. **Inspecionar os resultados** — revise a lista de usuários prontos para offboarding e os casos que exigem verificação manual.
3. **Converter para Caixa Compartilhada** — executa `Set-Mailbox -Type Shared` nas contas da lista de processamento. A conversão altera o tipo da caixa; não é uma ação de exclusão de e-mails.
4. **Revogar, Bloquear e Remover Licenças** — bloqueia o login, revoga sessões e remove as licenças atribuídas retornadas pelo Graph.

As duas ações do Passo 3 são independentes e não são encadeadas automaticamente. Execute a conversão primeiro e confirme seu resultado antes de iniciar a revogação. A lista enviada às ações vem de `data/desligados_para_powershell.csv`.

Na tabela **Para Verificação Manual**, **Ignorar nas próximas** grava a chapa em `data/chapas_ignoradas.json` e a remove da tabela e do CSV de verificação da sessão atual. Nas próximas buscas e cruzamentos, essa chapa será excluída dos resultados.

## Regras do cruzamento

- Somente registros inativos no SIGO são avaliados.
- A correspondência tenta matrícula (`employeeId`), e-mail/UPN/aliases e nome normalizado. Correspondências ambíguas ou sem conta correspondente vão para verificação manual.
- Uma conta correspondente entra na lista de processamento se estiver habilitada **ou** tiver uma ou mais licenças atribuídas; contas bloqueadas sem licenças não entram nas listas.
- Registros sem uma conta identificável ou sem UPN/e-mail utilizável para a ação são encaminhados para verificação manual.
- Chapas no JSON de exceções e os nomes/e-mails configurados como exceções no código são omitidos dos resultados.

## Arquivos gerados e logs

| Caminho | Conteúdo |
|---|---|
| `data/desligados_para_powershell.csv` | Contas aprovadas pelo cruzamento para as ações do PowerShell |
| `data/para_verificar_manual.csv` | Registros que precisam de revisão |
| `data/chapas_ignoradas.json` | Chapas ignoradas nas próximas buscas |
| `logs/pipeline_offboarding.log` | Eventos e resultados do pipeline Python |

Os CSVs são separados por ponto e vírgula e consumidos pelo script PowerShell. A seção **Histórico de execução** do painel mostra as últimas 200 linhas do log Python e oferece o download do arquivo completo. A saída das ações PowerShell e os resultados por usuário são apresentados no painel.

## Segurança e limitações operacionais

- As ações de bloqueio e licença são administrativas e podem afetar o acesso do colaborador. Confira os registros antes de executá-las.
- A aplicação não converte automaticamente a caixa depois da busca nem remove licenças depois da conversão; cada ação requer um clique separado.
- A remoção de licenças atua sobre as licenças atribuídas retornadas pelo Graph; não há distinção configurada entre planos pagos e não pagos.
- A retenção de caixas compartilhadas por 90 dias e a respectiva etapa de arquivamento ou exclusão ao fim desse prazo ainda serão implementadas. Até lá, esse acompanhamento é manual.

## Melhorias planejadas

Estas melhorias ainda não fazem parte da automação atual:

- [ ] Implementar o controle de retenção de 90 dias para caixas compartilhadas, incluindo a decisão aprovada de arquivamento, backup ou exclusão ao fim do prazo.
- [ ] Alinhar a ordem do processo entre a política e o sistema: atualmente o painel orienta converter a caixa antes de bloquear a conta; a política descreve o bloqueio como primeira etapa.
- [ ] Remover grupos de segurança, listas de distribuição e associações ao Teams, caso essa regra seja mantida pela organização.
- [ ] Criar agendamento semanal para reduzir a dependência da execução manual.
- [ ] Criar uma interface para consultar e remover exceções registradas em `data/chapas_ignoradas.json`.
- [ ] Produzir um histórico de auditoria por colaborador, com data, responsável, ações executadas e resultado.
- [ ] Remover via gitignore os logs de produção.

## Publicação no GitHub

Antes de publicar, confirme que o repositório não contém dados pessoais ou informações sensíveis. Não envie `.env`, segredos, certificados, tokens, planilhas de colaboradores nem logs de produção. 

## Estrutura do projeto

```text
├── app.py
├── scripts/
│   ├── python/
│   │   └── collect_data.py
│   └── powershell/
│       └── offboarding.ps1
├── data/
│   ├── chapas_ignoradas.json
│   ├── desligados_para_powershell.csv
│   ├── fluxo.drawio
│   └── para_verificar_manual.csv
├── docs/
├── logs/
│   ├── data_sigo.log
│   └── pipeline_offboarding.log
├── .env-example
├── requirements.txt
└── README.MD
```

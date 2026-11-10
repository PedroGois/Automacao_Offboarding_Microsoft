# M365 Offboarding

Aplicação de apoio ao offboarding de colaboradores. Consulta o SIGO e o Microsoft Entra ID, cruza os registros e permite executar separadamente a conversão de caixas postais e as ações de bloqueio e remoção de licenças.

> **Atenção:** as ações do Passo 3 alteram contas e caixas postais no tenant. Revise a lista de usuários antes de executá-las. Converta as caixas compartilhadas antes de remover as licenças.

## Requisitos

- Windows com PowerShell e Python instalados.
- Acesso à API do SIGO.
- Um aplicativo no Microsoft Entra ID configurado para autenticação de aplicativo.
- ExchangeOnlineManagement disponível para o usuário que executa o painel (necessário para conversão das caixas).
- Certificado instalado no Windows e cadastrado no mesmo aplicativo do Entra ID (necessário para conexão ao Exchange Online).

## Configuração

1. Instale as dependências Python:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Crie o arquivo `.env` na raiz do projeto, usando `.env-example` como referência:

   ```dotenv
   SIGO_DOCUMENT=seu-documento
   SIGO_PASSWORD=sua-senha

   AZURE_TENANT_ID=id-do-tenant
   AZURE_CLIENT_ID=id-do-aplicativo
   AZURE_CLIENT_SECRET=segredo-do-aplicativo

   EXCHANGE_ORGANIZATION=seu-tenant.onmicrosoft.com
   AZURE_CERTIFICATE_THUMBPRINT=impressao-digital-do-certificado
   ```

   `SIGO_DOCUMENT`, `SIGO_PASSWORD` e as três variáveis `AZURE_*` são necessárias para buscar os dados e executar as ações do Graph. `EXCHANGE_ORGANIZATION` e `AZURE_CERTIFICATE_THUMBPRINT` são necessárias para converter caixas compartilhadas.

   O certificado deve estar instalado no repositório de certificados do Windows acessível ao usuário que inicia o Streamlit, com chave privada disponível, e cadastrado no aplicativo do Entra ID. O aplicativo também precisa estar autorizado a conectar ao Exchange Online e ter as permissões administrativas necessárias. Não compartilhe nem versione o `.env`, o segredo ou a chave privada do certificado.

3. Configure no aplicativo do Entra ID as permissões de aplicativo necessárias às operações usadas no Graph: leitura de usuários, atualização de usuários, revogação de sessões e atribuição de licenças. Conceda o consentimento administrativo e valide a configuração com o administrador do tenant.

## Executar o painel

Na raiz do repositório:

```powershell
streamlit run app.py
```

No painel:

1. **Buscar e Cruzar Dados:** consulta SIGO e Entra ID, cruza os usuários e gera as listas para processamento e auditoria.
2. **Inspecionar visualmente:** revise a tabela de usuários prontos para offboarding e a tabela de casos para verificação manual.
3. **Executar ações separadamente, nesta ordem:**
   - **Converter para Caixa Compartilhada:** conecta ao Exchange Online e executa `Set-Mailbox -Type Shared`, preservando a caixa e seu histórico.
   - **Revogar, Bloquear e Remover Licenças:** usa o Microsoft Graph para bloquear o login, revogar sessões e remover as licenças atribuídas.

As ações são independentes: a segunda não é executada automaticamente após a primeira. Confirme que a conversão foi concluída antes de remover as licenças.

O painel aciona as funções `ConvertTo-SharedMailbox` e `Revoke-AndBlockUser` de `scripts/powershell/offboarding.ps1` pelas ações `converter` e `revogar`, respectivamente.

O módulo `scripts/python/collect_data.py` pode ser importado pelo painel. Ele disponibiliza `carregar_configuracoes()`, `obter_dados_sigo()`, `obter_usuarios_microsoft()` e `cruzar_dados(df_sigo, df_ms)`. A última função retorna os dois DataFrames do cruzamento e grava os CSVs de processamento e auditoria manual.

## Resultados e logs

- O painel exibe a saída do PowerShell para a ação executada e sinaliza falhas.
- O script informa o resultado por usuário e um resumo de sucessos e falhas. Se houver falha em qualquer usuário, retorna código de saída diferente de zero; a saída completa fica disponível no painel.
- A seção **Histórico de execução** mostra as últimas 200 linhas do log e permite baixar o arquivo completo.
- O log do pipeline Python fica em `logs/pipeline_offboarding.log`.
- As listas geradas ficam em `data/desligados_para_powershell.csv` e `data/para_verificar_manual.csv`.

## Critérios de cruzamento

São considerados para processamento os colaboradores inativos no SIGO que correspondem a uma conta no Entra ID. O cruzamento tenta usar matrícula, e-mail/UPN/aliases e nome normalizado único. Correspondências ambíguas ou sem conta correspondente vão para verificação manual.

Uma conta encontrada é enviada para a lista de processamento quando tem licenças atribuídas **ou** está habilitada no Entra ID. Contas já bloqueadas e sem licenças não são incluídas na lista de ações.

## Limitações e próximos passos

- A conversão de caixa compartilhada requer Exchange Online PowerShell e certificado; o segredo do Graph não substitui essa autenticação.
- A retenção e remoção automática de caixas compartilhadas após seis meses ainda não está implementada.

## Estrutura do projeto

```text
├── app.py
├── scripts/
│   ├── python/
│   │   └── collect_data.py
│   └── powershell/
│       └── offboarding.ps1
├── data/
│   ├── desligados_para_powershell.csv
│   └── para_verificar_manual.csv
├── logs/
│   └── pipeline_offboarding.log
├── .env-example
├── requirements.txt
└── README.MD
```

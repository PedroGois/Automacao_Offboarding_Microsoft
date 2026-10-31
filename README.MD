# M365 Offboarding 

> Automação de encerramento de ciclo de vida de identidades e otimização de licenças no Microsoft 365. 
Integrando sistema de RH (SIGO) via Python e PowerShell com Graph API.

---

## 🚨 A Dor (Problema)

- **Desperdício Financeiro:** Contas de colaboradores desligados permaneciam licenciadas por tempo indeterminado apenas para manter o recebimento de e-mails ou consulta de histórico, ou então mantidos até a necessidade de novas licenças, gerando custo desnecessário com aquisição de licenças do M365 acima do real.
- **Risco de Segurança:** Processos manuais de desligamento abriam margem para demoras no bloqueio de credenciais e revogação de sessões ativas.
- **Trabalho Manual Repetitivo:** A equipe de TI gastava tempo executando tarefas manuais e repetitivas de administração no portal do M365, tanto para manter o estoque de licenças quanto para conseguir novas licenças quando chegado ao limite.

---

## 💡 A Solução
Desenvolvimento de uma pipeline unificada de automação que une análise de dados e engenharia de infraestrutura:

1. **Coleta e ETL (`collect_data.py`):** Conecta à API do sistema de RH (SIGO), valida as chapas ignoradas, cruza os dados com o Microsoft Entra ID via Microsoft Graph API e separa automaticamente quem precisa ter o acesso revogado de quem vai para auditoria manual.

2. **Automação via PowerShell & Microsoft Graph API (`offboarding.ps1`):** Consome o `.csv` gerado e executa a política de desligamento automaticamente:
   * Bloqueio imediato de login e derrubada de sessões ativas.
   * Desvinculação das licenças pagas para reutilização e otimização financeira no tenant.
   * Geração de logs de auditoria da execução.

---

## ⏱️ Agendamento e Execução Automatizada
Toda a pipeline é iniciada executando o script principal (`collect_data.py`), que já engloba a extração, o cruzamento inteligente e aciona a limpeza no PowerShell. 

O processo pode ser facilmente **agendado** (via *Agendador de Tarefas do Windows* ou *Crontab* em ambientes Linux) para rodar automaticamente a cada 7 dias (ou na periodicidade desejada), garantindo conformidade contínua e economia de licenças sem intervenção manual.

---
## 🚨 Pendente :
1.Criar a caixa compartilhada antes da remoção das licenças para manter o histórico de emails por 6 meses, preciso verificar se existe um contador de tempo de vida de uma caixa compartilhada para realizar a desativação automaticamente .


## 🚨 Atualizações / Correções
.

## 📂 Estrutura do Repositório

```text
├── docs/
│   └── POLITICA_OFFBOARDING.md      # Diretrizes e regras de negócio do processo
├── scripts/
│   ├── python/
│   │   └── collect_data.py          # Script principal de ETL, cruzamento e início da pipeline
│   └── powershell/
│       └── offboarding.ps1          # Script de automação de bloqueio e remoção de licenças
├── data/
│   ├── desligados_para_powershell.csv # CSV gerado automaticamente com contas para offboarding
│   └── para_verificar_manual.csv    # CSV de auditoria para casos atípicos
├── logs/
│   └── pipeline_offboarding.log     # Histórico de auditoria e execuções
└── README.md                        # Documentação do projeto

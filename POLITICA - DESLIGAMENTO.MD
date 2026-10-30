# Política de Desligamento e Gestão de Identidades (M365)

## 1. Objetivo
Estabelecer um fluxo padronizado, seguro e otimizado para o desligamento de colaboradores no ambiente Microsoft 365, garantindo a revogação imediata de acessos, a conformidade de segurança e a reapropriação eficiente de licenças pagas, evitando o acúmulo de contas inativas no tenant.

---

## 2. Escopo e Recorrência
* **Escopo:** Aplicável a todas as contas de colaboradores desligados no ambiente corporativo.
* **Recorrência do Processo:** Execução semanal (a cada 7 dias) via rotina automatizada de auditoria e sincronização com o sistema de RH (SIGO).

---

## 3. Diretrizes do Processo de Offboarding

Ao ser identificado o desligamento de colaborados, a rotina de automação e a equipe de TI executarão o seguinte fluxo padronizado:

1. **Revogação Imediata de Acessos e Bloqueio:**
   * Bloqueio do início de sessão (*AccountDisabled*) no Microsoft Entra ID.
   * Revogação imediata de todas as sessões ativas (*Revoke Active Sessions*) em navegadores e dispositivos móveis.

2. **Conversão de Caixa de Correio e Otimização de Licenças:**
   * Conversão da caixa de correio do usuário para **Shared Mailbox** (Caixa Compartilhada).
   * Remoção imediata de todas as licenças pagas do M365 atreladas à conta, liberando-as para reutilização imediata por colaboradores ativos.
   * *Benefício:* Mantém o histórico e o recebimento de e-mails ativos sem o consumo de licença (para caixas até o limite de 50 GB).

3. **Remoção de Grupos de Segurança e Distribuição:**
   * Remoção do usuário de todos os grupos de segurança, listas de distribuição e equipes do Microsoft Teams.

4. **Retenção Temporária e Governança (Prazo de 90 dias):**
   * **Problema Identificado:** Manter caixas compartilhadas de ex-colaboradores de maneira indefinida polui o tenant, gera riscos de segurança/compliance (LGPD) e pode estourar o limite de tamanho da Microsoft.
   * **Diretriz Definitiva:** A caixa compartilhada permanecerá ativa por um **prazo máximo de 90 dias** para consulta ou encaminhamento de e-mails ao gestor responsável.
   * **Fim do Ciclo (Pós-90 dias):** Após o período limite, a conta e a caixa de correio serão submetidas a backup/arquivamento definitivo (se necessário por auditoria) e excluídas permanentemente do tenant, mantendo o ambiente limpo e otimizado.
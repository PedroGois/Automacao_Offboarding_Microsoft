import subprocess
from time import perf_counter
import streamlit as st

from scripts.python import collect_data

collect_data.carregar_configuracoes()

st.set_page_config(
    page_title="Painel de Offboarding M365",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Painel de Controle - Offboarding M365 & SIGO")
st.markdown("Automatize o ciclo de vida de identidades e otimização de licenças de forma modular e segura.")

# Sidebar informativa
st.sidebar.header("⚙️ Configurações")
st.sidebar.info("Certifique-se de que o arquivo `.env` está configurado com as credenciais do Azure e SIGO.")

# Inicializar Session State para persistência entre cliques
if "df_sigo" not in st.session_state:
    st.session_state["df_sigo"] = None
if "df_ms" not in st.session_state:
    st.session_state["df_ms"] = None
if "df_desligados" not in st.session_state:
    st.session_state["df_desligados"] = None
if "df_verificar" not in st.session_state:
    st.session_state["df_verificar"] = None

# ==========================================
# ETAPA 1: Busca e Cruzamento (SIGO + Microsoft)
# ==========================================
st.markdown("---")
st.header("Passo 1: Buscar e Cruzar Dados")
st.markdown("Consulta o SIGO e o Microsoft Entra ID, cruza os registros e gera as listas para inspeção.")

if st.button("🚀 Buscar e Cruzar Dados", type="primary"):
    for chave in ("df_sigo", "df_ms", "df_desligados", "df_verificar"):
        st.session_state[chave] = None

    with st.status("Iniciando busca e cruzamento...", expanded=True) as consulta_status:
        mensagem_progresso = consulta_status.empty()

        def mostrar_progresso(msg):
            mensagem_progresso.write(msg)

        try:
            # 1. Consulta SIGO
            inicio = perf_counter()
            df_sigo = collect_data.obter_dados_sigo(progresso=mostrar_progresso)
            mostrar_progresso(f"SIGO: {len(df_sigo)} registros obtidos ({perf_counter() - inicio:.1f}s).")

            # 2. Consulta Microsoft Graph
            inicio = perf_counter()
            mostrar_progresso("Consultando usuários e licenças no Microsoft Entra ID...")
            df_ms = collect_data.obter_usuarios_microsoft(progresso=mostrar_progresso)
            mostrar_progresso(f"Microsoft: Consulta concluída em {perf_counter() - inicio:.1f}s.")

            # Cruzar e salvar os resultados para inspeção e ações posteriores.
            mostrar_progresso("Cruzando os dados e gerando os CSVs...")
            df_desligados, df_verificar = collect_data.cruzar_dados(df_sigo, df_ms)

            st.session_state["df_sigo"] = df_sigo
            st.session_state["df_ms"] = df_ms
            st.session_state["df_desligados"] = df_desligados
            st.session_state["df_verificar"] = df_verificar

            consulta_status.update(label="Busca e cruzamento concluídos!", state="complete")
            st.success(
                f"Dados carregados: SIGO ({len(df_sigo)}) | Microsoft ({len(df_ms)}). "
                f"Prontos para offboarding ({len(df_desligados)}) | "
                f"Verificação manual ({len(df_verificar)})."
            )
            
        except Exception as e:
            consulta_status.update(label="Falha ao consultar as APIs", state="error")
            st.error(f"Erro: {e}")

# Prévia dos dados brutos
if st.session_state["df_sigo"] is not None and not st.session_state["df_sigo"].empty:
    with st.expander("📊 Visualizar Dados Brutos Obtidos"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("SIGO (Colaboradores)")
            st.dataframe(st.session_state["df_sigo"].head(10), use_container_width=True)
        with col2:
            st.subheader("Microsoft Entra ID")
            st.dataframe(st.session_state["df_ms"].head(10), use_container_width=True)

# Exibir tabelas resultantes do cruzamento
if st.session_state["df_desligados"] is not None:
    st.markdown("---")
    st.header("Passo 2: Inspeção Visual")
    st.markdown("Revise as listas antes de executar qualquer ação de offboarding.")

    len_desligados = len(st.session_state['df_desligados'])
    len_verificar = len(st.session_state['df_verificar'])
    
    tab1, tab2 = st.tabs([f"🔴 Prontos para Bloqueio ({len_desligados})", f"🟡 Para Verificação Manual ({len_verificar})"])
    
    with tab1:
        st.dataframe(st.session_state["df_desligados"], use_container_width=True)
    with tab2:
        st.dataframe(st.session_state["df_verificar"], use_container_width=True)

# ==========================================
# ETAPA 3: Ações de Offboarding Separadas
# ==========================================
st.markdown("---")
st.header("Passo 3: Ações de Offboarding (Execução por Etapas)")
st.markdown("Com os dados cruzados e gerados, escolha abaixo qual ação executar nos usuários da lista:")

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    st.info("📦 **Passo A:** Converte as caixas postais em caixas compartilhadas antes de remover licenças.")
    if st.button("🗂️ Converter para Caixa Compartilhada", type="secondary"):
        if st.session_state["df_desligados"] is None or st.session_state["df_desligados"].empty:
            st.warning("Não há usuários na lista para processar.")
        else:
            with st.spinner("Convertendo caixas de correio para Shared Mailbox..."):
                try:
                    output_ps = collect_data.executar_powershell("converter")
                    st.success("Conversão para Caixa Compartilhada concluída!")
                    if output_ps:
                        st.text(output_ps)
                except subprocess.CalledProcessError as e:
                    st.error(f"Erro ao executar conversão (código {e.returncode}).")
                    if e.stdout:
                        st.code(e.stdout)
                    if e.stderr:
                        st.code(e.stderr)
                except Exception as e:
                    st.error(f"Erro ao executar conversão: {e}")

with col_btn2:
    st.warning("🛑 **Passo B:** Bloqueia o acesso, derruba sessões ativas e remove as licenças.")
    if st.button("🛑 Revogar, Bloquear e Remover Licenças", type="primary"):
        if st.session_state["df_desligados"] is None or st.session_state["df_desligados"].empty:
            st.warning("Não há usuários na lista para processar.")
        else:
            with st.spinner("Executando bloqueio e remoção de licenças..."):
                try:
                    output_ps = collect_data.executar_powershell("revogar")
                    st.success("Revogação e remoção de licenças concluídas!")
                    if output_ps:
                        st.text(output_ps)
                except subprocess.CalledProcessError as e:
                    st.error(f"Erro ao executar revogação (código {e.returncode}).")
                    if e.stdout:
                        st.code(e.stdout)
                    if e.stderr:
                        st.code(e.stderr)
                except Exception as e:
                    st.error(f"Erro ao executar revogação: {e}")

st.markdown("---")
with st.expander("📄 Histórico de execução"):
    log_path = collect_data.LOG_PATH
    if log_path.is_file():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        st.code("\n".join(log_text.splitlines()[-200:]), language="log")
        st.download_button(
            "Baixar log completo",
            data=log_text,
            file_name=log_path.name,
            mime="text/plain",
        )
    else:
        st.info("Ainda não há arquivo de log. Ele será criado após a primeira execução.")
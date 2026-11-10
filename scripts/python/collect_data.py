from pathlib import Path
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlencode, urlsplit
import subprocess

from dotenv import load_dotenv
import pandas as pd

ENDPOINT_SIGO = "https://api-refeicao.jfi.com.br/users/licenses"

PASTA_SCRIPT = Path(__file__).resolve().parent
PASTA_RAIZ = PASTA_SCRIPT.parent.parent

OUTPUT_DESLIGADOS_CSV = PASTA_RAIZ / "data" / "desligados_para_powershell.csv"
OUTPUT_VERIFICAR_CSV = PASTA_RAIZ / "data" / "para_verificar_manual.csv"
LOG_PATH = PASTA_RAIZ / "logs" / "pipeline_offboarding.log"
CAMINHO_JSON_EXCECOES = PASTA_RAIZ / "data" / "chapas_ignoradas.json"




# Informe aqui os e-mails que devem ser ignorados.
EMAILS_IGNORADOS = []

# Informe os nomes que devem ser ignorados; a comparação desconsidera acentos e preposições.
NOMES_IGNORADOS = ["IARLEY NASCIMENTO DA SILVEIRA","JOAO ANTONIO MELO LEMOS"]


def carregar_configuracoes():
    load_dotenv(PASTA_RAIZ / ".env")
    (PASTA_RAIZ / "data").mkdir(parents=True, exist_ok=True)
    (PASTA_RAIZ / "logs").mkdir(parents=True, exist_ok=True)
    return {
        "pasta_raiz": PASTA_RAIZ,
        "pasta_dados": PASTA_RAIZ / "data",
        "pasta_logs": PASTA_RAIZ / "logs",
        "output_desligados_csv": OUTPUT_DESLIGADOS_CSV,
        "output_verificar_csv": OUTPUT_VERIFICAR_CSV,
        "log_path": LOG_PATH,
    }


def carregar_chapas_ignoradas():
    """Carrega do JSON as chapas que devem ser excluídas do cruzamento."""
    if not CAMINHO_JSON_EXCECOES.exists():
        return set()
    try:
        with CAMINHO_JSON_EXCECOES.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Não foi possível carregar as chapas ignoradas de "
            f"{CAMINHO_JSON_EXCECOES}: {error}"
        ) from error
    if not isinstance(dados, list):
        raise ValueError(
            f"O arquivo {CAMINHO_JSON_EXCECOES} deve conter uma lista JSON de chapas."
        )
    return {str(chapa).strip() for chapa in dados if str(chapa).strip()}


def adicionar_chapa_ignorada(chapa):
    """Persiste uma chapa na lista dinâmica de exceções."""
    chapa_str = str(chapa).strip()
    if not chapa_str or chapa_str == "N/A":
        return

    CAMINHO_JSON_EXCECOES.parent.mkdir(parents=True, exist_ok=True)
    chapas_ignoradas = carregar_chapas_ignoradas()
    if chapa_str in chapas_ignoradas:
        return
    chapas_ignoradas.add(chapa_str)
    try:
        with CAMINHO_JSON_EXCECOES.open("w", encoding="utf-8") as arquivo:
            json.dump(sorted(chapas_ignoradas), arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
    except OSError as error:
        raise RuntimeError(
            f"Não foi possível salvar as chapas ignoradas em "
            f"{CAMINHO_JSON_EXCECOES}: {error}"
        ) from error


def log_msg(mensagem):
    linha = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}"
    print(linha)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def normalizar_texto(texto):
    """
    Padroniza strings (nomes):
    - Converte para maiúsculas.
    - Remove acentos e substitui Ç por C.
    - Remove pontuações e caracteres especiais.
    - Remove preposições comuns (DE, DA, DO, DAS, DOS, E) para evitar ruído no match.
    """
    if not isinstance(texto, str) or not texto.strip():
        return ""
    
    # Normaliza para separar caracteres e acentos (NFKD)
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    
    maiuscula = sem_acento.upper().replace('Ç', 'C')
    
    # Remove tudo o que não for letra ou número (tira pontuação)
    limpo = re.sub(r'[^A-Z0-9\s]', '', maiuscula)
    
    # Remove preposições e conectivos comuns
    palavras = [p for p in limpo.split() if p not in {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E'}]
    
    return " " .join(palavras)


def request_json(url, method="GET", data=None, token=None, timeout=120):
    headers = {"Accept": "application/json"}
    body = None

    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Falha de conexão: {error.reason}") from error


def obter_dados_sigo(progresso=None):
    carregar_configuracoes()
    document = os.getenv("SIGO_DOCUMENT", "").strip()
    password = os.getenv("SIGO_PASSWORD", "")
    credenciais_ausentes = [
        nome
        for nome, valor in (
            ("SIGO_DOCUMENT", document),
            ("SIGO_PASSWORD", password),
        )
        if not valor
    ]
    if credenciais_ausentes:
        raise RuntimeError(
            "Credenciais do SIGO ausentes no .env: " + ", ".join(credenciais_ausentes)
        )

    endpoint = urlsplit(ENDPOINT_SIGO)
    auth_url = f"{endpoint.scheme}://{endpoint.netloc}/auth/login"
    if progresso:
        progresso("Autenticando no SIGO...")
    login = request_json(
        auth_url,
        method="POST",
        data={"document": document, "password": password},
        timeout=30,
    )
    token_sigo = login.get("accessToken") if isinstance(login, dict) else None
    if not token_sigo:
        raise RuntimeError("A autenticação do SIGO não retornou accessToken.")

    if progresso:
        progresso("Consultando usuários do SIGO...")
    resposta_sigo = request_json(ENDPOINT_SIGO, token=token_sigo, timeout=120)
    if isinstance(resposta_sigo, dict):
        if "data" in resposta_sigo:
            registros = resposta_sigo["data"]
        elif "users" in resposta_sigo:
            registros = resposta_sigo["users"]
        else:
            raise RuntimeError("A resposta do SIGO não contém os registros de usuários.")
    else:
        registros = resposta_sigo
    if not isinstance(registros, list):
        raise RuntimeError("A resposta do SIGO não contém uma lista de usuários.")

    df_sigo = pd.json_normalize(registros)
    log_msg(f"Dados do SIGO carregados: {len(df_sigo)} registros.")
    if progresso:
        progresso(f"SIGO: {len(df_sigo)} registros obtidos.")
    return df_sigo


def obter_usuarios_microsoft(progresso=None):
    carregar_configuracoes()
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    credenciais_ausentes = [
        nome
        for nome, valor in (
            ("AZURE_TENANT_ID", tenant_id),
            ("AZURE_CLIENT_ID", client_id),
            ("AZURE_CLIENT_SECRET", client_secret),
        )
        if not valor
    ]
    if credenciais_ausentes:
        raise RuntimeError(
            "Credenciais do Entra ID ausentes no .env: "
            + ", ".join(credenciais_ausentes)
        )

    log_msg("Autenticando no Microsoft Entra ID (Graph API)...")
    if progresso:
        progresso("Autenticando no Microsoft Entra ID...")
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    body_data = urlencode({
        "client_id": client_id,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }).encode("utf-8")

    req = urllib.request.Request(
        token_url,
        data=body_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token_resp = json.loads(resp.read().decode("utf-8"))
            access_token = token_resp.get("access_token")
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Erro ao autenticar no Entra ID: {e}")

    graph_url = "https://graph.microsoft.com/v1.0/users?$select=displayName,mail,userPrincipalName,otherMails,proxyAddresses,employeeId,accountEnabled,assignedLicenses"
    
    if not access_token:
        raise RuntimeError("A autenticação no Entra ID não retornou access_token.")

    usuarios_ms = []
    pagina = 1
    while graph_url:
        if progresso:
            progresso(f"Consultando Microsoft Graph (página {pagina}; {len(usuarios_ms)} usuários carregados)...")
        resposta_graph = request_json(graph_url, token=access_token)
        if not isinstance(resposta_graph, dict):
            raise RuntimeError("A resposta do Microsoft Graph está em formato inválido.")
        usuarios_pagina = resposta_graph.get("value")
        if not isinstance(usuarios_pagina, list):
            raise RuntimeError("A resposta do Microsoft Graph não contém a lista de usuários.")
        usuarios_ms.extend(usuarios_pagina)
        graph_url = resposta_graph.get("@odata.nextLink")
        pagina += 1

    df_ms = pd.json_normalize(usuarios_ms)
    if progresso:
        progresso(f"Microsoft Graph respondeu: {len(df_ms)} usuários carregados.")
    return df_ms


def _valor_texto(valor):
    if valor is None or isinstance(valor, (list, tuple, set, dict)):
        return ""
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _esta_inativo(valor):
    texto = _valor_texto(valor).lower()
    return texto in {"false", "0", "não", "nao"}


def _esta_habilitado(valor):
    return _valor_texto(valor).lower() in {"true", "1", "sim"}


def processar_cruzamento(df_sigo, df_ms):
    if "isactive" not in df_sigo.columns:
        raise RuntimeError("Coluna 'isactive' não encontrada no SIGO.")
    colunas_ms_necessarias = {"displayName", "assignedLicenses", "accountEnabled"}
    if not colunas_ms_necessarias.issubset(df_ms.columns):
        raise RuntimeError(
            "A resposta do Microsoft Graph precisa conter displayName, assignedLicenses e accountEnabled."
        )

    col_nome_sigo = next(
        (coluna for coluna in ("nome", "name", "displayName") if coluna in df_sigo.columns),
        None,
    )
    if col_nome_sigo is None:
        raise RuntimeError("Coluna de nome do colaborador não encontrada no SIGO.")

    indices_email = {}
    indices_chapa = {}
    indices_nome = {}

    for indice, usuario in df_ms.iterrows():
        for coluna in ("mail", "userPrincipalName", "otherMails", "proxyAddresses"):
            valor = usuario.get(coluna)
            valores = valor if isinstance(valor, (list, tuple, set)) else [valor]
            for item in valores:
                email = _valor_texto(item).lower()
                if email.startswith("smtp:"):
                    email = email[5:]
                if email:
                    indices_email.setdefault(email, []).append(indice)

        chapa = _valor_texto(usuario.get("employeeId"))
        if chapa:
            indices_chapa.setdefault(chapa, []).append(indice)

        nome = normalizar_texto(usuario.get("displayName"))
        if nome:
            indices_nome.setdefault(nome, []).append(indice)

    chapas_ignoradas = carregar_chapas_ignoradas()
    nomes_ignorados = {normalizar_texto(nome) for nome in NOMES_IGNORADOS}
    emails_ignorados = {email.strip().lower() for email in EMAILS_IGNORADOS}
    para_desativar = []
    para_verificar = []

    for _, row_sigo in df_sigo.iterrows():
        if not _esta_inativo(row_sigo.get("isactive")):
            continue

        chapa_sigo = _valor_texto(row_sigo.get("externalid")) or "N/A"
        nome_sigo = row_sigo.get(col_nome_sigo, "")
        nome_normalizado = normalizar_texto(nome_sigo)
        email_sigo = _valor_texto(row_sigo.get("email")).lower()
        if (
            chapa_sigo in chapas_ignoradas
            or nome_normalizado in nomes_ignorados
            or email_sigo in emails_ignorados
        ):
            continue

        encontrado = None
        motivo_nao_encontrado = "Inativo no SIGO mas não encontrado no Entra ID"

        matches_chapa = indices_chapa.get(chapa_sigo, []) if chapa_sigo != "N/A" else []
        if len(matches_chapa) == 1:
            encontrado = df_ms.loc[matches_chapa[0]]
        elif len(matches_chapa) > 1:
            motivo_nao_encontrado = "Correspondência de chapa ambígua no Entra ID"
        else:
            matches_email = indices_email.get(email_sigo, []) if email_sigo else []
            matches_email = list(dict.fromkeys(matches_email))
            if len(matches_email) == 1:
                encontrado = df_ms.loc[matches_email[0]]
            elif len(matches_email) > 1:
                motivo_nao_encontrado = "Correspondência de e-mail ambígua no Entra ID"
            else:
                matches_nome = indices_nome.get(nome_normalizado, []) if nome_normalizado else []
                if len(matches_nome) == 1:
                    encontrado = df_ms.loc[matches_nome[0]]
                elif len(matches_nome) > 1:
                    motivo_nao_encontrado = "Correspondência de nome ambígua no Entra ID"

        if encontrado is None:
            para_verificar.append({
                "ChapaSIGO": chapa_sigo,
                "NomeSIGO": nome_sigo,
                "EmailSIGO": email_sigo,
                "Motivo": motivo_nao_encontrado,
            })
            continue

        licencas = encontrado.get("assignedLicenses")
        tem_licenca = isinstance(licencas, (list, tuple, set)) and len(licencas) > 0
        habilitado = _esta_habilitado(encontrado.get("accountEnabled"))
        upn = _valor_texto(encontrado.get("userPrincipalName")) or _valor_texto(encontrado.get("mail"))

        if tem_licenca or habilitado:
            if not upn:
                para_verificar.append({
                    "ChapaSIGO": chapa_sigo,
                    "NomeSIGO": nome_sigo,
                    "EmailSIGO": email_sigo,
                    "Motivo": "Conta encontrada no Entra ID sem UPN ou e-mail para executar o bloqueio",
                })
                continue
            para_desativar.append({
                "UserPrincipalName": upn,
                "ChapaSIGO": chapa_sigo,
                "NomeSIGO": nome_sigo,
            })
        else:
            # Conta já bloqueada e sem licenças: ignorada e descartada da verificação manual
            continue

    return (
        pd.DataFrame(para_desativar, columns=["UserPrincipalName", "ChapaSIGO", "NomeSIGO"]),
        pd.DataFrame(para_verificar, columns=["ChapaSIGO", "NomeSIGO", "EmailSIGO", "Motivo"]),
    )


def cruzar_dados(df_sigo, df_ms):
    carregar_configuracoes()
    if not isinstance(df_sigo, pd.DataFrame) or not isinstance(df_ms, pd.DataFrame):
        raise TypeError("df_sigo e df_ms devem ser pandas.DataFrame.")
    if not df_sigo.empty and "isactive" not in df_sigo.columns:
        raise RuntimeError("Coluna 'isactive' não encontrada no SIGO.")

    col_nome_sigo = next(
        (coluna for coluna in ("nome", "name", "displayName") if coluna in df_sigo.columns),
        None,
    )
    if not df_sigo.empty and col_nome_sigo is None:
        raise RuntimeError("Coluna de nome do colaborador não encontrada no SIGO.")

    inativos = df_sigo[
        df_sigo["isactive"].apply(_esta_inativo)
    ].copy() if not df_sigo.empty else df_sigo.copy()

    if inativos.empty:
        df_desligados = pd.DataFrame(
            columns=["UserPrincipalName", "ChapaSIGO", "NomeSIGO"]
        )
        df_verificar = pd.DataFrame(
            columns=["ChapaSIGO", "NomeSIGO", "EmailSIGO", "Motivo"]
        )
    elif df_ms.empty:
        chapas_ignoradas = carregar_chapas_ignoradas()
        nomes_ignorados = {normalizar_texto(nome) for nome in NOMES_IGNORADOS}
        emails_ignorados = {email.strip().lower() for email in EMAILS_IGNORADOS}
        registros_manuais = []
        for _, row in inativos.iterrows():
            chapa = _valor_texto(row.get("externalid")) or "N/A"
            nome = row.get(col_nome_sigo, "")
            email = _valor_texto(row.get("email")).lower()
            if (
                chapa in chapas_ignoradas
                or normalizar_texto(nome) in nomes_ignorados
                or email in emails_ignorados
            ):
                continue
            registros_manuais.append({
                "ChapaSIGO": chapa,
                "NomeSIGO": nome,
                "EmailSIGO": email,
                "Motivo": "Comparação com a Microsoft não realizada",
            })
        df_desligados = pd.DataFrame(
            columns=["UserPrincipalName", "ChapaSIGO", "NomeSIGO"]
        )
        df_verificar = pd.DataFrame(
            registros_manuais,
            columns=["ChapaSIGO", "NomeSIGO", "EmailSIGO", "Motivo"],
        )
    else:
        df_desligados, df_verificar = processar_cruzamento(inativos, df_ms)

    OUTPUT_DESLIGADOS_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_desligados.to_csv(OUTPUT_DESLIGADOS_CSV, index=False, sep=";")
    df_verificar.to_csv(OUTPUT_VERIFICAR_CSV, index=False, sep=";")
    log_msg(
        "Cruzamento concluído: "
        f"{len(df_desligados)} conta(s) para processamento e "
        f"{len(df_verificar)} para verificação manual."
    )
    return df_desligados, df_verificar


def executar_powershell(acao):
    if acao not in {"converter", "revogar"}:
        raise ValueError(f"Ação PowerShell inválida: {acao}")

    ps_script_path = PASTA_RAIZ / "scripts" / "powershell" / "offboarding.ps1"
    if not ps_script_path.exists():
        raise FileNotFoundError(f"Script PowerShell não encontrado em: {ps_script_path}")

    log_msg(f"[OFFBOARDING/{acao.upper()}] Iniciando execução para os usuários do CSV.")
    try:
        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_script_path.resolve()),
                "-Acao",
                acao,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except subprocess.CalledProcessError as error:
        log_msg(f"[OFFBOARDING/{acao.upper()}] Falhou com código {error.returncode}.")
        if error.stdout:
            log_msg(f"[OFFBOARDING/{acao.upper()}] Saída:\n{error.stdout.strip()}")
        if error.stderr:
            log_msg(f"[OFFBOARDING/{acao.upper()}] Erros:\n{error.stderr.strip()}")
        raise

    log_msg(f"[OFFBOARDING/{acao.upper()}] Concluída com código 0.")
    if resultado.stdout:
        log_msg(f"[OFFBOARDING/{acao.upper()}] Saída:\n{resultado.stdout.strip()}")
    return resultado.stdout


def main():
    carregar_configuracoes()
    log_msg("Iniciando pipeline unificado de auditoria e offboarding...")
    df_sigo = obter_dados_sigo()
    df_ms = obter_usuarios_microsoft()
    cruzar_dados(df_sigo, df_ms)
    log_msg("Ações de offboarding aguardam execução manual pelo painel.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log_msg(f"Falha no pipeline ({type(error).__name__}): {error}")
        raise
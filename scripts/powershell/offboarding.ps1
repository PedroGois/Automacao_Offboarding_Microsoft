param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("converter", "revogar")]
    [string]$Acao
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$CsvPath = Join-Path $ScriptDir "..\..\data\desligados_para_powershell.csv"
$EnvPath = Join-Path $ScriptDir "..\..\.env"

# Carregar variáveis do .env
if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
        if ($_ -match '^\s*([^#\s]+)\s*=\s*(.*)\s*$') {
            $name = $matches[1]
            $value = $matches[2] -replace '^["'']|["'']$'
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$TenantId = $env:AZURE_TENANT_ID
$ClientId = $env:AZURE_CLIENT_ID
$ClientSecret = $env:AZURE_CLIENT_SECRET
$ExchangeOrganization = $env:EXCHANGE_ORGANIZATION
$CertificateThumbprint = $env:AZURE_CERTIFICATE_THUMBPRINT

if ($Acao -eq "converter") {
    $ExchangeVariaveisAusentes = @()
    if (-not $ClientId) { $ExchangeVariaveisAusentes += "AZURE_CLIENT_ID" }
    if (-not $ExchangeOrganization) { $ExchangeVariaveisAusentes += "EXCHANGE_ORGANIZATION" }
    if (-not $CertificateThumbprint) { $ExchangeVariaveisAusentes += "AZURE_CERTIFICATE_THUMBPRINT" }
    if ($ExchangeVariaveisAusentes.Count -gt 0) {
        Write-Output "ERRO: Conversão não iniciada. Configure no .env: $($ExchangeVariaveisAusentes -join ', ')."
        exit 1
    }
}
else {
    $GraphVariaveisAusentes = @()
    if (-not $TenantId) { $GraphVariaveisAusentes += "AZURE_TENANT_ID" }
    if (-not $ClientId) { $GraphVariaveisAusentes += "AZURE_CLIENT_ID" }
    if (-not $ClientSecret) { $GraphVariaveisAusentes += "AZURE_CLIENT_SECRET" }
    if ($GraphVariaveisAusentes.Count -gt 0) {
        Write-Output "ERRO: Revogação não iniciada. Configure no .env: $($GraphVariaveisAusentes -join ', ')."
        exit 1
    }
}

if (-not (Test-Path $CsvPath)) {
    Write-Host "CSV de desligados não encontrado." -ForegroundColor Yellow
    exit 0
}

$UsuariosDesligados = Import-Csv -Path $CsvPath -Delimiter ";"
if (-not $UsuariosDesligados -or $UsuariosDesligados.Count -eq 0) {
    Write-Host "Nenhum usuário no CSV para processar." -ForegroundColor Yellow
    exit 0
}

if ($Acao -eq "revogar") {
# Obter Token da Graph API
$Body = @{
    client_id     = $ClientId
    scope         = "https://graph.microsoft.com/.default"
    client_secret = $ClientSecret
    grant_type    = "client_credentials"
}
$TokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
try {
    $TokenResponse = Invoke-RestMethod -Method Post -Uri $TokenUrl -Body $Body -ErrorAction Stop
}
catch {
    Write-Output "ERRO: Falha na autenticação do Microsoft Graph. Confira tenant, client ID e validade do segredo. Detalhe: $($_.Exception.Message)"
    exit 1
}
$AccessToken = $TokenResponse.access_token
if (-not $AccessToken) {
    Write-Output "ERRO: A resposta de autenticação do Graph não contém access_token."
    exit 1
}

$Headers = @{
    "Authorization" = "Bearer $AccessToken"
    "Content-Type"  = "application/json"
}
}

# ==========================================
# FUNÇÃO 1: Converter para Caixa Compartilhada
# ==========================================
function Invoke-ConvertToSharedBox {
    Write-Host "--- INICIANDO CONVERSÃO PARA CAIXA COMPARTILHADA ---" -ForegroundColor Cyan
    $Sucessos = 0
    $Falhas = 0

    # Conexão no Exchange Online via ExchangeOnlineManagement
    try {
        if (-not (Get-Module -ListAvailable ExchangeOnlineManagement)) {
            throw "O módulo ExchangeOnlineManagement não está instalado. Instale-o antes de executar a conversão."
        }
        Import-Module ExchangeOnlineManagement
        Connect-ExchangeOnline -Organization $ExchangeOrganization -AppId $ClientId -CertificateThumbprint $CertificateThumbprint -ShowBanner:$false
    }
    catch {
        throw "Falha ao conectar no Exchange Online. Verifique certificado, permissões Exchange.ManageAsApp e organização. Detalhe: $($_.Exception.Message)"
    }

    foreach ($usuario in $UsuariosDesligados) {
        $upn = $usuario.UserPrincipalName
        $nome = $usuario.NomeSIGO
        try {
            Write-Host "Convertendo para Shared Box: $nome ($upn)..." -ForegroundColor Yellow
            Set-Mailbox -Identity $upn -Type Shared -ErrorAction Stop
            $Mailbox = Get-Mailbox -Identity $upn -ErrorAction Stop
            if ($Mailbox.RecipientTypeDetails -ne "SharedMailbox") {
                throw "O Exchange não confirmou RecipientTypeDetails=SharedMailbox (retornado: $($Mailbox.RecipientTypeDetails))."
            }
            $Sucessos++
            Write-Host "  -> SUCESSO: caixa confirmada como compartilhada." -ForegroundColor Green
        }
        catch {
            $Falhas++
            Write-Host "  -> ERRO ao converter/verificar caixa: $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    try { Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    Write-Host "RESUMO CONVERSÃO: $Sucessos sucesso(s), $Falhas falha(s)."
    if ($Falhas -gt 0) { exit 1 }
}

# ==========================================
# FUNÇÃO 2: Revogar, Bloquear e Remover Licenças
# ==========================================
function Invoke-RevokeAndBlock {
    Write-Host "--- INICIANDO BLOQUEIO E REMOÇÃO DE LICENÇAS ---" -ForegroundColor Cyan
    $Sucessos = 0
    $Falhas = 0

    foreach ($usuario in $UsuariosDesligados) {
        $upn = $usuario.UserPrincipalName
        $nome = $usuario.NomeSIGO
        $Etapa = "validar UPN"
        try {
            if (-not $upn) { throw "UPN vazio no CSV." }
            Write-Host "Processando revogação para: $nome ($upn)..." -ForegroundColor Yellow

            $Etapa = "buscar usuário e licenças no Graph"
            $UpnCodificado = [uri]::EscapeDataString($upn)
            $GetUserUrl = "https://graph.microsoft.com/v1.0/users/$UpnCodificado`?`$select=id,assignedLicenses"
            $GraphUser = Invoke-RestMethod -Method Get -Uri $GetUserUrl -Headers $Headers
            $UserId = $GraphUser.id

            if (-not $UserId) { throw "Usuário não encontrado no Entra ID." }

            $Etapa = "bloquear login"
            $UpdateUserBody = @{ accountEnabled = $false } | ConvertTo-Json
            Invoke-RestMethod -Method Patch -Uri "https://graph.microsoft.com/v1.0/users/$UserId" -Headers $Headers -Body $UpdateUserBody

            $Etapa = "revogar sessões"
            Invoke-RestMethod -Method Post -Uri "https://graph.microsoft.com/v1.0/users/$UserId/revokeSignInSessions" -Headers $Headers

            $Etapa = "remover licenças"
            if ($GraphUser.assignedLicenses.Count -gt 0) {
                $skuIdsToRemove = $GraphUser.assignedLicenses | Select-Object -ExpandProperty skuId
                $LicenseBody = @{ addLicenses = @(); removeLicenses = $skuIdsToRemove } | ConvertTo-Json -Depth 3
                Invoke-RestMethod -Method Post -Uri "https://graph.microsoft.com/v1.0/users/$UserId/assignLicense" -Headers $Headers -Body $LicenseBody
            }
            $Sucessos++
            Write-Host "  -> SUCESSO: login bloqueado, sessões revogadas; licenças removidas: $($GraphUser.assignedLicenses.Count)." -ForegroundColor Green
        }
        catch {
            $Falhas++
            Write-Host "  -> ERRO na etapa '$Etapa': $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    Write-Host "RESUMO REVOGAÇÃO: $Sucessos sucesso(s), $Falhas falha(s)."
    if ($Falhas -gt 0) { exit 1 }
}

# Executa com base no argumento recebido do Streamlit/Python
if ($Acao -eq "converter") {
    Invoke-ConvertToSharedBox
}
elseif ($Acao -eq "revogar") {
    Invoke-RevokeAndBlock
}
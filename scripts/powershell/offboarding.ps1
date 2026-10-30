$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$CsvPath = Join-Path $ScriptDir "..\..\data\desligados_para_powershell.csv"
$EnvPath = Join-Path $ScriptDir "..\..\.env"

Write-Host "Procurando arquivo .env em: $EnvPath" -ForegroundColor DarkGray
if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
        if ($_ -match '^\s*([^#\s]+)\s*=\s*(.*)\s*$') {
            $name = $matches[1]
            $value = $matches[2] -replace '^["'']|["'']$' # Remove aspas se houver
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$TenantId = $env:AZURE_TENANT_ID
$ClientId = $env:AZURE_CLIENT_ID
$ClientSecret = $env:AZURE_CLIENT_SECRET

if (-not $TenantId -or -not $ClientId -or -not $ClientSecret) {
    Write-Error "As credenciais do Azure (Tenant, Client ID, Secret) não foram encontradas no ambiente ou no .env."
    exit 1
}

if (-not (Test-Path $CsvPath)) {
    Write-Host "Arquivo CSV de desligados não encontrado em: $CsvPath. Encerrando." -ForegroundColor Yellow
    exit 0
}

# Importa o CSV usando o separador definido pelo script Python.
$UsuariosDesligados = Import-Csv -Path $CsvPath -Delimiter ";"

if (-not $UsuariosDesligados -or $UsuariosDesligados.Count -eq 0) {
    Write-Host "Nenhum usuário encontrado no CSV para processamento." -ForegroundColor Green
    exit 0
}

Write-Host "Total de usuários para processar no PowerShell: $($UsuariosDesligados.Count)" -ForegroundColor Cyan
Write-Host "Autenticando no Microsoft Graph..." -ForegroundColor Cyan

# Solicita um token do Microsoft Graph usando as credenciais da aplicação.
$Body = @{
    client_id     = $ClientId
    scope         = "https://graph.microsoft.com/.default"
    client_secret = $ClientSecret
    grant_type    = "client_credentials"
}
$TokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$TokenResponse = Invoke-RestMethod -Method Post -Uri $TokenUrl -Body $Body
$AccessToken = $TokenResponse.access_token

$Headers = @{
    "Authorization" = "Bearer $AccessToken"
    "Content-Type"  = "application/json"
}

foreach ($usuario in $UsuariosDesligados) {
    $upn = $usuario.UserPrincipalName
    $chapa = $usuario.ChapaSIGO
    $nome = $usuario.NomeSIGO

    Write-Host "Processando offboarding para: $nome (UPN: $upn | Chapa: $chapa)" -ForegroundColor Yellow

    try {
        # Localiza o usuário no Entra ID pelo UPN.
        $GetUserUrl = "https://graph.microsoft.com/v1.0/users/$upn`?`$select=id"
        $GraphUser = Invoke-RestMethod -Method Get -Uri $GetUserUrl -Headers $Headers
        $UserId = $GraphUser.id

        if (-not $UserId) {
            Write-Host "  -> Erro: Usuário não encontrado no Entra ID para o UPN: $upn" -ForegroundColor Red
            continue
        }

        # Bloqueia o login e revoga as sessões ativas do usuário.
        $UpdateUserBody = @{
            accountEnabled = $false
        } | ConvertTo-Json
        
        $UpdateUrl = "https://graph.microsoft.com/v1.0/users/$UserId"
        Invoke-RestMethod -Method Patch -Uri $UpdateUrl -Headers $Headers -Body $UpdateUserBody
        Write-Host "  -> Acesso bloqueado com sucesso." -ForegroundColor Green

        $RevokeUrl = "https://graph.microsoft.com/v1.0/users/$UserId/revokeSignInSessions"
        Invoke-RestMethod -Method Post -Uri $RevokeUrl -Headers $Headers
        Write-Host "  -> Sessões ativas derrubadas." -ForegroundColor Green

        # Remove as licenças atribuídas para liberar as vagas no tenant.
        $LicensesUrl = "https://graph.microsoft.com/v1.0/users/$UserId/assignedLicenses"
        $UserLicenses = Invoke-RestMethod -Method Get -Uri $LicensesUrl -Headers $Headers
        
        if ($UserLicenses.value.Count -gt 0) {
            $skuIdsToRemove = $UserLicenses.value | Select-Object -ExpandProperty skuId
            
            $LicenseBody = @{
                addLicenses    = @()
                removeLicenses = $skuIdsToRemove
            } | ConvertTo-Json -Depth 3

            $AssignLicenseUrl = "https://graph.microsoft.com/v1.0/users/$UserId/assignLicense"
            Invoke-RestMethod -Method Post -Uri $AssignLicenseUrl -Headers $Headers -Body $LicenseBody
            Write-Host "  -> Licenças removidas com sucesso: $($skuIdsToRemove -join ', ')" -ForegroundColor Green
        } else {
            Write-Host "  -> O usuário não possui licenças ativas para remover." -ForegroundColor Gray
        }

        Write-Host "  -> Offboarding concluído com sucesso para $upn" -ForegroundColor Cyan

    }
    catch {
        Write-Host "  -> Erro ao processar o usuário $upn : $_" -ForegroundColor Red
    }
}

Write-Host "Pipeline PowerShell finalizada com sucesso!" -ForegroundColor Green
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$watchLog = Join-Path $root "nexus-guardian.log"
$apiUrl = "http://127.0.0.1:5000/api/health"
$siteUrl = "https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/api/health"
$apiStarter = Join-Path $root "iniciar_nexus.py"
$httpsStarter = Join-Path $root "iniciar-nexus-https.ps1"
$script:lastEndpointError = "sin detalles"

function Write-Log([string]$message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message" |
        Out-File -FilePath $watchLog -Append -Encoding utf8
}

function Test-Endpoint([string]$url) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            return $true
        }
        $script:lastEndpointError = "HTTP $($response.StatusCode)"
        return $false
    }
    catch {
        $script:lastEndpointError = $_.Exception.Message
        return $false
    }
}

function Start-Api {
    if (Test-Endpoint $apiUrl) {
        return
    }

    Write-Log "API local no disponible ($script:lastEndpointError). Iniciando NEXUS..."
    $starter = Start-Process -FilePath "py.exe" `
        -ArgumentList "-X utf8 `"$apiStarter`"" `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $starter.WaitForExit(30000) | Out-Null
    if (-not (Test-Endpoint $apiUrl)) {
        Write-Log "La API sigue sin responder ($script:lastEndpointError). Se reintentará en el siguiente ciclo."
    }
    else {
        Write-Log "API local activa."
    }
}

function Start-SecureSite {
    if (Test-Endpoint $siteUrl) {
        return
    }

    Write-Log "Sitio HTTPS local no disponible. Iniciando el host seguro..."
    $env:DOTNET_CLI_HOME = Join-Path $root ".dotnet-cli"
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$httpsStarter`"" `
        -WorkingDirectory $root -WindowStyle Hidden | Out-Null

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-Endpoint $siteUrl) {
            Write-Log "Sitio HTTPS local activo."
            return
        }
        Start-Sleep -Seconds 1
    }
    Write-Log "El sitio HTTPS no respondió ($script:lastEndpointError). Se reintentará en el siguiente ciclo."
}

function Open-Chrome {
    if (-not (Test-Endpoint $siteUrl)) {
        return
    }

    try {
        & (Join-Path $root "abrir-nexus-chrome.ps1")
        Write-Log "NEXUS abierto en Chrome."
    }
    catch {
        Write-Log "No se pudo abrir Chrome: $($_.Exception.Message)"
    }
}

Write-Log "Guardian NEXUS iniciado al iniciar sesión."
$script:chromeOpened = $false
try {
    Start-Api
}
catch {
    Write-Log "Error al iniciar la API durante el arranque: $($_.Exception.Message)"
}
try {
    Start-SecureSite
}
catch {
    Write-Log "Error al iniciar el sitio HTTPS durante el arranque: $($_.Exception.Message)"
}
try {
    if (Test-Endpoint $siteUrl) {
        Open-Chrome
        $script:chromeOpened = $true
    }
}
catch {
    Write-Log "Error al abrir NEXUS en Chrome durante el arranque: $($_.Exception.Message)"
}

while ($true) {
    try {
        if (-not (Test-Endpoint $apiUrl)) {
            Write-Log "La API dejó de responder; se reiniciará."
            Start-Api
        }
    }
    catch {
        Write-Log "Error al supervisar o iniciar la API: $($_.Exception.Message)"
    }

    try {
        if (-not (Test-Endpoint $siteUrl)) {
            Write-Log "El sitio HTTPS dejó de responder; se reiniciará."
            Start-SecureSite
        }
    }
    catch {
        Write-Log "Error al supervisar o iniciar el sitio HTTPS: $($_.Exception.Message)"
    }

    if (-not $script:chromeOpened -and (Test-Endpoint $siteUrl)) {
        try {
            Open-Chrome
            $script:chromeOpened = $true
        }
        catch {
            Write-Log "Error al abrir NEXUS en Chrome: $($_.Exception.Message)"
        }
    }

    Start-Sleep -Seconds 60
}

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$siteUrl = "https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/"
$healthUrl = "https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/api/health"
$watchLog = Join-Path $root "nexus-guardian.log"

function Write-Log([string]$message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message" |
        Out-File -FilePath $watchLog -Append -Encoding utf8
}

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$([Environment]::GetEnvironmentVariable('ProgramFiles(x86)'))\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chromePath = $chromeCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if (-not $chromePath) {
    throw "No se encontró Google Chrome. Instálalo para abrir NEXUS automáticamente."
}

$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Start-Process -FilePath $chromePath -ArgumentList $siteUrl
            Write-Log "NEXUS abierto en Chrome al iniciar sesión."
            exit 0
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

Write-Log "No se pudo abrir NEXUS en Chrome: el sitio HTTPS no respondió en 90 segundos."
throw "NEXUS no respondió en $healthUrl. Revisa nexus-guardian.log."

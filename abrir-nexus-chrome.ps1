$ErrorActionPreference = "Stop"
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

$siteUrl = "https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/"
Start-Process -FilePath $chromePath -ArgumentList $siteUrl

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$watchLog = Join-Path $root "nexus-guardian.log"
$apiUrl = "http://127.0.0.1:5000/api/health"
$siteUrl = "https://localhost:5500/api/health"
$apiStarter = Join-Path $root "iniciar_nexus.py"
$httpsStarter = Join-Path $root "iniciar-nexus-https.ps1"
$pythonPathFile = Join-Path $root ".nexus-python-exe"
$pythonSitePathFile = Join-Path $root ".nexus-python-site"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$script:lastEndpointError = "sin detalles"
$script:runningAsSystem = [Security.Principal.WindowsIdentity]::GetCurrent().IsSystem
$script:pythonExecutable = if ($script:runningAsSystem -and
    (Test-Path -LiteralPath $pythonPathFile -PathType Leaf)) {
    (Get-Content -LiteralPath $pythonPathFile -Raw -Encoding UTF8).Trim()
}
elseif (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $venvPython
}
elseif (Test-Path -LiteralPath $pythonPathFile -PathType Leaf) {
    (Get-Content -LiteralPath $pythonPathFile -Raw -Encoding UTF8).Trim()
}
else {
    (Get-Command "py.exe" -ErrorAction SilentlyContinue).Source
}
$script:pythonSitePackages = if ($script:runningAsSystem -and
    $script:pythonExecutable -eq $venvPython) {
    Join-Path $root ".venv\Lib\site-packages"
}
elseif ($script:pythonExecutable -eq $venvPython) {
    $null
}
elseif (Test-Path -LiteralPath $pythonSitePathFile) {
    (Get-Content -LiteralPath $pythonSitePathFile -Raw -Encoding UTF8).Trim()
}
else {
    $null
}
$certificatePath = Join-Path $root "certs\localhost.crt"

function Write-Log([string]$message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message" |
        Out-File -FilePath $watchLog -Append -Encoding utf8
}

function Test-Endpoint([string]$url) {
    try {
        if ($script:runningAsSystem -and $url.StartsWith("https://")) {
            $curlPath = Join-Path $env:SystemRoot "System32\curl.exe"
            if (-not (Test-Path -LiteralPath $curlPath -PathType Leaf) -or
                -not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
                throw "Falta curl.exe o el certificado local requerido para comprobar HTTPS."
            }
            $httpStatus = & $curlPath --cacert $certificatePath --silent `
                --show-error --max-time 5 --output NUL --write-out "%{http_code}" $url 2>$null
            if ($LASTEXITCODE -eq 0 -and $httpStatus -eq "200") {
                return $true
            }
            $script:lastEndpointError = if ($LASTEXITCODE -ne 0) {
                "curl.exe terminó con código $LASTEXITCODE"
            }
            else {
                "HTTP $httpStatus"
            }
            return $false
        }
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

    if (-not $script:pythonExecutable -or
        -not (Test-Path -LiteralPath $script:pythonExecutable -PathType Leaf)) {
        throw "No se encontró el ejecutable de Python para iniciar la API: $script:pythonExecutable"
    }

    Write-Log "API local no disponible ($script:lastEndpointError). Iniciando NEXUS..."
    if ($script:pythonSitePackages) {
        $env:PYTHONPATH = if ($env:PYTHONPATH) {
            "$script:pythonSitePackages;$env:PYTHONPATH"
        }
        else {
            $script:pythonSitePackages
        }
    }
    $apiServer = Join-Path $root "server.py"
    $apiEntryPoint = if ($script:runningAsSystem) { $apiServer } else { $apiStarter }
    if ($script:runningAsSystem) {
        $env:NEXUS_HTTPS = "true"
        foreach ($secretFile in @(
                (Join-Path $root ".admin-code"),
                (Join-Path $root ".session-secret")
            )) {
            if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
                throw "No se encontró el archivo requerido para el inicio seguro de NEXUS: $([IO.Path]::GetFileName($secretFile))"
            }
            $secret = (Get-Content -LiteralPath $secretFile -Raw -Encoding UTF8).Trim()
            if (-not $secret) {
                throw "El archivo de seguridad de NEXUS está vacío: $([IO.Path]::GetFileName($secretFile))"
            }
            if ([IO.Path]::GetFileName($secretFile) -eq ".admin-code") {
                $env:NEXUS_ADMIN_CODE = $secret
            }
            else {
                $env:NEXUS_SESSION_SECRET = $secret
            }
        }
    }

    try {
        $starter = Start-Process -FilePath $script:pythonExecutable `
            -ArgumentList "-X utf8 `"$apiEntryPoint`"" `
            -RedirectStandardOutput (Join-Path $root "nexus-server.log") `
            -RedirectStandardError (Join-Path $root "nexus-server-error.log") `
            -WorkingDirectory $root -WindowStyle Hidden -PassThru
        $starter.WaitForExit(30000) | Out-Null
    }
    finally {
        if ($script:runningAsSystem) {
            Remove-Item Env:NEXUS_ADMIN_CODE -ErrorAction SilentlyContinue
            Remove-Item Env:NEXUS_SESSION_SECRET -ErrorAction SilentlyContinue
        }
    }
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
    Start-Process -FilePath (Join-Path $PSHOME "powershell.exe") `
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

function Stop-UserNexusProcesses {
    $apiServer = Join-Path $root "server.py"
    $guardianScript = Join-Path $root "nexus-siempre-activo.ps1"
    $patterns = @(
        [regex]::Escape($apiServer),
        [regex]::Escape($httpsStarter),
        [regex]::Escape((Join-Path $root "secure-host\NexusHttpsHost.csproj")),
        [regex]::Escape((Join-Path $root "secure-host\bin\Debug\net10.0\NexusHttpsHost.exe"))
    )
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $commandLine = $_.CommandLine
        $commandLine -and ($patterns | Where-Object { $commandLine -match $_ }).Count -gt 0
    }
    foreach ($process in $processes) {
        $owner = Invoke-CimMethod -InputObject $process -MethodName GetOwner `
            -ErrorAction SilentlyContinue
        if ($owner.User -and $owner.User -ne "SYSTEM") {
            Write-Log "Reiniciando el servicio NEXUS PID $($process.ProcessId) como SYSTEM para mantenerlo al cerrar sesión."
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    $duplicateGuardians = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.Name -match "^powershell(?:\.exe)?$" -and
        $_.CommandLine -match [regex]::Escape($guardianScript)
    }
    foreach ($guardian in $duplicateGuardians) {
        Write-Log "Cerrando supervisor NEXUS duplicado PID $($guardian.ProcessId)."
        Stop-Process -Id $guardian.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-Endpoint $apiUrl) -and -not (Test-Endpoint $siteUrl)) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    if (Test-Endpoint $apiUrl) {
        $apiPort = ([Uri]$apiUrl).Port
        $apiListeners = @(
            Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique
        )
        foreach ($listenerProcessId in $apiListeners) {
            $listenerProcess = Get-Process -Id $listenerProcessId -ErrorAction Stop
            if ($listenerProcess.ProcessName -notmatch "^python(?:3(?:\.\d+)?)?$") {
                continue
            }
            Write-Log "Reiniciando el listener de la API NEXUS PID $listenerProcessId para aplicar la versión del proyecto."
            Stop-Process -Id $listenerProcessId -Force -ErrorAction Stop
        }
        if (Test-Endpoint $apiUrl) {
            throw "La API NEXUS siguió respondiendo después de detener su listener; no se puede aplicar la migración."
        }
    }
}

if ($script:runningAsSystem) {
    if (-not $script:pythonExecutable -or
        -not (Test-Path -LiteralPath $script:pythonExecutable -PathType Leaf)) {
        throw "No se encontró el ejecutable de Python del sistema: $script:pythonExecutable"
    }
    Write-Log "Guardian NEXUS iniciado como SYSTEM al arrancar Windows."
    try {
        Stop-UserNexusProcesses
    }
    catch {
        Write-Log "No se pudieron reemplazar todos los servicios NEXUS de la sesión: $($_.Exception.Message)"
    }
}
else {
    Write-Log "Guardian NEXUS iniciado en la sesión de Windows."
}
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

    Start-Sleep -Seconds 60
}

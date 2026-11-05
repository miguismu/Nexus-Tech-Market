param(
    [string]$TaskUser,
    [string]$StartupDirectory,
    [string]$PythonSitePackages,
    [switch]$RunAtSystemStartup
)

$ErrorActionPreference = "Stop"
$systemTaskName = "NEXUS-SiempreActivo"
$taskName = if ($RunAtSystemStartup) {
    $systemTaskName
}
else {
    "NEXUS-SiempreActivo-Usuario"
}
if (-not $TaskUser) {
    $TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
}
if (-not $StartupDirectory) {
    $StartupDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
}
if ($RunAtSystemStartup) {
    $storedPythonSite = Get-Content (Join-Path $PSScriptRoot ".nexus-python-site") `
        -Raw -ErrorAction SilentlyContinue
    if (-not $PythonSitePackages -or
        -not (Test-Path -LiteralPath $PythonSitePackages -PathType Container)) {
        if ($storedPythonSite) {
            $PythonSitePackages = $storedPythonSite.Trim()
        }
    }
    if (-not $PythonSitePackages -or
        -not (Test-Path -LiteralPath $PythonSitePackages -PathType Container)) {
        throw "La carpeta site-packages de Python de $TaskUser no está disponible."
    }
    $venvConfig = Join-Path $PSScriptRoot ".venv\pyvenv.cfg"
    $versionMatch = if (Test-Path -LiteralPath $venvConfig -PathType Leaf) {
        [regex]::Match(
            (Get-Content -LiteralPath $venvConfig -Raw),
            "(?m)^version\s*=\s*(\d+)\.(\d+)\."
        )
    }
    if (-not $versionMatch.Success) {
        throw "No se pudo leer la versión de Python del entorno virtual del proyecto."
    }
    $pythonLauncher = (Get-Command "py.exe" -ErrorAction Stop).Source
    $machinePythonPrefix = Join-Path $env:ProgramFiles `
        "WindowsApps\PythonSoftwareFoundation.Python.$($versionMatch.Groups[1].Value).$($versionMatch.Groups[2].Value)_"
    $machinePython = @(
        & $pythonLauncher -0p | ForEach-Object {
            if ($_ -match "^\s*-\S+\s+(?:\*\s+)?(?<path>.+?\.exe)\s*$") {
                $candidate = $Matches.path.Trim()
                if ($candidate.StartsWith(
                        $machinePythonPrefix,
                        [StringComparison]::OrdinalIgnoreCase
                    ) -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                    $candidate
                }
            }
        }
    ) | Select-Object -First 1
    if (-not $machinePython) {
        throw "No se encontró Python $($versionMatch.Groups[1].Value).$($versionMatch.Groups[2].Value) accesible desde SYSTEM."
    }
    $priorPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $PythonSitePackages
        & $machinePython -c "import flask, sqlalchemy, waitress"
        if ($LASTEXITCODE -ne 0) {
            throw "El Python del sistema no puede importar Flask, SQLAlchemy y Waitress desde .venv."
        }
    }
    finally {
        $env:PYTHONPATH = $priorPythonPath
    }
    $pythonPathFile = Join-Path $PSScriptRoot ".nexus-python-exe"
    [System.IO.File]::WriteAllText(
        $pythonPathFile,
        $machinePython,
        (New-Object System.Text.UTF8Encoding($false))
    )
    $pythonSitePathFile = Join-Path $PSScriptRoot ".nexus-python-site"
    [System.IO.File]::WriteAllText(
        $pythonSitePathFile,
        $PythonSitePackages,
        (New-Object System.Text.UTF8Encoding($false))
    )
}
$currentTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($currentTask -and $currentTask.State -eq "Running") {
    Stop-ScheduledTask -TaskName $taskName
    $stopDeadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
        $currentTask = Get-ScheduledTask -TaskName $taskName
    } while ($currentTask.State -eq "Running" -and (Get-Date) -lt $stopDeadline)
    if ($currentTask.State -eq "Running") {
        throw "No se pudo detener la tarea '$taskName' antes de actualizarla."
    }
}
$action = New-ScheduledTaskAction `
    -Execute (Join-Path $PSHOME "powershell.exe") `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\nexus-siempre-activo.ps1`""
$trigger = if ($RunAtSystemStartup) {
    New-ScheduledTaskTrigger -AtStartup
}
else {
    New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
}
$principal = if ($RunAtSystemStartup) {
    New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}
else {
    New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType S4U -RunLevel Limited
}
$logonMode = if ($RunAtSystemStartup) { "SYSTEM boot" } else { "S4U" }
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

if (-not (Test-Path -LiteralPath $startupDirectory)) {
    throw "La carpeta de inicio de sesión no está disponible: $startupDirectory"
}

$taskUserSid = ([Security.Principal.NTAccount]::new($TaskUser)).Translate(
    [Security.Principal.SecurityIdentifier]
).Value
$userProfileKey = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$taskUserSid"
$taskUserProfile = if (Test-Path -LiteralPath $userProfileKey) {
    [Environment]::ExpandEnvironmentVariables(
        (Get-ItemPropertyValue -LiteralPath $userProfileKey -Name ProfileImagePath)
    )
}
$codeCandidates = @(
    $(if ($taskUserProfile) {
        Join-Path $taskUserProfile "AppData\Local\Programs\Microsoft VS Code\Code.exe"
    }),
    (Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\Code.exe"),
    (Join-Path $env:ProgramFiles "Microsoft VS Code\Code.exe"),
    (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFilesX86)) `
        "Microsoft VS Code\Code.exe")
)
$codePath = $codeCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1
if (-not $codePath) {
    throw "No se encontró VS Code para abrir automáticamente el proyecto."
}

$startupShortcut = Join-Path $startupDirectory "NEXUS-VSCode.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startupShortcut)
$shortcut.TargetPath = $codePath
$shortcut.Arguments = "--new-window `"$PSScriptRoot`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 1
$shortcut.Save()

$legacyChromeShortcut = Join-Path $startupDirectory "NEXUS-Abrir-en-Chrome.lnk"
if (Test-Path -LiteralPath $legacyChromeShortcut) {
    Remove-Item -LiteralPath $legacyChromeShortcut
}
$guardianStartupShortcut = Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk"
if (Test-Path -LiteralPath $guardianStartupShortcut) {
    Remove-Item -LiteralPath $guardianStartupShortcut
}

try {
    $description = if ($RunAtSystemStartup) {
        "Inicia y supervisa la API y el sitio HTTPS de NEXUS aun sin sesión interactiva."
    }
    else {
        "Supervisa la API y el sitio HTTPS de NEXUS."
    }
    Register-ScheduledTask -TaskName $taskName `
        -Description $description `
        -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force |
        Out-Null
}
catch {
    $accessDenied = $_.FullyQualifiedErrorId -match "0x80070005" -or
        $_.Exception.Message -match "Acceso denegado|Access is denied"
    if (-not $accessDenied) {
        throw
    }

    if ($RunAtSystemStartup) {
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
            Start-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        }
        throw
    }
    $principal = New-ScheduledTaskPrincipal `
        -UserId $TaskUser -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName `
        -Description "Supervisa NEXUS mientras la sesión de Windows está abierta." `
        -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force |
        Out-Null
    $logonMode = "Interactive"
    Write-Warning "Windows rechazó el inicio S4U. La tarea interactiva inicia NEXUS al iniciar sesión, pero Windows la detendrá al cerrar sesión."
}

$legacyStartupShortcut = Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk"
if ($RunAtSystemStartup -and (Test-Path -LiteralPath $legacyStartupShortcut)) {
    Remove-Item -LiteralPath $legacyStartupShortcut
}

$guardianPath = Join-Path $PSScriptRoot "nexus-siempre-activo.ps1"
$escapedGuardianPath = [regex]::Escape($guardianPath)
Get-CimInstance Win32_Process |
    Where-Object {
        $_.ProcessId -ne $PID -and
        $_.Name -match "^powershell(_ise)?\.exe$" -and
        $_.CommandLine -match $escapedGuardianPath
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-ScheduledTask -TaskName $taskName
$deadline = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Seconds 1
    $task = Get-ScheduledTask -TaskName $taskName
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
} while ($task.State -ne "Running" -and (Get-Date) -lt $deadline)

if ($task.State -ne "Running") {
    throw "La tarea '$taskName' no quedó ejecutándose. Último resultado: $($taskInfo.LastTaskResult). Revisa el Programador de tareas."
}

if ($RunAtSystemStartup -and
    ($task.Principal.UserId -notmatch "SYSTEM$" -or
     $task.Principal.LogonType -ne "ServiceAccount" -or
     $task.Triggers[0].CimClass.CimClassName -notmatch "BootTrigger")) {
    throw "La tarea se ejecuta, pero no quedó configurada como SYSTEM al iniciar Windows."
}
if (-not $RunAtSystemStartup) {
    $expectedUserSid = ([Security.Principal.NTAccount]::new($TaskUser)).Translate(
        [Security.Principal.SecurityIdentifier]
    ).Value
    $actualUserSid = ([Security.Principal.NTAccount]::new($task.Principal.UserId)).Translate(
        [Security.Principal.SecurityIdentifier]
    ).Value
    if ($task.Principal.LogonType -notin @("S4U", "Interactive") -or
        $task.Triggers[0].CimClass.CimClassName -notmatch "LogonTrigger" -or
        $actualUserSid -ne $expectedUserSid) {
        throw "La tarea no quedó configurada para iniciar la API con la cuenta local del usuario al iniciar sesión."
    }
}
if ($RunAtSystemStartup) {
    $apiHealthUrl = "http://127.0.0.1:5000/api/health"
    $apiDeadline = (Get-Date).AddSeconds(45)
    $apiReady = $false
    while ((Get-Date) -lt $apiDeadline) {
        try {
            $response = Invoke-RestMethod -Uri $apiHealthUrl `
                -TimeoutSec 3 -ErrorAction Stop
            if ($response.status -eq "ok") {
                $apiReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $apiReady) {
        $serverErrorLog = Join-Path $PSScriptRoot "nexus-server-error.log"
        $detail = if (Test-Path -LiteralPath $serverErrorLog -PathType Leaf) {
            (Get-Content -LiteralPath $serverErrorLog -Tail 10) -join "`n"
        }
        else {
            "Revisa nexus-guardian.log para obtener detalles."
        }
        throw "La API no respondió correctamente después de iniciar el supervisor SYSTEM. $detail"
    }

    $siteHealthUrl = "https://localhost:5500/api/health"
    $siteCertificate = Join-Path $PSScriptRoot "certs\localhost.crt"
    if (-not (Test-Path -LiteralPath $siteCertificate -PathType Leaf)) {
        throw "No se encontró el certificado local para verificar el sitio HTTPS: $siteCertificate"
    }
    $curlPath = Join-Path $env:SystemRoot "System32\curl.exe"
    if (-not (Test-Path -LiteralPath $curlPath -PathType Leaf)) {
        throw "No se encontró curl.exe para verificar el sitio HTTPS local."
    }
    $siteDeadline = (Get-Date).AddSeconds(45)
    $siteReady = $false
    while ((Get-Date) -lt $siteDeadline) {
        $siteStatus = & $curlPath --cacert $siteCertificate --silent `
            --show-error --max-time 5 --output NUL --write-out "%{http_code}" `
            $siteHealthUrl 2>$null
        if ($LASTEXITCODE -eq 0 -and $siteStatus -eq "200") {
            $siteReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $siteReady) {
        throw "El sitio HTTPS local no respondió con HTTP 200 después de iniciar el supervisor SYSTEM."
    }

    $userTaskName = "NEXUS-SiempreActivo-Usuario"
    $userTask = Get-ScheduledTask -TaskName $userTaskName -ErrorAction SilentlyContinue
    if ($userTask) {
        if ($userTask.State -eq "Running") {
            Stop-ScheduledTask -TaskName $userTaskName
        }
        Disable-ScheduledTask -TaskName $userTaskName | Out-Null
    }
}

$task | Select-Object TaskName, State, TaskPath, Description
Write-Output "Modo de inicio registrado: $logonMode"
if ($logonMode -eq "Interactive") {
    Write-Warning "La persistencia después de cerrar sesión requiere que un administrador habilite el inicio S4U para esta cuenta."
}
Write-Output "Acceso directo de VS Code al iniciar sesión: $startupShortcut"

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
    $pythonPathFile = Join-Path $PSScriptRoot ".nexus-python-exe"
    $storedPythonPath = Get-Content $pythonPathFile -Raw -ErrorAction SilentlyContinue
    $pythonExecutable = if ($storedPythonPath) { $storedPythonPath.Trim() }
    else { $null }
    if (-not $pythonExecutable -or
        -not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
        $pythonProcesses = @(Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and $_.CommandLine -match "server\.py" -and
            $_.CommandLine -match [regex]::Escape($PSScriptRoot)
        })
        if ($pythonProcesses.Count -ne 1 -or
            -not (Test-Path -LiteralPath $pythonProcesses[0].ExecutablePath -PathType Leaf)) {
            throw "No se pudo identificar una única instalación activa de Python ejecutando la API NEXUS."
        }
        $pythonExecutable = $pythonProcesses[0].ExecutablePath
        [System.IO.File]::WriteAllText(
            $pythonPathFile,
            $pythonExecutable,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    if (-not $PythonSitePackages -or
        -not (Test-Path -LiteralPath $PythonSitePackages -PathType Container)) {
        throw "La carpeta site-packages de Python de $TaskUser no está disponible."
    }
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

$task | Select-Object TaskName, State, TaskPath, Description
Write-Output "Modo de inicio registrado: $logonMode"
if ($logonMode -eq "Interactive") {
    Write-Warning "La persistencia después de cerrar sesión requiere que un administrador habilite el inicio S4U para esta cuenta."
}
Write-Output "Acceso directo de VS Code al iniciar sesión: $startupShortcut"

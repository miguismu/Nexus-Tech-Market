param(
    [string]$TaskUser,
    [string]$StartupDirectory
)

$ErrorActionPreference = "Stop"
$taskName = "NEXUS-SiempreActivo"
if (-not $TaskUser) {
    $TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
}
if (-not $StartupDirectory) {
    $StartupDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
}
$action = New-ScheduledTaskAction `
    -Execute (Join-Path $PSHOME "powershell.exe") `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\nexus-siempre-activo.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
$principal = New-ScheduledTaskPrincipal `
    -UserId $TaskUser -LogonType S4U -RunLevel Limited
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

$startupShortcut = Join-Path $startupDirectory "NEXUS-Abrir-en-Chrome.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startupShortcut)
$shortcut.TargetPath = Join-Path $PSHOME "powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\abrir-nexus-chrome.ps1`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Save()

$guardianStartupShortcut = Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk"
$guardianShortcut = $shell.CreateShortcut($guardianStartupShortcut)
$guardianShortcut.TargetPath = Join-Path $PSHOME "powershell.exe"
$guardianShortcut.Arguments = $action.Arguments
$guardianShortcut.WorkingDirectory = $PSScriptRoot
$guardianShortcut.WindowStyle = 7
$guardianShortcut.Save()

Register-ScheduledTask -TaskName $taskName `
    -Description "Supervisa la API y el sitio HTTPS de NEXUS aun después de cerrar sesión." `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force |
    Out-Null

$legacyStartupShortcut = Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk"
if (Test-Path -LiteralPath $legacyStartupShortcut) {
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

$task | Select-Object TaskName, State, TaskPath, Description
Write-Output "Inicio de sesión desatendido (S4U): $($task.Principal.LogonType)"
Write-Output "Acceso directo de Chrome al iniciar sesión: $startupShortcut"

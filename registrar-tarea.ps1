$ErrorActionPreference = "Stop"
$taskName = "NEXUS-SiempreActivo"
$taskFile = Join-Path $PSScriptRoot "NEXUS-task.xml"
$taskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\nexus-siempre-activo.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$principal = New-ScheduledTaskPrincipal `
    -UserId $taskUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
}
catch {
    if ($_.FullyQualifiedErrorId -notmatch "0x80070005" -and
        $_.Exception.Message -notmatch "Acceso denegado|Access is denied") {
        throw
    }

    $startupDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
    if (-not (Test-Path -LiteralPath $startupDirectory)) {
        throw "Windows rechazó el registro de la tarea y la carpeta de inicio no está disponible."
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut(
        (Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk")
    )
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = $action.Arguments
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    Start-Process -FilePath "powershell.exe" `
        -ArgumentList $action.Arguments `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden | Out-Null
    Write-Warning "Windows denegó el registro de tareas. Se configuró el inicio automático solo para tu usuario y se inició el guardián."
    Write-Output "Acceso directo de inicio: $(Join-Path $startupDirectory 'NEXUS-SiempreActivo.lnk')"
    exit 0
}

$taskXml = Export-ScheduledTask -TaskName $taskName
[System.IO.File]::WriteAllText($taskFile, $taskXml, [System.Text.Encoding]::Unicode)
$startupDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
$startupShortcut = Join-Path $startupDirectory "NEXUS-SiempreActivo.lnk"
if (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut
}
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
Get-ScheduledTask -TaskName $taskName |
    Select-Object TaskName, State, TaskPath, Description

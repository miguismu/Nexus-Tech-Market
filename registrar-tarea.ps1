$logFile = "$PSScriptRoot\tarea-resultado.txt"
"Intento $(Get-Date)" | Out-File $logFile -Encoding utf8
schtasks /create /tn NEXUS-SiempreActivo /xml "$PSScriptRoot\NEXUS-task.xml" /f 2>&1 | Out-File $logFile -Append -Encoding utf8
schtasks /query /tn NEXUS-SiempreActivo 2>&1 | Out-File $logFile -Append -Encoding utf8

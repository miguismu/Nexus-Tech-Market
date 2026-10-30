# NEXUS Tech Market - Guardian de actividad permanente
# Miguel Alejandro Munoz Suarez - Politecnico Superior de Occidente
# Verifica cada 60 segundos que el servidor este activo; si no, lo reinicia.
# Registrar como tarea programada al inicio de sesion.

$root = "C:\Users\Miguel Alejandro MS\Desktop\Proyecto Final - Area - Desarrollo Web -  Institución - Politecnico Superior de Occidente - Estudiante - Miguel Muñoz"
$watchLog = Join-Path $root "nexus-guardian.log"

function Write-Log([string]$msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Out-File -FilePath $watchLog -Append -Encoding utf8
}

function Test-Server {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5000/api/health" -UseBasicParsing -TimeoutSec 10
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

Write-Log "Guardian NEXUS iniciado."

while ($true) {
    if (-not (Test-Server)) {
        Write-Log "Servidor no responde. Reiniciando..."
        Start-Process -FilePath "py.exe" -ArgumentList "iniciar_nexus.py" -WorkingDirectory $root -WindowStyle Hidden
        Start-Sleep -Seconds 15
        if (Test-Server) {
            Write-Log "Servidor reiniciado y activo en http://localhost:5000"
        } else {
            Write-Log "ALERTA: reinicio fallido. Se reintentara en el siguiente ciclo."
        }
    }
    Start-Sleep -Seconds 60
}

$ErrorActionPreference = "Stop"
$client = [System.Net.Sockets.TcpClient]::new()
$connection = $null
$listener = $false

try {
    $connection = $client.BeginConnect("127.0.0.1", 5500, $null, $null)
    $listener = $connection.AsyncWaitHandle.WaitOne(1000)
    if ($listener) {
        $client.EndConnect($connection)
    }
}
catch {
    $listener = $false
}
finally {
    if ($connection) {
        $connection.AsyncWaitHandle.Close()
    }
    $client.Dispose()
}

if ($listener) {
    Write-Output "Now listening on: https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500"
    exit 0
}

dotnet run --no-launch-profile --project "$PSScriptRoot\secure-host\NexusHttpsHost.csproj"
exit $LASTEXITCODE

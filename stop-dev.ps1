param(
    [string[]]$Ports = @("8000", "3000"),
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSCommandPath
$RuntimeDir = Join-Path $RootDir ".dev"
$ProcessFile = Join-Path $RuntimeDir "processes.json"

function Resolve-PortList {
    param([string[]]$Values)

    $resolved = foreach ($value in $Values) {
        foreach ($part in ($value -split ",")) {
            $trimmed = $part.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed)) {
                continue
            }

            $port = 0
            if (-not [int]::TryParse($trimmed, [ref]$port)) {
                throw "Invalid port value: $trimmed"
            }

            $port
        }
    }

    return @($resolved | Select-Object -Unique)
}

function Get-ProcessTreeIds {
    param([int]$ProcessId)

    $ids = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($ProcessId)

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if ($ids.Contains($current)) {
            continue
        }

        $ids.Add($current)
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $current" -ErrorAction SilentlyContinue |
            ForEach-Object { $queue.Enqueue([int]$_.ProcessId) }
    }

    return $ids
}

function Stop-ProcessTree {
    param(
        [int]$ProcessId,
        [string]$Label
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return
    }

    $treeIds = @(Get-ProcessTreeIds -ProcessId $ProcessId)
    [array]::Reverse($treeIds)

    foreach ($id in $treeIds) {
        $target = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $target) {
            continue
        }

        if ($DryRun) {
            Write-Host "Would stop $Label process $id ($($target.ProcessName))"
            continue
        }

        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped $Label process $id ($($target.ProcessName))"
    }
}

function Stop-ListenersOnPorts {
    param([int[]]$TargetPorts)

    foreach ($port in $TargetPorts) {
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            Stop-ProcessTree -ProcessId $connection.OwningProcess -Label "port $port"
        }
    }
}

$trackedPids = New-Object System.Collections.Generic.HashSet[int]
$TargetPorts = Resolve-PortList -Values $Ports

if (Test-Path -LiteralPath $ProcessFile) {
    $state = Get-Content -Raw -LiteralPath $ProcessFile | ConvertFrom-Json

    foreach ($name in @("backend", "frontend")) {
        $entry = $state.$name
        if ($entry -and $entry.pid) {
            $trackedProcessId = [int]$entry.pid
            if ($trackedPids.Add($trackedProcessId)) {
                Stop-ProcessTree -ProcessId $trackedProcessId -Label $name
            }
        }
    }
}

Stop-ListenersOnPorts -TargetPorts $TargetPorts

if ((Test-Path -LiteralPath $ProcessFile) -and -not $DryRun) {
    Remove-Item -LiteralPath $ProcessFile -Force
}

Write-Host "SoulSmith dev servers stopped."

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$SkipInstall,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSCommandPath
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendVenv = Join-Path $BackendDir ".venv"
$BackendPython = Join-Path $BackendVenv "Scripts\python.exe"

function Resolve-RequiredCommand {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' was not found in PATH."
    }

    return $command.Source
}

function ConvertTo-QuotedPath {
    param([string]$Path)

    return "'" + $Path.Replace("'", "''") + "'"
}

function Assert-PortAvailable {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($connection) {
        throw "Port $Port is already in use by process $($connection.OwningProcess). Stop it or pass another port."
    }
}

function Invoke-InDirectory {
    param(
        [string]$Path,
        [scriptblock]$Command
    )

    Push-Location $Path
    try {
        & $Command
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}

if (-not (Test-Path $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

$Npm = Resolve-RequiredCommand "npm.cmd"
$PowerShell = Resolve-RequiredCommand "powershell.exe"

Assert-PortAvailable $BackendPort
Assert-PortAvailable $FrontendPort

if (-not $SkipInstall) {
    if (-not (Test-Path $BackendPython)) {
        $Python = Resolve-RequiredCommand "python.exe"
        Write-Host "Creating backend virtual environment..."
        & $Python -m venv $BackendVenv
        & $BackendPython -m pip install --upgrade pip
        & $BackendPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
    }

    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Invoke-InDirectory $FrontendDir { & $Npm install }
    }
}

if (-not (Test-Path $BackendPython)) {
    throw "Backend Python was not found. Run without -SkipInstall first."
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    throw "Frontend dependencies were not found. Run without -SkipInstall first."
}

$BackendCommand = @(
    "`$Host.UI.RawUI.WindowTitle = 'SoulSmith Backend'",
    "Set-Location -LiteralPath $(ConvertTo-QuotedPath $BackendDir)",
    "& $(ConvertTo-QuotedPath $BackendPython) -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort"
) -join "; "

$FrontendCommand = @(
    "`$Host.UI.RawUI.WindowTitle = 'SoulSmith Frontend'",
    "Set-Location -LiteralPath $(ConvertTo-QuotedPath $FrontendDir)",
    "& $(ConvertTo-QuotedPath $Npm) run dev -- --hostname 127.0.0.1 --port $FrontendPort"
) -join "; "

Write-Host ""
Write-Host "SoulSmith AI dev environment"
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host ""

if ($DryRun) {
    Write-Host "Dry run completed. No processes were started."
    exit 0
}

Start-Process -FilePath $PowerShell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand) -WindowStyle Normal
Start-Process -FilePath $PowerShell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand) -WindowStyle Normal

Write-Host "Started backend and frontend in separate PowerShell windows."
Write-Host "Close those windows or press Ctrl+C inside them to stop the servers."

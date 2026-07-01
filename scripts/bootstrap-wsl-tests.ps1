param(
    [string]$Distro = 'Ubuntu-24.04',
    [switch]$RecreateVenv,
    [switch]$InteractiveSudo
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Convert-WindowsPathToWsl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path $Path).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $rest = $Matches[2] -replace '\\', '/'
        return "/mnt/$drive/$rest"
    }

    throw "Unsupported Windows path format: $resolved"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$projectRootWsl = Convert-WindowsPathToWsl -Path $projectRoot
$wslExe = Join-Path $env:WINDIR 'System32\wsl.exe'

$distroListRaw = & $wslExe -l -q
$distroList = @($distroListRaw | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })

if (-not $distroList) {
    throw 'No WSL distributions found. Install Ubuntu 24.04 first.'
}

if ($distroList -notcontains $Distro) {
    throw (
        "Required distro '$Distro' not found. Available distros: " +
        ($distroList -join ', ')
    )
}

$recreateFlag = if ($RecreateVenv) { '1' } else { '0' }
$interactiveSudoFlag = if ($InteractiveSudo) { '1' } else { '0' }

$bashScript = @'
set -euo pipefail

project_root="$1"
recreate_venv="$2"
interactive_sudo="$3"

cd "$project_root"

command -v python3 >/dev/null 2>&1 || {
    echo "python3 is not installed in WSL distro" >&2
    exit 2
}

install_python3_venv() {
    echo "Attempting to install python3-venv..." >&2

    if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n apt-get update
        sudo -n apt-get install -y python3-venv
        return 0
    fi

    if [ "$interactive_sudo" = "1" ] && command -v sudo >/dev/null 2>&1; then
        echo "Non-interactive sudo unavailable. Falling back to interactive sudo..." >&2
        sudo apt-get update
        sudo apt-get install -y python3-venv
        return 0
    fi

    echo "Cannot install python3-venv automatically (sudo requires interactive password)." >&2
    echo "Re-run from Windows with interactive sudo enabled:" >&2
    echo "  .\\scripts\\bootstrap-wsl-tests.ps1 -Distro Ubuntu-24.04 -InteractiveSudo" >&2
    echo "Run in WSL terminal:" >&2
    echo "  sudo apt-get update" >&2
    echo "  sudo apt-get install -y python3-venv" >&2
    return 1
}

if [ "$recreate_venv" = "1" ]; then
    rm -rf .venv
fi

if [ -d .venv ] && ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "Existing .venv is incomplete (pip missing). Recreating..." >&2
    rm -rf .venv
fi

if [ ! -d .venv ]; then
    if ! python3 -m venv .venv; then
        rm -rf .venv
        if install_python3_venv; then
            python3 -m venv .venv
        else
            exit 2
        fi
    fi
fi

if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    rm -rf .venv
    if install_python3_venv; then
        python3 -m venv .venv
    else
        exit 2
    fi
fi

if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "Virtual environment is missing pip after setup attempts." >&2
    exit 2
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

date -Iseconds > .wsl-bootstrap.ok
'@

Write-Host 'Bootstrapping WSL test environment'
Write-Host "Distro: $Distro"
Write-Host "Project path: $projectRootWsl"
Write-Host "Recreate venv: $RecreateVenv"
Write-Host "Interactive sudo: $InteractiveSudo"

$tempScript = Join-Path $env:TEMP ("brodsky-bootstrap-wsl-{0}.sh" -f $PID)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempScript, ($bashScript -replace "`r`n", "`n"), $utf8NoBom)

try {
    $tempScriptWsl = Convert-WindowsPathToWsl -Path $tempScript
    $wslArgs = @(
        '-d', $Distro,
        '--',
        'bash',
        $tempScriptWsl,
        $projectRootWsl,
        $recreateFlag,
        $interactiveSudoFlag
    )

    & $wslExe @wslArgs
    exit $LASTEXITCODE
}
finally {
    Remove-Item $tempScript -ErrorAction SilentlyContinue
}

param(
    [ValidateSet('fast', 'integration', 'smoke')]
    [string]$Suite = 'fast',

    [string]$EnvFile = '.env.test',

    [string]$Distro = 'Ubuntu-24.04',

    [switch]$AllowProdSmoke,

    [string[]]$PytestArgs
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

switch ($Suite) {
    'fast' {
        $runLiveSmoke = '0'
        $allowProdSmokeValue = ''
        $defaultPytestArgs = @('tests', '--ignore', 'tests/test_smoke_live.py', '-q')
    }
    'integration' {
        $runLiveSmoke = '0'
        $allowProdSmokeValue = ''
        $defaultPytestArgs = @('tests', '-m', 'integration', '--ignore', 'tests/test_smoke_live.py', '-q')
    }
    'smoke' {
        $runLiveSmoke = '1'
        $allowProdSmokeValue = if ($AllowProdSmoke) { '1' } else { '' }
        $defaultPytestArgs = @('tests/test_smoke_live.py', '-s')
    }
    default {
        throw "Unsupported suite: $Suite"
    }
}

$finalPytestArgs = @() + $defaultPytestArgs
if ($PytestArgs) {
    $finalPytestArgs += $PytestArgs
}

Write-Host "Running suite in WSL: $Suite"
Write-Host "Distro: $Distro"
Write-Host "Project path: $projectRootWsl"
Write-Host "ENV_FILE: $EnvFile"
if ($Suite -eq 'smoke') {
    Write-Host "RUN_LIVE_SMOKE: $runLiveSmoke"
    Write-Host "ALLOW_PROD_SMOKE: $allowProdSmokeValue"
}

$wslArgs = @(
    '-d', $Distro,
    '--cd', $projectRootWsl,
    '--',
    'env',
    "ENV_FILE=$EnvFile",
    "RUN_LIVE_SMOKE=$runLiveSmoke",
    "PYTEST_ADDOPTS=",
    $(if ($allowProdSmokeValue) { "ALLOW_PROD_SMOKE=$allowProdSmokeValue" } else { "ALLOW_PROD_SMOKE=" }),
    "$projectRootWsl/.venv/bin/python",
    '-m',
    'pytest',
    '-c',
    "$projectRootWsl/pytest.ini"
) + $finalPytestArgs

& $wslExe @wslArgs
exit $LASTEXITCODE

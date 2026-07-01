param(
    [ValidateSet('fast', 'integration', 'smoke')]
    [string]$Suite = 'fast',

    [string]$EnvFile = '.env.test',

    [switch]$AllowProdSmoke,

    [string[]]$PytestArgs
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Push-Location $projectRoot
try {
    $venvPython = Join-Path $projectRoot 'venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $python = $venvPython
    } else {
        $python = 'python'
    }

    $env:ENV_FILE = $EnvFile

    switch ($Suite) {
        'fast' {
            $env:RUN_LIVE_SMOKE = '0'
            Remove-Item Env:ALLOW_PROD_SMOKE -ErrorAction SilentlyContinue
            $marker = 'not smoke'
            $defaultPytestArgs = @('-q')
        }
        'integration' {
            $env:RUN_LIVE_SMOKE = '0'
            Remove-Item Env:ALLOW_PROD_SMOKE -ErrorAction SilentlyContinue
            $marker = 'integration and not smoke'
            $defaultPytestArgs = @('-q')
        }
        'smoke' {
            $env:RUN_LIVE_SMOKE = '1'
            if ($AllowProdSmoke) {
                $env:ALLOW_PROD_SMOKE = '1'
            } else {
                Remove-Item Env:ALLOW_PROD_SMOKE -ErrorAction SilentlyContinue
            }
            $marker = 'smoke'
            $defaultPytestArgs = @('-s')
        }
        default {
            throw "Unsupported suite: $Suite"
        }
    }

    $finalPytestArgs = @('-m', $marker) + $defaultPytestArgs
    if ($PytestArgs) {
        $finalPytestArgs += $PytestArgs
    }

    Write-Host "Running suite: $Suite"
    Write-Host "ENV_FILE: $EnvFile"
    if ($Suite -eq 'smoke') {
        Write-Host "RUN_LIVE_SMOKE: $($env:RUN_LIVE_SMOKE)"
        Write-Host "ALLOW_PROD_SMOKE: $($env:ALLOW_PROD_SMOKE)"
    }

    & $python -m pytest @finalPytestArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

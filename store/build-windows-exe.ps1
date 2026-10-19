# Windows source -> private, immutable EXE candidate. No branch reset or workspace cleanup.
[CmdletBinding()]
param([string]$PythonLauncher = 'py')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Source = Join-Path $Root 'app.py'
if (-not (Test-Path -LiteralPath $Source)) { throw 'GUI app.py missing.' }
if (git -C $Root status --porcelain) { throw 'Source tree is dirty; do not build from uncommitted code.' }
$Head = (git -C $Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Head.Length -ne 40) { throw 'Cannot identify clean git source SHA.' }
$Branch = (git -C $Root branch --show-current).Trim()
if ($Branch -ne 'ui/simple-schema-key-picker-20261019') {
    throw "Unexpected branch: $Branch. Do not build another product revision."
}
$Output = Join-Path $Root ('dist-candidate-' + $Head.Substring(0,12))
if (Test-Path -LiteralPath $Output) { throw 'Candidate already exists; cannot overwrite it.' }
$Isolation = Join-Path $env:TEMP ('schema-audit-build-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $Isolation | Out-Null
    $Venv = Join-Path $Isolation 'venv'
    & $PythonLauncher -3.12 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 creation failed.' }
    $Py = Join-Path $Venv 'Scripts\python.exe'
    & $Py -m pip install -r (Join-Path $Root 'requirements.txt') 'pyinstaller>=6,<7'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed.' }
    Push-Location $Root
    try {
        & $Py -m compileall -q app.py audit_review_gate.py contract_auditor.py gui_schema_columns.py validator.py tests
        if ($LASTEXITCODE -ne 0) { throw 'Source syntax failed.' }
        & $Py -m unittest discover -s tests -p 'test*.py' -v
        if ($LASTEXITCODE -ne 0) { throw 'Unit regression failed; package blocked.' }
        & $Py -m PyInstaller --noconfirm --clean --onefile --windowed --name DataContractAuditor --collect-all pandas --collect-all openpyxl --distpath $Output --workpath (Join-Path $Isolation 'work') --specpath (Join-Path $Isolation 'spec') app.py
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller EXE build failed.' }
    } finally { Pop-Location }
    $Exe = Join-Path $Output 'DataContractAuditor.exe'
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'Candidate EXE missing.' }
    Write-Host "QA CANDIDATE ONLY / SOURCE SHA $Head / EXE $(Get-FileHash -LiteralPath $Exe -Algorithm SHA256 | Select-Object -ExpandProperty Hash)"
    Write-Host "PATH: $Exe"
    Write-Host 'Requires real GUI acceptance, package Identity, MSIX install and Store validation.'
} finally {
    if (Test-Path -LiteralPath $Isolation) { Remove-Item -LiteralPath $Isolation -Recurse -Force }
}

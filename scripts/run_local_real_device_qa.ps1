#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$EvidenceRoot = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

function GitText([string[]]$Args) {
    $Out = & git @Args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') failed: $Out" }
    return ($Out | Out-String).Trim()
}

$ExpectedBranch = "codex/store-p0-data-contract-20261023"
$Branch = GitText @("branch","--show-current")
if ($Branch -cne $ExpectedBranch) { throw "Wrong branch: $Branch" }

GitText @("fetch","origin") | Out-Null
$Head = GitText @("rev-parse","HEAD")
$RemoteHead = GitText @("rev-parse",("origin/" + $ExpectedBranch))
if ($Head -cne $RemoteHead) { throw "Local HEAD is not the current remote branch HEAD." }

$Dirty = GitText @("status","--porcelain","--untracked-files=all")
if (-not [string]::IsNullOrWhiteSpace($Dirty)) {
    throw "Working tree must be clean before QA. Dirty state: $Dirty"
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $Candidate = Join-Path $Root ".venv-qa\Scripts\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $Candidate) { $Candidate } else { "python" }
}

if ([string]::IsNullOrWhiteSpace($EvidenceRoot)) {
    $Base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $EvidenceRoot = Join-Path $Base ("OkinawaDesktopTools\DataContractAuditor\qa-evidence\" + $Stamp + "-" + $Head.Substring(0,12))
}
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null

& $PythonExe -m unittest discover -s tests -p "test*.py" -v
if ($LASTEXITCODE -ne 0) { throw "UNIT_TESTS_FAILED" }

& $PythonExe (Join-Path $PSScriptRoot "local_real_device_qa.py") --evidence-dir $EvidenceRoot
if ($LASTEXITCODE -ne 0) { throw "LOCAL_REAL_DEVICE_QA_FAILED" }

Write-Host ""
Write-Host "DATA_CONTRACT_AUTOMATED_LOCAL_QA=PASS"
Write-Host "SOURCE_SHA=$Head"
Write-Host "EVIDENCE_ROOT=$EvidenceRoot"
Write-Host "HUMAN_VISUAL_SPOT_CHECK=REMAINS"
Write-Host "STORE_UPLOAD_AUTHORIZED=FALSE"

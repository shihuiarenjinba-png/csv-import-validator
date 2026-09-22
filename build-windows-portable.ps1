param(
    [string]$ProductName = "DataContractSchemaDriftAuditor",
    [string]$ZipName = "Data-Contract-Schema-Drift-Auditor-Windows-Portable-RC.zip"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$BuildRoot = Join-Path $Root ".rc-build"
$Venv = Join-Path $BuildRoot "venv"
$StageRoot = Join-Path $BuildRoot "stage"
$PackageRoot = Join-Path $StageRoot $ProductName
$Artifacts = Join-Path $Root "artifacts"
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Assert-NoCredentialMaterial {
    $excluded = @(".git", ".venv", ".rc-build", "dist", "build", "artifacts", "__pycache__")
    $extensions = @(".py", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".md", ".ps1", ".cmd")
    $patterns = @(
        'AIza[0-9A-Za-z_\-]{25,}',
        '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
        '"private_key"\s*:\s*"',
        '"client_secret"\s*:\s*"[^"$]',
        '"refresh_token"\s*:\s*"[^"$]'
    )

    $files = Get-ChildItem -Path $Root -Recurse -File | Where-Object {
        $full = $_.FullName
        $blocked = $false
        foreach ($name in $excluded) {
            $needle = [IO.Path]::DirectorySeparatorChar + $name + [IO.Path]::DirectorySeparatorChar
            if ($full.Contains($needle)) { $blocked = $true; break }
        }
        (-not $blocked) -and ($extensions -contains $_.Extension.ToLowerInvariant())
    }

    foreach ($file in $files) {
        $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $text) { continue }
        foreach ($pattern in $patterns) {
            if ($text -match $pattern) {
                throw "Potential credential material detected in $($file.FullName). RC build stopped."
            }
        }
    }
}

Write-Host "== RC preflight =="
Assert-NoCredentialMaterial

Remove-IfExists $BuildRoot
Remove-IfExists $Dist
Remove-IfExists $Build
Remove-IfExists $Artifacts
New-Item -ItemType Directory -Path $BuildRoot, $Artifacts | Out-Null

Write-Host "== Python environment =="
py -3.12 -m venv $Venv
$Python = Join-Path $Venv "Scripts\python.exe"

& $Python -m pip install --upgrade pip
if (Test-Path (Join-Path $Root "requirements.txt")) {
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}

Write-Host "== Source tests =="
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "Source tests failed."
}

Write-Host "== Runtime dependency lock snapshot =="
& $Python -m pip freeze | Set-Content -LiteralPath (Join-Path $BuildRoot "runtime-requirements-lock.txt") -Encoding UTF8

Write-Host "== PyInstaller build =="
& $Python -m pip install "pyinstaller>=6,<7"
$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", $ProductName,
    (Join-Path $Root "app.py")
)
& $Python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$Exe = Join-Path $Dist "$ProductName\$ProductName.exe"
if (-not (Test-Path $Exe)) {
    throw "Built executable was not found: $Exe"
}

Write-Host "== Packaged executable smoke test =="
$Process = Start-Process -FilePath $Exe -PassThru
try {
    Start-Sleep -Seconds 5
    if ($Process.HasExited) {
        throw "Packaged executable exited during startup with code $($Process.ExitCode)."
    }
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit()
    }
}

Write-Host "== RC staging =="
New-Item -ItemType Directory -Path $PackageRoot -Force | Out-Null
Copy-Item -Path (Join-Path $Dist "$ProductName\*") -Destination $PackageRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $PackageRoot -Force
if (Test-Path (Join-Path $Root "schema.example.json")) {
    Copy-Item -LiteralPath (Join-Path $Root "schema.example.json") -Destination $PackageRoot -Force
}
Copy-Item -LiteralPath (Join-Path $BuildRoot "runtime-requirements-lock.txt") -Destination $PackageRoot -Force

@"
RC CANDIDATE ONLY — NOT FOR SALE

This ZIP is an internal Windows portable release candidate.
It has passed source tests, a credential-marker scan, PyInstaller packaging,
and a packaged-process startup smoke test.

Sales/public-release blockers remain until explicitly completed:
- approved product LICENSE
- approved third-party NOTICE
- approved SBOM
- Authenticode signing and signature verification
- manual Windows acceptance testing on supported versions/display scales

Do not add OAuth client JSON, refresh tokens, API keys, or other credentials to
this package. Test credentials must remain outside the repository and ZIP.
"@ | Set-Content -LiteralPath (Join-Path $PackageRoot "RC-NOT-FOR-SALE.txt") -Encoding UTF8

Write-Host "== Final staged credential scan =="
$stagedTextFiles = Get-ChildItem -Path $PackageRoot -Recurse -File | Where-Object {
    $_.Extension.ToLowerInvariant() -in @(".txt", ".md", ".json", ".yaml", ".yml", ".ini", ".cfg")
}
foreach ($file in $stagedTextFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $text) { continue }
    if ($text -match 'AIza[0-9A-Za-z_\-]{25,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|"private_key"\s*:\s*"|"client_secret"\s*:\s*"[^"$]|"refresh_token"\s*:\s*"[^"$]') {
        throw "Potential credential material detected in staged file $($file.FullName)."
    }
}

$ZipPath = Join-Path $Artifacts $ZipName
Compress-Archive -Path $PackageRoot -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host "== Re-extract and verify =="
$VerifyRoot = Join-Path $BuildRoot "verify"
Remove-IfExists $VerifyRoot
Expand-Archive -LiteralPath $ZipPath -DestinationPath $VerifyRoot
$VerifiedExe = Join-Path $VerifyRoot "$ProductName\$ProductName.exe"
if (-not (Test-Path $VerifiedExe)) {
    throw "Re-extracted ZIP does not contain the executable."
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
"$Hash  $ZipName" | Set-Content -LiteralPath (Join-Path $Artifacts "$ZipName.sha256") -Encoding ASCII

Write-Host ""
Write-Host "RC_BUILD_PASS"
Write-Host "ZIP: $ZipPath"
Write-Host "SHA256: $Hash"

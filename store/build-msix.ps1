#requires -Version 5.1
<#
Build an unsigned MSIX candidate from canonical registration JSON only.
Never signs, installs, uploads, submits, or publishes. Missing official data blocks the build.
#>
[CmdletBinding()]
param([switch]$PreflightOnly, [string]$Version, [string]$PythonExe = "python")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ExpectedBranch = "codex/store-p0-data-contract-20261023"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ConfigPath = Join-Path $PSScriptRoot "product.json"
$RegistrationPath = Join-Path $PSScriptRoot "partner_center_registration.json"
$ValidatorPath = Join-Path $PSScriptRoot "validate_store_config.py"
$VerifierPath = Join-Path $PSScriptRoot "verify_msix_candidate.py"
foreach ($Path in @($ConfigPath,$RegistrationPath,$ValidatorPath,$VerifierPath)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required Store input is missing: $Path" }
}
function Invoke-GitText {
    param([string[]]$GitArguments)
    $Output = & git @GitArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Git command failed (exit $LASTEXITCODE): git $($GitArguments -join ' '); output: $Output" }
    return ($Output | Out-String).Trim()
}
function Write-PreflightReport {
    param([object]$Report,[string]$Directory)
    $Report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $Directory "store-preflight.json") -Encoding UTF8
    $ReadyText = if ($Report.ready) { "true" } else { "false" }
    if ($env:GITHUB_OUTPUT) {
        Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "ready=$ReadyText" -Encoding UTF8
        Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "approved_version=$([string]$Report.version_to_build)" -Encoding UTF8
    }
    if ($env:GITHUB_STEP_SUMMARY) {
        $Summary = @("# Data Contract Auditor - Store MSIX preflight","","- Readiness: **$ReadyText**","- Store ID candidate: $($Report.store_id)","- Version: $($Report.version_to_build)","- Certification: **NOT AUTHORIZED**","- Sales release: **HOLD**","","## Blockers")
        if (@($Report.blockers).Count -eq 0) { $Summary += "- None" } else { $Summary += @($Report.blockers | ForEach-Object { "- $_" }) }
        if (@($Report.warnings).Count -gt 0) { $Summary += @("","## Warnings",($Report.warnings | ForEach-Object { "- $_" })) }
        $NL = [Environment]::NewLine
        Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value ($Summary -join $NL) -Encoding UTF8
    }
    Write-Output ($Report | ConvertTo-Json -Depth 12)
}
# Verify repository, working branch, local/remote commit and clean tree before any writes.
Set-Location -LiteralPath $Root
$RemoteUrl = Invoke-GitText -GitArguments @("remote","get-url","origin")
if ($RemoteUrl -notmatch '(?i)github[.]com[:/]shihuiarenjinba-png/csv-import-validator(?:[.]git)?$') {
    throw "Wrong origin repository; no files were changed."
}
Invoke-GitText -GitArguments @("fetch","origin") | Out-Null
$Branch = Invoke-GitText -GitArguments @("branch","--show-current")
$SourceSha = Invoke-GitText -GitArguments @("rev-parse","HEAD")
$RemoteSha = Invoke-GitText -GitArguments @("rev-parse",("origin/" + $ExpectedBranch))
$DirtyState = Invoke-GitText -GitArguments @("status","--porcelain","--untracked-files=all")
if ($Branch -cne $ExpectedBranch) { throw "Wrong working branch: $Branch; expected $ExpectedBranch" }
if ($SourceSha -notmatch "^[0-9a-f]{40}$" -or $RemoteSha -cne $SourceSha) {
    throw "Local and remote HEAD must be the same full commit SHA."
}
if (-not [string]::IsNullOrWhiteSpace($DirtyState)) { throw "Uncommitted changes exist; no preflight or packaging writes allowed." }

$ExtraBlockers = [System.Collections.Generic.List[string]]::new()
$Stamp = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
$OutputBase = Join-Path $Root "store-output"
New-Item -ItemType Directory -Path $OutputBase -Force | Out-Null
$PreflightDir = Join-Path $OutputBase ("preflight-" + $Stamp)
New-Item -ItemType Directory -Path $PreflightDir -Force | Out-Null

$ValidationArgs = @($ValidatorPath,"--json")
if (-not [string]::IsNullOrWhiteSpace($Version)) { $ValidationArgs += @("--version",$Version) }
$Raw = & $PythonExe @ValidationArgs 2>&1
if ($LASTEXITCODE -ne 0) { throw "Store config validator failed: $Raw" }
try { $Report = ($Raw | Out-String) | ConvertFrom-Json } catch { throw "Store config validator did not return valid JSON." }
$AllBlockers = @($Report.blockers) + @($ExtraBlockers)
$Report.blockers = @($AllBlockers | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
$Report.ready = (@($Report.blockers).Count -eq 0)
if ($PreflightOnly) { Write-PreflightReport -Report $Report -Directory $PreflightDir; return }
if (-not $Report.ready) {
    Write-PreflightReport -Report $Report -Directory $PreflightDir | Out-Null
    throw ("MSIX_BUILD_BLOCKED: unresolved identity, version, artwork, source, or branch gate. " + (@($Report.blockers) -join "; "))
}

$Product = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Registration = Get-Content -LiteralPath $RegistrationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Identity = $Registration.storeIdentity
$PackageVersion = [string]$Report.version_to_build
$Tag = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
$OutputRoot = Join-Path $OutputBase $Tag
if (Test-Path -LiteralPath $OutputRoot) { throw "Refusing to overwrite existing output directory: $OutputRoot" }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$ScratchBase = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } elseif ($env:TEMP) { $env:TEMP } else { [IO.Path]::GetTempPath() }
$Scratch = Join-Path $ScratchBase ("dca-msix-" + $Tag)
$Venv = Join-Path $Scratch "venv"
$Dist = Join-Path $Scratch "dist"
$Work = Join-Path $Scratch "work"
$Spec = Join-Path $Scratch "spec"
$Stage = Join-Path $Scratch "stage"
$Unpacked = Join-Path $Scratch "unpacked"
New-Item -ItemType Directory -Path $Scratch,$Dist,$Work,$Spec,$Stage,$Unpacked -Force | Out-Null
$StageApp = Join-Path $Stage "App"
$StageAssets = Join-Path $Stage "Assets"
New-Item -ItemType Directory -Path $StageApp,$StageAssets -Force | Out-Null

& $PythonExe -m venv $Venv
if ($LASTEXITCODE -ne 0) { throw "Could not create isolated Python environment." }
$BuildPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $BuildPython)) { throw "Python virtual environment executable is missing." }
& $BuildPython -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $BuildPython -m pip install "pyinstaller==6.16.0"
if ($LASTEXITCODE -ne 0) { throw "Pinned PyInstaller installation failed." }
& $BuildPython -m unittest discover -s tests -p "test*.py" -v
if ($LASTEXITCODE -ne 0) { throw "Source unit tests failed; MSIX generation stopped." }
& $BuildPython -m compileall -q app.py contract_auditor.py validator.py tests store
if ($LASTEXITCODE -ne 0) { throw "Python compileall failed." }

$PyInstallerArgs = @("-m","PyInstaller","--clean","--noconfirm","--windowed","--onedir","--name",[string]$Product.exeName,"--distpath",$Dist,"--workpath",$Work,"--specpath",$Spec,"--collect-all","numpy","--collect-all","pandas","--collect-all","openpyxl",[string]$Product.entryPoint)
& $BuildPython @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
$BuiltAppDirectory = Join-Path $Dist ([string]$Product.exeName)
$BuiltExe = Join-Path $BuiltAppDirectory ([string]$Product.exeName + ".exe")
if (-not (Test-Path -LiteralPath $BuiltExe -PathType Leaf)) { throw "Generated EXE is missing: $BuiltExe" }
Get-ChildItem -LiteralPath $BuiltAppDirectory | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $StageApp -Recurse -Force }
foreach ($LogoName in @("StoreLogo.png","Square44x44Logo.png","Square150x150Logo.png","Wide310x150Logo.png")) {
    Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot "assets") $LogoName) -Destination (Join-Path $StageAssets $LogoName)
}
Set-Content -LiteralPath (Join-Path $Stage "SOURCE_GIT_COMMIT.txt") -Value $SourceSha -Encoding ASCII

function Escape-Xml { param([string]$Value); return [System.Security.SecurityElement]::Escape($Value) }
$StoreNameXml = Escape-Xml ([string]$Registration.displayName)
$PublisherDisplayXml = Escape-Xml ([string]$Identity.publisherDisplayName)
$PublisherXml = Escape-Xml ([string]$Identity.packageIdentityPublisher)
$IdentityNameXml = Escape-Xml ([string]$Identity.packageIdentityName)
$AppIdXml = Escape-Xml ([string]$Product.appId)
$ExeNameXml = Escape-Xml ([string]$Product.exeName)
$NL = [Environment]::NewLine
$ResourceXml = (@($Registration.manifestResources) | ForEach-Object { '    <Resource Language="' + (Escape-Xml ([string]$_)) + '" />' }) -join $NL
$Manifest = @"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
  <Identity Name="$IdentityNameXml" Publisher="$PublisherXml" Version="$PackageVersion" ProcessorArchitecture="x64" />
  <Properties><DisplayName>$StoreNameXml</DisplayName><PublisherDisplayName>$PublisherDisplayXml</PublisherDisplayName><Logo>Assets\StoreLogo.png</Logo></Properties>
  <Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22621.0" /></Dependencies>
  <Resources>
$ResourceXml
  </Resources>
  <Applications><Application Id="$AppIdXml" Executable="App\$ExeNameXml.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements DisplayName="$StoreNameXml" Description="$StoreNameXml" BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png" /></Application></Applications>
  <Capabilities><rescap:Capability Name="runFullTrust" /></Capabilities>
</Package>
"@
Set-Content -LiteralPath (Join-Path $Stage "AppxManifest.xml") -Value $Manifest -Encoding UTF8

$SdkRoot = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
$MakeAppx = Get-ChildItem -Path $SdkRoot -Filter "makeappx.exe" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -match "\\x64$" } | Sort-Object -Property FullName -Descending | Select-Object -First 1
if (-not $MakeAppx) { throw "Windows SDK x64 makeappx.exe not found." }
$PackagePath = Join-Path $OutputRoot ("DataContractSchemaDrift_" + $PackageVersion + "_x64.msix")
if (Test-Path -LiteralPath $PackagePath) { throw "Refusing to overwrite existing MSIX: $PackagePath" }
& $MakeAppx.FullName pack /d $Stage /p $PackagePath
if ($LASTEXITCODE -ne 0) { throw "MakeAppx pack failed." }
& $MakeAppx.FullName unpack /p $PackagePath /d $Unpacked
if ($LASTEXITCODE -ne 0) { throw "MakeAppx unpack verification failed." }

$Xml = New-Object System.Xml.XmlDocument
$Xml.Load((Join-Path $Unpacked "AppxManifest.xml"))
$Ns = New-Object System.Xml.XmlNamespaceManager($Xml.NameTable)
$Ns.AddNamespace("m","http://schemas.microsoft.com/appx/manifest/foundation/windows10")
$Ns.AddNamespace("uap","http://schemas.microsoft.com/appx/manifest/uap/windows10")
$IdNode = $Xml.SelectSingleNode("/m:Package/m:Identity",$Ns)
$DisplayNode = $Xml.SelectSingleNode("/m:Package/m:Properties/m:DisplayName",$Ns)
$PublisherNode = $Xml.SelectSingleNode("/m:Package/m:Properties/m:PublisherDisplayName",$Ns)
$VisualNode = $Xml.SelectSingleNode("/m:Package/m:Applications/m:Application/uap:VisualElements",$Ns)
if (-not $IdNode -or $IdNode.GetAttribute("Name") -cne [string]$Identity.packageIdentityName -or $IdNode.GetAttribute("Publisher") -cne [string]$Identity.packageIdentityPublisher -or $IdNode.GetAttribute("Version") -cne $PackageVersion -or $IdNode.GetAttribute("ProcessorArchitecture") -cne "x64") { throw "Unpacked MSIX Identity contract mismatch." }
if (-not $DisplayNode -or $DisplayNode.InnerText -cne [string]$Registration.displayName -or -not $PublisherNode -or $PublisherNode.InnerText -cne [string]$Identity.publisherDisplayName -or -not $VisualNode -or $VisualNode.GetAttribute("DisplayName") -cne [string]$Registration.displayName) { throw "Unpacked MSIX display-name contract mismatch." }

$VerifyOutput = & $BuildPython $VerifierPath --msix $PackagePath --json
if ($LASTEXITCODE -ne 0) { throw "Python MSIX verifier failed: $VerifyOutput" }
$Verification = ($VerifyOutput | Out-String) | ConvertFrom-Json
if (-not $Verification.valid) { throw ("MSIX verifier reported blockers: " + (@($Verification.blockers) -join "; ")) }
$ExeHash = (Get-FileHash -LiteralPath $BuiltExe -Algorithm SHA256).Hash.ToLowerInvariant()
$MsixHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
$Evidence = [ordered]@{
    product = [string]$Registration.displayName
    repository = "shihuiarenjinba-png/csv-import-validator"
    store_id = [string]$Identity.storeId
    source_branch = $Branch
    source_sha = $SourceSha
    exe_path = $BuiltExe
    exe_sha256 = $ExeHash
    msix_path = $PackagePath
    msix_filename = [IO.Path]::GetFileName($PackagePath)
    msix_size_bytes = (Get-Item -LiteralPath $PackagePath).Length
    msix_sha256 = $MsixHash
    msix_version = $PackageVersion
    processor_architecture = "x64"
    signature_status = "UNSIGNED_CANDIDATE"
    certification_submission = "NOT_AUTHORIZED"
    sales_release = "HOLD"
    created_utc = [DateTime]::UtcNow.ToString("o")
}
$Evidence | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $OutputRoot "BUILD_EVIDENCE.json") -Encoding UTF8
$Verification | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $OutputRoot "MSIX_VERIFICATION.json") -Encoding UTF8
$Report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $OutputRoot "STORE_PREFLIGHT.json") -Encoding UTF8
Write-Output "MSIX_CANDIDATE_CREATED=$PackagePath"
Write-Output "SOURCE_SHA=$SourceSha"
Write-Output "EXE_SHA256=$ExeHash"
Write-Output "MSIX_SHA256=$MsixHash"
Write-Output "SIGNATURE_STATUS=UNSIGNED_CANDIDATE"
Write-Output "CERTIFICATION_SUBMISSION=NOT_AUTHORIZED"
Write-Output "SALES_RELEASE=HOLD"

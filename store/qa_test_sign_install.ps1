[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackagePath,
    [Parameter(Mandatory = $true)][string]$ExpectedPublisher,
    [Parameter(Mandatory = $true)][string]$ExpectedIdentity,
    [Parameter(Mandatory = $true)][string]$EvidencePath
)

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP -or -not $env:GITHUB_RUN_ID) {
    throw 'This ephemeral test-sign/install script may run only inside a GitHub-hosted Actions job.'
}
$PackagePath = (Resolve-Path -LiteralPath $PackagePath -ErrorAction Stop).Path
if ([IO.Path]::GetExtension($PackagePath) -ne '.msix') { throw 'Expected an .msix file.' }
$EvidencePath = [IO.Path]::GetFullPath($EvidencePath)
if (-not $EvidencePath.StartsWith([IO.Path]::GetFullPath($env:RUNNER_TEMP), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Evidence output must remain under RUNNER_TEMP.'
}
if (Test-Path -LiteralPath $EvidencePath) { throw "Refusing to overwrite evidence: $EvidencePath" }

Add-Type -AssemblyName System.IO.Compression.FileSystem
function Get-ZipHashes([string]$Path) {
    $archive = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $map = @{}
        foreach ($entry in $archive.Entries) {
            if ($entry.FullName -eq 'AppxSignature.p7x' -or $entry.FullName.EndsWith('/')) { continue }
            $stream = $entry.Open()
            try { $map[$entry.FullName] = (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash.ToLowerInvariant() }
            finally { $stream.Dispose() }
        }
        return $map
    } finally { $archive.Dispose() }
}

$sourceHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
$signedPath = Join-Path $env:RUNNER_TEMP ("DCA-QA-TestSigned-" + $env:GITHUB_RUN_ID + '-' + [guid]::NewGuid().ToString('N') + '.msix')
$pfxPath = Join-Path $env:RUNNER_TEMP ("DCA-QA-TestCert-" + [guid]::NewGuid().ToString('N') + '.pfx')
$cerPath = [IO.Path]::ChangeExtension($pfxPath, '.cer')
$appPackageFullName = $null
$installAttempted = $false
$certificateThumbprint = $null
$testCopyHash = $null
$installStatus = 'NOT_RUN'
$launchStatus = 'NOT_RUN'
$payloadIdentical = $false
$failure = $null

try {
    $sourceHashes = Get-ZipHashes $PackagePath
    $archive = [IO.Compression.ZipFile]::OpenRead($PackagePath)
    try {
        $manifestEntry = $archive.GetEntry('AppxManifest.xml')
        if (-not $manifestEntry) { throw 'AppxManifest.xml is missing.' }
        $reader = [IO.StreamReader]::new($manifestEntry.Open())
        try { [xml]$manifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $archive.Dispose() }
    $identity = $manifest.SelectSingleNode("//*[local-name()='Identity']")
    $application = $manifest.SelectSingleNode("//*[local-name()='Application']")
    if (-not $identity -or -not $application) { throw 'Manifest Identity/Application is missing.' }
    if ($identity.GetAttribute('Name') -cne $ExpectedIdentity -or $identity.GetAttribute('Publisher') -cne $ExpectedPublisher) {
        throw 'Package Identity or Publisher differs from the expected DCA profile.'
    }
    if ($identity.GetAttribute('ProcessorArchitecture') -cne 'x64') { throw 'Test package architecture is not x64.' }

    Copy-Item -LiteralPath $PackagePath -Destination $signedPath
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $ExpectedPublisher `
        -CertStoreLocation Cert:\CurrentUser\My -KeyAlgorithm RSA -KeyLength 2048 `
        -HashAlgorithm SHA256 -NotAfter (Get-Date).AddHours(2)
    $certificateThumbprint = $cert.Thumbprint
    $testPassword = [guid]::NewGuid().ToString('N')
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password (ConvertTo-SecureString $testPassword -AsPlainText -Force) | Out-Null
    Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
    Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\CurrentUser\TrustedPeople | Out-Null
    Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\CurrentUser\Root | Out-Null

    $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $signTool = Get-ChildItem -LiteralPath $sdkRoot -Filter signtool.exe -Recurse -File |
        Where-Object { $_.DirectoryName -match '\\x64$' } | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $signTool) { throw 'Windows SDK x64 signtool.exe is unavailable on the runner.' }
    & $signTool.FullName sign /fd SHA256 /f $pfxPath /p $testPassword $signedPath
    if ($LASTEXITCODE -ne 0) { throw "Test signing failed with exit code $LASTEXITCODE." }
    & $signTool.FullName verify /pa /v $signedPath
    if ($LASTEXITCODE -ne 0) { throw "Signed-copy verification failed with exit code $LASTEXITCODE." }

    $signedHashes = Get-ZipHashes $signedPath
    $sourceNames = @($sourceHashes.Keys | Sort-Object)
    $signedNames = @($signedHashes.Keys | Sort-Object)
    $sameNames = ($sourceNames.Count -eq $signedNames.Count)
    if ($sameNames) {
        for ($i = 0; $i -lt $sourceNames.Count; $i++) {
            if ($sourceNames[$i] -cne $signedNames[$i]) { $sameNames = $false; break }
        }
    }
    $sameBytes = [bool]$sameNames
    if ($sameNames) {
        foreach ($name in $sourceHashes.Keys) {
            if ($sourceHashes[$name] -cne $signedHashes[$name]) { $sameBytes = $false; break }
        }
    }
    $payloadIdentical = [bool]($sameNames -and $sameBytes)
    if (-not $payloadIdentical) { throw 'Signed derivative payload differs from the unsigned QA package.' }
    $testCopyHash = (Get-FileHash -LiteralPath $signedPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sourceHash) {
        throw 'The original unsigned MSIX changed during test signing.'
    }

    $existing = @(Get-AppxPackage -Name $ExpectedIdentity -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) { throw 'Unexpected pre-existing package identity on the supposedly ephemeral runner.' }
    $installAttempted = $true
    Add-AppxPackage -Path $signedPath -ErrorAction Stop
    $installed = Get-AppxPackage -Name $ExpectedIdentity -ErrorAction Stop | Select-Object -First 1
    $appPackageFullName = $installed.PackageFullName
    $installStatus = 'PASS'
    if ($installed.Publisher -cne $ExpectedPublisher) { throw 'Installed package Publisher mismatch.' }

    $appUserModelId = $installed.PackageFamilyName + '!' + $application.GetAttribute('Id')
    Start-Process -FilePath explorer.exe -ArgumentList ("shell:AppsFolder\" + $appUserModelId)
    $exeName = [IO.Path]::GetFileNameWithoutExtension($application.GetAttribute('Executable').Split('\')[-1])
    $deadline = (Get-Date).AddSeconds(45)
    $process = $null
    while ((Get-Date) -lt $deadline) {
        $process = Get-Process -Name $exeName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($process) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $process) { throw 'AUMID launch did not create the expected application process within 45 seconds.' }
    $launchStatus = 'PROCESS_STARTED'

    $receipt = [ordered]@{
        schema_version = 'dca-test-sign-install-receipt/1'
        created_at_utc = [DateTime]::UtcNow.ToString('o')
        environment_lane = 'WINDOWS_SERVER_AUTOMATION'
        product_identity = $ExpectedIdentity
        publisher = $ExpectedPublisher
        package_path = $PackagePath
        unsigned_package_sha256 = $sourceHash
        signed_copy_sha256 = $testCopyHash
        original_unsigned_package_unchanged = $true
        non_signature_payload_identical = $payloadIdentical
        test_certificate_thumbprint = $certificateThumbprint
        install_status = $installStatus
        installed_package_full_name = $appPackageFullName
        aumid = $appUserModelId
        launch_status = $launchStatus
        process_id = $process.Id
        limitations = @('This is a new QA_UNSIGNED package built by this workflow, not the fixed 1.0.0.0 Store candidate.', 'Windows Server package install/activation is not Windows 10/11 visual or DPI QA.', 'Product-specific source GUI/data checks are recorded in the companion DCA_GUI_QA_RECEIPT.json.')
    }
    New-Item -ItemType Directory -Path (Split-Path $EvidencePath) -Force | Out-Null
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    Write-Host "DCA_TEST_SIGN_INSTALL_RECEIPT=$EvidencePath"
}
catch {
    $failure = $_.Exception.Message
    $receipt = [ordered]@{
        schema_version = 'dca-test-sign-install-receipt/1'
        created_at_utc = [DateTime]::UtcNow.ToString('o')
        environment_lane = 'WINDOWS_SERVER_AUTOMATION'
        unsigned_package_sha256 = $sourceHash
        signed_copy_sha256 = $testCopyHash
        original_unsigned_package_unchanged = ((Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $sourceHash)
        non_signature_payload_identical = $payloadIdentical
        install_status = $installStatus
        launch_status = $launchStatus
        failure = $failure
        store_upload_performed = $false
        certification_executed = $false
        publish_executed = $false
    }
    New-Item -ItemType Directory -Path (Split-Path $EvidencePath) -Force | Out-Null
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    throw
}
finally {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    if ($appPackageFullName) {
        Remove-AppxPackage -Package $appPackageFullName -ErrorAction SilentlyContinue
    } elseif ($installAttempted) {
        Get-AppxPackage -Name $ExpectedIdentity -ErrorAction SilentlyContinue |
            Where-Object { $_.Publisher -ceq $ExpectedPublisher } |
            ForEach-Object { Remove-AppxPackage -Package $_.PackageFullName -ErrorAction SilentlyContinue }
    }
    if ($certificateThumbprint) {
        Remove-Item -Path ("Cert:\CurrentUser\TrustedPeople\" + $certificateThumbprint) -Force -ErrorAction SilentlyContinue
        Remove-Item -Path ("Cert:\CurrentUser\Root\" + $certificateThumbprint) -Force -ErrorAction SilentlyContinue
        Remove-Item -Path ("Cert:\CurrentUser\My\" + $certificateThumbprint) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $signedPath,$pfxPath,$cerPath -Force -ErrorAction SilentlyContinue
}


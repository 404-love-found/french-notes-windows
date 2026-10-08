[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$BuildInstaller,
    [switch]$InstallInnoSetup,
    [switch]$SkipDependencyInstall
)

# ASCII source works in Windows PowerShell 5.1 as well as PowerShell 7.
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$AppVersion = "0.2.0"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Find-InnoSetup {
    $candidates = @()
    if (${env:ProgramFiles(x86)}) {
        $candidates += Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    }
    if ($env:ProgramFiles) {
        $candidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
    }
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += $command.Source
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

if ($env:OS -ne "Windows_NT") {
    throw "Build on Windows: PyInstaller cannot create a Windows EXE on macOS or Linux."
}

Push-Location $ProjectRoot
try {
    if (-not $SkipDependencyInstall) {
        & $Python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
    }

    & $Python -c "import struct; from french_notes import __version__; assert struct.calcsize('P') == 8, 'Use 64-bit Python'; assert __version__ == '$AppVersion', 'Update the packaging version metadata'"
    if ($LASTEXITCODE -ne 0) { throw "Python architecture or app version is inconsistent." }

    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "The application test suite failed." }

    $distPath = Join-Path $ProjectRoot "dist"
    $buildPath = Join-Path $ProjectRoot "build"
    New-Item -ItemType Directory -Path $distPath, $buildPath -Force | Out-Null
    $exePath = Join-Path $distPath "FrenchNotes.exe"
    $setupPath = Join-Path $distPath "FrenchNotes-Setup-$AppVersion.exe"
    $zipPath = Join-Path $distPath "FrenchNotes-$AppVersion-Windows-x64.zip"
    $readmePath = Join-Path $distPath "README-windows.txt"
    $reportCopyPath = Join-Path $distPath "FrenchNotes-self-test-result.json"
    $hashPath = Join-Path $distPath "SHA256SUMS.txt"
    foreach ($oldOutput in @($exePath, $setupPath, $zipPath, $readmePath, $reportCopyPath, $hashPath)) {
        if (Test-Path -LiteralPath $oldOutput) {
            Remove-Item -LiteralPath $oldOutput -Force
        }
    }

    $pyinstallerArguments = @(
        "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", "FrenchNotes",
        "--collect-all", "docx",
        "--version-file", (Join-Path $PSScriptRoot "version_info.txt"),
        "--distpath", $distPath,
        "--workpath", (Join-Path $buildPath "pyinstaller"),
        "--specpath", $buildPath,
        "run.py"
    )
    & $Python @pyinstallerArguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "PyInstaller did not produce FrenchNotes.exe."
    }

    # Do not create this directory: --self-test requires a new output directory.
    $tempBase = [System.IO.Path]::GetTempPath()
    if ($env:RUNNER_TEMP) { $tempBase = $env:RUNNER_TEMP }
    $smokePath = Join-Path $tempBase ("FrenchNotes-self-test-" + [guid]::NewGuid().ToString("N"))
    $smokeProcess = Start-Process -FilePath $exePath -ArgumentList @(
        "--self-test", ('"{0}"' -f $smokePath)
    ) -Wait -PassThru
    if ($smokeProcess.ExitCode -ne 0) {
        throw "The packaged EXE self-test failed with exit code $($smokeProcess.ExitCode). See $smokePath."
    }
    $reportPath = Join-Path $smokePath "self-test-result.json"
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw "The packaged EXE did not create its self-test report."
    }
    $report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (($report.success -isnot [bool]) -or (-not $report.success)) {
        throw "The packaged EXE self-test report does not confirm success. See $reportPath."
    }
    Copy-Item -LiteralPath $reportPath -Destination $reportCopyPath
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README-windows.txt") -Destination $readmePath
    $noticesPath = Join-Path $distPath "licenses"
    & $Python (Join-Path $PSScriptRoot "collect_notices.py") --output $noticesPath
    if ($LASTEXITCODE -ne 0) { throw "Could not collect third-party software notices." }

    $releaseFiles = @($exePath)
    if ($BuildInstaller) {
        $compiler = Find-InnoSetup
        if ((-not $compiler) -and $InstallInnoSetup) {
            # Fixed package version, official Chocolatey feed; no downloaded shell script.
            & choco install innosetup --version=6.7.1 --source=https://community.chocolatey.org/api/v2/ --no-progress -y
            if ($LASTEXITCODE -ne 0) { throw "Inno Setup installation failed." }
            $compiler = Find-InnoSetup
        }
        if (-not $compiler) {
            throw "Inno Setup 6 is required for -BuildInstaller. Install it, or pass -InstallInnoSetup if Chocolatey is available."
        }
        & $compiler (Join-Path $PSScriptRoot "installer.iss")
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
        if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
            throw "Inno Setup did not produce the expected installer."
        }
        $releaseFiles += $setupPath
    }

    # The portable archive contains the EXE and user instructions, never local notes.
    Compress-Archive -LiteralPath @($exePath, $readmePath, $noticesPath) -DestinationPath $zipPath -CompressionLevel Optimal
    $releaseFiles += $zipPath
    $releaseFiles += $readmePath
    $hashLines = foreach ($releaseFile in $releaseFiles) {
        $hash = (Get-FileHash -LiteralPath $releaseFile -Algorithm SHA256).Hash.ToLowerInvariant()
        "{0}  {1}" -f $hash, (Split-Path -Leaf $releaseFile)
    }
    [System.IO.File]::WriteAllLines($hashPath, [string[]]$hashLines, [System.Text.Encoding]::ASCII)
    Write-Host "Built and tested FrenchNotes $AppVersion. Outputs: $distPath"
    Write-Host "The app and installer are unsigned. No signing certificate is configured."
    Write-Host "Packaged executable self-test: $reportCopyPath"
}
finally {
    Pop-Location
}

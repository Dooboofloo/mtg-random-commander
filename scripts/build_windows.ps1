param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Version = 'dev',
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (-not $SkipBuild) {
        & python -m PyInstaller `
            --noconfirm --clean --onedir --console `
            --name MTGRandomCommander `
            --collect-submodules mtg_carddb `
            --copy-metadata mtg-carddb `
            main.py

        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed with exit code $LASTEXITCODE"
        }
    }

    $bundle = Join-Path $root 'dist\MTGRandomCommander'
    $exe = Join-Path $bundle 'MTGRandomCommander.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "Missing Windows executable: $exe"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $bundle '_internal') -PathType Container)) {
        throw 'Missing bundled runtime directory _internal.'
    }

    Copy-Item -LiteralPath (Join-Path $root 'packaging\Run.bat') `
        -Destination (Join-Path $bundle 'Run.bat') -Force
    Copy-Item -LiteralPath (Join-Path $root 'packaging\WINDOWS-README.txt') `
        -Destination (Join-Path $bundle 'README.txt') -Force

    $archive = Join-Path $root "dist\MTGRandomCommander-windows-x64-$Version.zip"
    $pendingArchive = Join-Path $root "dist\MTGRandomCommander-windows-x64-$Version.pending.zip"
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force -ErrorAction Stop
    }

    # Antivirus/indexer locks may briefly prevent reading newly built files.
    # Retry failed ZIP creation instead of publishing a partial archive.
    $maxAttempts = 6
    $packaged = $false
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            if (Test-Path -LiteralPath $pendingArchive) {
                Remove-Item -LiteralPath $pendingArchive -Force -ErrorAction Stop
            }
            # Write each file with an explicit archive entry name. This avoids
            # differing directory-root conventions between ZIP APIs.
            $sourceFiles = @(Get-ChildItem -LiteralPath $bundle -File -Recurse)
            if ($sourceFiles.Count -eq 0) {
                throw 'The PyInstaller bundle contains no files.'
            }

            $expected = @{}
            $writer = [System.IO.Compression.ZipFile]::Open(
                $pendingArchive,
                [System.IO.Compression.ZipArchiveMode]::Create
            )
            try {
                foreach ($file in $sourceFiles) {
                    $relative = $file.FullName.Substring($bundle.Length + 1).Replace('\', '/')
                    $entryName = "MTGRandomCommander/$relative"
                    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                        $writer,
                        $file.FullName,
                        $entryName,
                        [System.IO.Compression.CompressionLevel]::Optimal
                    ) | Out-Null
                    $expected[$entryName] = $file.Length
                }
            }
            finally {
                $writer.Dispose()
            }

            if (-not (Test-Path -LiteralPath $pendingArchive -PathType Leaf)) {
                throw "ZIP file was not created: $pendingArchive"
            }

            # Independently read the archive and compare exactly what was
            # written with the expected paths and uncompressed file sizes.
            $zip = [System.IO.Compression.ZipFile]::OpenRead($pendingArchive)
            try {
                $actual = @{}
                foreach ($entry in $zip.Entries) {
                    if (-not $entry.FullName.EndsWith('/')) {
                        $actual[$entry.FullName] = $entry.Length
                    }
                }
                foreach ($entryName in $expected.Keys) {
                    if (-not $actual.ContainsKey($entryName)) {
                        $preview = ($actual.Keys | Select-Object -First 8) -join ', '
                        throw "ZIP is missing bundled file '$entryName'; first entries: $preview"
                    }
                    if ($actual[$entryName] -ne $expected[$entryName]) {
                        throw "ZIP file size mismatch: $entryName"
                    }
                }
                if ($actual.Count -ne $expected.Count) {
                    throw "ZIP entry count mismatch: expected $($expected.Count), got $($actual.Count)"
                }
            }
            finally {
                $zip.Dispose()
            }

            # Only expose the release filename once verification has passed.
            Move-Item -LiteralPath $pendingArchive -Destination $archive -ErrorAction Stop
            $packaged = $true
            break
        }
        catch {
            if ($attempt -eq $maxAttempts) {
                if (Test-Path -LiteralPath $pendingArchive) {
                    Remove-Item -LiteralPath $pendingArchive -Force -ErrorAction SilentlyContinue
                }
                throw "Windows ZIP packaging failed after $maxAttempts attempts: $($_.Exception.Message)"
            }
            Write-Warning "ZIP attempt $attempt/$maxAttempts failed: $($_.Exception.Message)"
            Start-Sleep -Seconds ($attempt * 2)
        }
    }
    if (-not $packaged) {
        throw 'Windows ZIP packaging did not complete.'
    }

    Write-Host "Executable: $exe"
    Write-Host "Release ZIP: $archive"
}
finally {
    Pop-Location
}

[CmdletBinding()]
param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$specPath = Join-Path $projectRoot "packaging\nfse_facil.spec"

Push-Location (Join-Path $projectRoot "packaging")
try {
    python -m pytest (Join-Path $projectRoot "tests") -q
    if ($LASTEXITCODE -ne 0) { throw "Os testes falharam; o pacote não foi criado." }

    python -m PyInstaller --noconfirm --clean --distpath (Join-Path $projectRoot "dist") --workpath (Join-Path $projectRoot "build\pyinstaller") $specPath
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executável." }

    $exePath = Join-Path $projectRoot "dist\NFSeFacil\NFSeFacil.exe"
    if (-not (Test-Path -LiteralPath $exePath)) { throw "Executável final não encontrado." }

    if ($Installer) {
        $iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if (-not $iscc) {
            $isccCandidates = @(
                "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
                "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
                "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
                "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
            )
            foreach ($isccPath in $isccCandidates) {
                if (Test-Path -LiteralPath $isccPath) {
                    $iscc = Get-Item -LiteralPath $isccPath
                    break
                }
            }
        }
        if (-not $iscc) { throw "Inno Setup 7 ou 6 não encontrado. Instale-o e execute novamente com -Installer." }
        $isccExecutable = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
        & $isccExecutable (Join-Path $projectRoot "packaging\installer.iss")
        if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o instalador." }
        Write-Host "Instalador criado em: $(Join-Path $projectRoot 'dist\installer\NFSeFacil-Setup-0.6.0.exe')"
    }

    Write-Host "Pacote criado em: $(Join-Path $projectRoot 'dist\NFSeFacil')"
}
finally {
    Pop-Location
}

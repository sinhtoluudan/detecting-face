param([switch]$CaiDat)
$ErrorActionPreference = 'Stop'
$web = Split-Path $PSScriptRoot -Parent
$python = Join-Path (Split-Path $web -Parent) '.venv\Scripts\python.exe'
$private = Join-Path $env:LOCALAPPDATA 'FaceCam-Kiosk'
$keyFile = Join-Path $private 'facecam-kiosk.key'
if (!(Test-Path -LiteralPath $keyFile)) {
    if (!$CaiDat) { throw 'Hãy chạy lại với -CaiDat để thiết lập máy chấm công.' }
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    $key = & $python -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0 -or !$key) { throw 'Không tạo được khóa máy chấm công.' }
    [IO.File]::WriteAllText($keyFile, $key)
}
$env:FACECAM_KIOSK_KEY = [IO.File]::ReadAllText($keyFile).Trim()
$env:MONGO_PORT = '27020'
if ($CaiDat) {
    Push-Location -LiteralPath $web
    try {
        docker compose -p facecam up -d --build --wait
        if ($LASTEXITCODE -ne 0) { throw 'Không cập nhật được máy chủ FaceCam.' }
    } finally {
        Pop-Location
    }
}
& $python (Join-Path $PSScriptRoot 'FaceCam-May-Chung.py')

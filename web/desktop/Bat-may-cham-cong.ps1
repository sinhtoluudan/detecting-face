param([switch]$CaiDat)
$ErrorActionPreference = 'Stop'
$web = Split-Path $PSScriptRoot -Parent
$private = Join-Path $env:LOCALAPPDATA 'FaceCam-Kiosk'
$venv = Join-Path $private 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
if ($CaiDat) {
    if (!(Test-Path -LiteralPath $python)) {
        py -3.11 -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw 'Cần Python 3.11 để tạo môi trường camera.' }
    }
    & $python -m pip install -r (Join-Path $web 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Không cài được thư viện camera.' }
} elseif (!(Test-Path -LiteralPath $python)) {
    throw 'Hãy chạy lại với -CaiDat để cài camera lần đầu.'
}
$keyFile = Join-Path $private 'facecam-kiosk.key'
if (!(Test-Path -LiteralPath $keyFile)) {
    if (!$CaiDat) { throw 'Hãy chạy lại với -CaiDat để thiết lập máy chấm công.' }
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    $key = & $python -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0 -or !$key) { throw 'Không tạo được khóa máy chấm công.' }
    [IO.File]::WriteAllText($keyFile, $key)
}
$env:FACECAM_KIOSK_KEY = [IO.File]::ReadAllText($keyFile).Trim()
Push-Location -LiteralPath $web
try {
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'Không khởi động được máy chủ FaceCam.' }
} finally {
    Pop-Location
}
& $python (Join-Path $PSScriptRoot 'FaceCam-May-Chung.py')

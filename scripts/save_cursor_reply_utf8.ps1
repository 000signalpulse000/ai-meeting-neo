# temp/cursor_reply.txt を UTF-8（BOM なし）で保存する例。
# プロジェクトルートから:  pwsh -File scripts/save_cursor_reply_utf8.ps1
$root = Split-Path -Parent $PSScriptRoot
$path = Join-Path $root "temp\cursor_reply.txt"
$text = @'
ここに Cursor の返答を貼る
'@
$utf8 = New-Object System.Text.UTF8Encoding $false
$dir = Split-Path -Parent $path
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
[System.IO.File]::WriteAllText($path, $text, $utf8)
Write-Host "Wrote $path"

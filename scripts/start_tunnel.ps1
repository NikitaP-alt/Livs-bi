# Запускает Cloudflare-туннель к Metabase и печатает готовые публичные ссылки на дашборды.
# Запуск (из папки проекта):  powershell -ExecutionPolicy Bypass -File scripts\start_tunnel.ps1
# ВАЖНО: ПК и Docker должны оставаться включёнными, пока смотрят. При перезапуске URL меняется.

$ErrorActionPreference = "Stop"

# публичные UUID дашбордов (стабильны, не зависят от URL туннеля)
$DASH = [ordered]@{
  "Доходность"          = "b5058a4a-0989-4662-8ac7-3506a6257144"
  "План-факт"           = "98fccf88-9ac7-4c8d-bd30-1dc98a2b79ad"
  "Прогноз"             = "5e5addec-b1db-4b10-9355-6041c0441ad1"
  "Матрица"             = "f6337d64-9efd-4a49-be3a-f810a0b12ae9"
  "Динамика и прирост"  = "20a75a62-22e3-4aee-ae80-74b283d30f06"
  "Сверка SI/SO"        = "b527fb14-632c-4a3b-a6a9-4963544166f7"
  "Клиенты и каналы"    = "2754bf0a-c6e8-4b49-a612-e965f4e24f77"
  "Остатки: покрытие"   = "eb72cc73-70ec-4a4b-898f-721da8501bc7"
  "Продажи и остатки"   = "8312a73e-9f35-40c8-ada9-dd7a9d56793e"
  "Остатки и закуп"     = "c38ad802-54fd-4237-a86a-94df67656545"
  "Sell-In (1С)"        = "64db3fdf-a134-4517-8197-7d93060d2e54"
  "Валовая маржа (1С)"  = "3101d253-da8f-4005-8d72-67640723d884"
}

Write-Host "Перезапуск туннеля..."
docker rm -f livs_tunnel 2>$null | Out-Null
docker run -d --name livs_tunnel --restart unless-stopped --network livs-bi_default cloudflare/cloudflared:latest `
  tunnel --no-autoupdate --protocol http2 --url http://metabase:3000 | Out-Null

$url = $null
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 3
  $log = docker logs livs_tunnel 2>&1 | Out-String
  if (-not $url -and $log -match "https://[a-z0-9-]+\.trycloudflare\.com") { $url = $matches[0] }
  if ($log -match "Registered tunnel connection") { break }
}

if (-not $url) { Write-Host "URL не появился — проверь: docker logs livs_tunnel"; exit 1 }

Write-Host ""
Write-Host "=== ГОТОВЫЕ ССЫЛКИ (отправь руководителю) ===" -ForegroundColor Green
foreach ($k in $DASH.Keys) { "{0,-22} {1}/public/dashboard/{2}" -f $k, $url, $DASH[$k] }
Write-Host ""
Write-Host "Все дашборды (с логином): $url"

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$api = Join-Path $raiz "apps\metodo"

Start-Process -FilePath python -ArgumentList @("app.py") -WorkingDirectory $api -WindowStyle Hidden
Start-Process -FilePath python -ArgumentList @("-m", "http.server", "8000") -WorkingDirectory $raiz -WindowStyle Hidden

Write-Host "AIDA.ON iniciado."
Write-Host "Site: http://127.0.0.1:8000/pages/index-seleciona.html"
Write-Host "API:  http://127.0.0.1:5000/"

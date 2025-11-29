# Baixa pdf.min.js e pdf.worker.min.js versão 4.2.67 para fallback offline
$ErrorActionPreference = 'Continue'
$version = '4.3.136'
$files = 'pdf.min.js','pdf.worker.min.js'
$mirrors = @(
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/$version",
  "https://cdn.jsdelivr.net/npm/pdfjs-dist@$version/build",
  "https://unpkg.com/pdfjs-dist@$version/build",
  # GitHub raw (precisa dos caminhos internos do pacote)
  "https://raw.githubusercontent.com/mozilla/pdf.js/v$version/build"
)

function Try-NpmCopy {
  param($File)
  try {
    $nodePath = Join-Path -Path (Resolve-Path '..\..\..\..').Path -ChildPath 'node_modules/pdfjs-dist/build'
    if(Test-Path $nodePath){
      $src = Join-Path $nodePath $File
      if(Test-Path $src){
        Copy-Item $src -Destination $File -Force
        Write-Host "Copiado de node_modules: $File" -ForegroundColor Green
        return $true
      }
    }
  } catch { }
  return $false
}

foreach($f in $files){
  $ok = $false
  foreach($m in $mirrors){
    $url = "$m/$f"
    Write-Host "Tentando $url" -ForegroundColor Cyan
    try {
      Invoke-WebRequest -Uri $url -OutFile $f -UseBasicParsing -TimeoutSec 20
      if( (Get-Item $f).Length -lt 1000 ){ throw 'Arquivo muito pequeno (possível erro/HTML).' }
      Write-Host "OK: $f" -ForegroundColor Green
      $ok = $true
      break
    } catch {
      Write-Host "Falhou: $url : $($_.Exception.Message)" -ForegroundColor Yellow
    }
  }
  if(-not $ok){
    Write-Host "Tentando copiar via node_modules (npm)." -ForegroundColor DarkCyan
    if(Try-NpmCopy -File $f){ $ok=$true }
  }
  if(-not $ok){ Write-Host "Não foi possível obter $f. Coloque manualmente." -ForegroundColor Red }
}
Write-Host 'Finalizado. Se arquivos vieram de CDN, rode o server novamente se necessário.' -ForegroundColor Magenta

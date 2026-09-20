$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
$Log = Join-Path $Root 'logs\restart-gateway.log'
$StatePath = Join-Path $Root '.runtime\service_restart_state.json'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null
New-Item -ItemType Directory -Force (Split-Path $StatePath) | Out-Null

function Log([string]$m) { Add-Content -Path $Log -Value ("{0:o} {1}" -f (Get-Date), $m) }
function Read-State { try { return (Get-Content $StatePath -Raw | ConvertFrom-Json) } catch { return $null } }
function Write-State([string]$newState,[bool]$success,[string[]]$errors) {
  $old = Read-State
  $obj = [ordered]@{
    request_id = if ($old -and $old.request_id) { [string]$old.request_id } else { '' }
    state = $newState
    success = $success
    reason = if ($old -and $old.reason) { [string]$old.reason } else { 'panel-service-restart' }
    updated_at = (Get-Date).ToString('o')
    errors = @($errors)
  }
  if ($newState -eq 'running') { $obj.started_at = (Get-Date).ToString('o') }
  if ($newState -in @('completed','failed')) { $obj.completed_at = (Get-Date).ToString('o') }
  $obj | ConvertTo-Json -Depth 5 | Set-Content -Path $StatePath -Encoding UTF8
}

function Get-RuntimeConfig {
  if (-not (Test-Path $Python)) { throw "Runtime inventory Python not found: $Python" }
  Push-Location $Root
  try {
    $raw = & $Python -m core.runtime_inventory 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($raw -join "`n") }
    return (($raw -join "`n") | ConvertFrom-Json)
  } finally {
    Pop-Location
  }
}

$errors = @()
Write-State 'running' $false @()
Log 'BEGIN independent gateway restart'

try {
  $runtimeConfig = Get-RuntimeConfig
  $gatewayService = [string]$runtimeConfig.orchestration.gateway_service
  $healthUrl = [string]$runtimeConfig.orchestration.gateway_health_url
} catch {
  $errors += "runtime orchestration load: $($_.Exception.Message)"
  Write-State 'failed' $false $errors
  Log ("END independent gateway restart success=False errors={0}" -f ($errors -join ' | '))
  exit 1
}

# Allow the HTTP 202 response that scheduled this task to leave the old process first.
Start-Sleep -Milliseconds 1200
try {
  Restart-Service -Name $gatewayService -Force -ErrorAction Stop
  Log ("Restart-Service returned service={0}" -f $gatewayService)
} catch {
  $errors += "gateway restart: $($_.Exception.Message)"
  Log ("Restart-Service ERROR: {0}" -f $_.Exception.Message)
}

$healthOk = $false
for ($i=0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
    if ($h.status -eq 'ok') { $healthOk=$true; break }
  } catch { }
}
if (-not $healthOk) { $errors += "gateway health did not recover: $healthUrl" }

$ok = ($errors.Count -eq 0)
Write-State ($(if($ok){'completed'}else{'failed'})) $ok $errors
Log ("END independent gateway restart success={0} errors={1}" -f $ok, ($errors -join ' | '))
if (-not $ok) { exit 1 }

$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
$Log = Join-Path $Root 'logs\restart-all.log'
$StatePath = Join-Path $Root '.runtime\restart_state.json'
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
$warnings = @()
Write-State 'running' $false @()
Log 'BEGIN config-triggered restart-all'

try {
  $runtimeConfig = Get-RuntimeConfig
} catch {
  $errors += "runtime inventory load: $($_.Exception.Message)"
  Write-State 'failed' $false $errors
  Log ("END config-triggered restart-all success=False errors={0}" -f ($errors -join ' | '))
  exit 1
}

$orchestration = $runtimeConfig.orchestration
$providers = @($runtimeConfig.providers | Where-Object { $_.enabled -eq $true })
$agentBase = ([string]$orchestration.desktop_agent_url).TrimEnd('/')

Log ("enabled provider runtimes from config: {0}" -f (($providers | ForEach-Object { $_.id }) -join ', '))
foreach ($provider in $providers) {
  try {
    $providerId = [uri]::EscapeDataString([string]$provider.id)
    $r = Invoke-RestMethod -Method Post -Uri ("{0}/providers/{1}/restart" -f $agentBase, $providerId) -TimeoutSec 60
    if (-not $r.ok) { $warnings += "provider $($provider.id) returned ok=false" }
    Log ("provider {0} restart ok={1}" -f $provider.id, $r.ok)
  } catch {
    $warnings += "provider $($provider.id) restart: $($_.Exception.Message)"
    Log ("provider {0} restart ERROR: {1}" -f $provider.id, $_.Exception.Message)
  }
}

try {
  $agentTask = [string]$orchestration.desktop_agent_task
  Stop-ScheduledTask -TaskName $agentTask -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 500
  Start-ScheduledTask -TaskName $agentTask -ErrorAction Stop
  Start-Sleep -Seconds 1
  Log ("desktop runtime agent restarted task={0}" -f $agentTask)
} catch {
  $errors += "desktop runtime agent restart: $($_.Exception.Message)"
  Log ("desktop runtime agent restart ERROR: {0}" -f $_.Exception.Message)
}

try {
  $gatewayService = [string]$orchestration.gateway_service
  Restart-Service -Name $gatewayService -Force -ErrorAction Stop
  Log ("gateway restarted service={0}" -f $gatewayService)
} catch {
  $errors += "gateway restart: $($_.Exception.Message)"
  Log ("gateway restart ERROR: {0}" -f $_.Exception.Message)
}

$healthOk = $false
$healthUrl = [string]$orchestration.gateway_health_url
for ($i=0; $i -lt 20; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
    if ($h.status -eq 'ok') { $healthOk=$true; break }
  } catch { }
}
if (-not $healthOk) { $errors += "gateway health did not recover: $healthUrl" }

# Readiness is required only for enabled runtime providers declared in config.
foreach ($provider in $providers) {
  $ready = $false
  $probe = ([string]$provider.cdp_url).TrimEnd('/') + '/json/version'
  for ($j=0; $j -lt 30; $j++) {
    try {
      Invoke-RestMethod -Uri $probe -TimeoutSec 3 | Out-Null
      $ready=$true
      break
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $ready) { $errors += "provider runtime $($provider.id) not ready after wait: $probe" }
}

$ok = ($errors.Count -eq 0)
Write-State ($(if($ok){'completed'}else{'failed'})) $ok $errors
Log ("END config-triggered restart-all success={0} errors={1} warnings={2}" -f $ok, ($errors -join ' | '), ($warnings -join ' | '))
if (-not $ok) { exit 1 }

<# Hooshka Web Gateway Service Manager (NSSM)
   Provider/runtime inventory and Windows service identities are read from config.yaml.
#>
param(
  [Parameter(Mandatory=$true,Position=0)]
  [ValidateSet('install','uninstall','start','stop','restart','status','logs','config','runtime-start','runtime-restart','runtime-repair','runtime-status')]
  [string]$Command,
  [Parameter(Position=1)]
  [string]$Provider='all',
  [string]$ConfigPath='config.yaml'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonExe = Join-Path $ScriptDir '.venv\Scripts\python.exe'
$MainScript = Join-Path $ScriptDir 'main.py'
$Nssm = 'D:\nssm-2.24-103-gdee49fc\win64\nssm.exe'
$EnvFile = Join-Path $ScriptDir '.env'
$ConfigFullPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) { $ConfigPath } else { Join-Path $ScriptDir $ConfigPath }
$ConfigFullPath = [System.IO.Path]::GetFullPath($ConfigFullPath)
$env:HWG_CONFIG_PATH = $ConfigFullPath

function Assert-Prereqs {
  if (-not (Test-Path $Nssm)) { throw "NSSM not found: $Nssm" }
  if (-not (Test-Path $PythonExe)) { throw "Python venv not found: $PythonExe" }
  if (-not (Test-Path $MainScript)) { throw "main.py not found: $MainScript" }
  if (-not (Test-Path $ConfigFullPath)) { throw "Config not found: $ConfigFullPath" }
}

function Get-RuntimeConfiguration {
  if (-not (Test-Path $PythonExe)) { throw "Python venv not found: $PythonExe" }
  Push-Location $ScriptDir
  try {
    $raw = & $PythonExe -m core.runtime_inventory 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($raw -join "`n") }
    return (($raw -join "`n") | ConvertFrom-Json)
  } finally {
    Pop-Location
  }
}

$RuntimeConfiguration = Get-RuntimeConfiguration
$Orchestration = $RuntimeConfiguration.orchestration
$ServiceName = [string]$Orchestration.gateway_service
$LegacyServiceName = [string]$Orchestration.legacy_gateway_service
$AgentBase = ([string]$Orchestration.desktop_agent_url).TrimEnd('/')
$GatewayHealthUrl = [string]$Orchestration.gateway_health_url
$RuntimeProviders = @($RuntimeConfiguration.providers)

function Ensure-RuntimeCredential {
  $apiKey = $null
  $identity = 'local-user'
  if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
      if ($line -match '^BRIDGE_API_KEY=(.+)$') { $apiKey = $Matches[1].Trim() }
      elseif ($line -match '^BRIDGE_API_IDENTITY=(.+)$') { $identity = $Matches[1].Trim() }
    }
  }
  if (-not $apiKey) {
    $apiKey = 'sk-local-' + [guid]::NewGuid().ToString('N')
    @(
      "BRIDGE_API_KEY=$apiKey"
      "BRIDGE_API_IDENTITY=$identity"
    ) | Set-Content -Path $EnvFile -Encoding ASCII
  }
  return [pscustomobject]@{ ApiKey=$apiKey; Identity=$identity }
}

function Get-SelectedProviders([string]$RequestedProvider, [bool]$IncludeDisabledForAll) {
  if ($RequestedProvider -eq 'all') {
    if ($IncludeDisabledForAll) { return @($RuntimeProviders) }
    return @($RuntimeProviders | Where-Object { $_.enabled -eq $true })
  }
  $match = @($RuntimeProviders | Where-Object { $_.id -eq $RequestedProvider })
  if ($match.Count -eq 0) { throw "Provider runtime is not configured: $RequestedProvider" }
  return $match
}

function Invoke-AgentAction([string]$ProviderId, [string]$Action) {
  $encodedProvider = [uri]::EscapeDataString($ProviderId)
  $encodedAction = [uri]::EscapeDataString($Action)
  return Invoke-RestMethod -Method Post -Uri ("{0}/providers/{1}/{2}" -f $AgentBase, $encodedProvider, $encodedAction) -TimeoutSec 65
}

function Invoke-RuntimeAction([string]$RequestedProvider, [string]$Action, [bool]$IncludeDisabledForAll=$false) {
  $selected = @(Get-SelectedProviders $RequestedProvider $IncludeDisabledForAll)
  $results = @()
  foreach ($runtime in $selected) {
    try {
      $response = Invoke-AgentAction ([string]$runtime.id) $Action
      $results += [pscustomobject]@{ id=[string]$runtime.id; enabled=[bool]$runtime.enabled; success=[bool]$response.ok; response=$response }
    } catch {
      $results += [pscustomobject]@{ id=[string]$runtime.id; enabled=[bool]$runtime.enabled; success=$false; error=$_.Exception.Message }
    }
  }
  return $results
}

function Get-RuntimeStatus {
  return Invoke-RestMethod -Uri ($AgentBase + '/status') -TimeoutSec 10
}

function Stop-AllConfiguredRuntimes {
  $results = @(Invoke-RuntimeAction 'all' 'stop' $true)
  foreach ($item in $results) {
    if (-not $item.success) { Write-Warning ("Runtime stop failed for {0}: {1}" -f $item.id, $item.error) }
  }
}

switch ($Command) {
  'install' {
    Assert-Prereqs
    $runtimeCredential = Ensure-RuntimeCredential
    & $Nssm install $ServiceName $PythonExe $MainScript | Out-Null
    & $Nssm set $ServiceName AppDirectory $ScriptDir | Out-Null
    & $Nssm set $ServiceName Start SERVICE_AUTO_START | Out-Null
    & $Nssm set $ServiceName AppStdout (Join-Path $ScriptDir 'logs\nssm-out.log') | Out-Null
    & $Nssm set $ServiceName AppStderr (Join-Path $ScriptDir 'logs\nssm-error.log') | Out-Null
    & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" "HWG_CONFIG_PATH=$ConfigFullPath" | Out-Null
    Write-Output "INSTALLED $ServiceName"
    Write-Output "RUNTIME_CREDENTIAL_READY source=.env+nssm_environment"
  }
  'start' {
    $runtimeCredential = Ensure-RuntimeCredential
    & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" "HWG_CONFIG_PATH=$ConfigFullPath" | Out-Null
    Start-Service $ServiceName
    Get-Service $ServiceName
  }
  'stop' {
    Stop-Service $ServiceName -Force
    Stop-AllConfiguredRuntimes
    Get-Service $ServiceName
  }
  'restart' {
    $runtimeCredential = Ensure-RuntimeCredential
    & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" "HWG_CONFIG_PATH=$ConfigFullPath" | Out-Null
    # Gateway restart deliberately preserves browser/CDP runtimes and login state.
    Restart-Service $ServiceName -Force
    Start-Sleep -Seconds 1
    Get-Service $ServiceName
  }
  'runtime-start' {
    @(Invoke-RuntimeAction $Provider 'start' $false) | ConvertTo-Json -Depth 8
  }
  'runtime-restart' {
    @(Invoke-RuntimeAction $Provider 'restart' $false) | ConvertTo-Json -Depth 8
  }
  'runtime-repair' {
    # Explicit Repair All includes disabled runtimes; ordinary all-start/all-restart do not.
    @(Invoke-RuntimeAction $Provider 'repair' ($Provider -eq 'all')) | ConvertTo-Json -Depth 8
  }
  'runtime-status' {
    Get-RuntimeStatus | ConvertTo-Json -Depth 8
  }
  'status' {
    Get-Service $ServiceName
  }
  'uninstall' {
    $serviceNames = @($ServiceName)
    if ($LegacyServiceName) { $serviceNames += $LegacyServiceName }
    foreach ($name in ($serviceNames | Select-Object -Unique)) {
      if (Get-Service $name -ErrorAction SilentlyContinue) {
        Stop-Service $name -Force -ErrorAction SilentlyContinue
        & $Nssm remove $name confirm | Out-Null
        Write-Output "REMOVED $name"
      }
    }
    Stop-AllConfiguredRuntimes
  }
  'logs' {
    Get-Content (Join-Path $ScriptDir 'logs\bridge.log') -Tail 80
  }
  'config' {
    Assert-Prereqs
    [ordered]@{
      service=$ServiceName
      legacy_service=$LegacyServiceName
      python=$PythonExe
      app=$MainScript
      directory=$ScriptDir
      nssm=$Nssm
      runtime_credential_source='.env+nssm_environment'
      config_path=$ConfigFullPath
      gateway_health_url=$GatewayHealthUrl
      desktop_agent_url=$AgentBase
      providers=$RuntimeProviders
    } | ConvertTo-Json -Depth 8
  }
}

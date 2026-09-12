<# Hooshka Web Gateway Service Manager (NSSM) #>
param(
 [Parameter(Mandatory=$true,Position=0)]
 [ValidateSet('install','uninstall','start','stop','restart','status','logs','config')]
 [string]$Command
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ServiceName = 'HooshkaWebGateway'
$LegacyServiceName = 'WebLLMBridge'
$PythonExe = Join-Path $ScriptDir '.venv\Scripts\python.exe'
$MainScript = Join-Path $ScriptDir 'main.py'
$Nssm = 'D:\nssm-2.24-103-gdee49fc\win64\nssm.exe'
$EnvFile = Join-Path $ScriptDir '.env'
$ChatGPTProfile = Join-Path $ScriptDir '.runtime\chatgpt-profile'
$ChatGPTRuntimeLabel = 'HWG-ChatGPT-Web-CDP'
$ChatGPTCdpPort = 9224
$QwenProfile = Join-Path $ScriptDir '.runtime\qwen-profile'
$QwenRuntimeLabel = 'HWG-Qwen-Web-Controller'
$QwenCdpPort = 9225
$ZaiProfile = Join-Path $ScriptDir '.runtime\zai-profile'
$ZaiLegacyProfile = Join-Path $ScriptDir '.runtime\zai-cdp-profile'
$ZaiRuntimeLabel = 'HWG-Zai-Web-SSE-Capture'
$ZaiCdpPort = 9223
$DeepSeekProfile = Join-Path $ScriptDir '.runtime\deepseek-profile'
$DeepSeekRuntimeLabel = 'HWG-DeepSeek-Web-UI'
$DeepSeekCdpPort = 9226

function Get-ChromeExecutable {
  $chromeCandidates = @(
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
  )
  return ($chromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1)
}

function Get-PortOwnerProcess([int]$Port) {
  $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $listener) { return $null }
  return Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
}

function Assert-ProjectChromeOwnership([int]$Port, [string]$Profile, [string]$Label) {
  $owner = Get-PortOwnerProcess $Port
  if (-not $owner) { return $false }
  $profileNeedle = [Regex]::Escape($Profile)
  $isOwned = $owner.Name -eq 'chrome.exe' -and $owner.CommandLine -and $owner.CommandLine -match $profileNeedle
  if (-not $isOwned) {
    throw "$Label CDP port $Port is owned by a non-project process (pid=$($owner.ProcessId), name=$($owner.Name)); refusing to attach"
  }
  return $true
}

function Ensure-ChatGPTChromeCdp {
  if (Assert-ProjectChromeOwnership $ChatGPTCdpPort $ChatGPTProfile $ChatGPTRuntimeLabel) { return }

  $chrome = Get-ChromeExecutable
  if (-not $chrome) { throw 'Chrome not found for ChatGPT Web CDP runtime' }

  New-Item -ItemType Directory -Force $ChatGPTProfile | Out-Null
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$ChatGPTCdpPort",
    '--remote-debugging-address=127.0.0.1',
    "--user-data-dir=$ChatGPTProfile",
    '--no-first-run',
    '--disable-default-apps',
    '--new-window',
    'https://chatgpt.com/'
  ) | Out-Null
  Start-Sleep -Seconds 5
  if (-not (Assert-ProjectChromeOwnership $ChatGPTCdpPort $ChatGPTProfile $ChatGPTRuntimeLabel)) {
    throw 'ChatGPT Web project-owned Chrome CDP runtime did not start'
  }
}

function Stop-ChatGPTChromeCdp {
  $needle = [Regex]::Escape($ChatGPTProfile)
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match $needle }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  if ($procs) { Start-Sleep -Milliseconds 500 }
}

function Assert-Prereqs {
  if (-not (Test-Path $Nssm)) { throw "NSSM not found: $Nssm" }
  if (-not (Test-Path $PythonExe)) { throw "Python venv not found: $PythonExe" }
  if (-not (Test-Path $MainScript)) { throw "main.py not found: $MainScript" }
}

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

function Stop-OrphanQwenBrowsers {
  $needle = [Regex]::Escape($QwenProfile)
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match $needle }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  if ($procs) { Start-Sleep -Milliseconds 500 }
}


function Ensure-QwenChromeCdp {
  if (Assert-ProjectChromeOwnership $QwenCdpPort $QwenProfile $QwenRuntimeLabel) { return }

  $chrome = Get-ChromeExecutable
  if (-not $chrome) { throw 'Chrome not found for Qwen Web CDP runtime' }

  New-Item -ItemType Directory -Force $QwenProfile | Out-Null
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$QwenCdpPort",
    '--remote-debugging-address=127.0.0.1',
    "--user-data-dir=$QwenProfile",
    '--no-first-run',
    '--disable-default-apps',
    '--new-window',
    'https://chat.qwen.ai/'
  ) | Out-Null
  Start-Sleep -Seconds 6
  if (-not (Assert-ProjectChromeOwnership $QwenCdpPort $QwenProfile $QwenRuntimeLabel)) {
    throw 'Qwen Web project-owned Chrome CDP runtime did not start'
  }
}

function Stop-QwenChromeCdp {
  # Prefer graceful CDP browser close so cookies/local storage/session state
  # are flushed. Force kill is only a final fallback for remaining project-owned
  # processes after a short grace period.
  if (Assert-ProjectChromeOwnership $QwenCdpPort $QwenProfile $QwenRuntimeLabel) {
    try {
      Invoke-RestMethod "http://127.0.0.1:$QwenCdpPort/json/close" -TimeoutSec 3 | Out-Null
      Start-Sleep -Seconds 2
    } catch { }
  }
  $needle = [Regex]::Escape($QwenProfile)
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match $needle }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  if ($procs) { Start-Sleep -Milliseconds 500 }
}

function Ensure-ZaiChromeCdp {
  if (Assert-ProjectChromeOwnership $ZaiCdpPort $ZaiProfile $ZaiRuntimeLabel) { return }

  $chrome = Get-ChromeExecutable
  if (-not $chrome) { throw 'Chrome not found for Z.ai CDP runtime' }

  New-Item -ItemType Directory -Force $ZaiProfile | Out-Null
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$ZaiCdpPort",
    '--remote-debugging-address=127.0.0.1',
    "--user-data-dir=$ZaiProfile",
    '--no-first-run',
    '--disable-default-apps',
    '--new-window',
    'https://chat.z.ai/'
  ) | Out-Null
  Start-Sleep -Seconds 5
  if (-not (Assert-ProjectChromeOwnership $ZaiCdpPort $ZaiProfile $ZaiRuntimeLabel)) {
    throw 'Z.ai project-owned Chrome CDP runtime did not start'
  }
}

function Stop-ZaiChromeCdp {
  $needles = @([Regex]::Escape($ZaiProfile), [Regex]::Escape($ZaiLegacyProfile))
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
      $cmd = $_.CommandLine
      $cmd -and ($needles | Where-Object { $cmd -match $_ })
    }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  if ($procs) { Start-Sleep -Milliseconds 500 }
}

function Ensure-DeepSeekChromeCdp {
  if (Assert-ProjectChromeOwnership $DeepSeekCdpPort $DeepSeekProfile $DeepSeekRuntimeLabel) { return }

  $chrome = Get-ChromeExecutable
  if (-not $chrome) { throw 'Chrome not found for DeepSeek Web CDP runtime' }

  New-Item -ItemType Directory -Force $DeepSeekProfile | Out-Null
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$DeepSeekCdpPort",
    '--remote-debugging-address=127.0.0.1',
    "--user-data-dir=$DeepSeekProfile",
    '--no-first-run',
    '--disable-default-apps',
    '--new-window',
    'https://chat.deepseek.com/'
  ) | Out-Null
  Start-Sleep -Seconds 6
  if (-not (Assert-ProjectChromeOwnership $DeepSeekCdpPort $DeepSeekProfile $DeepSeekRuntimeLabel)) {
    throw 'DeepSeek Web project-owned Chrome CDP runtime did not start'
  }
}

function Stop-DeepSeekChromeCdp {
  $needle = [Regex]::Escape($DeepSeekProfile)
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match $needle }
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
  }
  if ($procs) { Start-Sleep -Milliseconds 500 }
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
   & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" | Out-Null
   Write-Output "INSTALLED $ServiceName"
   Write-Output "RUNTIME_CREDENTIAL_READY source=.env+nssm_environment"
 }
 'start' {
   $runtimeCredential = Ensure-RuntimeCredential
   & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" | Out-Null
   Ensure-ChatGPTChromeCdp
   Ensure-QwenChromeCdp
   Ensure-ZaiChromeCdp
   Ensure-DeepSeekChromeCdp
   Start-Service $ServiceName
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'stop' {
   Stop-Service $ServiceName -Force
   Stop-QwenChromeCdp
   Stop-ChatGPTChromeCdp
   Stop-ZaiChromeCdp
   Stop-DeepSeekChromeCdp
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'restart' {
   Stop-Service $ServiceName -Force
   $runtimeCredential = Ensure-RuntimeCredential
   & $Nssm set $ServiceName AppEnvironmentExtra "BRIDGE_API_KEY=$($runtimeCredential.ApiKey)" "BRIDGE_API_IDENTITY=$($runtimeCredential.Identity)" | Out-Null
   # Keep Qwen's authenticated CDP runtime alive across service restarts so
   # the official-login session is not disturbed. Ensure-* verifies ownership
   # and starts it only when it is missing.
   Stop-ChatGPTChromeCdp
   Stop-ZaiChromeCdp
   Ensure-ChatGPTChromeCdp
   Ensure-QwenChromeCdp
   Ensure-ZaiChromeCdp
   Ensure-DeepSeekChromeCdp
   Start-Service $ServiceName
   Start-Sleep -Seconds 1
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'status' { Get-Service $ServiceName }
 'uninstall' {
   foreach ($name in @($ServiceName, $LegacyServiceName)) {
     if (Get-Service $name -ErrorAction SilentlyContinue) {
       Stop-Service $name -Force -ErrorAction SilentlyContinue
       & $Nssm remove $name confirm | Out-Null
       Write-Output "REMOVED $name"
     }
   }
   Stop-QwenChromeCdp
   Stop-ChatGPTChromeCdp
   Stop-ZaiChromeCdp
   Stop-DeepSeekChromeCdp
 }
 'logs' { Get-Content (Join-Path $ScriptDir 'logs\bridge.log') -Tail 80 }
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
     bind='127.0.0.1:5000'
     chatgpt_cdp="127.0.0.1:$ChatGPTCdpPort"
     chatgpt_profile=$ChatGPTProfile
     qwen_cdp="127.0.0.1:$QwenCdpPort"
     qwen_profile=$QwenProfile
     zai_cdp="127.0.0.1:$ZaiCdpPort"
     zai_profile=$ZaiProfile
     deepseek_cdp="127.0.0.1:$DeepSeekCdpPort"
     deepseek_profile=$DeepSeekProfile
   } | ConvertTo-Json
 }
}
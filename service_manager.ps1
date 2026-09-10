<# Web LLM Bridge Service Manager (NSSM) #>
param(
 [Parameter(Mandatory=$true,Position=0)]
 [ValidateSet('install','uninstall','start','stop','restart','status','logs','config')]
 [string]$Command
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ServiceName = 'WebLLMBridge'
$PythonExe = Join-Path $ScriptDir '.venv\Scripts\python.exe'
$MainScript = Join-Path $ScriptDir 'main.py'
$Nssm = 'D:\nssm-2.24-103-gdee49fc\win64\nssm.exe'
$EnvFile = Join-Path $ScriptDir '.env'
$QwenProfile = Join-Path $ScriptDir '.runtime\qwen-profile'
$ZaiProfile = Join-Path $ScriptDir '.runtime\zai-profile'
$ZaiLegacyProfile = Join-Path $ScriptDir '.runtime\zai-cdp-profile'
$ZaiRuntimeLabel = 'MWB-Zai-Web-SSE-Capture'
$ZaiCdpPort = 9223

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

function Ensure-ZaiChromeCdp {
  $existing = Get-NetTCPConnection -LocalPort $ZaiCdpPort -State Listen -ErrorAction SilentlyContinue
  if ($existing) { return }

  $chromeCandidates = @(
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
  )
  $chrome = $chromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
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
   Ensure-ZaiChromeCdp
   Start-Service $ServiceName
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'stop' {
   Stop-Service $ServiceName -Force
   Stop-OrphanQwenBrowsers
   Stop-ZaiChromeCdp
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'restart' {
   Stop-Service $ServiceName -Force
   Stop-OrphanQwenBrowsers
   Stop-ZaiChromeCdp
   Ensure-ZaiChromeCdp
   Start-Service $ServiceName
   Start-Sleep -Seconds 1
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'status' { Get-Service $ServiceName }
 'uninstall' {
   if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
     Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
     Stop-OrphanQwenBrowsers
     Stop-ZaiChromeCdp
     & $Nssm remove $ServiceName confirm | Out-Null
   }
   Write-Output "REMOVED $ServiceName"
 }
 'logs' { Get-Content (Join-Path $ScriptDir 'logs\bridge.log') -Tail 80 }
 'config' {
   Assert-Prereqs
   [ordered]@{
     service=$ServiceName
     python=$PythonExe
     app=$MainScript
     directory=$ScriptDir
     nssm=$Nssm
     runtime_credential_source='.env+nssm_environment'
     bind='127.0.0.1:5000'
     zai_cdp="127.0.0.1:$ZaiCdpPort"
     zai_profile=$ZaiProfile
   } | ConvertTo-Json
 }
}
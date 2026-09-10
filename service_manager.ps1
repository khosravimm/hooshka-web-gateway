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
   Start-Service $ServiceName
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'stop' {
   Stop-Service $ServiceName -Force
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'restart' {
   Restart-Service $ServiceName -Force
   Start-Sleep -Seconds 1
   (Get-Service $ServiceName) | Format-Table -AutoSize
 }
 'status' { Get-Service $ServiceName }
 'uninstall' {
   if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
     Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
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
   } | ConvertTo-Json
 }
}
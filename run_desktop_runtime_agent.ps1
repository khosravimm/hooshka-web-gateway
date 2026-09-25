$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Agent = Join-Path $Root 'desktop_runtime_agent.py'
$Log = Join-Path $Root 'logs\desktop-runtime-agent-supervisor.log'
New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null
function Log([string]$Message) { Add-Content -Path $Log -Value ("{0:o} {1}" -f (Get-Date), $Message) }
if (-not (Test-Path $Python)) { throw "Python runtime not found: $Python" }
if (-not (Test-Path $Agent)) { throw "Desktop runtime agent not found: $Agent" }
Log 'SUPERVISOR_START'
while ($true) {
  $started = Get-Date
  Log 'AGENT_START'
  & $Python $Agent
  $code = $LASTEXITCODE
  $elapsed = [int]((Get-Date) - $started).TotalSeconds
  Log ("AGENT_EXIT code={0} elapsed_seconds={1}; restarting in 2s" -f $code, $elapsed)
  Start-Sleep -Seconds 2
}

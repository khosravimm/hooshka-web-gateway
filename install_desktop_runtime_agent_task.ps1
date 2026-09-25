$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Agent = Join-Path $Root 'desktop_runtime_agent.py'
$Supervisor = Join-Path $Root 'run_desktop_runtime_agent.ps1'
if (-not (Test-Path $Python)) { throw "Python venv not found: $Python" }
if (-not (Test-Path $Agent)) { throw "Desktop runtime agent not found: $Agent" }
if (-not (Test-Path $Supervisor)) { throw "Desktop runtime supervisor not found: $Supervisor" }
Push-Location $Root
try {
  $cfg = (& $Python -m core.runtime_inventory | ConvertFrom-Json)
} finally { Pop-Location }
$TaskName = [string]$cfg.orchestration.desktop_agent_task
if (-not $TaskName) { throw 'desktop_agent_task is not configured' }
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $Supervisor) -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Output "INSTALLED_AND_STARTED $TaskName user=$User"
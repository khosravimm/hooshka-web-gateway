<# Web LLM Bridge Service Manager #>
param(
 [Parameter(Mandatory=$true,Position=0)]
 [ValidateSet('install','uninstall','start','stop','restart','status','logs','config')]
 [string]$Command
)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonExe = Join-Path $ScriptDir '.venv\Scripts\python.exe'
$MainScript = Join-Path $ScriptDir 'bridge_service.py'

switch ($Command) {
 'install' {
   & $PythonExe $MainScript install --startup auto
 }
 'start' {
   & $PythonExe $MainScript start
 }
 'stop' {
   & $PythonExe $MainScript stop
 }
 'restart' {
   & $PythonExe $MainScript restart
 }
 'status' {
   Get-Service WebLLMBridge
 }
 'uninstall' {
   & $PythonExe $MainScript remove
 }
 'logs' { Get-Content (Join-Path $ScriptDir 'logs\bridge.log') -Tail 50 }
}

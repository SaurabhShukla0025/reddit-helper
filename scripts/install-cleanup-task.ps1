param([string]$PythonPath)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonPath) { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
$pythonExe = (Resolve-Path -LiteralPath $PythonPath).Path
$pythonWindowless = Join-Path (Split-Path -Parent $pythonExe) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw 'pythonw.exe is required for hidden cleanup.' }
$entry = Join-Path $projectRoot 'main.py'
$taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($projectRoot.ToLowerInvariant())) }
finally { $sha.Dispose() }
$suffix = ([System.BitConverter]::ToString($digest)).Replace('-', '').Substring(0, 12)
$taskName = 'ContributionHelper-Cleanup-' + $suffix
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { throw "Task $taskName already exists. Inspect it rather than replacing it." }
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument ('"' + $entry + '" cleanup') -WorkingDirectory $projectRoot
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $taskIdentity
$principal = New-ScheduledTaskPrincipal -UserId $taskIdentity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($hourly, $logon) -Principal $principal -Settings $settings -Description 'Local-only retention cleanup. No API credentials or Reddit calls.' | Out-Null
@{task_name=$taskName; project_root=$projectRoot; account=$taskIdentity; mode='hourly-and-logon-interactive'; installed_at=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot '.cleanup-task.json') -Encoding utf8
Start-ScheduledTask -TaskName $taskName
Write-Output "Installed and started $taskName. Runs hourly and at logon while this user is logged in; catches up when available."

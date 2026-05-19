param(
    [string]$TaskName = "Philippines_Coconut_Weather_Daily",
    [string]$RunTime = "08:20"
)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "run_update.bat"
$Action = New-ScheduledTaskAction -Execute $BatPath
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily Philippines coconut/CNO weather monitor" -Force
Write-Host "Created daily task: $TaskName at $RunTime"

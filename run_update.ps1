param(
    [string]$EndDate = "",
    [string]$Lookbacks = "7,14,30,90",
    [string]$Formats = "xlsx,html,docx",
    [string]$HistoryStart = "1981-01-01",
    [int]$ForecastDays = 16,
    [switch]$Quick,
    [switch]$Force,
    [switch]$NoBuildSite
)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$cmd = @("run_update.py", "--lookbacks", $Lookbacks, "--formats", $Formats, "--history-start", $HistoryStart, "--forecast-days", "$ForecastDays")
if ($EndDate -ne "") { $cmd += @("--end", $EndDate) }
if ($Quick) { $cmd += "--quick" }
if ($Force) { $cmd += "--force" }
if (-not $NoBuildSite) { $cmd += @("--build-site", "--site-dir", "site") }
python @cmd

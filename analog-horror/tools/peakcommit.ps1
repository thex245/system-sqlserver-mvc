# Run a command and report the lowest system free-commit seen while it runs (Windows).
param([string]$Exe, [string]$ArgString, [string]$Log = "$env:TEMP\peak.log")
$os = Get-CimInstance Win32_OperatingSystem
$start = $os.FreeVirtualMemory
$p = Start-Process -FilePath $Exe -ArgumentList $ArgString -RedirectStandardOutput $Log -RedirectStandardError "$Log.err" -PassThru -NoNewWindow
$min = $start
while (-not $p.HasExited) {
    Start-Sleep -Milliseconds 400
    $f = (Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory
    if ($f -lt $min) { $min = $f }
}
"free commit before {0:N2} GB, min during {1:N2} GB, used by run {2:N2} GB, exit {3}" -f ($start / 1MB), ($min / 1MB), (($start - $min) / 1MB), $p.ExitCode

# Run a command and report its peak private memory (Windows).
# usage: peakmem.ps1 -Exe blender.exe -ArgString '-b file.blend --python x.py -- a b'
param([string]$Exe, [string]$ArgString, [string]$Log = "$env:TEMP\peak.log")
$p = Start-Process -FilePath $Exe -ArgumentList $ArgString -RedirectStandardOutput $Log -RedirectStandardError "$Log.err" -PassThru -NoNewWindow
$peak = 0
while (-not $p.HasExited) {
    Start-Sleep -Milliseconds 500
    try { $p.Refresh(); if ($p.PrivateMemorySize64 -gt $peak) { $peak = $p.PrivateMemorySize64 } } catch {}
}
"peak private GB: {0:N2}" -f ($peak / 1GB)

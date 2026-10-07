# Iterate: assemble -> contact QA -> offsets (tables / diners / chairs), N rounds.
param([int]$Rounds = 3, [switch]$Reset)
$env:TEMP = 'D:\VAMA_work\tmp'; $env:TMP = 'D:\VAMA_work\tmp'
$b = 'D:\Steam\steamapps\common\Blender\blender.exe'
$py = 'D:\VAMA_work\venv\Scripts\python.exe'
if ($Reset) { foreach ($f in 'table_offsets', 'diner_offsets', 'chair_offsets') { [System.IO.File]::WriteAllText("D:\VAMA_work\blend\$f.json", '{}') } }
for ($i = 1; $i -le $Rounds; $i++) {
    & $b -b --factory-startup D:\VAMA_work\blend\set.blend --python analog-horror\blender\assemble.py -- D:\VAMA_work\blend\film.blend > D:\VAMA_work\tmp\assemble.log 2>&1
    if (-not (Select-String -Path D:\VAMA_work\tmp\assemble.log -Pattern '^SAVED' -Quiet)) { "assemble failed"; Select-String -Path D:\VAMA_work\tmp\assemble.log -Pattern 'Error|Traceback|line \d+' | Select-Object -First 8 | ForEach-Object { $_.Line }; break }
    & $b -b --factory-startup D:\VAMA_work\blend\film.blend --python analog-horror\blender\qa_contacts.py -- "D:\VAMA_work\tmp\qa_round$i.json" 5 > D:\VAMA_work\tmp\qa_contacts.log 2>&1
    "== round $i"
    Select-String -Path D:\VAMA_work\tmp\qa_contacts.log -Pattern '^QA' | ForEach-Object { ($_.Line -split '\{')[0] }
    if ($i -lt $Rounds) { & $py analog-horror\blender\table_offsets.py "D:\VAMA_work\tmp\qa_round$i.json" D:\VAMA_work\blend\table_offsets.json | Select-Object -Last 2 }
}

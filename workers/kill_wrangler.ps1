# 找出執行 wrangler dev 的 node 程序並結束（及其 workerd 子程序）
$procs = Get-CimInstance Win32_Process
$targets = $procs | Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'wrangler|workerd' }
foreach ($p in $targets) {
    Write-Output "kill node $($p.ProcessId) :: $($p.CommandLine.Substring(0, [Math]::Min(100, $p.CommandLine.Length)))"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Get-Process workerd -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "kill workerd $($_.Id)"; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

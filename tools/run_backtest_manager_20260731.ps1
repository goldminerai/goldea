param(
  [ValidateSet('scan','watch')]
  [string]$Mode = 'scan',
  [int]$Interval = 30
)

$python = 'C:\Users\Custom\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$repo = 'D:\GitHub\goldea'
$script = Join-Path $repo 'tools\backtest_manager_20260731.py'
$sources = @(
  'D:\GitHub\goldea\incoming_backtests',
  'D:\Workspace\00_Inbox\From_Downloads',
  'C:\Users\Custom\AppData\Roaming\MetaQuotes\Terminal'
)

$args = @($script, $Mode, '--repo', $repo, '--interval', $Interval)
foreach ($source in $sources) { $args += @('--source', $source) }
& $python @args

# Copy the v6.50 US100.cash tester book into every MT5 data folder on this PC.
# Does not stop terminal64.exe. Close MT5, run this, then open MT5 again.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcExpert = Join-Path $root "MQL5\Experts\RobustForexEA.mq5"
$srcEx5 = Join-Path $root "MQL5\Experts\RobustForexEA.ex5"
$srcSet = Join-Path $root "MQL5\Profiles\Tester\RobustForexEA.set"
foreach ($need in @($srcExpert, $srcEx5, $srcSet)) {
    if (-not (Test-Path $need)) { throw "Missing $need. Run git pull in the mt5bot folder first." }
}

$fromUnix = [DateTimeOffset]::new(2026, 1, 1, 0, 0, 0, [TimeSpan]::Zero).ToUnixTimeSeconds()
$toUnix = [DateTimeOffset]::new(2026, 10, 26, 0, 0, 0, [TimeSpan]::Zero).ToUnixTimeSeconds()

function Read-MtText([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    $utf16 = ($bytes.Length -ge 2 -and $bytes[0] -eq 255 -and $bytes[1] -eq 254)
    if ($utf16) {
        return @{ Text = [Text.Encoding]::Unicode.GetString($bytes); Utf16 = $true }
    }
    return @{ Text = [Text.Encoding]::UTF8.GetString($bytes); Utf16 = $false }
}

function Write-MtText([string]$Path, [string]$Text, [bool]$Utf16) {
    $enc = if ($Utf16) { [Text.Encoding]::Unicode } else { New-Object System.Text.UTF8Encoding $false }
    $payload = $enc.GetBytes($Text)
    if ($Utf16) { $payload = $enc.GetPreamble() + $payload }
    [IO.File]::WriteAllBytes($Path, $payload)
}

function Update-IniSection([string]$Path, [string]$Section, [object[]]$Pairs) {
    $dir = Split-Path $Path
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $utf16 = $false
    $newline = "`r`n"
    $lines = @()
    if (Test-Path $Path) {
        $read = Read-MtText $Path
        $utf16 = $read.Utf16
        if ($read.Text.Contains("`r`n")) { $newline = "`r`n" } else { $newline = "`n" }
        $lines = [regex]::Split($read.Text, "`r?`n")
    }
    $map = [ordered]@{}
    foreach ($pair in $Pairs) { $map[$pair[0]] = $pair[1] }
    $out = New-Object System.Collections.Generic.List[string]
    $inSection = $false
    $seen = @{}
    $found = $false
    foreach ($line in $lines) {
        if ($line -match '^\[(.+)\]\s*$') {
            if ($inSection) {
                foreach ($key in $map.Keys) {
                    if (-not $seen.ContainsKey($key)) { $out.Add("$key=$($map[$key])") }
                }
                $inSection = $false
            }
            $found = $found -or ($Matches[1] -eq $Section)
            $inSection = ($Matches[1] -eq $Section)
            $out.Add($line)
            continue
        }
        if ($inSection -and $line -match '^([^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $hit = $null
            foreach ($name in $map.Keys) {
                if ($name -eq $key) { $hit = $name; break }
            }
            if ($hit) {
                $out.Add("$hit=$($map[$hit])")
                $seen[$hit] = $true
                continue
            }
        }
        $out.Add($line)
    }
    if ($inSection) {
        foreach ($key in $map.Keys) {
            if (-not $seen.ContainsKey($key)) { $out.Add("$key=$($map[$key])") }
        }
    } elseif (-not $found) {
        if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne "") { $out.Add("") }
        $out.Add("[$Section]")
        foreach ($key in $map.Keys) { $out.Add("$key=$($map[$key])") }
    }
    Write-MtText $Path (($out -join $newline).TrimEnd() + $newline) $utf16
}

$terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$folders = @()
if (Test-Path $terminalRoot) {
    $folders = Get-ChildItem $terminalRoot -Directory | Where-Object { $_.Name -match '^[0-9A-Fa-f]{32}$' }
}
if ($folders.Count -eq 0) {
    Write-Output "No MT5 data folder under $terminalRoot."
    Write-Output "Open MetaTrader 5 once, close it, then run this again."
    exit 1
}

$running = Get-Process terminal64 -ErrorAction SilentlyContinue
if ($running) {
    Write-Output "MetaTrader is open. Files will be copied, but a running terminal can ignore them until you close it and open it again."
    Write-Output "This script will not close MetaTrader."
}

$setText = (Read-MtText $srcSet).Text
$inputLines = @()
$keep = $false
foreach ($line in ([regex]::Split($setText, "`r?`n"))) {
    if ($line -match '^; Model' -or $line -match '^Inp') { $keep = $true }
    if ($keep -and $line.Trim() -ne "") { $inputLines += $line }
}
$profile = @(
    ";Expert Advisor single test: RobustForexEA, US100.cash M5, real ticks, 2026.01.01 - 2026.10.26"
    "[Tester]"
    "Expert=RobustForexEA.ex5"
    "Symbol=US100.cash"
    "Period=M5"
    "Optimization=0"
    "Model=4"
    "FromDate=2026.01.01"
    "ToDate=2026.10.26"
    "ForwardMode=0"
    "Deposit=100000"
    "Currency=USD"
    "ProfitInPips=0"
    "Leverage=100"
    "ExecutionMode=0"
    "OptimizationCriterion=0"
    "Visual=0"
    "[TesterInputs]"
) + $inputLines

$dialogKeys = @(
    @("LastExpert", "Experts\RobustForexEA.ex5"),
    @("Expert", "Experts\RobustForexEA.ex5"),
    @("Symbol", "US100.cash"),
    @("Period", "5"),
    @("DateRange", "3"),
    @("DateFrom", "$fromUnix"),
    @("DateTo", "$toUnix"),
    @("Deposit", "100000.00"),
    @("Currency", "USD")
)
$commonKeys = @(
    @("Expert", "RobustForexEA.ex5"),
    @("Symbol", "US100.cash"),
    @("Period", "M5"),
    @("FromDate", "2026.01.01"),
    @("ToDate", "2026.10.26")
)

foreach ($folder in $folders) {
    Write-Output "Updating $($folder.FullName)"
    $experts = Join-Path $folder.FullName "MQL5\Experts"
    $tester = Join-Path $folder.FullName "MQL5\Profiles\Tester"
    New-Item -ItemType Directory -Force -Path $experts, $tester | Out-Null
    Copy-Item $srcExpert (Join-Path $experts "RobustForexEA.mq5") -Force
    Copy-Item $srcEx5 (Join-Path $experts "RobustForexEA.ex5") -Force
    Copy-Item $srcSet (Join-Path $tester "RobustForexEA.set") -Force
    $iniName = "RobustForexEA.US100.cash.M5.20260101_20261026.400.ini"
    Write-MtText (Join-Path $tester $iniName) (($profile -join "`r`n") + "`r`n") $false
    Update-IniSection (Join-Path $folder.FullName "config\terminal.ini") "Tester" $dialogKeys
    Update-IniSection (Join-Path $folder.FullName "config\common.ini") "Tester" $commonKeys
}

Write-Output ""
Write-Output "Strategy Tester is set to RobustForexEA.ex5, US100.cash, M5, 2026.01.01-2026.10.26, v6.50 inputs."
Write-Output "Close MetaTrader if it is open, then start it again and open View -> Strategy Tester."
Write-Output "Not started for you, so a live terminal stays untouched."

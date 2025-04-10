# Save this as Enhanced-Bootstrap3-Audit.ps1
$structuralResults = @()

# Define a more comprehensive pattern set with categories
$auditPatterns = @{
    'Grid System' = @(
        '\bcol-xs-\d+\b', '\bcol-sm-\d+\b', '\bcol-md-\d+\b', '\bcol-lg-\d+\b',
        '\brow\b', '\bcontainer-fluid\b', '\bvisible-\w+\b', '\bhidden-\w+\b'
    )
    'Components' = @(
        '\bpanel\b', '\bpanel-heading\b', '\bpanel-body\b', '\bpanel-footer\b', '\bpanel-title\b',
        '\bpanel-(default|primary|success|info|warning|danger)\b',
        '\bwell\b', '\bjumbotron\b', '\bprogress-bar\b', '\bmedia\b', '\bmedia-body\b',
        '\bcarousel\b', '\bcarousel-inner\b', '\bcarousel-control\b',
        '\bdropdown\b', '\bdropdown-toggle\b', '\bdropdown-menu\b'
    )
    'Navigation' = @(
        '\bnavbar(-default|-inverse|-fixed-\w+)?\b', '\bnavbar-header\b', '\bnavbar-collapse\b',
        '\bnavbar-toggle\b', '\bnavbar-brand\b', '\bnavbar-nav\b', '\bnavbar-form\b',
        '\bnav(-tabs|-pills|-stacked)?\b'
    )
    'Forms' = @(
        '\bform-control\b', '\bform-group\b', '\bform-control-static\b', '\bform-horizontal\b',
        '\bform-inline\b', '\bhelp-block\b', '\bcontrol-label\b', '\binput-group\b',
        '\binput-group-addon\b', '\binput-sm\b', '\binput-lg\b', '\bhas-error\b', '\bhas-success\b'
    )
    'Buttons' = @(
        '\bbtn(-default|-primary|-success|-info|-warning|-danger|-link)?\b',
        '\bbtn-group\b', '\bbtn-toolbar\b', '\bbtn-xs\b', '\bbtn-sm\b', '\bbtn-lg\b'
    )
    'Utilities' = @(
        '\bpull-(left|right)\b', '\bclearfix\b', '\bshow\b', '\bhidden\b', '\bvisible-\w+\b',
        '\btext-(left|right|center|justify|nowrap|lowercase|uppercase|capitalize)\b',
        '\btext-(muted|primary|success|info|warning|danger)\b',
        '\bbg-(primary|success|info|warning|danger)\b'
    )
    'JS Components' = @(
        '\bmodal\b', '\bmodal-dialog\b', '\bmodal-content\b', '\bmodal-header\b', '\bmodal-body\b',
        '\bmodal-footer\b', '\btab\b', '\btab-content\b', '\btab-pane\b', '\bpopover\b', '\btooltip\b',
        '\bcollapse\b', '\balert\b', '\balert-dismissible\b'
    )
    'jQuery Dependencies' = @(
        'jQuery\(', '\$\(', '\.modal\(', '\.collapse\(', '\.dropdown\(', '\.tab\(', 
        '\.tooltip\(', '\.popover\(', '\.alert\(', '\.carousel\('
    )
    'Structural Changes' = @(
        '<div class="[^"]*panel[^"]*"', '<div class="[^"]*navbar[^"]*"',
        '<div class="[^"]*carousel[^"]*"', '<div class="[^"]*modal[^"]*"'
    )
}

$extensions = '*.html', '*.htm', '*.js', '*.css', '*.cshtml', '*.razor', '*.vue', '*.jsx', '*.tsx'

# Create a directory for the audit output
$auditDir = ".\bootstrap3_audit"
New-Item -ItemType Directory -Force -Path $auditDir | Out-Null

Write-Host "Starting comprehensive Bootstrap 3 audit..." -ForegroundColor Cyan

# Initialize results collection
$results = @()
$categoryCounts = @{}
$auditPatterns.Keys | ForEach-Object { $categoryCounts[$_] = 0 }

# Main file scanning loop
foreach ($ext in $extensions) {
    Get-ChildItem -Recurse -Include $ext -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $file = $_.FullName
            $relativePath = $file.Substring((Get-Location).Path.Length).TrimStart('\')
            $lines = Get-Content $file -ErrorAction Stop
            
            # Skip files in node_modules and dist folders
            if ($relativePath -match "node_modules|dist|bin\\") {
                return
            }
            
            for ($i = 0; $i -lt $lines.Length; $i++) {
                foreach ($category in $auditPatterns.Keys) {
                    foreach ($pattern in $auditPatterns[$category]) {
                        if ($lines[$i] -match $pattern) {
                            $lineNumber = $i + 1
                            $match = $lines[$i].Trim()
                            $results += [PSCustomObject]@{
                                FilePath = $relativePath
                                LineNumber = $lineNumber
                                Category = $category
                                Pattern = $pattern
                                Match = $match
                            }
                            $categoryCounts[$category]++
                            
                            # For structural patterns, capture context (few lines before and after)
                            if ($category -eq "Structural Changes") {
                                $contextStart = [Math]::Max(0, $i - 2)
                                $contextEnd = [Math]::Min($lines.Length - 1, $i + 2)
                                $context = @()
                                for ($j = $contextStart; $j -le $contextEnd; $j++) {
                                    $context += "Line $($j+1): $($lines[$j])"
                                }
                                
                                $structuralResults += [PSCustomObject]@{
                                    FilePath = $relativePath
                                    LineNumber = $lineNumber
                                    Pattern = $pattern
                                    Context = $context -join "`n"
                                }
                            }
                        }
                    }
                }
            }
        }
        catch {
            Write-Host "Error processing file $($file): $_" -ForegroundColor Red
        }
    }
}

# Generate summary report
Write-Host "`nBootstrap 3 Audit Summary:" -ForegroundColor Yellow
$totalMatches = 0
foreach ($category in $auditPatterns.Keys) {
    $count = $categoryCounts[$category]
    $totalMatches += $count
    Write-Host "$category`: $count matches" -ForegroundColor $(if ($count -gt 0) { "Yellow" } else { "Green" })
}
Write-Host "Total: $totalMatches matches" -ForegroundColor $(if ($totalMatches -gt 0) { "Yellow" } else { "Green" })

# Generate CSV reports
$results | Export-Csv -Path "$auditDir\bootstrap3_audit_report.csv" -NoTypeInformation
$results | Group-Object -Property Category | ForEach-Object {
    $categoryName = $_.Name
    $_.Group | Export-Csv -Path "$auditDir\bootstrap3_audit_$($categoryName -replace ' ', '_').csv" -NoTypeInformation
}

# Generate an HTML report for easier review
[string]$htmlReport = ''
$htmlReport = @"
<!DOCTYPE html>
<html>
<head>
    <title>Bootstrap 3 to 5 Migration Audit</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; }
        h1, h2 { color: #0066cc; }
        .summary { margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }
        .category { margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .file-path { max-width: 250px; overflow: hidden; text-overflow: ellipsis; }
        .file-link { color: #0066cc; text-decoration: none; }
        .file-link:hover { text-decoration: underline; }
        .match { font-family: monospace; background-color: #f5f5f5; padding: 2px 4px; }
    </style>
</head>
<body>
    <h1>Bootstrap 3 to 5 Migration Audit</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total matches: $totalMatches</p>
        <ul>
"@

foreach ($category in $auditPatterns.Keys) {
    $count = $categoryCounts[$category]
    $htmlReport += "<li>${category}: ${count} matches</li>`n"
}

$htmlReport += @"
        </ul>
    </div>
"@

foreach ($category in $auditPatterns.Keys) {
    $categoryResults = $results | Where-Object { $_.Category -eq $category }
    if ($categoryResults.Count -gt 0) {
        $htmlReport += @"
    <div class="category">
        <h2>$category</h2>
        <table>
            <tr>
                <th>File</th>
                <th>Line</th>
                <th>Pattern</th>
                <th>Match</th>
            </tr>
"@

        foreach ($result in $categoryResults) {
            $htmlReport += @"
            <tr>
                <td class="file-path"><a class="file-link" href="file:///$($result.FilePath)">$($result.FilePath)</a></td>
                <td>$($result.LineNumber)</td>
                <td>$($result.Pattern)</td>
                <td class="match">$($result.Match -replace '<', '&lt;' -replace '>', '&gt;')</td>
            </tr>
"@
        }

        $htmlReport += @"
        </table>
    </div>
"@
    }
}

$htmlReport += @"
</body>
</html>
"@

Set-Content -Path "$auditDir\bootstrap3_audit_report.html" -Value $htmlReport
Write-Host "`nAudit completed. Reports saved to '$auditDir'" -ForegroundColor Green
Write-Host "Open '$auditDir\bootstrap3_audit_report.html' for an interactive report" -ForegroundColor Cyan
param(
    [string]$SearchPath = ".\ad2web"
)

# --- Configuration ---
$FileExtensions = "*.js", "*.html"
$ExclusionRegex = '[\\/](static[\\/](js[\\/]vendor|css|img|fonts|bootstrap3|bootstrap5|swagger)|bootstrap3_backup|bootstrap3_audit|bootstrap3_migration_logs|_pgbackup)[\\/]'

Write-Host "Starting search for potential usage of specific JS files..."
Write-Host "Searching within: $SearchPath"
Write-Host "Excluding paths matching regex: $ExclusionRegex`n" -ForegroundColor Gray

# --- Check 1: Bootstrap Datepicker ---
Write-Host "--- [1] Checking for Bootstrap Datepicker Usage ---" -ForegroundColor Cyan
$patternDatepicker = '\.datepicker\('
$datepickerFiles = @()

try {
    Get-ChildItem -Path $SearchPath -Recurse -Include $FileExtensions -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.FullName -notmatch $ExclusionRegex) {
            if (Select-String -Path $_.FullName -Pattern $patternDatepicker -Quiet) {
                $datepickerFiles += $_.FullName
            }
        }
    }
} catch {
    Write-Warning "An error occurred during Datepicker search: $($_.Exception.Message)"
}

if ($datepickerFiles.Count -gt 0) {
    Write-Host "[WARN] '.datepicker(' usage found. Review before deleting 'bootstrap-datepicker.js'." -ForegroundColor Yellow
    Write-Host "   Files potentially using it:"
    $datepickerFiles | Select-Object -Unique | ForEach-Object { Write-Host "   - $_" }
} else {
    Write-Host "[OK] No usage of '.datepicker(' found." -ForegroundColor Green
    Write-Host "   Consider deleting 'ad2web/static/js/vendor/bootstrap-datepicker.js'."
}
Write-Host ""

# --- Check 2: DataTables TableTools ---
Write-Host "--- [2] Checking for DataTables TableTools Usage ---" -ForegroundColor Cyan

# Simplified regex to look for 'TableTools' or dom/sDom containing 'T'
$patternsTableTools = @(
    'TableTools',
    "sDom\s*[:=]\s*[`"'][^`"']*T[^`"']*[`"']",
    "dom\s*[:=]\s*[`"'][^`"']*T[^`"']*[`"']"
)

$tableToolsFiles = @()

try {
    Get-ChildItem -Path $SearchPath -Recurse -Include $FileExtensions -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.FullName -notmatch $ExclusionRegex) {
            if (Select-String -Path $_.FullName -Pattern $patternsTableTools -Quiet) {
                $tableToolsFiles += $_.FullName
            }
        }
    }
} catch {
    Write-Warning "An error occurred during TableTools search: $($_.Exception.Message)"
}

if ($tableToolsFiles.Count -gt 0) {
    Write-Host "[WARN] 'TableTools' or legacy sDom/dom options with 'T' found." -ForegroundColor Yellow
    Write-Host "   Review before deleting 'dataTables.tableTools.js'."
    Write-Host "   Files potentially using it:"
    $tableToolsFiles | Select-Object -Unique | ForEach-Object { Write-Host "   - $_" }
} else {
    Write-Host "[OK] No 'TableTools' or 'sDom/dom' with 'T' found." -ForegroundColor Green
    Write-Host "   Consider deleting 'ad2web/static/js/vendor/dataTables.tableTools.js'."
}
Write-Host ""

# --- Check 3: Unminified DataTables JS ---
Write-Host "--- [3] Checking for Direct Links to Unminified DataTables JS ---" -ForegroundColor Cyan
$patternsDtFiles = @('jquery\.dataTables\.js', 'datatables\.js')
$dtLinkFiles = @()

try {
    Get-ChildItem -Path $SearchPath -Recurse -Include $FileExtensions -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.FullName -notmatch $ExclusionRegex) {
            if (Select-String -Path $_.FullName -Pattern $patternsDtFiles -Quiet) {
                $matchResults = Select-String -Path $_.FullName -Pattern $patternsDtFiles -AllMatches
                foreach ($m in $matchResults.Matches) {
                    if ($m.Value -ne 'datatables.min.js') {
                        $dtLinkFiles += "$($_.FullName) (found '$($m.Value)')"
                        break
                    }
                }
            }
        }
    }
} catch {
    Write-Warning "An error occurred during DataTables filename search: $($_.Exception.Message)"
}

$dtLinkFiles = $dtLinkFiles | Select-Object -Unique

if ($dtLinkFiles.Count -gt 0) {
    Write-Host "[WARN] Found references to non-minified 'jquery.dataTables.js' or 'datatables.js'." -ForegroundColor Yellow
    Write-Host "   Verify these aren't active <script src=...> before deleting."
    Write-Host "   Files referencing them:"
    $dtLinkFiles | ForEach-Object { Write-Host "   - $_" }
} else {
    Write-Host "[OK] No references to unminified DataTables JS found." -ForegroundColor Green
    Write-Host "   You can likely remove unminified duplicates of 'datatables.min.js'."
}
Write-Host ""

# --- Final Note ---
Write-Host "Search Complete" -ForegroundColor Cyan
Write-Host "Please review the findings above. Don't forget to check 'ad2web/static/js/plugins.js' manually if unclear."
Write-Host "Use 'git rm' to stage deletions before committing." -ForegroundColor Gray

# Quick debug for Test 26
$LeftPath = "C:\pdrive_local"
$RightPath = "p:\"
$test_left = "$LeftPath\case_conflict_canonical"
$test_right = "$RightPath\case_conflict_canonical"

$canonicalLeftPath = "$test_left\casetest.txt"
$canonicalRightPath = "$test_right\casetest.txt"

Write-Host "Checking canonical content..." -ForegroundColor Cyan
$leftContent = Get-Content $canonicalLeftPath -Raw
$rightContent = Get-Content $canonicalRightPath -Raw

Write-Host "Left content length: $($leftContent.Length)" -ForegroundColor Yellow
Write-Host "Left content bytes: $([System.Text.Encoding]::UTF8.GetBytes($leftContent))" -ForegroundColor Gray
Write-Host "Right content length: $($rightContent.Length)" -ForegroundColor Yellow
Write-Host "Right content bytes: $([System.Text.Encoding]::UTF8.GetBytes($rightContent))" -ForegroundColor Gray

$matches1 = $leftContent -eq "NEW-RIGHT-CONTENT"
$matches2 = $rightContent -eq "NEW-RIGHT-CONTENT"
Write-Host "Left matches 'NEW-RIGHT-CONTENT': $matches1" -ForegroundColor $(if ($matches1) { "Green" } else { "Red" })
Write-Host "Right matches 'NEW-RIGHT-CONTENT': $matches2" -ForegroundColor $(if ($matches2) { "Green" } else { "Red" })

Write-Host "`nChecking conflict content..." -ForegroundColor Cyan
$conflictLeft = Get-ChildItem -LiteralPath $test_left -Filter "CaseTest.CONFLICT*.txt" | Select-Object -First 1
if ($conflictLeft) {
    $conflictContent = Get-Content $conflictLeft.FullName -Raw
    Write-Host "Conflict content length: $($conflictContent.Length)" -ForegroundColor Yellow
    Write-Host "Conflict content: '$conflictContent'" -ForegroundColor Gray
    $conflictMatches = $conflictContent -eq "older-left-case"
    Write-Host "Matches 'older-left-case': $conflictMatches" -ForegroundColor $(if ($conflictMatches) { "Green" } else { "Red" })
}

Write-Host "`nChecking old casing..." -ForegroundColor Cyan
$leftNames = Get-ChildItem -LiteralPath $test_left | Select-Object -ExpandProperty Name
Write-Host "Files in left: $($leftNames -join ', ')" -ForegroundColor Yellow
$hasOldCasing = $leftNames -contains "CaseTest.txt"
Write-Host "Has 'CaseTest.txt': $hasOldCasing" -ForegroundColor $(if (-not $hasOldCasing) { "Green" } else { "Red" })

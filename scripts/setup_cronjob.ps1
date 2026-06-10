# scripts/setup_cronjob.ps1
# Run this once to register the morning trigger on cron-job.org
#
# Usage:
#   $env:GITHUB_PAT = "your_github_pat"
#   $env:CRONJOB_TOKEN = "your_cronjob_org_token"
#   .\scripts\setup_cronjob.ps1

$GITHUB_PAT   = $env:GITHUB_PAT
$CRONJOB_TOKEN = $env:CRONJOB_TOKEN

if (-not $GITHUB_PAT -or -not $CRONJOB_TOKEN) {
    Write-Error "Set GITHUB_PAT and CRONJOB_TOKEN environment variables first."
    exit 1
}

$body = @{
    job = @{
        title         = "Linear Tinker Morning Trigger"
        url           = "https://api.github.com/repos/gejbuc/linear-tinker/actions/workflows/291200018/dispatches"
        enabled       = $true
        saveResponses = $true
        schedule      = @{
            timezone = "Africa/Nairobi"
            hours    = @(12)
            minutes  = @(0)
            mdays    = @(-1)
            months   = @(-1)
            wdays    = @(-1)
        }
        requestMethod = 1
        extendedData  = @{
            headers = @(
                @{ name = "Accept";              value = "application/vnd.github+json" }
                @{ name = "Authorization";       value = "Bearer $GITHUB_PAT" }
                @{ name = "User-Agent";          value = "cron-job-org-trigger" }
                @{ name = "X-GitHub-Api-Version"; value = "2022-11-28" }
            )
            body = '{"ref":"master"}'
        }
    }
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod `
    -Uri "https://api.cron-job.org/jobs" `
    -Method POST `
    -Headers @{ "Authorization" = "Bearer $CRONJOB_TOKEN" } `
    -ContentType "application/json" `
    -Body $body

Write-Host "Done. cron-job.org job ID: $($response.jobId)"

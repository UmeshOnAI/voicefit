# Creates one git worktree per agent, next to the main checkout.
# Run from the root of the voicefit repository after cloning.
$ErrorActionPreference = 'Stop'

$root = (git rev-parse --show-toplevel)
$wt = Join-Path (Split-Path $root -Parent) 'voicefit-wt'

git fetch origin
foreach ($name in 'coder', 'coder-ui', 'reviewer', 'tester') {
    $path = Join-Path $wt $name
    if (Test-Path $path) {
        Write-Host "exists: $path"
    } else {
        git worktree add --detach $path origin/main
    }
}
git worktree list
Write-Host "Copy .env.example to .env in the coder and tester worktrees and add the API key."

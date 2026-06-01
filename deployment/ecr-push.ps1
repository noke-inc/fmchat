# deployment/ecr-push.ps1
# Builds the Docker image and pushes it to ECR.
#
# Usage (run from the fm-chat root directory):
#   .\deployment\ecr-push.ps1
#   .\deployment\ecr-push.ps1 -Tag "v1.0.1"
#
# Prerequisites:
#   - AWS CLI configured (aws configure / SSO / env vars with ECR push permissions)
#   - Docker Desktop running
#   - ECR repository already created (see README or run the one-time command below)
#
# One-time repo creation:
#   aws ecr create-repository --repository-name noke-fm-mcp-server --region us-east-2

param(
    [string]$Tag = "v1.0.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AccountId = "440124919638"
$Region    = "us-east-2"
$RepoName  = "noke-fm-mcp-server"
$Registry  = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$FullImage = "$Registry/$RepoName`:$Tag"

# Ensure we are in the fm-chat root (Dockerfile references mcp_server/ and index.html)
if (-not (Test-Path "mcp_server/main.py")) {
    Write-Error "Run this script from the fm-chat root directory (where mcp_server/ lives)."
    exit 1
}

Write-Host "`n==> [1/4] Authenticating with ECR ($Region)..." -ForegroundColor Cyan
aws ecr get-login-password --region $Region |
    docker login --username AWS --password-stdin $Registry

Write-Host "`n==> [2/4] Building image: $FullImage" -ForegroundColor Cyan
docker build -f deployment/Dockerfile -t $FullImage .

if ($Tag -ne "latest") {
    # Also tag as latest so EKS deployment.yaml (which uses :latest) picks it up
    $LatestImage = "$Registry/$RepoName`:latest"
    Write-Host "`n==> [3/4] Tagging as latest: $LatestImage" -ForegroundColor Cyan
    docker tag $FullImage $LatestImage
    Write-Host "`n==> [4/4] Pushing both tags..." -ForegroundColor Cyan
    docker push $FullImage
    docker push $LatestImage
} else {
    Write-Host "`n==> [3/4] Skipping extra tag (already latest)" -ForegroundColor Gray
    Write-Host "`n==> [4/4] Pushing image..." -ForegroundColor Cyan
    docker push $FullImage
}

Write-Host "`nDone. Image available at:" -ForegroundColor Green
Write-Host "  $FullImage" -ForegroundColor Green

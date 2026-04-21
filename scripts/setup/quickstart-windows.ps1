Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info {
  param([string]$Message)
  Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

if (-not $IsWindows) {
  throw "This script is for Windows only."
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Write-Info "Project root: $RepoRoot"

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "winget is not available. Install App Installer from Microsoft Store and rerun."
}

function Ensure-WingetPackage {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$DisplayName
  )

  $alreadyInstalled = winget list --id $Id --exact 2>$null | Out-String
  if ($alreadyInstalled -match [Regex]::Escape($Id)) {
    Write-Info "$DisplayName already installed."
    return
  }

  Write-Info "Installing $DisplayName..."
  winget install --id $Id --exact --accept-package-agreements --accept-source-agreements --silent
}

Ensure-WingetPackage -Id "Docker.DockerDesktop" -DisplayName "Docker Desktop"
Ensure-WingetPackage -Id "Kubernetes.kubectl" -DisplayName "kubectl"
Ensure-WingetPackage -Id "Google.Skaffold" -DisplayName "Skaffold"
Ensure-WingetPackage -Id "Kubernetes.kind" -DisplayName "kind"

if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
  Write-Info "Launching Docker Desktop..."
  Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
}

Write-Info "Waiting for Docker daemon..."
$timeoutSec = 300
$elapsedSec = 0
while ($true) {
  try {
    docker info *>$null
    break
  } catch {
    Start-Sleep -Seconds 5
    $elapsedSec += 5
    if ($elapsedSec -ge $timeoutSec) {
      throw "Docker daemon is not ready after ${timeoutSec}s. Please open Docker Desktop manually and rerun."
    }
  }
}

$clusterReady = $true
try {
  kubectl get nodes *>$null
} catch {
  $clusterReady = $false
}

if (-not $clusterReady) {
  $clusters = @()
  try {
    $clusters = kind get clusters 2>$null
  } catch {
    $clusters = @()
  }

  if ($clusters -contains "however-lab") {
    Write-Info "Using existing kind cluster: however-lab"
  } else {
    Write-Info "No active cluster detected. Creating kind cluster: however-lab"
    kind create cluster --name however-lab
  }
}

Set-Location $RepoRoot
Write-Info "Running skaffold deployment (first run may take 15-20 minutes)..."
skaffold run

Write-Info "Deployment finished."
Write-Info "Check pods: kubectl get pods"
Write-Info "Access app: kubectl port-forward deployment/frontend 8080:8080"
Write-Info "Then open: http://localhost:8080"

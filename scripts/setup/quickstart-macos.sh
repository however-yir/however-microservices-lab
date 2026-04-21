#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[ERROR] This script is for macOS only."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() {
  printf "\033[1;34m[INFO]\033[0m %s\n" "$1"
}

warn() {
  printf "\033[1;33m[WARN]\033[0m %s\n" "$1"
}

install_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    return
  fi

  log "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

ensure_brew_package() {
  local pkg="$1"
  if brew list --formula "$pkg" >/dev/null 2>&1; then
    log "${pkg} already installed."
  else
    log "Installing ${pkg}..."
    brew install "$pkg"
  fi
}

ensure_brew_cask() {
  local cask="$1"
  if brew list --cask "$cask" >/dev/null 2>&1; then
    log "${cask} already installed."
  else
    log "Installing ${cask}..."
    brew install --cask "$cask"
  fi
}

wait_for_docker() {
  local timeout=240
  local elapsed=0
  while ! docker info >/dev/null 2>&1; do
    sleep 3
    elapsed=$((elapsed + 3))
    if ((elapsed >= timeout)); then
      warn "Docker daemon is not ready after ${timeout}s. Please open Docker Desktop manually and rerun this script."
      return 1
    fi
  done
  return 0
}

ensure_cluster() {
  if kubectl get nodes >/dev/null 2>&1; then
    log "Detected active Kubernetes cluster."
    return
  fi

  if kind get clusters | grep -qx "however-lab"; then
    log "Using existing kind cluster: however-lab"
    kubectl cluster-info >/dev/null
    return
  fi

  log "No active cluster detected. Creating kind cluster: however-lab"
  kind create cluster --name however-lab
}

log "Project root: ${ROOT_DIR}"
install_homebrew

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

ensure_brew_cask docker
ensure_brew_package kubectl
ensure_brew_package skaffold
ensure_brew_package kind

if ! pgrep -x "Docker Desktop" >/dev/null 2>&1; then
  log "Launching Docker Desktop..."
  open -a "Docker"
fi

log "Waiting for Docker daemon..."
wait_for_docker

ensure_cluster

log "Running skaffold deployment (first run may take 15-20 minutes)..."
cd "${ROOT_DIR}"
skaffold run

log "Deployment finished."
log "Check pods: kubectl get pods"
log "Access app: kubectl port-forward deployment/frontend 8080:8080"
log "Then open: http://localhost:8080"

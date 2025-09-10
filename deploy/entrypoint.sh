#!/bin/bash
set -e

# Use a writable log location in the user's home directory
LOG_DIR="/home/appuser/logs"
LOG_FILE="$LOG_DIR/entrypoint.log"
mkdir -p "$LOG_DIR"

# Redirect all output to a log file while also printing to the console
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $@"
}

error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $@" >&2
    exit 1
}

log "Entrypoint execution started."

# --- CHANGE IS HERE ---
# Execute dapr init as 'appuser' to ensure binaries are installed in the correct home directory.
log "Initializing Dapr runtime as appuser..."
su -s /bin/bash -c "dapr init --slim --runtime-version=1.14.4" appuser || error "Failed to initialize Dapr."
log "Dapr initialized successfully."

# Start Supervisor to manage all processes.
log "Starting supervisord..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf || error "Failed to start supervisord."


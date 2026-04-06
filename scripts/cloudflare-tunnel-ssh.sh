#!/usr/bin/env bash
#
# Cloudflare Tunnel for SSH — resilient, auto-reconnecting
#
# Usage:
#   ./cloudflare-tunnel-ssh.sh              # uses default SSH port 22
#   ./cloudflare-tunnel-ssh.sh 2222         # custom SSH port
#
set -euo pipefail

SSH_PORT="${1:-22}"
RETRY_BASE=2        # initial backoff seconds
RETRY_MAX=60        # max backoff seconds
RETRY_COUNT=0
CLOUDFLARED_PID=""
LOG_FILE=$(mktemp /tmp/cloudflared-ssh-XXXXXX.log)

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$@"; }

cleanup() {
    log "Shutting down tunnel…"
    if [[ -n "$CLOUDFLARED_PID" ]] && kill -0 "$CLOUDFLARED_PID" 2>/dev/null; then
        kill "$CLOUDFLARED_PID" 2>/dev/null
        wait "$CLOUDFLARED_PID" 2>/dev/null || true
    fi
    rm -f "$LOG_FILE"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Verify cloudflared is available
if ! command -v cloudflared &>/dev/null; then
    log "ERROR: cloudflared is not installed. Install it first:"
    log "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
fi

# Verify SSH is listening
if ! ss -tlnp 2>/dev/null | grep -q ":${SSH_PORT} " && \
   ! netstat -tlnp 2>/dev/null | grep -q ":${SSH_PORT} "; then
    log "WARNING: Nothing appears to be listening on port ${SSH_PORT}. Proceeding anyway…"
fi

print_connection_info() {
    local hostname="$1"
    local user
    user=$(whoami)
    echo
    echo "=============================================="
    echo "  TUNNEL IS UP"
    echo "  Hostname: ${hostname}"
    echo ""
    echo "  To connect via SSH from another machine:"
    echo ""
    echo "  cloudflared access tcp --hostname ${hostname} --url localhost:2222 &"
    echo "  ssh -p 2222 ${user}@localhost"
    echo ""
    echo "  Or add to ~/.ssh/config:"
    echo ""
    echo "  Host pricemap-tunnel"
    echo "    ProxyCommand cloudflared access tcp --hostname ${hostname} --listener localhost:0"
    echo "    User ${user}"
    echo "=============================================="
    echo
}

log "Starting Cloudflare quick-tunnel for SSH (port ${SSH_PORT})…"
log "Press Ctrl+C to stop."
echo

while true; do
    # Truncate log file for this attempt
    > "$LOG_FILE"

    # Run cloudflared in the background, writing all output to the log file
    cloudflared tunnel --url "tcp://localhost:${SSH_PORT}" \
        --protocol quic \
        --no-autoupdate \
        > "$LOG_FILE" 2>&1 &
    CLOUDFLARED_PID=$!

    # Monitor the log file for the URL, and also watch if cloudflared dies
    URL_FOUND=false
    while kill -0 "$CLOUDFLARED_PID" 2>/dev/null; do
        if [[ "$URL_FOUND" == false ]]; then
            hostname=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | head -1 || true)
            if [[ -n "$hostname" ]]; then
                hostname="${hostname#https://}"
                print_connection_info "$hostname"
                URL_FOUND=true
                # Now tail the log so user sees ongoing output
                tail -f "$LOG_FILE" &
                TAIL_PID=$!
            fi
        fi
        sleep 1
    done

    # cloudflared has exited — stop tailing
    if [[ -n "${TAIL_PID:-}" ]] && kill -0 "$TAIL_PID" 2>/dev/null; then
        kill "$TAIL_PID" 2>/dev/null || true
        wait "$TAIL_PID" 2>/dev/null || true
    fi
    unset TAIL_PID

    wait "$CLOUDFLARED_PID" 2>/dev/null
    exit_code=$?
    CLOUDFLARED_PID=""

    # If killed by our own cleanup (signal), don't retry
    if [[ $exit_code -eq 0 || $exit_code -ge 128 ]]; then
        log "Tunnel exited (code ${exit_code})."
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    backoff=$(( RETRY_BASE ** (RETRY_COUNT > 5 ? 5 : RETRY_COUNT) ))
    [[ $backoff -gt $RETRY_MAX ]] && backoff=$RETRY_MAX

    log "Tunnel exited with code ${exit_code}. Reconnecting in ${backoff}s… (attempt #${RETRY_COUNT})"
    sleep "$backoff"

    log "Reconnecting…"
done

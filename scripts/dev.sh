#!/bin/bash
#
# CatSyphon Development Script
#
# Usage:
#   ./scripts/dev.sh start    - Start all services (PostgreSQL, API server)
#   ./scripts/dev.sh stop     - Stop all services
#   ./scripts/dev.sh restart  - Restart all services
#   ./scripts/dev.sh reset    - Delete all data and start fresh
#   ./scripts/dev.sh status   - Show status of all services
#
# Requirements:
#   - Colima (Docker runtime for macOS)
#   - uv (Python package manager)
#   - Node.js/pnpm (for frontend)

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
API_PORT="${API_PORT:-8000}"
API_WORKERS="${API_WORKERS:-4}"  # 4 workers recommended to avoid file descriptor exhaustion
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# Increase file descriptor limit (macOS default of 256 is too low)
ulimit -n 4096 2>/dev/null || true

# Set Docker socket for Colima (if not already set)
if [[ -z "${DOCKER_HOST:-}" ]]; then
    if [[ -S "${HOME}/.config/colima/default/docker.sock" ]]; then
        export DOCKER_HOST="unix://${HOME}/.config/colima/default/docker.sock"
    elif [[ -S "/var/run/docker.sock" ]]; then
        export DOCKER_HOST="unix:///var/run/docker.sock"
    fi
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Colima is running AND Docker is accessible
check_colima() {
    if ! colima status &>/dev/null; then
        return 1
    fi
    # Also verify Docker is actually accessible
    if ! docker info &>/dev/null; then
        return 1
    fi
    return 0
}

# Start Colima if not running (or restart if Docker is broken)
start_colima() {
    # Check if Colima claims to be running
    if colima status &>/dev/null; then
        # Verify Docker is actually working
        if docker info &>/dev/null; then
            log_info "Colima is already running"
            return 0
        else
            log_warn "Colima is running but Docker is not accessible - restarting..."
            colima stop 2>/dev/null || true
            sleep 2
        fi
    fi

    log_info "Starting Colima..."
    colima start

    # Wait for Docker to be ready
    local retries=10
    while [[ $retries -gt 0 ]]; do
        if docker info &>/dev/null; then
            log_success "Colima started"
            return 0
        fi
        sleep 1
        ((retries--))
    done

    log_error "Colima started but Docker is not accessible"
    return 1
}

# Set up SSH tunnel for PostgreSQL port forwarding
# Required because Colima with vz driver doesn't auto-forward Docker ports
setup_port_forward() {
    local ssh_config="$HOME/.config/colima/_lima/colima/ssh.config"

    # Check if tunnel already exists
    if lsof -i :${POSTGRES_PORT} &>/dev/null; then
        log_info "Port ${POSTGRES_PORT} already forwarded"
        return 0
    fi

    if [[ -f "$ssh_config" ]]; then
        log_info "Setting up SSH tunnel for PostgreSQL (port ${POSTGRES_PORT})..."
        ssh -F "$ssh_config" -L ${POSTGRES_PORT}:localhost:${POSTGRES_PORT} -N -f lima-colima 2>/dev/null || true
        sleep 1

        if lsof -i :${POSTGRES_PORT} &>/dev/null; then
            log_success "PostgreSQL port forwarded"
        else
            log_warn "Port forwarding may have failed - PostgreSQL might not be accessible"
        fi
    else
        log_warn "Colima SSH config not found - port forwarding skipped"
    fi
}

# Kill SSH tunnel for PostgreSQL
kill_port_forward() {
    local pids=$(lsof -ti :${POSTGRES_PORT} 2>/dev/null | grep -v "^$$" || true)
    if [[ -n "$pids" ]]; then
        log_info "Stopping PostgreSQL port forward..."
        echo "$pids" | xargs kill 2>/dev/null || true
        log_success "Port forward stopped"
    fi
}

# Start PostgreSQL container
start_postgres() {
    log_info "Starting PostgreSQL container..."
    cd "$PROJECT_ROOT"
    docker-compose up -d 2>&1 | grep -v "^WARN" || true

    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    local retries=30
    while [[ $retries -gt 0 ]]; do
        if docker exec catsyphon-postgres pg_isready -U catsyphon -d catsyphon &>/dev/null; then
            log_success "PostgreSQL is ready"
            return 0
        fi
        sleep 1
        ((retries--))
    done

    log_error "PostgreSQL failed to start"
    return 1
}

# Stop PostgreSQL container
stop_postgres() {
    log_info "Stopping PostgreSQL container..."
    cd "$PROJECT_ROOT"
    docker-compose down 2>&1 | grep -v "^WARN" || true
    log_success "PostgreSQL stopped"
}

# Reset PostgreSQL (delete all data)
reset_postgres() {
    log_warn "This will DELETE ALL DATA. Are you sure? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Reset cancelled"
        return 1
    fi

    log_info "Resetting PostgreSQL (deleting all data)..."
    cd "$PROJECT_ROOT"
    docker-compose down -v 2>&1 | grep -v "^WARN" || true
    log_success "PostgreSQL data deleted"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    cd "$BACKEND_DIR"
    uv run alembic upgrade head
    log_success "Migrations complete"
}

# Start API server
start_api() {
    log_info "Starting API server on port ${API_PORT} with ${API_WORKERS} workers..."
    cd "$BACKEND_DIR"

    # Check if already running
    if lsof -ti :${API_PORT} &>/dev/null; then
        log_warn "Port ${API_PORT} is already in use"
        return 1
    fi

    # Ensure high file descriptor limit for the server process
    # macOS default of 256 is too low for multi-worker setup
    ulimit -n 4096 2>/dev/null || log_warn "Could not increase file descriptor limit"

    # Start in background
    nohup uv run uvicorn catsyphon.api.app:app \
        --host 0.0.0.0 \
        --port ${API_PORT} \
        --workers ${API_WORKERS} \
        > /dev/null 2>&1 &

    # Wait for server to start
    sleep 3

    if lsof -ti :${API_PORT} &>/dev/null; then
        log_success "API server started on http://localhost:${API_PORT}"
    else
        log_error "API server failed to start"
        return 1
    fi
}

# Stop API server
stop_api() {
    log_info "Stopping API server..."
    local pids=$(lsof -ti :${API_PORT} 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 2
        # Force kill if still running
        pids=$(lsof -ti :${API_PORT} 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
        log_success "API server stopped"
    else
        log_info "API server was not running"
    fi
}

# Show status of all services
show_status() {
    echo ""
    echo "=== CatSyphon Service Status ==="
    echo ""

    # Colima
    if check_colima; then
        echo -e "Colima:     ${GREEN}running${NC}"
    else
        echo -e "Colima:     ${RED}stopped${NC}"
    fi

    # PostgreSQL
    if docker exec catsyphon-postgres pg_isready -U catsyphon -d catsyphon &>/dev/null; then
        echo -e "PostgreSQL: ${GREEN}running${NC} (container)"
    else
        echo -e "PostgreSQL: ${RED}stopped${NC}"
    fi

    # Port forward
    if lsof -i :${POSTGRES_PORT} &>/dev/null; then
        echo -e "Port ${POSTGRES_PORT}:   ${GREEN}forwarded${NC}"
    else
        echo -e "Port ${POSTGRES_PORT}:   ${RED}not forwarded${NC}"
    fi

    # API Server
    if lsof -i :${API_PORT} &>/dev/null; then
        echo -e "API Server: ${GREEN}running${NC} on port ${API_PORT}"
    else
        echo -e "API Server: ${RED}stopped${NC}"
    fi

    # Health check
    if curl -s "http://localhost:${API_PORT}/health" 2>/dev/null | grep -q '"status"'; then
        local health=$(curl -s "http://localhost:${API_PORT}/health" 2>/dev/null)
        local db_status=$(echo "$health" | grep -o '"database":"[^"]*"' | cut -d'"' -f4)
        echo -e "Health:     ${GREEN}API responding${NC}, database: ${db_status}"
    fi

    echo ""
}

# Main command handler
cmd_start() {
    log_info "Starting CatSyphon development environment..."
    echo ""

    start_colima
    start_postgres
    setup_port_forward
    run_migrations
    start_api

    echo ""
    show_status

    log_success "CatSyphon is ready!"
    echo ""
    echo "  API:      http://localhost:${API_PORT}"
    echo "  Swagger:  http://localhost:${API_PORT}/docs"
    echo "  Logs:     ~/.local/state/catsyphon/logs/"
    echo ""
}

cmd_stop() {
    log_info "Stopping CatSyphon..."
    echo ""

    stop_api
    kill_port_forward
    stop_postgres

    echo ""
    log_success "CatSyphon stopped"
}

cmd_restart() {
    cmd_stop
    echo ""
    cmd_start
}

cmd_reset() {
    log_warn "=== RESET MODE ==="
    log_warn "This will:"
    log_warn "  - Stop all services"
    log_warn "  - Delete all PostgreSQL data"
    log_warn "  - Start fresh with empty database"
    echo ""

    cmd_stop
    reset_postgres || return 1
    echo ""
    cmd_start
}

cmd_status() {
    show_status
}

cmd_logs() {
    local log_dir="$HOME/.local/state/catsyphon/logs"
    local log_type="${1:-all}"

    if [[ ! -d "$log_dir" ]]; then
        log_error "Log directory not found: $log_dir"
        return 1
    fi

    case "$log_type" in
        error|errors)
            log_info "Streaming error logs (Ctrl+C to stop)..."
            tail -f "$log_dir/api-error.log"
            ;;
        app|application)
            log_info "Streaming application logs (Ctrl+C to stop)..."
            tail -f "$log_dir/api-application.log"
            ;;
        watch)
            log_info "Streaming watch daemon logs (Ctrl+C to stop)..."
            tail -f "$log_dir"/watch-*-application.log 2>/dev/null || log_error "No watch daemon logs found"
            ;;
        all|*)
            log_info "Streaming all API logs (Ctrl+C to stop)..."
            tail -f "$log_dir/api-application.log" "$log_dir/api-error.log"
            ;;
    esac
}

cmd_help() {
    echo "CatSyphon Development Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start     Start all services (PostgreSQL, API server)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  reset     Delete all data and start fresh"
    echo "  status    Show status of all services"
    echo "  logs      Stream logs (logs, logs error, logs app, logs watch)"
    echo "  help      Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  API_PORT      API server port (default: 8000)"
    echo "  API_WORKERS   Number of uvicorn workers (default: 4)"
    echo "  POSTGRES_PORT PostgreSQL port (default: 5432)"
    echo ""
}

# Main entry point
case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    reset)
        cmd_reset
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs "${2:-all}"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        cmd_help
        exit 1
        ;;
esac

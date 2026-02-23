# Multi-Mac Log Collection Setup

**Collecting Claude Code and Codex logs from multiple Macs into a central Mac Studio running CatSyphon.**

---

## 1. Readiness Assessment

### What Already Works

CatSyphon's architecture was built with this exact use case in mind. The Collector Events API (Phase 1 complete) provides the full server-side infrastructure:

| Component | Status | Key Files |
|-----------|--------|-----------|
| **Collector Events API** | Implemented | `api/routes/collectors.py` |
| **API key auth** (SHA-256 hashed, HMAC-verified) | Implemented | `api/routes/collectors.py:99-117` |
| **Collector registration** with hostname tracking | Implemented | `api/routes/collectors.py:185-235` |
| **Event batching** with sequence tracking | Implemented | `api/routes/collectors.py:238-294` |
| **Session resumption** after network outage | Implemented | `api/routes/collectors.py:297-339` |
| **Content-based deduplication** (event_hash) | Implemented | `collector_client.py:79-93` |
| **Workspace isolation** (multi-tenant) | Implemented | `api/auth.py` |
| **Watch daemon with remote server support** | Implemented | `watch.py:102-136` |
| **CollectorClient** (Python HTTP client) | Implemented | `collector_client.py` |
| **Auto-bootstrap** (org/workspace/watch creation) | Implemented | `bootstrap.py` |
| **Incremental parsing** (append detection) | Implemented | `parsers/incremental.py` |

### What's Missing (Gaps)

These are the pieces you'll need to work around or build:

| Gap | Impact | Workaround |
|-----|--------|------------|
| **No `pip install catsyphon` for clients** | Client machines need the full repo or a vendored `collector_client.py` | Install from git or copy the client module |
| **No persistent daemon on client Macs** | Watch daemon dies when terminal closes | Use macOS LaunchAgent (plist provided below) |
| **No TLS built into Docker stack** | Traffic between Macs is unencrypted | Use Tailscale (zero-config) or Caddy reverse proxy |
| **No client-side CLI for registration** | Must register collectors via `curl` | Script provided below |
| **Backend not exposed on host port** | Nginx proxies `/api/*` but collectors need direct access | Add port mapping in override (shown below) |
| **No API key rotation** | Keys can't be refreshed without re-registration | Acceptable for a 5-machine setup |
| **No offline buffering on clients** | If server is down, events are lost until retry window expires | Watch daemon has retry queue (5min→15min→45min) |

### Verdict

The server side is production-ready. The client side needs a LaunchAgent wrapper and network access to the Mac Studio. For a 5-machine LAN setup, this is straightforward.

---

## 2. Network Architecture

```
┌──────────────────────────┐  ┌──────────────────────────┐
│  Mac #1 (MacBook)        │  │  Mac #2 (MacBook)        │
│  ~/.claude/projects/     │  │  ~/.claude/projects/     │
│  ~/.codex/sessions/      │  │  ~/.codex/sessions/      │
│  catsyphon-watcher       │  │  catsyphon-watcher       │
│  (LaunchAgent)           │  │  (LaunchAgent)           │
└──────────┬───────────────┘  └──────────┬───────────────┘
           │                             │
           │  POST /api/collectors/events
           │  Bearer cs_live_xxxxx
           │                             │
           └──────────┬──────────────────┘
                      │
        ┌─────────────▼──────────────────────┐
        │  Mac Studio (CatSyphon Server)     │
        │                                    │
        │  :3000  Nginx → React UI           │
        │         └→ /api/* → FastAPI :8000  │
        │                                    │
        │  :8000  FastAPI (Collector API)     │
        │  :5432  PostgreSQL (internal)       │
        └────────────────────────────────────┘
```

All client Macs push events over HTTP to the Mac Studio. The Mac Studio runs the full CatSyphon Docker stack (Postgres + FastAPI + React).

**Network requirement**: All Macs must reach the Mac Studio on port 3000 (or 8000 if you expose the backend directly). The simplest approach is a local network — all machines on the same Wi-Fi/Ethernet, or connected via Tailscale.

---

## 3. Step-by-Step Setup

### Phase A: Mac Studio (Server)

#### A1. Clone and configure

```bash
git clone https://github.com/kulesh/catsyphon.git
cd catsyphon

# Create environment file
cat > .env << 'EOF'
POSTGRES_PASSWORD=pick-a-strong-password-here
ENVIRONMENT=production
API_WORKERS=1
LOG_LEVEL=INFO
# Optional: enables AI-powered tagging (~$10/1000 conversations)
# OPENAI_API_KEY=sk-...
EOF
```

#### A2. Expose the backend API to the network

The default `docker-compose.yml` does not expose port 8000 to the host — Nginx handles all traffic via `/api/*` on port 3000. Collectors can use `http://<mac-studio-ip>:3000/api/collectors/events` through Nginx, which already proxies `/api/*` to the backend.

However, the Nginx config strips the `/api` prefix before forwarding, so the collector client URL must use the `/api` prefix. The built-in `CollectorClient` uses bare paths like `/collectors/events`, so you have two options:

**Option 1 (Recommended): Expose backend port directly**

Create or edit `docker-compose.override.yml` on the Mac Studio:

```yaml
# docker-compose.override.yml
services:
  backend:
    ports:
      - "8000:8000"
    environment:
      AUTO_SETUP: "true"
      AUTO_ORG_NAME: "YourTeamName"
      AUTO_WORKSPACE_NAME: "Engineering"
```

This lets collectors hit `http://<mac-studio-ip>:8000` directly.

**Option 2: Use the launcher with manual override**

```bash
# Let the launcher detect local tools and generate override
./catsyphon up

# Then manually add the backend port to the generated override
```

Edit the generated `docker-compose.override.yml` and add `ports: ["8000:8000"]` under `backend:`.

#### A3. Start the stack

```bash
docker compose up --build -d

# Verify health
curl http://localhost:8000/health
# → {"status": "healthy", ...}

curl http://localhost:3000/api/health
# → {"status": "healthy", ...}
```

#### A4. Find your workspace ID

The auto-bootstrap creates an organization and workspace on first boot. Get the workspace ID:

```bash
curl -s http://localhost:8000/workspaces | python3 -m json.tool
```

Or check the backend logs:

```bash
docker compose logs backend | grep "Auto-bootstrap: workspace"
# → Auto-bootstrap: workspace 'Engineering' (id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
```

Save this workspace ID — you'll need it for every collector registration.

#### A5. Find the Mac Studio's IP address

```bash
# On the Mac Studio
ipconfig getifaddr en0    # Wi-Fi
ipconfig getifaddr en1    # Ethernet (Thunderbolt)
```

Example: `192.168.1.100`. All client Macs will use this address.

#### A6. Register a collector for each client Mac

Run this **on the Mac Studio** (or from any machine that can reach port 8000):

```bash
WORKSPACE_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # from step A4
SERVER="http://localhost:8000"

# Register Mac #1
curl -s -X POST "$SERVER/collectors" \
  -H "Content-Type: application/json" \
  -d "{
    \"collector_type\": \"watcher\",
    \"collector_version\": \"1.0.0\",
    \"hostname\": \"kulesh-macbook-1.local\",
    \"workspace_id\": \"$WORKSPACE_ID\"
  }" | python3 -m json.tool

# Response:
# {
#   "collector_id": "550e8400-...",
#   "api_key": "cs_live_xK7mN2pQ...",
#   "api_key_prefix": "cs_live_xK7m"
# }
```

**Save the `api_key` and `collector_id`** — the API key is shown only once.

Repeat for each Mac. Each machine gets its own collector registration so you can track which machine submitted which conversations.

---

### Phase B: Client Macs (Collectors)

Each client Mac runs a CatSyphon watcher daemon that monitors local log directories and pushes events to the Mac Studio.

#### B1. Install CatSyphon on each client

The watcher needs Python 3.11+ and the CatSyphon backend package:

```bash
# Option A: Install from the repo (recommended)
git clone https://github.com/kulesh/catsyphon.git ~/catsyphon
cd ~/catsyphon/backend
pip install --user -e .

# Option B: If you use mise
mise install python@3.11
cd ~/catsyphon/backend
uv sync --all-extras
```

Verify it works:

```bash
python3 -c "from catsyphon.collector_client import CollectorClient; print('OK')"
```

#### B2. Create the watcher configuration

Create a config file for the watcher on each client Mac:

```bash
mkdir -p ~/.config/catsyphon

cat > ~/.config/catsyphon/collector.env << 'EOF'
# Mac Studio server address
CATSYPHON_SERVER_URL=http://192.168.1.100:8000

# Credentials from registration (step A6)
CATSYPHON_API_KEY=cs_live_xK7mN2pQ...
CATSYPHON_COLLECTOR_ID=550e8400-...

# Batch size for event uploads
CATSYPHON_COLLECTOR_BATCH_SIZE=20

# Database connection for local operations (required by watcher)
POSTGRES_HOST=192.168.1.100
POSTGRES_PORT=5432
POSTGRES_DB=catsyphon
POSTGRES_USER=catsyphon
POSTGRES_PASSWORD=pick-a-strong-password-here
EOF
```

> **Important caveat**: The current watch daemon architecture requires a database connection because it creates watch configurations and ingestion jobs in the DB directly, in addition to using the Collector API for event submission. This is a design gap — ideally the client watcher would be purely API-driven. See "Current Limitation" below.

#### Current Limitation: Watch Daemon Needs DB Access

The watch daemon in `watch.py` does two things:
1. **Monitors directories** and parses log files locally
2. **Pushes events** via the Collector HTTP API

However, it also writes directly to the database for:
- Watch configuration status updates (`is_active`, `stats`)
- Ingestion job creation and tracking
- Raw log metadata storage

This means client Macs need either:
- **Direct PostgreSQL access** (expose port 5432 from Docker — not ideal for security)
- **Or**: Use a simpler approach — **skip the watch daemon entirely and use API upload**

#### B3. Recommended Approach: rsync + Server-Side Watching

Given the DB dependency, the cleanest approach for your 5-Mac setup is:

1. **Client Macs**: rsync log files to the Mac Studio on a schedule
2. **Mac Studio**: Watch daemon monitors the synced directories locally

This avoids the DB access problem entirely and is simpler to operate.

**On each client Mac**, create a sync script:

```bash
cat > ~/catsyphon-sync.sh << 'SCRIPT'
#!/bin/bash
# Sync Claude Code and Codex logs to Mac Studio
# Runs as a LaunchAgent every 30 seconds

STUDIO="192.168.1.100"
STUDIO_USER="kulesh"  # your username on the Mac Studio
MACHINE_ID="$(hostname -s)"

# Sync Claude Code logs
if [ -d "$HOME/.claude/projects" ]; then
    rsync -az --append \
        "$HOME/.claude/projects/" \
        "${STUDIO_USER}@${STUDIO}:~/catsyphon-logs/${MACHINE_ID}/claude/projects/"
fi

# Sync Codex logs
if [ -d "$HOME/.codex/sessions" ]; then
    rsync -az --append \
        "$HOME/.codex/sessions/" \
        "${STUDIO_USER}@${STUDIO}:~/catsyphon-logs/${MACHINE_ID}/codex/sessions/"
fi
SCRIPT

chmod +x ~/catsyphon-sync.sh
```

**Key rsync flags**:
- `-az`: archive mode + compression
- `--append`: only transfer appended data (perfect for growing JSONL files)

#### B4. Set up SSH key auth (passwordless rsync)

On each client Mac:

```bash
# Generate key if you don't have one
ssh-keygen -t ed25519 -C "catsyphon-$(hostname -s)" -f ~/.ssh/catsyphon_sync -N ""

# Copy to Mac Studio
ssh-copy-id -i ~/.ssh/catsyphon_sync "${STUDIO_USER}@192.168.1.100"

# Test
ssh -i ~/.ssh/catsyphon_sync "${STUDIO_USER}@192.168.1.100" echo "OK"
```

Update the sync script to use this key:

```bash
# Add to rsync commands:
rsync -az --append -e "ssh -i ~/.ssh/catsyphon_sync" \
    "$HOME/.claude/projects/" \
    "${STUDIO_USER}@${STUDIO}:~/catsyphon-logs/${MACHINE_ID}/claude/projects/"
```

#### B5. Create a macOS LaunchAgent for automatic sync

```bash
cat > ~/Library/LaunchAgents/com.catsyphon.sync.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.catsyphon.sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$HOME/catsyphon-sync.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>/tmp/catsyphon-sync.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/catsyphon-sync-error.log</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
PLIST

# Load the agent (starts immediately and on every login)
launchctl load ~/Library/LaunchAgents/com.catsyphon.sync.plist

# Verify it's running
launchctl list | grep catsyphon
```

**To stop**: `launchctl unload ~/Library/LaunchAgents/com.catsyphon.sync.plist`
**To check logs**: `tail -f /tmp/catsyphon-sync.log`

---

### Phase C: Mac Studio — Watch the Synced Directories

#### C1. Create the log landing directory

On the Mac Studio:

```bash
mkdir -p ~/catsyphon-logs
```

After rsync runs from each client, the structure will be:

```
~/catsyphon-logs/
├── macbook-1/
│   ├── claude/projects/         # Claude Code logs from Mac #1
│   └── codex/sessions/          # Codex logs from Mac #1
├── macbook-2/
│   ├── claude/projects/
│   └── codex/sessions/
├── macbook-3/
│   └── claude/projects/
└── mac-studio/                  # Local Mac Studio logs (optional)
    └── claude/projects/
```

#### C2. Mount synced logs into Docker

Update `docker-compose.override.yml` on the Mac Studio to mount all synced directories:

```yaml
# docker-compose.override.yml
services:
  backend:
    ports:
      - "8000:8000"
    volumes:
      # Local Mac Studio logs
      - ~/.claude:/data/mac-studio/claude:ro
      - ~/.codex:/data/mac-studio/codex:ro
      # Synced remote logs
      - ~/catsyphon-logs:/data/remote:ro
    environment:
      AUTO_SETUP: "true"
      AUTO_ORG_NAME: "Kulesh"
      AUTO_WORKSPACE_NAME: "Engineering"
      AUTO_WATCH_DIRS: >-
        /data/mac-studio/claude/projects,
        /data/mac-studio/codex/sessions,
        /data/remote/macbook-1/claude/projects,
        /data/remote/macbook-1/codex/sessions,
        /data/remote/macbook-2/claude/projects,
        /data/remote/macbook-2/codex/sessions,
        /data/remote/macbook-3/claude/projects,
        /data/remote/macbook-3/codex/sessions,
        /data/remote/macbook-4/claude/projects
```

#### C3. Restart the stack

```bash
cd ~/catsyphon
docker compose down
docker compose up --build -d

# Verify watch directories are configured
docker compose logs backend | grep "Auto-bootstrap"
```

#### C4. Verify in the Web UI

Open `http://localhost:3000` on the Mac Studio. Navigate to **Ingestion** to see:
- Watch directories for each machine
- Jobs processing as logs sync in
- Pipeline performance metrics

---

## 4. Operational Playbook

### Adding a new Mac

1. Set up SSH key auth from the new Mac to the Mac Studio (step B4)
2. Create the sync script and LaunchAgent on the new Mac (steps B3, B5)
3. Add the new directory paths to `AUTO_WATCH_DIRS` in `docker-compose.override.yml`
4. Restart: `docker compose down && docker compose up -d`

### Monitoring sync health

```bash
# On any client Mac — check last sync
tail -5 /tmp/catsyphon-sync.log

# On Mac Studio — check for recent files
find ~/catsyphon-logs -name "*.jsonl" -mmin -5

# On Mac Studio — check CatSyphon health
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:3000/api/stats/overview | python3 -m json.tool
```

### Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| Sync not running | `launchctl list \| grep catsyphon` | `launchctl load ~/Library/LaunchAgents/com.catsyphon.sync.plist` |
| rsync permission denied | `ssh -i ~/.ssh/catsyphon_sync user@studio echo OK` | Re-run `ssh-copy-id` |
| Logs synced but not ingested | `docker compose logs backend \| grep -i error` | Check `AUTO_WATCH_DIRS` paths match mounted volumes |
| Conversations not appearing in UI | Check Ingestion page for watch daemon status | Start daemon via UI or restart container |
| Mac Studio runs out of disk | `du -sh ~/catsyphon-logs` | Add a retention/cleanup cron job |

### Database backup (Mac Studio)

```bash
# Daily backup — add to crontab
docker exec catsyphon-postgres pg_dump -U catsyphon catsyphon | gzip > ~/backups/catsyphon-$(date +%Y%m%d).sql.gz
```

---

## 5. aiobscura as a Local Collector

### What Is aiobscura?

aiobscura is a planned Rust-based local collector agent designed to run on developer workstations. It would parse conversation logs locally, store them in SQLite, provide a personal TUI, and optionally push data to CatSyphon via the Collector Events API.

### Current Status

**aiobscura does not exist as a usable tool yet.** It is referenced extensively in CatSyphon's collector architecture docs (`docs/collectors/`) as the intended client-side agent, but:

- No published crate or binary
- No repository found at `/home/user/aiobscura/` or as a git submodule
- SDK docs (`docs/collectors/sdk.md`) list it as "In Development"
- Enterprise deployment guide references `pip install aiobscura` — this package does not exist

### What CatSyphon Built for aiobscura

The server side is ready. CatSyphon implemented the full Collector Events API based on aiobscura's protocol design:

- HTTP event ingestion (`POST /collectors/events`)
- Collector registration with API keys
- Session tracking, resumption, and completion
- Event sequence ordering with gap detection
- Content-based deduplication via event hashes
- Three-tier timestamp model (`emitted_at`, `observed_at`, `server_received_at`)
- Type system with 6 author roles, 8 message types
- Parent-child session linking for sub-agent conversations

### Gaps to Fill if Building aiobscura

To make aiobscura functional as a local collector for your setup:

| Component | Description | Effort |
|-----------|-------------|--------|
| **Log parser** | Parse `~/.claude/projects/*/` JSONL files | Medium — CatSyphon's Python parser exists as reference (`parsers/claude_code.py`) |
| **File watcher** | Detect new/changed log files | Low — use `notify` crate (Rust) or `watchdog` (Python) |
| **Collector client** | HTTP client implementing the events protocol | Low — CatSyphon's Python `CollectorClient` is the reference implementation |
| **Local SQLite store** | Buffer events for offline resilience | Medium — schema needs design |
| **Checkpoint tracking** | Resume from byte offset after restart | Low — CatSyphon's incremental parser shows the pattern |
| **LaunchAgent integration** | Start on login, restart on crash | Low — plist template above works |
| **TUI** | Personal analytics dashboard | Nice-to-have, not required |

### Recommendation for Your Setup

**Don't wait for aiobscura.** The rsync + server-side watching approach described in Phase B/C above is simpler, requires no custom client-side software, and works today. It handles:

- Incremental file transfer (rsync `--append`)
- Automatic scheduling (LaunchAgent)
- Server-side parsing and ingestion (existing watch daemon)
- Deduplication (content hashing in the pipeline)

If you later want to build aiobscura, the rsync approach gives you a working baseline to compare against. The Collector Events API on the server will be ready whenever a client appears.

---

## 6. Security Notes

### Current Setup (LAN only)

For a home/office LAN where all Macs are on the same trusted network:

- **rsync over SSH** provides encrypted transport for log files
- **CatSyphon API** runs over plain HTTP (port 8000/3000)
- **PostgreSQL** is not exposed to the network (Docker internal only)

This is acceptable for a trusted LAN. The SSH keys used by rsync are the main security boundary.

### If You Need WAN Access (Remote Macs)

If any Mac is outside the local network:

1. **Tailscale** (strongly recommended): Zero-config encrypted mesh VPN. Install on all Macs, and they can reach each other by Tailscale IP. No port forwarding, no certificates to manage.

2. **Caddy reverse proxy**: Automatic HTTPS with Let's Encrypt.

3. **Use the Collector Events API directly**: Skip rsync entirely. Install the CatSyphon watcher on each remote Mac with `CATSYPHON_SERVER_URL=https://catsyphon.tailnet-xxxx.ts.net:8000`. This requires exposing PostgreSQL to the client (or fixing the DB dependency gap noted above).

---

## 7. Cost and Resource Estimates

| Resource | Estimate |
|----------|----------|
| **Disk (Mac Studio)** | ~100MB per developer per month of raw logs |
| **Bandwidth** | rsync transfers ~1-5MB per sync cycle (appended data only) |
| **PostgreSQL storage** | ~50MB per 1,000 conversations |
| **CPU (Mac Studio)** | Parsing is lightweight; the Mac Studio will barely notice |
| **OpenAI tagging** (optional) | ~$10 per 1,000 conversations |
| **Docker resources** | 4 CPU cores, 4GB RAM minimum (Mac Studio has plenty) |

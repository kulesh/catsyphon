# Edge Sensors on macOS -> Central CatSyphon Collector

**Goal:** run CatSyphon on a central machine (for example a Mac Studio) and ingest logs continuously from multiple macOS edge machines running Claude Code CLI and Codex.

This guide uses:
- CatSyphon server as the central collector
- `aiobscura-sync --watch` as the edge sensor process
- one collector credential set per edge machine

## Topology

```text
[Edge Mac 1]  aiobscura-sync --watch  \
[Edge Mac 2]  aiobscura-sync --watch   -> HTTPS -> [CatSyphon API on Mac Studio]
[Edge Mac N]  aiobscura-sync --watch  /
```

Each edge machine:
1. parses local assistant logs (`~/.claude`, `~/.codex`)
2. stores normalized events locally in SQLite
3. forwards to CatSyphon collector endpoints with API key auth

## 1. Bring up central CatSyphon (Mac Studio)

On the Mac Studio:

```bash
git clone https://github.com/kulesh/catsyphon.git
cd catsyphon
cp .env.example .env
docker-compose up -d
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run catsyphon serve
```

If you also run the frontend:

```bash
cd ../frontend
pnpm install
pnpm dev
```

Use a stable HTTPS URL for edges (for example `https://catsyphon.yourdomain.com`).

## 2. Create organization/workspace (once)

Collector registration requires a `workspace_id`.

### Check if onboarding is needed

```bash
curl -s http://<catsyphon-host>:8000/setup/status | jq
```

### Create organization and workspace (if needed)

```bash
# Create organization
ORG_JSON=$(curl -s -X POST http://<catsyphon-host>:8000/setup/organizations \
  -H "Content-Type: application/json" \
  -d '{"name":"Kulesh Engineering","slug":"kulesh-engineering"}')
ORG_ID=$(echo "$ORG_JSON" | jq -r '.id')

# Create workspace
WS_JSON=$(curl -s -X POST http://<catsyphon-host>:8000/setup/workspaces \
  -H "Content-Type: application/json" \
  -d "{\"organization_id\":\"$ORG_ID\",\"name\":\"edge-sensors\",\"slug\":\"edge-sensors\"}")
WORKSPACE_ID=$(echo "$WS_JSON" | jq -r '.id')

echo "$WORKSPACE_ID"
```

If workspace already exists:

```bash
curl -s http://<catsyphon-host>:8000/setup/workspaces | jq
```

## 3. Register one collector per edge machine

Run this once for each edge Mac, using a unique hostname:

```bash
curl -s -X POST http://<catsyphon-host>:8000/collectors \
  -H "Content-Type: application/json" \
  -d '{
    "collector_type":"aiobscura",
    "collector_version":"0.1.10",
    "hostname":"edge-mac-01",
    "workspace_id":"<WORKSPACE_ID>"
  }' | tee collector-edge-mac-01.json
```

Capture and store from the response:
- `collector_id`
- `api_key` (shown once)

## 4. Configure each edge machine (aiobscura)

Install aiobscura on each edge Mac:

```bash
brew install kulesh/tap/aiobscura
```

Create `~/.config/aiobscura/config.toml`:

```toml
[collector]
enabled = true
server_url = "https://catsyphon.yourdomain.com"
collector_id = "REPLACE_WITH_COLLECTOR_ID"
api_key = "REPLACE_WITH_API_KEY"
batch_size = 20
flush_interval_secs = 5
timeout_secs = 30
max_retries = 3
```

## 5. Validate ingestion from an edge

On the edge Mac:

```bash
aiobscura-sync
aiobscura-collector status
aiobscura-collector sessions
```

Then on central CatSyphon:

```bash
curl -s -H "Authorization: Bearer <API_KEY>" \
  -H "X-Collector-ID: <COLLECTOR_ID>" \
  "https://catsyphon.yourdomain.com/collectors/sessions/<SESSION_ID>" | jq
```

You should see session records in the CatSyphon UI.

## 6. Run 24/7 on each edge with launchd

Create `~/Library/LaunchAgents/com.aiobscura.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.aiobscura.sync</string>

    <key>ProgramArguments</key>
    <array>
      <string>/opt/homebrew/bin/aiobscura-sync</string>
      <string>--watch</string>
      <string>--poll</string>
      <string>5000</string>
    </array>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/aiobscura-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/aiobscura-sync.log</string>
  </dict>
</plist>
```

Load it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.aiobscura.sync.plist
launchctl enable gui/$(id -u)/com.aiobscura.sync
launchctl kickstart -k gui/$(id -u)/com.aiobscura.sync
launchctl list | rg aiobscura
tail -f /tmp/aiobscura-sync.log
```

Notes:
- On Intel macOS, binary path may be `/usr/local/bin/aiobscura-sync`.
- You can verify with `command -v aiobscura-sync`.

## 7. Ongoing operations

- Add a new machine: repeat **Register collector** + **edge config**.
- Recover from outage on edge:

```bash
aiobscura-collector resume
```

- Rotate credentials: register a new collector credential and update edge config.
- Verify CI/API health centrally:

```bash
curl -s https://catsyphon.yourdomain.com/health
```

## 8. Troubleshooting

- `401 Collector not found` / `Invalid API key`
  - confirm `collector_id` and `api_key` match the same registration record
- `404 Workspace ... not found` on registration
  - confirm `workspace_id` from `/setup/workspaces`
- No events arriving
  - run `aiobscura-collector status` and `aiobscura-collector sessions`
  - check edge launchd log (`/tmp/aiobscura-sync.log`)
  - verify central API reachable from edge over HTTPS

## Related docs

- [Collector Protocol](protocol.md)
- [Collector SDK](sdk.md)
- [Enterprise Deployment](../guides/enterprise-deployment.md)

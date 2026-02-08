# Enterprise Deployment Guide

**For teams and organizations deploying CatSyphon with remote collectors (aiobscura, watcher).**

This guide covers setting up CatSyphon as a central analytics server with multiple collectors pushing data from developer workstations.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEVELOPER WORKSTATIONS                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Claude Code │  │   Cursor    │  │    Aider    │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              aiobscura / watcher                      │       │
│  │   • Local parsing and buffering                       │       │
│  │   • Incremental sync to server                        │       │
│  └────────────────────────┬─────────────────────────────┘       │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            │ HTTPS (Collector Events API)
                            │ POST /collectors/events
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                        CATSYPHON SERVER                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Collector Events API                      │  │
│  │   • API key authentication                                   │  │
│  │   • Workspace isolation                                      │  │
│  │   • Sequence tracking & deduplication                        │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      PostgreSQL                              │  │
│  │   organizations → workspaces → conversations → messages      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## Deployment Options

### Option 1: Docker Compose (Recommended for Small Teams)

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: catsyphon
      POSTGRES_USER: catsyphon
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://catsyphon:${POSTGRES_PASSWORD}@postgres:5432/catsyphon
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
```

### Option 2: Kubernetes (Recommended for Large Teams)

See `deploy/kubernetes/` for Helm charts and manifests.

### Option 3: Managed Cloud

*Coming soon: CatSyphon Cloud*

---

## Server Setup

### 1. Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Docker and Docker Compose
- Domain name with SSL certificate
- Firewall allowing ports 80/443

### 2. Install CatSyphon

```bash
# Clone repository
git clone https://github.com/kulesh/catsyphon.git
cd catsyphon

# Create production environment
cp .env.example .env.prod
```

### 3. Configure Environment

Edit `.env.prod`:

```bash
# Required
POSTGRES_PASSWORD=<strong-random-password>
SECRET_KEY=<strong-random-key>

# Optional (for AI tagging)
OPENAI_API_KEY=sk-...

# Production settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 4. Start Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Run Migrations

```bash
docker-compose exec backend uv run alembic upgrade head
```

### 6. Configure Reverse Proxy (nginx example)

```nginx
server {
    listen 443 ssl;
    server_name catsyphon.yourcompany.com;

    ssl_certificate /etc/ssl/certs/catsyphon.crt;
    ssl_certificate_key /etc/ssl/private/catsyphon.key;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
    }

    # Collector Events API
    location /collectors {
        proxy_pass http://localhost:8000/collectors;
    }
}
```

---

## Workspace Management

### Creating a Workspace

Workspaces provide multi-tenant isolation. Each team or project gets its own workspace.

```bash
# Via API (admin credentials required)
curl -X POST https://catsyphon.yourcompany.com/api/workspaces \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering Team",
    "slug": "engineering"
  }'
```

### Registering a Collector

Each developer workstation needs a registered collector:

```bash
curl -X POST https://catsyphon.yourcompany.com/collectors \
  -H "Content-Type: application/json" \
  -d '{
    "collector_type": "aiobscura",
    "collector_version": "1.0.0",
    "hostname": "dev-laptop.local",
    "workspace_id": "<workspace-uuid>"
  }'

# Response includes API key (save it securely!)
# {
#   "collector_id": "...",
#   "api_key": "cs_live_xxxxxxxxxxxx",
#   "api_key_prefix": "cs_live_xxxx"
# }
```

---

## Collector Setup (Developer Workstations)

### aiobscura Setup

```bash
# Install aiobscura
pip install aiobscura

# Configure CatSyphon export
aiobscura config set catsyphon.server_url https://catsyphon.yourcompany.com
aiobscura config set catsyphon.api_key cs_live_xxxxxxxxxxxx
aiobscura config set catsyphon.enabled true

# Start syncing
aiobscura sync start
```

### CatSyphon Watcher Setup

```bash
# Configure watcher to use remote server
export CATSYPHON_SERVER_URL=https://catsyphon.yourcompany.com
export CATSYPHON_API_KEY=cs_live_xxxxxxxxxxxx

# Start watcher
catsyphon watch ~/.claude/projects/
```

---

## Security Considerations

### Network Security

- Use HTTPS for all collector communications
- Restrict collector API to VPN or internal network if possible
- Use firewall rules to limit source IPs

### API Key Management

- Each developer gets their own API key
- Keys are hashed (SHA-256) before storage
- Rotate keys periodically
- Revoke keys when employees leave

### Data Privacy

- Conversation content is stored in PostgreSQL
- Consider data retention policies
- Workspace isolation prevents cross-team access
- Audit logs track all ingestion activity

### Compliance

- All data stays within your infrastructure
- No data sent to third parties (except optional OpenAI tagging)
- GDPR: Implement data deletion workflows as needed

---

## Monitoring

### Health Checks

```bash
# API health
curl https://catsyphon.yourcompany.com/health

# Database connectivity
curl https://catsyphon.yourcompany.com/ready
```

### Metrics to Watch

- Collector heartbeats (stale collectors indicate issues)
- Ingestion job success/failure rates
- Database size growth
- API response times

### Log Files

```
/var/log/catsyphon/
├── application.log      # General application logs
├── error.log           # Errors and warnings
├── api-access.log      # API request logs
└── collector-events.log # Collector activity
```

---

## Backup and Recovery

### Database Backup

```bash
# Daily backup script
docker-compose exec postgres pg_dump -U catsyphon catsyphon > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20250101.sql | docker-compose exec -T postgres psql -U catsyphon catsyphon
```

### Disaster Recovery

1. Restore PostgreSQL from backup
2. Run migrations: `uv run alembic upgrade head`
3. Collectors will automatically resync from last sequence

---

## Scaling

### Horizontal Scaling (Multiple Backend Instances)

- Backend is stateless; run multiple instances behind load balancer
- Database is the bottleneck; use connection pooling (PgBouncer)
- Consider read replicas for dashboard queries

### Performance Tuning

```bash
# PostgreSQL tuning for ingestion workload
shared_buffers = 256MB
work_mem = 64MB
effective_cache_size = 1GB
max_connections = 200
```

---

## Troubleshooting

### Collector Not Connecting

1. Verify API key is correct
2. Check network connectivity: `curl https://catsyphon.yourcompany.com/health`
3. Check collector logs for errors
4. Verify workspace_id matches

### Events Not Appearing

1. Check ingestion job status in Web UI
2. Look for sequence gaps (409 errors in collector logs)
3. Verify collector is active: `GET /collectors/{id}`

### High Memory Usage

1. Check for large sessions (>10k messages)
2. Enable incremental parsing for watch daemons
3. Consider batching collector events (50 max per request)

---

## Next Steps

- [Collector Protocol Reference](../collectors/protocol.md) - Full API specification
- [Collector SDK](../collectors/sdk.md) - Build custom collectors
- [API Reference](../reference/api-reference.md) - REST API documentation

---

## Support

- **Issues**: https://github.com/kulesh/catsyphon/issues
- **Enterprise Support**: enterprise@catsyphon.dev

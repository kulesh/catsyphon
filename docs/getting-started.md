# Getting Started with CatSyphon

**For individual developers who want to analyze their AI coding assistant conversations.**

This guide gets you up and running with CatSyphon in about 10 minutes.

---

## What You'll Need

- **Docker Desktop** - For running the database
- **Your Claude Code logs** - Usually in `~/.claude/projects/`

That's it! We'll handle the rest.

---

## Quick Install

### Option 1: One-Line Setup (Recommended)

```bash
curl -sSL https://catsyphon.dev/install.sh | bash
```

This installs CatSyphon and opens the web UI automatically.

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/kulesh/catsyphon.git
cd catsyphon

# Copy environment file
cp .env.example .env

# Start the database
docker-compose up -d

# Install and start backend
cd backend
pip install uv  # If you don't have uv
uv sync --all-extras
uv run alembic upgrade head
uv run catsyphon serve &

# Install and start frontend
cd ../frontend
npm install -g pnpm  # If you don't have pnpm
pnpm install
pnpm dev
```

Open **http://localhost:5173** in your browser.

---

## Import Your First Logs

### Step 1: Find Your Logs

Claude Code stores conversation logs in:

| OS | Location |
|----|----------|
| macOS/Linux | `~/.claude/projects/` |
| Windows | `%USERPROFILE%\.claude\projects\` |

Each project folder contains JSONL files with your conversations.

### Step 2: Add a Watch Directory

1. Go to **Ingestion** in the sidebar
2. Click **Add Directory**
3. Enter the path to your Claude Code logs folder
4. Click **Start Watching**

CatSyphon will automatically import existing logs and watch for new ones.

### Step 3: Explore Your Data

- **Dashboard** - Overview of all your sessions
- **Sessions** - Browse individual conversations
- **Analytics** - Tool usage, sentiment trends, file changes
- **Health** - AI collaboration effectiveness score

---

## Understanding the Dashboard

### Session Archive
Browse all your AI coding sessions. Each card shows:
- Session name and project
- Git branch (if available)
- Token usage
- Plan indicator (if Claude made a plan)

### Analytics
- **Tool Usage** - Which tools Claude uses most (Read, Edit, Bash, etc.)
- **Sentiment** - Track frustration vs. productivity over time
- **Files Changed** - Most frequently modified files

### Health Score
An overall effectiveness score based on:
- Session success rates
- Error patterns
- Tool efficiency
- Completion rates

---

## Optional: AI-Powered Tagging

For deeper insights, add your OpenAI API key to enable automatic tagging:

1. Edit `.env` in the CatSyphon folder
2. Add: `OPENAI_API_KEY=sk-your-key-here`
3. Restart the backend

CatSyphon will analyze sessions for:
- Intent (feature, bug fix, refactor, learning)
- Outcome (success, partial, failed)
- Sentiment score
- Key problems encountered

**Cost:** ~$0.01 per conversation (using gpt-4o-mini)

---

## Troubleshooting

### "Database connection failed"
Make sure Docker is running:
```bash
docker-compose up -d
```

### "No logs found"
Check the log path exists and contains `.jsonl` files:
```bash
ls ~/.claude/projects/
```

### "Frontend won't start"
Make sure you're in the frontend directory:
```bash
cd frontend && pnpm dev
```

---

## Next Steps

- **Watch multiple directories** - Add more log sources from the Ingestion page
- **Enable auto-refresh** - Dashboard updates every 15 seconds by default
- **Explore Analytics** - Find patterns in your AI collaboration

---

## Getting Help

- **Issues**: https://github.com/kulesh/catsyphon/issues
- **Documentation**: [Full Docs](./README.md)

---

*Happy analyzing!*

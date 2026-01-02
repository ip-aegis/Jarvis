# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis is an AI/LLM-enabled lab monitoring and management application. It provides:
- Server onboarding with SSH key exchange and agent installation
- Real-time monitoring of CPU, GPU, memory, disk, and temperatures
- LLM-powered chat with isolated contexts (general, monitoring, projects)
- Project scanning with tech stack detection
- Web search integration via SearXNG

## Architecture

### Infrastructure
| Component | Host | Purpose |
|-----------|------|---------|
| Jarvis Web App | 10.10.20.235 | FastAPI backend + React frontend |
| Nginx | 10.10.20.235 | HTTPS reverse proxy (port 443) |
| Ollama LLM | 10.10.20.62 (Alpha) | Llama 3.1 70B with RTX 3090 |
| SearXNG | 10.10.20.235:8888 | Self-hosted web search |
| PostgreSQL | 10.10.20.235:5432 | TimescaleDB for metrics |

### Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Paramiko
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **Database**: PostgreSQL with TimescaleDB
- **LLM**: Ollama with Llama 3.1 70B (4-bit quantized)

## Development Commands

```bash
# Start development environment
docker-compose up -d

# Backend only (for local dev)
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend only (for local dev)
cd frontend && npm install
npm run dev

# Run database migrations
cd backend && alembic upgrade head

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Project Structure

```
Jarvis/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (env vars)
│   │   ├── api/routes/          # API endpoints
│   │   ├── services/            # Business logic
│   │   │   ├── ssh.py           # SSH operations
│   │   │   ├── ollama.py        # LLM client
│   │   │   └── search.py        # SearXNG client
│   │   ├── models/              # SQLAlchemy models
│   │   └── tools/               # LLM tool definitions
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/          # Sidebar, Layout
│   │   │   ├── chat/            # ChatPanel
│   │   │   └── servers/         # OnboardingWizard
│   │   └── pages/               # Dashboard, Chat, Servers, Monitoring, Projects
│   └── package.json
├── agent/                       # Remote monitoring agent
├── nginx/                       # HTTPS proxy config
├── scripts/                     # Setup scripts
└── docker-compose.yml
```

## Key APIs

### Server Onboarding
```
POST /api/servers/onboard
{
  "credentials": {
    "hostname": "server-01",
    "ip_address": "10.10.20.x",
    "username": "root",
    "password": "...",
    "port": 22
  },
  "install_agent": true
}
```

### Chat (Streaming)
```
POST /api/chat/message/stream
{
  "message": "...",
  "session_id": "...",
  "context": "general|monitoring|projects",
  "history": [...]
}
```

### Metrics WebSocket
```
WS /api/monitoring/ws
```

## LLM Integration

The Ollama service (`backend/app/services/ollama.py`) provides:
- `chat()` - Single response
- `chat_stream()` - Streaming response (SSE)
- `chat_with_tools()` - Tool calling support

Chat contexts are isolated:
- **general**: Full lab context, all tools available
- **monitoring**: Server metrics focus, monitoring tools
- **projects**: Project info, code analysis tools

## UI Design

Cisco Magnetic / Meraki style:
- Primary: `#00bceb`
- Background: `#1a1a2e`
- Surface: `#252542`
- Use `magnetic-card`, `magnetic-button-primary` utility classes

## Environment Variables

```bash
DATABASE_URL=postgresql://jarvis:password@db:5432/jarvis
OLLAMA_URL=http://10.10.20.62:11434
SEARXNG_URL=http://localhost:8888
```

## Setup Scripts

```bash
# Set up Ollama on Alpha (run on 10.10.20.62)
./scripts/setup-ollama.sh

# Set up Nginx HTTPS (run on 10.10.20.235)
./scripts/setup-nginx.sh
```

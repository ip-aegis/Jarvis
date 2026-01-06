# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis is an AI/LLM-enabled lab monitoring, smart home automation, and personal productivity platform. It provides:
- Server onboarding with SSH key exchange and agent installation
- Real-time monitoring of CPU, GPU, memory, disk, and temperatures
- Network device management with SNMP support
- Smart home integration (Ring, LG ThinQ, Bosch, HomeKit, Apple TV)
- Personal journaling with AI-powered search and summarization
- Work account and notes management
- LLM-powered chat with isolated contexts
- Infrastructure automation with scheduled actions
- Project scanning with tech stack detection
- Web search integration via SearXNG

## Architecture

### Infrastructure
| Component | Host | Purpose |
|-----------|------|---------|
| Jarvis Web App | 10.10.20.235 | FastAPI backend + React frontend |
| Nginx | 10.10.20.235 | HTTPS reverse proxy (port 443) |
| OpenAI API | External | Primary LLM provider |
| Ollama (Legacy) | 10.10.20.62 | Llama 3.1 8B with RTX 3090 |
| SearXNG | 10.10.20.235:8888 | Self-hosted web search |
| PostgreSQL | 10.10.20.235:5432 | TimescaleDB for metrics |

### Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Paramiko, pysnmp
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts
- **Database**: PostgreSQL 15 with TimescaleDB
- **LLM**: OpenAI API (primary), Ollama (legacy)
- **Task Scheduling**: APScheduler

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

# Run tests
cd backend && pytest
cd frontend && npm test

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
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── api/routes/          # API endpoints
│   │   │   ├── chat.py          # LLM chat
│   │   │   ├── servers.py       # Server management
│   │   │   ├── monitoring.py    # Metrics & WebSocket
│   │   │   ├── projects.py      # Project scanning
│   │   │   ├── network.py       # SNMP device management
│   │   │   ├── actions.py       # Infrastructure automation
│   │   │   ├── home.py          # Smart home control
│   │   │   ├── journal.py       # Personal journaling
│   │   │   ├── work.py          # Work accounts & notes
│   │   │   └── settings.py      # User preferences
│   │   ├── services/            # Business logic
│   │   │   ├── ssh.py           # SSH operations
│   │   │   ├── openai_service.py # OpenAI LLM client
│   │   │   ├── ollama.py        # Ollama LLM client (legacy)
│   │   │   ├── search.py        # SearXNG client
│   │   │   ├── snmp.py          # SNMP device polling
│   │   │   ├── actions.py       # Action execution & scheduling
│   │   │   ├── journal.py       # Journal management
│   │   │   ├── work_notes.py    # Work account management
│   │   │   └── home/            # Smart home integrations
│   │   ├── models/              # SQLAlchemy models
│   │   ├── tools/               # LLM tool definitions
│   │   └── core/                # Security, logging, exceptions
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main app with routing
│   │   ├── components/
│   │   │   ├── layout/          # Sidebar, Layout
│   │   │   ├── chat/            # ChatPanel
│   │   │   └── servers/         # OnboardingWizard
│   │   ├── pages/               # Page components
│   │   │   ├── Dashboard.tsx    # System overview
│   │   │   ├── Servers.tsx      # Server management
│   │   │   ├── Monitoring.tsx   # Real-time metrics
│   │   │   ├── Chat.tsx         # LLM chat interface
│   │   │   ├── Projects.tsx     # Project scanning
│   │   │   ├── Network.tsx      # Network devices
│   │   │   ├── Actions.tsx      # Infrastructure automation
│   │   │   ├── Home.tsx         # Smart home control
│   │   │   ├── Journal.tsx      # Personal journaling
│   │   │   ├── Work.tsx         # Work management
│   │   │   └── Settings.tsx     # User preferences
│   │   ├── services/            # API client
│   │   └── types/               # TypeScript definitions
│   └── package.json
├── agent/                       # Remote monitoring agent
├── nginx/                       # HTTPS proxy config
├── scripts/                     # Setup scripts
├── docker-compose.yml           # Development environment
└── docker-compose.prod.yml      # Production environment
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
  "context": "general|monitoring|projects|network|actions|home|journal|work",
  "history": [...]
}
```

### Network Device Onboarding
```
POST /api/network/devices/onboard
{
  "name": "switch-01",
  "ip_address": "10.10.20.x",
  "device_type": "switch",
  "connection_method": "snmp",
  "snmp_community": "public",
  "snmp_version": "2c"
}
```

### Metrics WebSocket
```
WS /api/monitoring/ws
```

### Smart Home
```
POST /api/home/devices/{device_id}/action
{
  "action": "unlock|lock|arm|disarm|set_temperature|...",
  "params": {}
}
```

## LLM Integration

The OpenAI service (`backend/app/services/openai_service.py`) is the primary LLM provider:
- `chat()` - Single response with tool support
- `list_models()` - Available models
- Embedding generation for semantic search

Legacy Ollama support in `backend/app/services/ollama.py`:
- `chat()` - Single response
- `chat_stream()` - Streaming response (SSE)
- `chat_with_tools()` - Tool calling support

### Chat Contexts
- **general**: Full lab context, all tools available
- **monitoring**: Server metrics focus, monitoring tools
- **projects**: Project info, code analysis tools
- **network**: Network device management, SNMP tools
- **actions**: Infrastructure automation, command execution
- **home**: Smart home device control, automation
- **journal**: Personal journal entries, search, summaries
- **work**: Work accounts, notes, action items

## LLM Tools

Tools are defined in `backend/app/tools/` and registered for LLM function calling:
- `server_tools.py` - Server metrics and management
- `project_tools.py` - Project scanning
- `web_search.py` - SearXNG integration
- `network_tools.py` - SNMP device queries
- `infrastructure_actions.py` - Command execution
- `home_tools.py` - Smart home control
- `journal_tools.py` - Journal search/create
- `work_tools.py` - Work account lookup

## Database Models

Core models in `backend/app/models/`:
- **Server** - Monitored servers with SSH credentials
- **Metric** - Time-series performance data (TimescaleDB)
- **Project** - Codebase metadata per server
- **ChatSession/ChatMessage** - Conversation history
- **NetworkDevice/NetworkMetric** - SNMP devices and metrics
- **HomeDevice/HomeEvent/HomeAutomation** - Smart home
- **JournalEntry/JournalSummary** - Personal journal
- **WorkAccount/WorkNote/WorkUserProfile** - Work management

## UI Design

Cisco Magnetic / Meraki style:
- Primary: `#00bceb`
- Background: `#1a1a2e`
- Surface: `#252542`
- Use `magnetic-card`, `magnetic-button-primary` utility classes

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://jarvis:password@db:5432/jarvis

# LLM Providers
OPENAI_API_KEY=sk-...
OLLAMA_URL=http://10.10.20.62:11434

# Search
SEARXNG_URL=http://localhost:8888

# Security
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Smart Home (optional)
RING_USERNAME=...
RING_PASSWORD=...
LG_THINQ_USERNAME=...
LG_THINQ_PASSWORD=...
```

## Setup Scripts

```bash
# Set up Ollama on Alpha (run on 10.10.20.62)
./scripts/setup-ollama.sh

# Set up Nginx HTTPS (run on 10.10.20.235)
./scripts/setup-nginx.sh
```

## Testing

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm test

# With coverage
cd backend && pytest --cov=app
```

## Production Deployment

```bash
# Build and start production containers
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

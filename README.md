# Jarvis

An AI/LLM-enabled lab monitoring, smart home automation, and personal productivity platform.

## Features

### Server Monitoring
- SSH-based server onboarding with key exchange
- Automatic monitoring agent deployment
- Real-time metrics: CPU, GPU, memory, disk, temperatures
- WebSocket-based live updates
- Historical metric tracking with TimescaleDB

### Network Management
- SNMP v2c/v3 device monitoring
- Multi-vendor support (Cisco, HP, Ubiquiti, pfSense, Aruba)
- Interface discovery and traffic statistics
- REST API device integration (Unifi)

### Smart Home Automation
- **Ring**: Doorbells, cameras, security systems
- **LG ThinQ**: Washers, dryers, appliances
- **Bosch**: Home appliances
- **Apple HomeKit/Ecobee**: Thermostats, sensors
- **Apple TV/HomePod**: Media control
- Event monitoring and automation rules

### Personal Productivity
- **Journal**: Personal journaling with AI-powered semantic search and automatic summarization
- **Work Management**: Client/vendor account tracking, notes with action items, account enrichment

### AI-Powered Chat
- Multiple isolated contexts for different tasks
- OpenAI API integration with tool calling
- Context-aware responses with access to real-time data
- Streaming responses

### Infrastructure Automation
- Command execution with confirmation workflow
- Scheduled actions with APScheduler
- Rollback support and audit trail

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Paramiko |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Database | PostgreSQL 15 with TimescaleDB |
| LLM | OpenAI API (primary), Ollama (local) |
| Search | SearXNG (self-hosted) |
| Proxy | Nginx with HTTPS |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API key (or local Ollama instance)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/jarvis.git
cd jarvis

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start the development environment
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Configuration

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://jarvis:password@localhost:5432/jarvis

# LLM Providers
OPENAI_API_KEY=sk-your-openai-api-key
OLLAMA_URL=http://localhost:11434

# Search
SEARXNG_URL=http://localhost:8888

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Smart Home (optional)
RING_USERNAME=your-ring-email
RING_PASSWORD=your-ring-password
```

## Architecture

```
                    +------------------+
                    |     Nginx        |
                    |   (HTTPS:443)    |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +---------v--------+
     |    Frontend     |          |     Backend      |
     |  React + Vite   |          |     FastAPI      |
     |   (port 3000)   |          |    (port 8000)   |
     +-----------------+          +--------+---------+
                                           |
         +------------+------------+-------+-------+
         |            |            |               |
   +-----v----+ +-----v----+ +-----v-----+ +-------v------+
   | OpenAI   | | Ollama   | | SearXNG   | | PostgreSQL   |
   | API      | | (LLM)    | | (Search)  | | TimescaleDB  |
   +----------+ +----------+ +-----------+ +--------------+
```

## API Documentation

When the backend is running, access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/servers/onboard` | Onboard a new server |
| `WS /api/monitoring/ws` | Real-time metrics WebSocket |
| `POST /api/chat/message/stream` | Streaming LLM chat |
| `POST /api/network/devices/onboard` | Add network device |
| `POST /api/home/devices/{id}/action` | Control smart home device |
| `POST /api/journal/entries` | Create journal entry |
| `GET /api/work/accounts` | List work accounts |

## Project Structure

```
Jarvis/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── models/          # Database models
│   │   ├── tools/           # LLM tool definitions
│   │   └── core/            # Security, logging
│   ├── alembic/             # Database migrations
│   └── tests/               # Test suite
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable UI
│   │   └── services/        # API client
│   └── package.json
├── docker-compose.yml       # Development environment
├── docker-compose.prod.yml  # Production environment
└── CLAUDE.md                # AI assistant instructions
```

## Testing

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Frontend tests
cd frontend
npm test
```

## Production Deployment

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Set up Nginx with SSL certificates
./scripts/setup-nginx.sh
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

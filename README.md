# Refind Cloud - Production Discord Bot Foundation

Refind Cloud is a production-oriented Discord bot project built from scratch using Python 3.12+, `discord.py`, PostgreSQL, async SQLAlchemy 2.x, `asyncpg`, Alembic, and Pydantic Settings.

---

## 1. Project Architecture

The repository enforces clean separation of concerns:

```
Refind Cloud/
├── alembic.ini                   # Alembic migration configuration
├── alembic/                      # Database migration scripts & async env.py
├── app/                          # Core application package
│   ├── __init__.py
│   ├── __main__.py               # Application startup entry point
│   ├── core/                     # Core settings, logging, and AppContext
│   │   ├── config.py             # Pydantic BaseSettings validation
│   │   ├── context.py            # Shared AppContext singleton container
│   │   └── logging.py            # Production JSON & Dev log formatters
│   ├── database/                 # Database engine, session, health checks
│   │   ├── base.py               # DeclarativeBase class
│   │   └── session.py            # Async engine, sessionmaker, healthcheck
│   ├── bot/                      # Discord bot client & cogs
│   │   ├── client.py             # RefindCloudBot (commands.Bot subclass)
│   │   └── cogs/                 # Slash command extensions
│   │       ├── ping.py           # Real /ping slash command
│   │       └── user.py           # Real /profile slash command
│   ├── modules/                  # Business domain modules
│   │   ├── README.md             # Architecture roadmap for future features
│   │   └── users/                # Discord User Identity domain module
│   │       ├── __init__.py
│   │       ├── models.py         # User ORM model (users table)
│   │       └── service.py        # Async user persistence & lookup service
│   └── services/                 # Cross-cutting service layer placeholder
│       └── README.md             # Service layer guidelines
├── tests/                        # Automated unit test suite
│   ├── conftest.py               # Test environment fixtures
│   ├── test_config.py            # Configuration validation tests
│   ├── test_database_utils.py    # Database utility & logger tests
│   └── test_users.py             # User model and service logic tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # PostgreSQL 16 infrastructure container
├── pyproject.toml                # Project metadata & dependency definitions
└── README.md                     # Project documentation
```

---

## 2. Current Implementation Scope

### Implemented Features:
- **Environment Management**: Type-safe settings validation using `pydantic-settings`.
- **Async Database Connection**: SQLAlchemy 2.x async engine with `asyncpg` pool management using `AppContext` as single resource owner.
- **Strict Database Startup Gate**: Real PostgreSQL health check (`SELECT 1`). Aborts startup, disposes engine, and exits with non-zero status if database is unreachable.
- **Discord User Identity Domain**: Persisted `users` table via `User` ORM model storing real Discord user ID, username, and global name.
- **Discord Bot Foundation & Cogs**: `RefindCloudBot` with minimum required intents, async `setup_hook`, cog loading, and graceful shutdown engine disposal.
- **Real Slash Commands**:
  - `/ping`: Returns real-time websocket latency in milliseconds.
  - `/profile`: Creates or retrieves the invoking Discord user's Refind Cloud profile in PostgreSQL.
- **Structured Logging**: Development colorized logs or production JSON logs based on `ENVIRONMENT`.
- **Safe Database Migrations**: Async Alembic setup with `Base.metadata` auto-detection for `users` table.
- **Automated Tests**: Pytest test suite for configuration, database utilities, and User domain logic.

---

## 3. Environment Variables

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `DISCORD_TOKEN` | **Yes** | — | Bot authentication token from Discord Developer Portal. |
| `DATABASE_URL` | **Yes** | — | PostgreSQL connection string (`postgresql+asyncpg://...`). |
| `POSTGRES_DB` | No | `refind_cloud` | Database name used by Docker Compose. |
| `POSTGRES_USER` | No | `postgres` | Database user used by Docker Compose. |
| `POSTGRES_PASSWORD` | No | `postgres` | Database password used by Docker Compose. |
| `DISCORD_GUILD_ID` | No | `None` | Guild ID for instant slash command sync during development. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `ENVIRONMENT` | No | `production` | Deployment mode (`development` or `production`). |

---

## 4. Setup & Running Instructions

### Step 1: Create a Python 3.12 Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 2: Install Dependencies

```bash
pip install -e ".[dev]"
```

---

### Step 3: Start Local PostgreSQL Database

Ensure Docker Desktop is running, then launch the database container:

```bash
docker-compose up -d postgres
```

To check PostgreSQL container status:
```bash
docker-compose ps
```

---

### Step 4: Configure Environment Variables

Create your local `.env` file by copying `.env.example`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Open `.env` and configure your credentials:
- `DISCORD_TOKEN`: Replace with your actual Discord Bot Token.
- `DATABASE_URL`: Set to `postgresql+asyncpg://postgres:postgres@localhost:5432/refind_cloud`
- `DISCORD_GUILD_ID`: (Optional) Set your Discord Server ID to instantly sync slash commands.
- `ENVIRONMENT`: Set to `development` for readable logs.

---

### Step 5: Run Database Migrations

Generate and apply the Alembic migration for the `users` table:

```bash
# Generate the initial users table revision script
alembic revision --autogenerate -m "create_users_table"

# Apply pending database migrations
alembic upgrade head
```

---

### Step 6: Run Automated Tests

Run the test suite manually without requiring Docker or active Discord connections:

```bash
pytest
```

---

### Step 7: Start Refind Cloud Bot

Start the Discord bot:

```bash
python -m app
```

Upon startup, the application will:
1. Load and validate required environment variables.
2. Configure structured application logging.
3. Perform a mandatory `SELECT 1` database health check against PostgreSQL.
4. Log in to Discord and execute `sync_application_commands()`.
5. Register `/ping` and `/profile` slash commands.

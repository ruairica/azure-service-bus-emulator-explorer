# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Azure Service Bus Emulator Explorer - a web-based UI for interacting with the Azure Service Bus Emulator. Built with Python using FastHTML (server-side HTMX framework), MonsterUI components, and the Azure Service Bus SDK.

## Common Commands

```bash
# Install dependencies
uv sync

# Run the application (starts web server, typically on localhost:8000)
uv run python src/sb.py
```

No test or lint configuration exists yet.

## Architecture

### Key Files
- **src/sb.py** - Main FastHTML application with all routes and UI components
- **src/sb_config_models.py** - Pydantic models defining Service Bus configuration structure (Namespaces, Queues, Topics, Subscriptions)

### Tech Stack
- **FastHTML** (python-fasthtml) - Server-side web framework with HTMX integration
- **MonsterUI** - UI component library (violet theme)
- **azure-servicebus** - Azure SDK for Service Bus emulator interaction
- **Pydantic** - Configuration data models
- **SQLite** - Persistent storage via FastHTML's database utilities

### Database
SQLite database at `src/data/sb9.db` with two tables:
- `configs` - Stores Service Bus configuration file paths (id, path, name, priority)
- `sent_messages` - Caches sent messages for reuse (stores message properties as comma-separated strings)

### Route Patterns
- `/` - Home page
- `/loadconfig` - Load Service Bus configuration file
- `/configs/{configId}` - Configuration management
- `/{namespace}/{entity}/send` - Send messages to queue/topic
- `/{namespace}/{entity}/{subscription}/messages/...` - View subscription messages

### HTMX Integration
The app uses HTMX for dynamic updates. Routes detect HTMX requests via `hx-request` header to return partial HTML fragments vs full page renders.

## Connection String
Currently hardcoded for development emulator:
```
Endpoint=mytester://localhost;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=SAS_KEY_VALUE;UseDevelopmentEmulator=true;
```

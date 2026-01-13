# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Azure Service Bus Emulator Explorer - a web-based UI for interacting with the Azure Service Bus Emulator. Built with Python using FastHTML (server-side HTMX framework), MonsterUI components, and the Azure Service Bus SDK.

## Common Commands

```bash
# Install dependencies
uv sync

# Run the application (starts web server, typically on localhost:8000)
uv run python sb.py

# after completing a task, format the code
uvx ruff format
```

No test or lint configuration exists yet.

## Architecture

### Key Files
- **sb.py** - Main FastHTML application with all routes and UI components
- **models.py** - Data models including Pydantic models for Service Bus configuration (Namespaces, Queues, Topics, Subscriptions) and dataclasses for message handling

### Tech Stack
- **FastHTML** (python-fasthtml) - Server-side web framework with HTMX integration
- **MonsterUI** - UI component library (violet theme)
- **azure-servicebus** - Azure SDK for Service Bus emulator interaction
- **Pydantic** - Configuration data models
- **SQLite** - Persistent storage via FastHTML's database utilities

### Database
SQLite database at `sb9.db` with two tables:
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

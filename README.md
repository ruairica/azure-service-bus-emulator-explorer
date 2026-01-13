# SB Emulator Explorer

A local web UI for the Azure Service Bus Emulator. Send messages, view active and dead-lettered messages, and save messages for easy re-use.

### Prerequisites

- Python 3.10 or higher
- UV (install from https://docs.astral.sh/uv/getting-started/installation/)

### Installation

1. Clone or download this repository
2. Run the following command to install dependencies:

```bash
uv sync
```

This will create a virtual environment and install all required dependencies.

## Running the Application

To run the application:

```bash
uv run sb.py
```

## Dependencies

- **python-fasthtml**: Web framework
- **azure-servicebus**: Azure Service Bus SDK
- **monsterui**: UI components
- **pydantic**: Data validation


## Limitations
- Assumes service bus emulator is running on localhost

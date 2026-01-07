# SB Emulator Explorer

A web-based tool for interacting with Azure Service Bus Emulator.

## Setup

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

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
uv run python sb.py
```

Or use the FastHTML serve command:

```bash
uv run fasthtml serve sb.py
```

## Dependencies

- **python-fasthtml**: Web framework
- **azure-servicebus**: Azure Service Bus SDK
- **monsterui**: UI components
- **pydantic**: Data validation

## Project Structure

- `sb.py`: Main application file
- `sb_config_models.py`: Pydantic models for Service Bus configuration
- `data/`: SQLite database storage
- `pyproject.toml`: Project configuration and dependencies


## TODO
- currently turning the list of headers into a comma separated list which is terrible but simple
- Database table creation should use FastHTML best practices, there are also some other best practices here that should be implemented https://www.fastht.ml/docs/ref/best_practice.html#database-table-creation
- Connection string/PORT should be configurable in some way
- I think all of the endpoints should be potentially under the config top-level path so that the topics aren't shared across different configs.
- Currently, you can only stand to a topic or a queue, not both.


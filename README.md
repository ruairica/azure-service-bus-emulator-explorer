# SB Emulator Explorer

A local web UI for the Azure Service Bus Emulator. (since Service bus Explorer doesn't support the emulator)

## Getting Started

1. Install Python and UV.
2. Clone the repository
3. Install dependencies: `uv sync`
4. Start the app: `uv run sb.py` (this starts the FastHTML web app locally)
5. Open `http://localhost:5001` in your browser

## Features

- Insert a path to a service bus emulator json configuration file to connect (it's persisted in sqlite for future)
- Browse namespaces, topics, subscriptions, and queues.
- Send messages to topics and queues (can send custom headers)
- Save sent messages to reuse them in the future
- View active and deadlettered messages on topic subscriptions and queues.
- Click a message to inspect it.
- Delete individual active or dead-lettered messages from subscriptions and queues

## Limitations
The code assumes the service bus emulator is already running, and is running on localhost.

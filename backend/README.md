# UAV Log Viewer Backend

This is the backend server for the UAV Log Viewer application, built with FastAPI.

## Features

-   HTTP API endpoints
-   WebSocket support for real-time communication
-   CORS enabled for frontend integration
-   Connection management for multiple clients

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Server

To run the development server:

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:

-   HTTP API: http://localhost:8000
-   WebSocket: ws://localhost:8000/ws/{client_id}

## API Endpoints

### HTTP Endpoints

-   `GET /`: Welcome message
-   `GET /health`: Health check endpoint

### WebSocket Endpoint

-   `WS /ws/{client_id}`: WebSocket connection for real-time communication

## WebSocket Message Format

Messages should be sent as JSON strings with the following structure:

```json
{
    "type": "message_type",
    "content": "message_content",
    "timestamp": "2023-11-14T12:00:00Z" // Added automatically by server
}
```

## Development

The server uses FastAPI's automatic reload feature. Any changes to the code will automatically restart the server.

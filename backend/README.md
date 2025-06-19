# UAV Log Viewer Backend

A sophisticated AI-powered backend system for analyzing ArduPilot flight logs using an agentic architecture with Large Language Models (LLMs) and vector databases.

## What It Does

The UAV Log Viewer Backend is an intelligent system that:

-   **Processes ArduPilot DataFlash logs** (.bin files) and converts them to structured JSON format
-   **Provides AI-powered analysis** of flight data through natural language queries
-   **Uses an agentic architecture** with multiple specialized AI agents working together
-   **Implements semantic search** using ChromaDB vector database for log message retrieval
-   **Supports real-time communication** via WebSocket connections
-   **Handles file uploads** with chunked transfer for large log files
-   **Maintains conversation context** for multi-turn interactions

## Agentic Architecture

The system implements a sophisticated multi-agent workflow using LangGraph:

### Core Components

1. **Connection Manager** (`main.py`)

    - Manages WebSocket connections and client sessions
    - Handles file uploads and chunked file reconstruction
    - Maintains conversation histories per client

2. **Log Processor** (`log_processor.py`)

    - Parses ArduPilot DataFlash logs using MAVdataflash library
    - Converts binary logs to structured JSON format
    - Extracts message types and their data fields

3. **LLM Processor** (`llm_processor.py`)
    - Orchestrates the agentic workflow
    - Manages conversation state and context
    - Coordinates between different AI agents

### Agentic Workflow

The system uses a state-based workflow with the following nodes:

1. **Retrieve Node** - Semantic search using ChromaDB

    - Searches for relevant log message definitions based on user query
    - Uses sentence transformers for semantic similarity

2. **Analyze Node** - Query understanding and planning

    - Analyzes user intent and determines required message types
    - Identifies specific fields needed to answer the query
    - Uses Claude-3-Sonnet for intelligent query parsing

3. **Fetch Data Node** - Data retrieval and filtering

    - Retrieves actual log data for identified message types
    - Filters data based on required fields
    - Combines schema information with actual data

4. **Analyze Data Node** - Data analysis and response generation

    - Analyzes the retrieved flight data
    - Generates comprehensive, contextual responses
    - Provides insights and explanations about flight behavior

5. **Update History Node** - Conversation management
    - Maintains conversation context for follow-up questions
    - Updates conversation history for future interactions

### State Management

The system maintains a `AgentState` that includes:

-   User query
-   Conversation history
-   Retrieved message definitions
-   Selected message types and fields
-   Fetched flight data
-   Final answer

## Setup Instructions

### Prerequisites

-   Python 3.11 or higher
-   pip package manager
-   Git (for cloning the repository)

### Installation

1. **Clone the repository** (if not already done):

```bash
git clone <repository-url>
cd UAVLogViewer/backend
```

2. **Create a virtual environment**:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:

```bash
cp .env.example .env  # Create from template if available
# Edit .env with your API keys
```

5. **Initialize the vector database**:

```bash
python3 indexer/main.py
```

### Running the Server

#### Development Mode

```bash
#  using Python directly
python3 run.py

# Or using uvicorn directly
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:

-   **HTTP API**: http://localhost:8000
-   **WebSocket**: ws://localhost:8000/ws/{client_id}
-   **API Documentation**: http://localhost:8000/docs (Swagger UI)

## Environment Variables

Create a `.env` file in the backend directory with the following variables:

```bash
# Required: Anthropic API Key for Claude LLM
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: Environment configuration
ENVIRONMENT=development  # or production

# Optional: Server configuration
HOST=0.0.0.0
PORT=8000

# Optional: Database configuration
CHROMA_DB_PATH=chroma_db
COLLECTION_NAME=ardupilot_logs

# Optional: Logging configuration
LOG_LEVEL=INFO
```

### Getting API Keys

1. **Anthropic API Key**:
    - Visit [Anthropic Console](https://console.anthropic.com/)
    - Create an account and generate an API key
    - Add the key to your `.env` file

## Technologies Used

### Core Framework

-   **FastAPI** (0.109.2) - Modern, fast web framework for building APIs
-   **Uvicorn** (0.27.1) - ASGI server for running FastAPI applications

### AI and Machine Learning

-   **LangChain** - Framework for building LLM applications
-   **LangGraph** (0.0.26) - Library for building stateful, multi-actor applications
-   **Claude-3-Sonnet** - Anthropic's advanced language model
-   **Sentence Transformers** (2.5.1) - For semantic text embeddings

### Vector Database

-   **ChromaDB** (0.4.22) - Vector database for similarity search
-   **all-MiniLM-L6-v2** - Embedding model for semantic search

### Data Processing

-   **Pandas** (2.2.0) - Data manipulation and analysis
-   **NumPy** (1.26.3) - Numerical computing
-   **PyMAVLink** (2.4.37) - MAVLink protocol implementation
-   **MAVdataflash** (≥1.0.0) - ArduPilot DataFlash log parser

### WebSocket and Real-time Communication

-   **WebSockets** (≥10.0) - Real-time bidirectional communication

### Security and Authentication

-   **Python-Jose** (3.3.0) - JavaScript Object Signing and Encryption
-   **Passlib** (1.7.4) - Password hashing library

### Utilities

-   **Python-multipart** (0.0.9) - File upload handling
-   **Pydantic** (2.6.1) - Data validation using Python type annotations
-   **Python-dotenv** (1.0.0) - Environment variable management

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and WebSocket handling
│   ├── log_processor.py     # ArduPilot log file processing
│   └── llm_processor.py     # AI agent orchestration and LLM integration
├── chroma_db/               # Vector database storage
├── indexer/
│   └── main.py              # Vector database initialization
├── processed/               # Processed log files
├── scraper/
│   ├── schema.json          # ArduPilot log message schemas
│   └── scraper.py           # Schema scraping utility
├── uploads/                 # Uploaded log files
├── requirements.txt         # Python dependencies
├── run.py                   # Server startup script
├── run.sh                   # Development server script
└── README.md               # This file
```

## API Endpoints

### HTTP Endpoints

-   `GET /` - Welcome message and server status
-   `GET /health` - Health check endpoint
-   `GET /docs` - Interactive API documentation (Swagger UI)

### WebSocket Endpoint

-   `WS /ws/{client_id}` - Real-time communication endpoint

### WebSocket Message Format

Messages should be sent as JSON strings:

```json
{
    "type": "message_type",
    "content": "message_content",
    "timestamp": "2023-11-14T12:00:00Z"
}
```

#### Supported Message Types

-   `upload_file` - Upload a log file (chunked)
-   `chat` - Send a question about flight data
-   `system` - System messages and status updates

## Workflow Example

1. **Client connects** via WebSocket with unique client ID
2. **File upload** - Client uploads ArduPilot .bin log file in chunks
3. **File processing** - Server reconstructs file and processes it to JSON
4. **Vector database initialization** - Log message schemas are indexed
5. **AI conversation** - Client asks questions about flight data
6. **Agentic processing**:
    - Retrieve relevant message definitions
    - Analyze query and determine required data
    - Fetch actual flight data
    - Generate comprehensive response
7. **Response streaming** - AI response is streamed back to client

#!/bin/bash

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the FastAPI server
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --reload-exclude "uploads/*" --reload-exclude "*.log" --reload-exclude "*.tmp"

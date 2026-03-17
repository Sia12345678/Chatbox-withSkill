#!/bin/bash
# Start script for Render deployment

# Load environment variables from .env if exists
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Start the server
uvicorn main:app --host 0.0.0.0 --port $PORT

# Doxa AI Agent - Full Stack

A robust AI support agent featuring a FastAPI backend and a premium React frontend.

## Features

- **Intelligent RAG**: Uses ChromaDB and Mistral AI for context-aware responses.
- **Modern UI**: React-based frontend with glassmorphism, animations, and responsive design.
- **Safety First**: Deterministic evaluation for sensitive data and confidence scoring.
- **Docker Ready**: Easy deployment using Docker Compose.

## Prerequisites

- Python 3.10+
- Node.js 20+
- Docker & Docker Compose (optional for containerized deployment)
- Mistral AI API Key

## Quick Start (Docker)

1. Create a `.env` file in the root directory (or ensure `ai/.env` exists) with your `MISTRAL_API_KEY`.
2. Run the entire stack:
   ```bash
   docker-compose up --build
   ```
3. Access the frontend at `http://localhost:80` and the backend documentation at `http://localhost:8000/docs`.

## Manual Setup

### Backend
1. Install dependencies:
   ```bash
   pip install -r ai/requirements.txt
   pip install fastapi uvicorn pydantic python-dotenv structlog tenacity circuitbreaker flask-cors
   ```
2. Start the FastAPI server:
   ```bash
   python backend/main.py
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

## Project Structure

- `ai/`: Core AI agent logic (AgentManager, RAG, etc.).
- `backend/`: FastAPI application and API endpoints.
- `frontend/`: React/Vite application with modern CSS.
- `docker-compose.yml`: Orchestration for backend and frontend.

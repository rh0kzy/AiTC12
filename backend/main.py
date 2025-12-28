import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Add the project root to sys.path to allow importing from the 'ai' directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agent_manager import AgentManager
from ai.solutionfinder import ingest_pdf_to_chroma

app = FastAPI(title="Doxa AI Agent API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AgentManager
agent_manager = AgentManager()

class TicketRequest(BaseModel):
    ticket: str

class IngestRequest(BaseModel):
    content: str
    category: str = "general"
    is_path: bool = False

@app.post("/ingest")
async def ingest_doc(request: IngestRequest):
    try:
        if request.is_path:
            if os.path.exists(request.content):
                ingest_pdf_to_chroma(request.content, category=request.category)
                return {"status": "success", "message": f"Ingested PDF: {request.content}"}
            else:
                raise HTTPException(status_code=404, detail="File not found on server")
        else:
            return {"status": "error", "message": "Text ingestion not implementation yet"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RatingRequest(BaseModel):
    ticket_id: str
    stars: int
    analysis: Dict[str, Any]
    precheck: Dict[str, Any]

@app.post("/process_ticket")
async def process_ticket(request: TicketRequest):
    if not request.ticket:
        raise HTTPException(status_code=400, detail="No ticket content provided")
    
    try:
        # Run the agent pipeline
        result = agent_manager.process_ticket(request.ticket)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rate_ticket")
async def rate_ticket(request: RatingRequest):
    try:
        result = agent_manager.handle_rating(
            request.ticket_id, 
            request.stars, 
            request.analysis, 
            request.precheck
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

#!/usr/bin/env -S uv run
"""
FastAPI service template
"""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="app-template",
    description="FastAPI service template",
    version="1.0.0",
)

class HealthResponse(BaseModel):
    status: str
    version: str
    commit_sha: str | None = None

class MessageResponse(BaseModel):
    message: str
    timestamp: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for load balancer"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        commit_sha=os.getenv("COMMIT_SHA")
    )

@app.get("/", response_model=MessageResponse)
async def root():
    """Root endpoint"""
    from datetime import datetime
    return MessageResponse(
        message="Hello from FastAPI!",
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/api/status", response_model=dict)
async def api_status():
    """API status endpoint"""
    return {
        "api": "running",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "port": int(os.getenv("APP_PORT", "3000"))
    }

if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", os.getenv("PORT", "3000")))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Development vs production settings
    if os.getenv("ENVIRONMENT") == "production":
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            workers=2,
            access_log=True
        )
    else:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=True,
            access_log=True
        )


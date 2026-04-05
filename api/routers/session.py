"""
OrientAgent - Session Router

API endpoints for session management and workflow execution.
"""

import os
import uuid
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse

from api.schemas import (
    SessionRequest,
    SessionResponse,
    SessionResult,
)
from api.sse import event_stream
from graph.state import create_initial_state, StudentProfile
from graph.graph import stream_graph, get_graph

router = APIRouter(prefix="/api/session", tags=["session"])

# In-memory session storage (for demo; use Redis in production)
_sessions: dict[str, dict] = {}


def _get_db_path() -> str:
    """Get SQLite database path from environment."""
    return os.getenv("SQLITE_DB_PATH", "./data/orient_agent.db")


def _init_db():
    """Initialize SQLite database with sessions table."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'started',
            profile_json TEXT,
            pdf_path TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def _save_session(session_id: str, profile: dict, status: str = "started"):
    """Save session to SQLite."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO sessions (id, status, profile_json, pdf_path)
        VALUES (?, ?, ?, ?)
    """, (session_id, status, json.dumps(profile, ensure_ascii=False), profile.get("pdf_path")))
    
    conn.commit()
    conn.close()


def _load_session(session_id: str) -> Optional[dict]:
    """Load session from SQLite."""
    db_path = _get_db_path()
    
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, profile_json, pdf_path FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        profile = json.loads(row[1]) if row[1] else {}
        profile["status"] = row[0]
        profile["pdf_path"] = row[2]
        return profile
    
    return None


async def _run_graph_background(session_id: str, initial_state: StudentProfile):
    """Run the graph in background and update session state."""
    try:
        _sessions[session_id]["status"] = "running"
        
        async for event_type, event_data in stream_graph(initial_state):
            # Store events for SSE retrieval
            if "events" not in _sessions[session_id]:
                _sessions[session_id]["events"] = []
            _sessions[session_id]["events"].append((event_type, event_data))
            
            if event_type == "agent_done":
                # Persist full node output (not only SSE summary fields)
                state_update = event_data.get("state_update", {})
                if isinstance(state_update, dict):
                    _sessions[session_id]["state"].update(state_update)

                    if state_update.get("error"):
                        _sessions[session_id]["status"] = "error"
                        _sessions[session_id]["error"] = state_update["error"]
            
            if event_type == "complete":
                if _sessions[session_id].get("status") != "error":
                    _sessions[session_id]["status"] = "complete"
                break
            
            if event_type == "error":
                _sessions[session_id]["status"] = "error"
                _sessions[session_id]["error"] = event_data.get("error", "Unknown error")
                _sessions[session_id]["state"]["error"] = _sessions[session_id]["error"]
                break
        
        # Save final state to DB
        _save_session(
            session_id,
            _sessions[session_id].get("state", {}),
            _sessions[session_id].get("status", "complete")
        )
        
    except Exception as e:
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["error"] = str(e)
        _save_session(session_id, _sessions[session_id].get("state", {}), "error")


@router.post("/start", response_model=SessionResponse)
async def start_session(
    request: SessionRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new orientation session.
    
    Creates a session, initializes the student profile, and begins
    the multi-agent workflow in the background.
    """
    # Initialize DB
    _init_db()
    
    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    
    # Create initial state
    initial_state = create_initial_state(
        nom=request.nom,
        serie_bac=request.serie_bac,
        notes=request.notes,
        interets=request.interets,
        ville=request.ville,
        langue=request.langue,
        budget=request.budget,
        session_id=session_id,
    )
    
    # Store in memory
    _sessions[session_id] = {
        "state": dict(initial_state),
        "status": "started",
        "created_at": datetime.now().isoformat(),
        "events": [],
    }
    
    # Save to DB
    _save_session(session_id, dict(initial_state), "started")
    
    # Start graph execution in background
    background_tasks.add_task(_run_graph_background, session_id, initial_state)
    
    return SessionResponse(
        session_id=session_id,
        status="started",
        message="Session créée. Suivez la progression via /api/session/{id}/status"
    )


@router.get("/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Stream session status via Server-Sent Events.
    
    Returns real-time updates as each agent completes its work.
    """
    if session_id not in _sessions:
        # Try loading from DB
        db_session = _load_session(session_id)
        if db_session:
            _sessions[session_id] = {
                "state": db_session,
                "status": db_session.get("status", "complete"),
                "events": [],
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    
    async def generate_events():
        """Generate SSE events from session state."""
        session = _sessions[session_id]
        sent_events = 0
        
        while True:
            # Send any new events
            events = session.get("events", [])
            while sent_events < len(events):
                yield events[sent_events]
                sent_events += 1
            
            # Check if complete
            status = session.get("status", "running")
            if status in ["complete", "error"]:
                if status == "error":
                    yield ("error", {"error": session.get("error", "Unknown error")})
                yield ("complete", {"session_id": session_id})
                break
            
            # Wait for more events
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_stream(generate_events()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{session_id}/result", response_model=SessionResult)
async def get_session_result(session_id: str):
    """
    Get the full session result.
    
    Returns the complete StudentProfile with all agent outputs.
    """
    session = _sessions.get(session_id)
    
    if not session:
        # Try loading from DB
        db_session = _load_session(session_id)
        if db_session:
            session = {"state": db_session, "status": db_session.get("status", "complete")}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    
    state = session.get("state", {})
    status = session.get("status", "running")
    
    return SessionResult(
        session_id=session_id,
        status=status,
        nom=state.get("nom", ""),
        serie_bac=state.get("serie_bac", ""),
        domain_scores=state.get("domain_scores", {}),
        learning_style=state.get("learning_style", ""),
        filieres_count=len(state.get("filieres_retrieved", [])),
        top_3=state.get("top_3", []),
        filiere_choisie=state.get("filiere_choisie"),
        interview_score=state.get("interview_score"),
        interview_feedback=state.get("interview_feedback"),
        pdf_path=state.get("pdf_path"),
        error=state.get("error") or session.get("error"),
    )


@router.get("/{session_id}/pdf")
async def download_pdf(session_id: str):
    """
    Download the PDF report for a session.
    """
    session = _sessions.get(session_id)
    
    if not session:
        db_session = _load_session(session_id)
        if db_session:
            session = {"state": db_session}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    
    pdf_path = session.get("state", {}).get("pdf_path")
    
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found. Please wait for generation to complete.")
    
    return FileResponse(
        path=pdf_path,
        filename=f"orient_agent_rapport_{session_id}.pdf",
        media_type="application/pdf"
    )

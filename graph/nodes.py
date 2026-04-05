"""
OrientAgent - Graph Node Wrappers

Wraps agent classes as LangGraph node functions.
"""

import os
from typing import Any
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from graph.state import StudentProfile
from agents.profiler import ProfileurAgent
from agents.explorer import ExplorateurAgent
from agents.advisor import ConseillerAgent
from pdf.generator import generate_report

load_dotenv()

# Lazy LLM initialization
_llm = None


def _get_llm() -> ChatGroq:
    """Get or create the shared LLM instance."""
    global _llm
    if _llm is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        
        _llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=api_key,
            temperature=0.7,
            max_tokens=4096,
        )
    return _llm


async def profileur_node(state: StudentProfile) -> dict[str, Any]:
    """
    LangGraph node for Agent 1: Profileur.
    
    Analyzes student profile and calculates domain scores.
    """
    llm = _get_llm()
    agent = ProfileurAgent(llm=llm)
    
    try:
        result = await agent.run(state)
        return result
    except Exception as e:
        return {
            "error": f"Profileur agent failed: {str(e)}",
            "current_step": "error",
        }


async def explorateur_node(state: StudentProfile) -> dict[str, Any]:
    """
    LangGraph node for Agent 2: Explorateur.
    
    Retrieves relevant filières using RAG and enriches with Tavily data.
    """
    llm = _get_llm()
    
    # Optional: Initialize Tavily client
    tavily_client = None
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            tavily_client = TavilyClient(api_key=tavily_key)
        except ImportError:
            pass
    
    agent = ExplorateurAgent(llm=llm, tavily_client=tavily_client)
    
    try:
        result = await agent.run(state)
        return result
    except Exception as e:
        return {
            "error": f"Explorateur agent failed: {str(e)}",
            "current_step": "error",
            "filieres_retrieved": [],
        }


async def conseiller_node(state: StudentProfile) -> dict[str, Any]:
    """
    LangGraph node for Agent 3: Conseiller.
    
    Ranks filières and generates personalized recommendations.
    """
    llm = _get_llm()
    agent = ConseillerAgent(llm=llm)
    
    try:
        result = await agent.run(state)
        return result
    except Exception as e:
        return {
            "error": f"Conseiller agent failed: {str(e)}",
            "current_step": "error",
            "top_3": [],
        }


async def pdf_generator_node(state: StudentProfile) -> dict[str, Any]:
    """
    LangGraph node for PDF generation.
    
    Creates a downloadable PDF report with all results.
    """
    try:
        import asyncio
        
        # Run sync PDF generation in executor
        loop = asyncio.get_event_loop()
        pdf_path = await loop.run_in_executor(
            None,
            generate_report,
            dict(state)
        )
        
        return {
            "pdf_path": pdf_path,
            "current_step": "complete",
        }
    except Exception as e:
        return {
            "error": f"PDF generation failed: {str(e)}",
            "current_step": "complete",  # Still complete, just without PDF
        }


def error_handler_node(state: StudentProfile) -> dict[str, Any]:
    """
    Error handler node for graceful failure recovery.
    """
    error = state.get("error", "Unknown error")
    current_step = state.get("current_step", "unknown")
    
    print(f"⚠️ Error in step '{current_step}': {error}")
    
    return {
        "current_step": "error",
    }


def should_continue(state: StudentProfile) -> str:
    """
    Conditional router to check for errors and route accordingly.
    
    Returns:
        The name of the next node to execute
    """
    if state.get("error"):
        return "error_handler"
    
    current_step = state.get("current_step", "")
    
    # Route to next step based on current_step
    step_routing = {
        "profileur": "explorateur",
        "explorateur": "conseiller",
        "conseiller": "coach_entretien",
        "coach_entretien": "pdf_generator",
        "interview_active": "__end__",  # Interview handled separately
        "complete": "__end__",
        "error": "__end__",
    }
    
    return step_routing.get(current_step, "__end__")

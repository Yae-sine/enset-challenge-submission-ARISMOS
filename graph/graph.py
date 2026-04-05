"""
OrientAgent - LangGraph Graph Builder

Defines and compiles the multi-agent LangGraph workflow.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import StudentProfile
from graph.nodes import (
    profileur_node,
    explorateur_node,
    conseiller_node,
    pdf_generator_node,
    error_handler_node,
)


def build_graph() -> StateGraph:
    """
    Build the OrientAgent LangGraph workflow.
    
    Graph structure:
    START -> profileur -> explorateur -> conseiller -> pdf_generator -> END
                ↓              ↓              ↓
            error_handler  error_handler  error_handler
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the graph with StudentProfile as state
    workflow = StateGraph(StudentProfile)
    
    # Add all nodes
    workflow.add_node("profileur", profileur_node)
    workflow.add_node("explorateur", explorateur_node)
    workflow.add_node("conseiller", conseiller_node)
    workflow.add_node("pdf_generator", pdf_generator_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Define the main flow with conditional routing
    workflow.set_entry_point("profileur")
    
    # Profileur -> Explorateur (or error)
    workflow.add_conditional_edges(
        "profileur",
        lambda state: "error_handler" if state.get("error") else "explorateur",
        {
            "explorateur": "explorateur",
            "error_handler": "error_handler",
        }
    )
    
    # Explorateur -> Conseiller (or error)
    workflow.add_conditional_edges(
        "explorateur",
        lambda state: "error_handler" if state.get("error") else "conseiller",
        {
            "conseiller": "conseiller",
            "error_handler": "error_handler",
        }
    )
    
    # Conseiller -> PDF Generator (or error)
    workflow.add_conditional_edges(
        "conseiller",
        lambda state: "error_handler" if state.get("error") else "pdf_generator",
        {
            "pdf_generator": "pdf_generator",
            "error_handler": "error_handler",
        }
    )
    
    # PDF Generator -> END
    workflow.add_edge("pdf_generator", END)
    
    # Error handler -> END
    workflow.add_edge("error_handler", END)
    
    return workflow


def compile_graph(checkpointer=None):
    """
    Compile the graph with optional checkpointer for state persistence.
    
    Args:
        checkpointer: Optional LangGraph checkpointer (default: MemorySaver)
    
    Returns:
        Compiled graph ready for invocation
    """
    workflow = build_graph()
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)


# Pre-compiled graph singleton for API use
_compiled_graph = None


def get_graph():
    """
    Get the singleton compiled graph instance.
    
    Returns:
        Compiled LangGraph
    """
    global _compiled_graph
    
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    
    return _compiled_graph


async def run_graph(initial_state: StudentProfile, config: dict = None) -> StudentProfile:
    """
    Run the graph from start to finish.
    
    Args:
        initial_state: The initial StudentProfile with user inputs
        config: Optional LangGraph config (e.g., thread_id for checkpointing)
    
    Returns:
        Final StudentProfile state after all agents have run
    """
    graph = get_graph()
    
    if config is None:
        config = {"configurable": {"thread_id": initial_state.get("session_id", "default")}}
    
    final_state = await graph.ainvoke(initial_state, config)
    return final_state


async def stream_graph(initial_state: StudentProfile, config: dict = None):
    """
    Stream graph execution events for SSE.
    
    Args:
        initial_state: The initial StudentProfile with user inputs
        config: Optional LangGraph config
    
    Yields:
        Tuples of (event_type, event_data) for SSE streaming
    """
    graph = get_graph()
    
    if config is None:
        config = {"configurable": {"thread_id": initial_state.get("session_id", "default")}}
    
    # Stream using astream_events for detailed progress
    async for event in graph.astream_events(initial_state, config, version="v2"):
        event_type = event.get("event", "")
        
        if event_type == "on_chain_start":
            name = event.get("name", "")
            if name in ["profileur", "explorateur", "conseiller", "coach_entretien", "pdf_generator"]:
                yield ("agent_start", {
                    "agent": name,
                    "message": f"Démarrage de l'agent {name}..."
                })
        
        elif event_type == "on_chain_end":
            name = event.get("name", "")
            output = event.get("data", {}).get("output", {})
            
            if name in ["profileur", "explorateur", "conseiller", "coach_entretien", "pdf_generator"]:
                yield ("agent_done", {
                    "agent": name,
                    "data": _extract_event_data(name, output),
                    "state_update": output if isinstance(output, dict) else {}
                })
        
        elif event_type == "on_chain_error":
            yield ("error", {
                "error": str(event.get("data", {}).get("error", "Unknown error"))
            })
    
    yield ("complete", {"session_id": initial_state.get("session_id", "")})


def _extract_event_data(agent_name: str, output: dict) -> dict:
    """Extract relevant data from agent output for SSE events."""
    if agent_name == "profileur":
        return {
            "domain_scores": output.get("domain_scores", {}),
            "learning_style": output.get("learning_style", ""),
        }
    elif agent_name == "explorateur":
        filieres = output.get("filieres_retrieved", [])
        return {
            "filieres_count": len(filieres),
            "top_types": list(set(f.get("type", "") for f in filieres[:5]))
        }
    elif agent_name == "conseiller":
        top_3 = output.get("top_3", [])
        return {
            "top_3_names": [f.get("filiere_nom", "") for f in top_3[:3]]
        }
    elif agent_name == "coach_entretien":
        return {
            "questions_count": len(output.get("interview_questions", [])),
            "filiere_choisie": output.get("filiere_choisie", ""),
        }
    elif agent_name == "pdf_generator":
        return {
            "pdf_path": output.get("pdf_path", ""),
        }
    return {}

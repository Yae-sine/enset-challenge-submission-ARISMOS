"""
OrientAgent - Tavily Search Tool

LangChain tool wrapper for Tavily web search to get real-time employment data.
"""

import os
from typing import Optional
from langchain_core.tools import tool
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

# Lazy initialization
_tavily_client: Optional[TavilyClient] = None


def _get_tavily_client() -> TavilyClient:
    """Lazily initialize the Tavily client."""
    global _tavily_client
    
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY environment variable not set. "
                "Get your API key at https://tavily.com"
            )
        _tavily_client = TavilyClient(api_key=api_key)
    
    return _tavily_client


def _truncate_result(text: str, max_chars: int = 500) -> str:
    """Truncate text to max_chars, ending at a word boundary."""
    if len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    
    return truncated + "..."


@tool
def search_employment_data(filiere_name: str) -> str:
    """
    Search for real-time employment data and salary information for a Moroccan filière.
    
    Use this tool to get up-to-date employment rates, salary ranges, and job market
    information for a specific study program in Morocco. This complements the static
    data in the RAG knowledge base with current market insights.
    
    Args:
        filiere_name: Name of the filière or career path to search for.
                      Examples: "ENSA Génie Informatique", "ingénieur BTP Maroc",
                      "diplômé ENCG emploi"
    
    Returns:
        Formatted string with employment data, salaries, and job market insights
        from recent web sources.
    
    Note:
        Results are limited to 500 characters per source to control token usage.
        For detailed information, refer to the original sources.
    """
    try:
        client = _get_tavily_client()
    except RuntimeError as e:
        return f"Erreur: {str(e)}"
    
    # Build search query optimized for Moroccan employment data
    query = f"{filiere_name} taux emploi salaire Maroc 2024"
    
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_domains=["rekrute.com", "emploi.ma", "linkedin.com", "medias24.com"],
        )
    except Exception as e:
        return f"Erreur lors de la recherche: {str(e)}"
    
    results = response.get("results", [])
    
    if not results:
        return f"Aucune donnée d'emploi récente trouvée pour '{filiere_name}'."
    
    # Format results
    output_lines = [f"📈 Données emploi pour **{filiere_name}**:\n"]
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "Sans titre")
        url = result.get("url", "")
        content = result.get("content", "")
        
        # Truncate content to control token usage
        truncated_content = _truncate_result(content, max_chars=500)
        
        output_lines.append(
            f"{i}. **{title}**\n"
            f"   {truncated_content}\n"
            f"   🔗 Source: {url}\n"
        )
    
    return "\n".join(output_lines)


@tool
def search_career_insights(career_path: str) -> str:
    """
    Search for career path insights and professional development opportunities in Morocco.
    
    Use this tool to understand career trajectories, required skills, and growth
    opportunities for specific professions in the Moroccan job market.
    
    Args:
        career_path: The career or profession to research.
                     Examples: "Data Scientist Maroc", "Ingénieur Civil carrière",
                     "Expert comptable évolution"
    
    Returns:
        Formatted string with career insights, skill requirements, and growth paths.
    """
    try:
        client = _get_tavily_client()
    except RuntimeError as e:
        return f"Erreur: {str(e)}"
    
    query = f"{career_path} carrière compétences évolution professionnelle Maroc"
    
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
        )
    except Exception as e:
        return f"Erreur lors de la recherche: {str(e)}"
    
    results = response.get("results", [])
    
    if not results:
        return f"Aucune information trouvée pour le parcours '{career_path}'."
    
    output_lines = [f"🎯 Perspectives de carrière pour **{career_path}**:\n"]
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "Sans titre")
        content = result.get("content", "")
        
        truncated_content = _truncate_result(content, max_chars=400)
        
        output_lines.append(
            f"{i}. **{title}**\n"
            f"   {truncated_content}\n"
        )
    
    return "\n".join(output_lines)


async def search_employment_async(filiere_name: str) -> dict:
    """
    Async version of employment search for parallel execution.
    
    Args:
        filiere_name: Name of the filière to search for
    
    Returns:
        Dict with employment data
    """
    import asyncio
    
    # Run sync search in executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: search_employment_data.invoke(filiere_name)
    )
    
    return {
        "filiere": filiere_name,
        "data": result
    }

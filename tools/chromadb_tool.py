"""
OrientAgent - ChromaDB Tool

LangChain tool wrapper for ChromaDB semantic search over filières.
"""

from langchain_core.tools import tool
from rag.retriever import chromadb_retrieve


@tool
def search_filieres(query: str, k: int = 8, domain: str | None = None) -> str:
    """
    Search for Moroccan higher education programs (filières) using semantic search.
    
    Use this tool to find relevant study programs based on a student's profile,
    interests, or specific criteria. The search is performed over a knowledge base
    of 40+ verified Moroccan filières including CPGE, ENSA, FST, BTS, grandes écoles,
    and private institutions.
    
    Args:
        query: Natural language search query describing what you're looking for.
               Examples: "ingénieur informatique Casablanca", "formation commerce gestion",
               "école préparatoire sciences Rabat"
        k: Number of results to return (default: 8, max: 15)
        domain: Optional filter by domain. One of: "sciences", "tech", "lettres", "economie"
    
    Returns:
        Formatted string with search results including filière name, type, city,
        employment rate, salary, and conditions d'accès.
    
    Example:
        >>> search_filieres("formation data science Maroc", k=5, domain="tech")
    """
    # Apply filters if domain specified
    filters = {"domaine": domain} if domain else None
    
    # Clamp k to reasonable bounds
    k = max(1, min(k, 15))
    
    try:
        results = chromadb_retrieve(query=query, k=k, filters=filters)
    except RuntimeError as e:
        return f"Erreur: {str(e)}"
    
    if not results:
        return "Aucune filière trouvée pour cette recherche."
    
    # Format results for LLM consumption
    output_lines = [f"📚 {len(results)} filières trouvées:\n"]
    
    for i, filiere in enumerate(results, 1):
        score = filiere.get("similarity_score", 0)
        nom = filiere.get("nom", "N/A")
        type_ = filiere.get("type", "N/A")
        ville = filiere.get("ville", "N/A")
        taux_emploi = filiere.get("taux_emploi", "N/A")
        salaire = filiere.get("salaire_moyen_premier_emploi_mad", "N/A")
        debouches = filiere.get("debouches", "")
        
        output_lines.append(
            f"{i}. **{nom}**\n"
            f"   Type: {type_} | Ville: {ville}\n"
            f"   Taux d'emploi: {taux_emploi}% | Salaire moyen: {salaire} MAD\n"
            f"   Débouchés: {debouches}\n"
            f"   Pertinence: {score:.0%}\n"
        )
    
    return "\n".join(output_lines)


@tool
def get_filiere_details(filiere_id: str) -> str:
    """
    Get detailed information about a specific filière by its ID.
    
    Use this after search_filieres to get full details about a program
    the student is interested in.
    
    Args:
        filiere_id: The unique identifier of the filière (e.g., "ensa_casablanca_genie_info")
    
    Returns:
        Detailed information about the filière including conditions, duration,
        costs, career prospects, and description.
    """
    from rag.retriever import get_filiere_by_id
    
    filiere = get_filiere_by_id(filiere_id)
    
    if not filiere:
        return f"Filière avec l'ID '{filiere_id}' non trouvée."
    
    # Format detailed output
    serie_bac = filiere.get("serie_bac_requise", "N/A")
    debouches = filiere.get("debouches", "")
    grandes_ecoles = filiere.get("grandes_ecoles_accessibles", [])
    
    output = f"""
📋 **{filiere.get('nom', 'N/A')}**

🏛️ Type: {filiere.get('type', 'N/A')}
📍 Ville: {filiere.get('ville', 'N/A')}
🎯 Domaine: {filiere.get('domaine', 'N/A')}

📝 **Conditions d'accès:**
{filiere.get('conditions_acces', 'N/A')}

📚 Série Bac requise: {serie_bac}
🗣️ Langue d'enseignement: {filiere.get('langue_enseignement', 'N/A')}
⏱️ Durée: {filiere.get('duree_annees', 'N/A')} ans
💰 Frais annuels: {filiere.get('frais_annuels_mad', 0)} MAD

📊 **Insertion professionnelle:**
- Taux d'emploi: {filiere.get('taux_emploi', 'N/A')}%
- Salaire moyen 1er emploi: {filiere.get('salaire_moyen_premier_emploi_mad', 'N/A')} MAD

💼 **Débouchés:** {debouches}

🎓 **Passerelles vers grandes écoles:** {', '.join(grandes_ecoles) if grandes_ecoles else 'N/A'}

📖 **Description:**
{filiere.get('document', filiere.get('description', 'N/A'))}
"""
    return output.strip()

"""
OrientAgent - Scholarship Finder Tool

LangChain tool wrapper for discovering scholarships matching student profile.
"""

from langchain_core.tools import tool
from tavily import TavilyClient
import os
from dotenv import load_dotenv
from typing import Optional

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


@tool
def find_scholarships(
    filiere_nom: str,
    serie_bac: str,
    budget_category: str = "public"
) -> str:
    """
    Find scholarships and financial aid matching student's profile and chosen filière.
    
    Searches for:
    - Government scholarships (OCP, BMCE, Banque Populaire, etc.)
    - University-specific aid programs
    - NGO/Foundation scholarships
    - International scholarships for Moroccan students
    - Work-study programs
    
    Args:
        filiere_nom: Name of the chosen filière (e.g., "Génie Informatique ENSA Marrakech")
        serie_bac: Student's Bac series (Sciences, Lettres, Economie, Technique)
        budget_category: "public" (public universities only), "private" (all including private)
    
    Returns:
        Formatted string with scholarship opportunities, eligibility criteria,
        application deadlines, and financial support amounts.
    
    Example:
        >>> find_scholarships("ENSA Informatique", "Sciences", "public")
    """
    try:
        client = _get_tavily_client()
    except RuntimeError as e:
        return f"Erreur: {str(e)}"
    
    # Build scholarship search query optimized for Morocco
    query = f"bourse scholarship {filiere_nom} Maroc étudiant {serie_bac} 2024 2025 aide financière"
    
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_domains=[
                "gouv.ma",
                "campusfrance.org",
                "ensa-maroc.ac.ma",
                "universityofmarocco.org",
                "massar.ma",
                "emploi.ma",
                "studyportals.com",
            ],
        )
    except Exception as e:
        return f"Erreur lors de la recherche: {str(e)}"
    
    results = response.get("results", [])
    
    if not results:
        return f"""Aucune bourse trouvée pour '{filiere_nom}'.

**Ressources alternatives :**
1. Contactez directement l'établissement pour les bourses internes
2. Vérifiez les organisations comme :
   - Fondation Mohammed VI pour l'Enseignement Supérieur
   - Groupe OCP (scholarships OCP)
   - BMCE Bank (Programme de bourses)
   - Fondation Zakoura
3. Explorez les programmes erasmus+ pour les étudiants marocains"""
    
    # Format results
    output_lines = [f"🎓 Bourses et aides trouvées pour **{filiere_nom}**:\n"]
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "Sans titre")
        url = result.get("url", "")
        content = result.get("content", "")
        
        # Truncate content
        if len(content) > 400:
            content = content[:400] + "..."
        
        output_lines.append(
            f"\n**{i}. {title}**\n"
            f"{content}\n"
            f"🔗 Source: {url}\n"
        )
    
    # Add general tips
    output_lines.append("""
---

**💡 Tips pour maximiser vos chances:**
1. **Postulez tôt** - Les bourses ont des délais stricts (généralement avant juin)
2. **Carnet de notes** - Maintenez une bonne moyenne (>14/20 pour les bourses compétitives)
3. **Lettres de motivation** - Écrivez des lettres personnalisées pour chaque bourse
4. **Certificat de famille** - Préparez les documents financiers de votre déclaration d'impôts
5. **Contactez les établissements** - Beaucoup offrent des réductions de frais d'inscription

**Organismes clés à vérifier:**
- 📋 Ministère de l'Enseignement Supérieur (massar.ma)
- 🏢 Votre établissement d'accueil (bureau des bourses)
- 🌍 Ambassade de France (Erasmus+)
- 💼 Grandes entreprises marocaines (bourses d'excellence)
""")
    
    return "\n".join(output_lines)


@tool
def estimate_study_costs(
    filiere_nom: str,
    ville: str,
    type_etablissement: str = "public"
) -> str:
    """
    Estimate total cost of study (tuition + living expenses) in Morocco.
    
    Args:
        filiere_nom: Name of the filière
        ville: City where student will study
        type_etablissement: "public" or "private"
    
    Returns:
        Breakdown of estimated costs
    
    Example:
        >>> estimate_study_costs("ENSA Informatique", "Marrakech", "public")
    """
    try:
        client = _get_tavily_client()
    except RuntimeError as e:
        return f"Erreur: {str(e)}"
    
    query = f"cost of living tuition {ville} Maroc university 2024 prix formation {filiere_nom}"
    
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
        )
    except Exception as e:
        return f"Erreur: {str(e)}"
    
    results = response.get("results", [])
    
    # Default estimates (update based on research)
    default_costs = {
        "public": {
            "tuition_annual": 1500,  # MAD
            "housing": 2000,  # MAD/month
            "food": 1500,  # MAD/month
            "transport": 500,  # MAD/month
            "books": 1000,  # MAD/year
        },
        "private": {
            "tuition_annual": 50000,  # MAD
            "housing": 2500,  # MAD/month
            "food": 2000,  # MAD/month
            "transport": 600,  # MAD/month
            "books": 1500,  # MAD/year
        }
    }
    
    costs = default_costs.get(type_etablissement, default_costs["public"])
    
    # Calculate annual cost
    annual_total = (
        costs["tuition_annual"] +
        (costs["housing"] * 9) +  # 9 months for school year
        (costs["food"] * 9) +
        (costs["transport"] * 9) +
        costs["books"]
    )
    
    output = f"""
💰 **Estimation des frais pour {filiere_nom} à {ville}**

**Type d'établissement:** {type_etablissement.capitalize()}

**Frais annuels (détail):**
- Scolarité: {costs['tuition_annual']:,.0f} MAD
- Logement (9 mois): {costs['housing'] * 9:,.0f} MAD
- Alimentation (9 mois): {costs['food'] * 9:,.0f} MAD
- Transport (9 mois): {costs['transport'] * 9:,.0f} MAD
- Livres & matériel: {costs['books']:,.0f} MAD
- **TOTAL ANNUEL: {annual_total:,.0f} MAD** (~${annual_total/10:,.0f})

**Coût total pour 3-4 ans:** {annual_total * 3:,.0f} - {annual_total * 4:,.0f} MAD

**Moyennes par mois (pendant les études):**
- Logement: {costs['housing']:,.0f} MAD
- Nourriture: {costs['food']:,.0f} MAD
- Transport: {costs['transport']:,.0f} MAD
- **Total mensuel**: {costs['housing'] + costs['food'] + costs['transport']:,.0f} MAD

**Conseil:** Recherchez des résidences universitaires (moins chères) et des repas subventionnés.
"""
    
    if results:
        output += f"\n**Sources trouvées:**\n"
        for result in results[:2]:
            output += f"- {result.get('title', 'Sans titre')}: {result.get('url', '')}\n"
    
    return output

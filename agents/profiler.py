"""
OrientAgent - Agent 1: Profileur

Analyzes a student's academic profile and calculates domain scores.
"""

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import StudentProfile


SYSTEM_PROMPT = """Tu es un expert en orientation scolaire marocaine. Ton rôle est d'analyser le profil d'un lycéen et de calculer ses scores par domaine.

À partir des informations fournies, tu dois :
1. Calculer les domain_scores (valeurs entre 0 et 1) pour : sciences, tech, lettres, economie
2. Déterminer le style d'apprentissage préféré
3. Extraire les contraintes du profil

Règles de pondération par série Bac :
- Sciences : maths×0.3 + physique×0.25 + SVT×0.2 + autres×0.25
- Lettres : arabe×0.3 + français×0.25 + histoire_geo×0.25 + philo×0.2
- Economie : maths×0.25 + economie×0.3 + compta×0.25 + langues×0.2
- Technique : maths×0.25 + physique×0.2 + techno×0.35 + autres×0.2

Instructions de scoring :
1. Normalise les notes sur 20 (divise par 20 pour obtenir un score 0-1)
2. Applique les coefficients selon la série Bac
3. Ajuste les scores selon les intérêts déclarés (+0.1 par intérêt aligné, max +0.3)
4. Le score final pour chaque domaine doit être entre 0 et 1

Mapping intérêts → domaines :
- informatique, robotique, programmation, IA → tech
- maths, physique, chimie, biologie → sciences
- littérature, langues, histoire, philosophie, droit → lettres
- commerce, gestion, finance, marketing, entrepreneuriat → economie

Réponds UNIQUEMENT en JSON valide avec cette structure exacte :
{
    "domain_scores": {
        "sciences": <float 0-1>,
        "tech": <float 0-1>,
        "lettres": <float 0-1>,
        "economie": <float 0-1>
    },
    "learning_style": "<theorique|pratique|mixte>",
    "constraints": {
        "ville": "<ville>",
        "langue": "<langue>",
        "budget": "<budget>",
        "mobilite": <true|false>
    }
}"""


def _calculate_domain_scores_fallback(
    serie_bac: str,
    notes: dict[str, float],
    interets: list[str]
) -> dict[str, float]:
    """
    Fallback calculation if LLM fails to return valid JSON.
    Implements the weighted scoring formula from the spec.
    """
    # Normalize notes to 0-1 scale
    normalized = {k: min(1.0, v / 20.0) for k, v in notes.items()}
    
    # Calculate base scores by serie
    if serie_bac == "Sciences":
        sciences = (
            normalized.get("maths", 0.5) * 0.3 +
            normalized.get("physique", 0.5) * 0.25 +
            normalized.get("svt", 0.5) * 0.2 +
            normalized.get("francais", 0.5) * 0.125 +
            normalized.get("arabe", 0.5) * 0.125
        )
        tech = sciences * 0.9  # Tech correlates with sciences
        lettres = (
            normalized.get("francais", 0.5) * 0.4 +
            normalized.get("arabe", 0.5) * 0.3 +
            normalized.get("histoire_geo", 0.5) * 0.3
        )
        economie = (
            normalized.get("maths", 0.5) * 0.5 +
            normalized.get("francais", 0.5) * 0.25 +
            lettres * 0.25
        )
    elif serie_bac == "Lettres":
        lettres = (
            normalized.get("arabe", 0.5) * 0.3 +
            normalized.get("francais", 0.5) * 0.25 +
            normalized.get("histoire_geo", 0.5) * 0.25 +
            normalized.get("philo", 0.5) * 0.2
        )
        sciences = lettres * 0.4
        tech = sciences * 0.5
        economie = lettres * 0.6
    elif serie_bac == "Economie":
        economie = (
            normalized.get("maths", 0.5) * 0.25 +
            normalized.get("economie", 0.5) * 0.3 +
            normalized.get("compta", 0.5) * 0.25 +
            normalized.get("francais", 0.5) * 0.2
        )
        sciences = economie * 0.5
        tech = economie * 0.4
        lettres = economie * 0.6
    elif serie_bac == "Technique":
        tech = (
            normalized.get("maths", 0.5) * 0.25 +
            normalized.get("physique", 0.5) * 0.2 +
            normalized.get("techno", 0.5) * 0.35 +
            normalized.get("francais", 0.5) * 0.2
        )
        sciences = tech * 0.8
        lettres = tech * 0.3
        economie = tech * 0.5
    else:
        # Default balanced scores
        avg = sum(normalized.values()) / max(len(normalized), 1)
        sciences = tech = lettres = economie = avg
    
    # Adjust for interests
    interest_mapping = {
        "informatique": "tech", "robotique": "tech", "programmation": "tech", "ia": "tech",
        "maths": "sciences", "physique": "sciences", "chimie": "sciences", "biologie": "sciences",
        "littérature": "lettres", "langues": "lettres", "histoire": "lettres", 
        "philosophie": "lettres", "droit": "lettres",
        "commerce": "economie", "gestion": "economie", "finance": "economie",
        "marketing": "economie", "entrepreneuriat": "economie",
    }
    
    adjustments = {"sciences": 0, "tech": 0, "lettres": 0, "economie": 0}
    
    for interet in interets:
        interet_lower = interet.lower()
        for key, domain in interest_mapping.items():
            if key in interet_lower:
                adjustments[domain] = min(adjustments[domain] + 0.1, 0.3)
                break
    
    # Apply adjustments and clamp to 0-1
    return {
        "sciences": min(1.0, max(0.0, sciences + adjustments["sciences"])),
        "tech": min(1.0, max(0.0, tech + adjustments["tech"])),
        "lettres": min(1.0, max(0.0, lettres + adjustments["lettres"])),
        "economie": min(1.0, max(0.0, economie + adjustments["economie"])),
    }


def _determine_learning_style(interets: list[str], serie_bac: str) -> str:
    """Determine learning style from interests and serie."""
    practical_keywords = ["robotique", "programmation", "projet", "stage", "pratique"]
    theoretical_keywords = ["recherche", "théorie", "maths", "philosophie"]
    
    interets_lower = " ".join(interets).lower()
    
    practical_count = sum(1 for kw in practical_keywords if kw in interets_lower)
    theoretical_count = sum(1 for kw in theoretical_keywords if kw in interets_lower)
    
    if practical_count > theoretical_count + 1:
        return "pratique"
    elif theoretical_count > practical_count + 1:
        return "theorique"
    return "mixte"


class ProfileurAgent:
    """
    Agent 1: Analyzes student profile and calculates domain scores.
    
    Uses weighted scoring formulas based on Bac series and adjusts
    scores according to declared interests.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the Profileur agent.
        
        Args:
            llm: A LangChain chat model (e.g., ChatGROQ)
        """
        self.llm = llm
    
    async def run(self, state: StudentProfile) -> dict[str, Any]:
        """
        Analyze the student profile and compute domain scores.
        
        Args:
            state: Current StudentProfile state with input fields populated
        
        Returns:
            Partial state update with domain_scores, learning_style, constraints
        """
        # Build user message with student info
        user_message = f"""
Analyse le profil suivant :

**Informations générales :**
- Nom : {state.get('nom', 'Anonyme')}
- Série Bac : {state.get('serie_bac', 'Sciences')}
- Ville : {state.get('ville', 'Non spécifiée')}
- Langue préférée : {state.get('langue', 'fr')}
- Budget : {state.get('budget', 'public')}

**Notes par matière :**
{json.dumps(state.get('notes', {}), indent=2, ensure_ascii=False)}

**Centres d'intérêt :**
{', '.join(state.get('interets', []))}

Calcule les domain_scores et détermine le profil de cet étudiant.
"""
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
            
            # Validate and extract fields
            domain_scores = result.get("domain_scores", {})
            learning_style = result.get("learning_style", "mixte")
            constraints = result.get("constraints", {})
            
            # Ensure all domains are present
            for domain in ["sciences", "tech", "lettres", "economie"]:
                if domain not in domain_scores:
                    domain_scores[domain] = 0.5
                else:
                    # Clamp to valid range
                    domain_scores[domain] = min(1.0, max(0.0, float(domain_scores[domain])))
            
            # Ensure constraints has required fields
            if "ville" not in constraints:
                constraints["ville"] = state.get("ville", "")
            if "langue" not in constraints:
                constraints["langue"] = state.get("langue", "fr")
            if "budget" not in constraints:
                constraints["budget"] = state.get("budget", "public")
            if "mobilite" not in constraints:
                constraints["mobilite"] = True
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback to deterministic calculation
            print(f"ProfileurAgent: LLM parsing failed ({e}), using fallback")
            
            domain_scores = _calculate_domain_scores_fallback(
                state.get("serie_bac", "Sciences"),
                state.get("notes", {}),
                state.get("interets", [])
            )
            learning_style = _determine_learning_style(
                state.get("interets", []),
                state.get("serie_bac", "Sciences")
            )
            constraints = {
                "ville": state.get("ville", ""),
                "langue": state.get("langue", "fr"),
                "budget": state.get("budget", "public"),
                "mobilite": True,
            }
        
        return {
            "domain_scores": domain_scores,
            "learning_style": learning_style,
            "constraints": constraints,
            "current_step": "explorateur",
        }

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
from agents.static.profiler_prompt import SYSTEM_PROMPT
from agents.logic.profiler_scoring import (
    _calculate_domain_scores_fallback,
    _determine_learning_style,
)


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

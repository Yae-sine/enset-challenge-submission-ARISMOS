"""
OrientAgent - Agent 2: Explorateur

Retrieves relevant filières using RAG and enriches with Tavily employment data.
"""

import asyncio
import json
import re
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import StudentProfile
from rag.retriever import chromadb_retrieve
from agents.static.explorer_prompt import SYSTEM_PROMPT
from agents.logic.explorer_utils import build_rag_query, format_filieres_context


class ExplorateurAgent:
    """
    Agent 2: Explores and retrieves relevant filières using RAG + Tavily.
    
    Uses ChromaDB for semantic search over the filières corpus and
    optionally enriches results with real-time Tavily employment data.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        retriever_fn=chromadb_retrieve,
        tavily_client: Optional[Any] = None
    ):
        """
        Initialize the Explorateur agent.
        
        Args:
            llm: A LangChain chat model
            retriever_fn: Function to retrieve from ChromaDB (default: chromadb_retrieve)
            tavily_client: Optional Tavily client for employment data enrichment
        """
        self.llm = llm
        self.retriever_fn = retriever_fn
        self.tavily_client = tavily_client
    
    async def _fetch_tavily_data(self, filieres: list[dict]) -> dict[str, str]:
        """
        Fetch employment data from Tavily for each filière.
        
        Args:
            filieres: List of filière dicts
        
        Returns:
            Dict mapping filière ID to Tavily search results
        """
        if not self.tavily_client:
            return {}
        
        async def search_one(filiere: dict) -> tuple[str, str]:
            filiere_id = filiere.get("id", "")
            nom = filiere.get("nom", "")
            
            try:
                query = f"{nom} taux emploi salaire Maroc 2026"
                # Run sync search in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.tavily_client.search(
                        query=query,
                        search_depth="basic",
                        max_results=2
                    )
                )
                
                results = response.get("results", [])
                if results:
                    # Take first result content, truncated
                    content = results[0].get("content", "")[:300]
                    return (filiere_id, content)
                return (filiere_id, "")
            except Exception as e:
                print(f"Tavily search failed for {nom}: {e}")
                return (filiere_id, "")
        
        # Limit to 8 concurrent searches
        tasks = [search_one(f) for f in filieres[:8]]
        results = await asyncio.gather(*tasks)
        
        return dict(results)
    
    async def run(self, state: StudentProfile) -> dict[str, Any]:
        """
        Retrieve and rank relevant filières for the student profile.
        
        Args:
            state: Current StudentProfile state with domain_scores populated
        
        Returns:
            Partial state update with filieres_retrieved list
        """
        # Build semantic query
        query = build_rag_query(state)
        
        # Retrieve from ChromaDB
        try:
            raw_filieres = self.retriever_fn(query=query, k=12)
        except RuntimeError as e:
            # ChromaDB not initialized
            return {
                "filieres_retrieved": [],
                "current_step": "conseiller",
                "error": f"RAG retrieval failed: {str(e)}"
            }
        
        if not raw_filieres:
            return {
                "filieres_retrieved": [],
                "current_step": "conseiller",
                "error": "No filières found in knowledge base"
            }
        
        # Fetch Tavily data (optional)
        tavily_data = await self._fetch_tavily_data(raw_filieres)
        
        # Format context for LLM
        filieres_context = format_filieres_context(raw_filieres)
        
        tavily_context = ""
        if tavily_data:
            tavily_lines = ["**Données emploi récentes (Tavily):**"]
            for fid, content in tavily_data.items():
                if content:
                    tavily_lines.append(f"- {fid}: {content}")
            tavily_context = "\n".join(tavily_lines)
        
        # Build LLM prompt
        system_content = SYSTEM_PROMPT.format(
            filieres_rag_context=filieres_context,
            domain_scores=json.dumps(state.get("domain_scores", {})),
            serie_bac=state.get("serie_bac", "Sciences"),
            ville=state.get("ville", "Non spécifiée"),
            budget=state.get("budget", "public"),
            langue=state.get("langue", "fr"),
            tavily_context=tavily_context or "Aucune donnée Tavily disponible."
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content="Sélectionne et classe les filières les plus pertinentes pour ce profil."),
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                filieres_retrieved = result.get("filieres", [])
            else:
                raise ValueError("No JSON found in response")
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback: use raw RAG results with basic scoring
            print(f"ExplorateurAgent: LLM parsing failed ({e}), using raw RAG results")
            
            domain_scores = state.get("domain_scores", {})
            serie_bac = state.get("serie_bac", "Sciences")
            
            filieres_retrieved = []
            for f in raw_filieres[:10]:
                # Basic pertinence scoring
                domaine = f.get("domaine", "tech")
                domain_match = domain_scores.get(domaine, 0.5)
                
                # Check serie_bac compatibility
                serie_requise = f.get("serie_bac_requise", "")
                if isinstance(serie_requise, str):
                    serie_match = 1.0 if serie_bac in serie_requise else 0.5
                else:
                    serie_match = 1.0 if serie_bac in serie_requise else 0.5
                
                score = domain_match * 0.5 + serie_match * 0.3 + f.get("similarity_score", 0.5) * 0.2
                
                filieres_retrieved.append({
                    "id": f.get("id", ""),
                    "nom": f.get("nom", ""),
                    "type": f.get("type", ""),
                    "ville": f.get("ville", ""),
                    "domaine": domaine,
                    "score_pertinence": round(score, 2),
                    "taux_emploi": f.get("taux_emploi", 0),
                    "salaire_moyen": f.get("salaire_moyen_premier_emploi_mad", 0),
                    "debouches": f.get("debouches", "").split(", ")[:3] if isinstance(f.get("debouches"), str) else f.get("debouches", [])[:3],
                    "conditions_acces": f.get("conditions_acces", ""),
                    "justification_courte": f"Correspond au domaine {domaine} avec score {domain_match:.0%}"
                })
        
        # Sort by pertinence
        filieres_retrieved.sort(key=lambda x: x.get("score_pertinence", 0), reverse=True)
        
        return {
            "filieres_retrieved": filieres_retrieved[:12],
            "current_step": "conseiller",
        }

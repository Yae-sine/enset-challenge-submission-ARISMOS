"""
OrientAgent - Agent 4: Coach Entretien

Generates interview questions and evaluates student responses.
"""

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import StudentProfile


QUESTION_GENERATION_PROMPT = """Tu es un recruteur et directeur des admissions marocain pour la filière **{filiere_nom}**.

Tu dois générer 6 questions d'entretien de motivation adaptées à cette filière dans le contexte éducatif marocain.

Les questions doivent tester :
- La connaissance réelle de la filière (2 questions) - Le candidat connaît-il vraiment ce domaine ?
- La motivation et le projet professionnel (2 questions) - Pourquoi cette filière ? Quel projet ?
- La personnalité et les soft skills (2 questions) - Comment travaille-t-il ? Gère-t-il le stress ?

Adapte le registre à la langue : {langue}
- Si langue = "fr" : questions formelles mais accessibles en français
- Si langue = "ar" : questions en arabe marocain standard (Darija évitée)

Contexte filière :
{filiere_context}

Réponds en JSON avec cette structure exacte :
{{
    "questions": [
        "<question 1 sur la connaissance>",
        "<question 2 sur la connaissance>",
        "<question 3 sur la motivation>",
        "<question 4 sur le projet pro>",
        "<question 5 sur les soft skills>",
        "<question 6 sur la personnalité>"
    ]
}}

Les questions doivent être spécifiques à la filière, pas génériques."""


EVALUATION_PROMPT = """Tu évalues la réponse d'un lycéen marocain à une question d'entretien pour **{filiere_nom}**.

**Question posée :**
{question}

**Réponse de l'étudiant :**
{answer}

**Contexte :**
- Série Bac : {serie_bac}
- Centres d'intérêt : {interets}

Évalue sur 3 axes (note sur 10 chacun) :
1. **Clarté** : Structure de la réponse, cohérence, qualité d'expression
2. **Motivation** : Authenticité, enthousiasme, projet professionnel aligné avec la filière
3. **Connaissance filière** : Maîtrise du domaine, compréhension du contexte marocain, pertinence

Fournis aussi un **feedback bref et constructif** (2-3 phrases) qui aide l'étudiant à s'améliorer.

Sois exigeant mais juste. Un lycéen de 17-18 ans n'est pas censé tout savoir, mais doit montrer de la curiosité et de la motivation.

Réponds en JSON :
{{
    "clarte": <int 0-10>,
    "motivation": <int 0-10>,
    "connaissance": <int 0-10>,
    "feedback": "<2-3 phrases de feedback constructif>"
}}"""


def compute_interview_score(evaluations: list[dict]) -> dict:
    """
    Compute the final interview score from individual question evaluations.
    
    Each evaluation has: clarte (0-10), motivation (0-10), connaissance (0-10)
    Final score is /100, with 3 strengths and 3 improvement axes.
    
    Args:
        evaluations: List of evaluation dicts from evaluate_answer
    
    Returns:
        Dict with score, points_forts, axes_amelioration
    """
    if not evaluations:
        return {
            "score": 0,
            "points_forts": ["Aucune évaluation disponible"],
            "axes_amelioration": ["Complétez l'entretien pour recevoir un feedback"],
        }
    
    # Calculate averages per axis
    avg_clarte = sum(e.get("clarte", 5) for e in evaluations) / len(evaluations)
    avg_motivation = sum(e.get("motivation", 5) for e in evaluations) / len(evaluations)
    avg_connaissance = sum(e.get("connaissance", 5) for e in evaluations) / len(evaluations)
    
    # Final score: average of three axes, scaled to /100
    final_score = int((avg_clarte + avg_motivation + avg_connaissance) / 3 * 10)
    final_score = min(100, max(0, final_score))
    
    # Determine strengths and weaknesses
    axis_scores = [
        ("Clarté et expression", avg_clarte),
        ("Motivation et projet professionnel", avg_motivation),
        ("Connaissance de la filière", avg_connaissance),
    ]
    
    # Sort to find best and worst
    sorted_axes = sorted(axis_scores, key=lambda x: x[1], reverse=True)
    
    points_forts = []
    axes_amelioration = []
    
    # Best axes (score >= 6)
    for name, score in sorted_axes:
        if score >= 7:
            points_forts.append(f"{name} : excellent ({score:.1f}/10)")
        elif score >= 5:
            if len(points_forts) < 2:
                points_forts.append(f"{name} : satisfaisant ({score:.1f}/10)")
    
    # Axes to improve (score < 6)
    for name, score in reversed(sorted_axes):
        if score < 6:
            axes_amelioration.append(f"{name} : à renforcer ({score:.1f}/10)")
        elif score < 7 and len(axes_amelioration) < 2:
            axes_amelioration.append(f"{name} : peut progresser ({score:.1f}/10)")
    
    # Ensure we have at least some feedback
    if not points_forts:
        points_forts = ["Participation à l'entretien", "Effort de réponse"]
    if not axes_amelioration:
        axes_amelioration = ["Continuer à se préparer aux entretiens"]
    
    # Add specific advice based on scores
    if avg_clarte < 5:
        axes_amelioration.append("Conseil : Structure tes réponses en introduction-développement-conclusion")
    if avg_motivation < 5:
        axes_amelioration.append("Conseil : Prépare des exemples concrets qui illustrent ta motivation")
    if avg_connaissance < 5:
        axes_amelioration.append("Conseil : Recherche davantage sur les débouchés et le contenu de la formation")
    
    return {
        "score": final_score,
        "points_forts": points_forts[:3],
        "axes_amelioration": axes_amelioration[:3],
        "details": {
            "clarte_moyenne": round(avg_clarte, 1),
            "motivation_moyenne": round(avg_motivation, 1),
            "connaissance_moyenne": round(avg_connaissance, 1),
        }
    }


class CoachEntretienAgent:
    """
    Agent 4: Simulates admission interviews and evaluates responses.
    
    Generates context-specific questions for the chosen filière and
    provides detailed feedback on each answer with final scoring.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the Coach Entretien agent.
        
        Args:
            llm: A LangChain chat model
        """
        self.llm = llm
        self._evaluations: list[dict] = []
    
    async def generate_questions(
        self,
        filiere_nom: str,
        filiere_context: str,
        langue: str = "fr"
    ) -> list[str]:
        """
        Generate interview questions for a specific filière.
        
        Args:
            filiere_nom: Name of the filière
            filiere_context: Additional context about the filière
            langue: Language for questions ("fr", "ar", "en")
        
        Returns:
            List of 6 interview questions
        """
        system_content = QUESTION_GENERATION_PROMPT.format(
            filiere_nom=filiere_nom,
            langue=langue,
            filiere_context=filiere_context or "Pas de contexte supplémentaire."
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=f"Génère 6 questions d'entretien pour {filiere_nom}."),
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                questions = result.get("questions", [])
                if len(questions) >= 6:
                    return questions[:6]
            
            raise ValueError("Could not parse questions from response")
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"CoachEntretienAgent: Question generation failed ({e}), using defaults")
            
            # Fallback questions
            return [
                f"Pourquoi avez-vous choisi {filiere_nom} ?",
                f"Que savez-vous des débouchés professionnels de {filiere_nom} au Maroc ?",
                "Quel est votre projet professionnel à 5 ans ?",
                "Comment comptez-vous contribuer à votre future promotion ?",
                "Décrivez une situation où vous avez dû surmonter un défi académique.",
                "Quelles sont vos qualités qui vous distinguent des autres candidats ?",
            ]
    
    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        filiere_nom: str,
        serie_bac: str = "Sciences",
        interets: list[str] = None
    ) -> dict:
        """
        Evaluate a single answer to an interview question.
        
        Args:
            question: The interview question
            answer: Student's response
            filiere_nom: Name of the filière
            serie_bac: Student's Bac series
            interets: Student's interests
        
        Returns:
            Dict with clarte, motivation, connaissance scores and feedback
        """
        if interets is None:
            interets = []
        
        system_content = EVALUATION_PROMPT.format(
            filiere_nom=filiere_nom,
            question=question,
            answer=answer,
            serie_bac=serie_bac,
            interets=", ".join(interets) if interets else "Non spécifiés"
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content="Évalue cette réponse."),
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                evaluation = json.loads(json_match.group())
                
                # Validate and clamp scores
                for key in ["clarte", "motivation", "connaissance"]:
                    if key in evaluation:
                        evaluation[key] = min(10, max(0, int(evaluation[key])))
                    else:
                        evaluation[key] = 5
                
                if "feedback" not in evaluation:
                    evaluation["feedback"] = "Réponse évaluée."
                
                return evaluation
            
            raise ValueError("Could not parse evaluation from response")
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"CoachEntretienAgent: Evaluation failed ({e}), using defaults")
            
            # Fallback evaluation based on answer length and keywords
            answer_length = len(answer.split())
            
            clarte = 5
            if answer_length > 50:
                clarte = 6
            if answer_length > 100:
                clarte = 7
            
            motivation = 5
            motivation_keywords = ["passion", "motivé", "projet", "objectif", "rêve", "futur"]
            for kw in motivation_keywords:
                if kw in answer.lower():
                    motivation += 1
            motivation = min(10, motivation)
            
            connaissance = 5
            if filiere_nom.lower() in answer.lower():
                connaissance += 1
            
            return {
                "clarte": clarte,
                "motivation": motivation,
                "connaissance": connaissance,
                "feedback": "Réponse correcte. Continue à développer tes arguments avec des exemples concrets."
            }
    
    def compute_final_score(self, evaluations: list[dict]) -> dict:
        """Public wrapper for score computation."""
        return compute_interview_score(evaluations)
    
    async def run(self, state: StudentProfile) -> dict[str, Any]:
        """
        Run the full interview simulation.
        
        This generates questions based on the chosen filière.
        Note: Actual Q&A happens interactively via the API.
        
        Args:
            state: Current StudentProfile state
        
        Returns:
            Partial state update with interview_questions
        """
        # Get the chosen filière (first from top_3 by default)
        top_3 = state.get("top_3", [])
        filiere_choisie = state.get("filiere_choisie", "")
        
        if not filiere_choisie and top_3:
            filiere_choisie = top_3[0].get("filiere_nom", "")
        
        if not filiere_choisie:
            return {
                "interview_questions": [],
                "current_step": "complete",
                "error": "No filière selected for interview"
            }
        
        # Build context from top_3
        filiere_context = ""
        for f in top_3:
            if f.get("filiere_nom") == filiere_choisie:
                filiere_context = f.get("justification", "")
                break
        
        # Generate questions
        questions = await self.generate_questions(
            filiere_nom=filiere_choisie,
            filiere_context=filiere_context,
            langue=state.get("langue", "fr")
        )
        
        return {
            "filiere_choisie": filiere_choisie,
            "interview_questions": questions,
            "current_step": "interview_active",
        }
    
    async def process_answer(
        self,
        state: StudentProfile,
        question_index: int,
        answer: str
    ) -> dict[str, Any]:
        """
        Process a single interview answer and update state.
        
        Args:
            state: Current state with questions
            question_index: Index of the question being answered
            answer: Student's response
        
        Returns:
            Partial state update with evaluation
        """
        questions = state.get("interview_questions", [])
        filiere_choisie = state.get("filiere_choisie", "")
        
        if question_index >= len(questions):
            return {"error": "Invalid question index"}
        
        question = questions[question_index]
        
        # Evaluate the answer
        evaluation = await self.evaluate_answer(
            question=question,
            answer=answer,
            filiere_nom=filiere_choisie,
            serie_bac=state.get("serie_bac", "Sciences"),
            interets=state.get("interets", [])
        )
        
        # Store evaluation
        self._evaluations.append(evaluation)
        
        # Update answers list
        current_answers = list(state.get("interview_answers", []))
        current_answers.append(answer)
        
        # Check if interview is complete
        is_complete = len(current_answers) >= len(questions)
        
        update = {
            "interview_answers": current_answers,
        }
        
        if is_complete:
            # Compute final score
            final_feedback = self.compute_final_score(self._evaluations)
            update["interview_score"] = final_feedback["score"]
            update["interview_feedback"] = final_feedback
            update["current_step"] = "complete"
            self._evaluations = []  # Reset for next session
        
        return update

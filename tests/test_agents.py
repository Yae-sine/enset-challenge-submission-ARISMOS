"""
OrientAgent - Agent Tests

Tests for the 4 agent classes using pytest-asyncio.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from graph.state import StudentProfile, create_initial_state
from agents.profiler import ProfileurAgent, _calculate_domain_scores_fallback
from agents.advisor import ConseillerAgent, score_filiere


# Test fixtures
@pytest.fixture
def sample_profile() -> StudentProfile:
    """Create a sample student profile for testing."""
    return create_initial_state(
        nom="Ahmed Test",
        serie_bac="Sciences",
        notes={
            "maths": 16.5,
            "physique": 15.0,
            "svt": 14.0,
            "francais": 13.5,
            "arabe": 14.0,
        },
        interets=["informatique", "robotique", "intelligence artificielle"],
        ville="Casablanca",
        langue="fr",
        budget="public",
        session_id="test-123",
    )


@pytest.fixture
def sample_filiere() -> dict:
    """Create a sample filière for testing."""
    return {
        "id": "ensa_casablanca_genie_info",
        "nom": "ENSA Casablanca — Génie Informatique",
        "type": "ENSA",
        "ville": "Casablanca",
        "domaine": "tech",
        "taux_emploi": 94,
        "frais_annuels_mad": 0,
        "langue_enseignement": "fr",
        "conditions_acces": "Concours national",
        "debouches": ["Ingénieur logiciel", "Data Scientist"],
    }


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    return llm


# ProfileurAgent Tests
class TestProfileurAgent:
    @pytest.mark.asyncio
    async def test_run_with_valid_llm_response(self, sample_profile, mock_llm):
        """Test ProfileurAgent.run() with a valid LLM JSON response."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain_scores": {
                "sciences": 0.85,
                "tech": 0.90,
                "lettres": 0.45,
                "economie": 0.55,
            },
            "learning_style": "pratique",
            "constraints": {
                "ville": "Casablanca",
                "langue": "fr",
                "budget": "public",
                "mobilite": True,
            },
        })
        mock_llm.ainvoke.return_value = mock_response

        agent = ProfileurAgent(llm=mock_llm)
        result = await agent.run(sample_profile)

        assert "domain_scores" in result
        assert "learning_style" in result
        assert "constraints" in result
        assert result["domain_scores"]["tech"] == 0.90
        assert result["learning_style"] == "pratique"

    @pytest.mark.asyncio
    async def test_run_with_invalid_json_uses_fallback(self, sample_profile, mock_llm):
        """Test that ProfileurAgent falls back to deterministic scoring on JSON error."""
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        mock_llm.ainvoke.return_value = mock_response

        agent = ProfileurAgent(llm=mock_llm)
        result = await agent.run(sample_profile)

        # Should still return valid scores from fallback
        assert "domain_scores" in result
        assert all(0 <= v <= 1 for v in result["domain_scores"].values())
        assert "learning_style" in result

    def test_fallback_scoring_sciences_bac(self):
        """Test the fallback scoring formula for Sciences series."""
        scores = _calculate_domain_scores_fallback(
            serie_bac="Sciences",
            notes={"maths": 18, "physique": 16, "svt": 14, "francais": 12},
            interets=["informatique", "programmation"]
        )

        # Sciences bac should score high in sciences and tech
        assert scores["sciences"] > 0.6
        assert scores["tech"] > 0.6
        # Tech interest boost should apply
        assert scores["tech"] >= 0.5

    def test_fallback_scoring_lettres_bac(self):
        """Test the fallback scoring formula for Lettres series."""
        scores = _calculate_domain_scores_fallback(
            serie_bac="Lettres",
            notes={"arabe": 17, "francais": 16, "histoire_geo": 15, "philo": 14},
            interets=["littérature", "langues"]
        )

        # Lettres bac should score high in lettres
        assert scores["lettres"] > 0.6


# ConseillerAgent Tests
class TestConseillerAgent:
    def test_score_filiere_perfect_match(self, sample_profile, sample_filiere):
        """Test scoring a filière that perfectly matches the profile."""
        # Update profile with domain scores
        sample_profile["domain_scores"] = {
            "sciences": 0.8,
            "tech": 0.9,
            "lettres": 0.4,
            "economie": 0.5,
        }
        sample_profile["constraints"] = {
            "ville": "Casablanca",
            "langue": "fr",
            "budget": "public",
        }

        score = score_filiere(sample_filiere, sample_profile)

        # Should be high score: tech domain matches, same city, public, fr
        assert 0.7 <= score <= 1.0

    def test_score_filiere_poor_match(self, sample_profile, sample_filiere):
        """Test scoring a filière that doesn't match the profile."""
        # Profile with low tech score
        sample_profile["domain_scores"] = {
            "sciences": 0.3,
            "tech": 0.2,
            "lettres": 0.9,
            "economie": 0.7,
        }
        sample_profile["constraints"] = {
            "ville": "Fès",  # Different city
            "langue": "ar",  # Different language
            "budget": "public",
        }

        score = score_filiere(sample_filiere, sample_profile)

        # Should be lower score
        assert score < 0.7

    def test_score_filiere_handles_missing_fields(self, sample_profile):
        """Test that scoring handles missing filière fields gracefully."""
        minimal_filiere = {
            "id": "test",
            "domaine": "tech",
        }

        sample_profile["domain_scores"] = {"tech": 0.8}
        sample_profile["constraints"] = {}

        # Should not raise exception
        score = score_filiere(minimal_filiere, sample_profile)
        assert 0 <= score <= 1


# Integration-style tests
class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_full_profile_analysis_flow(self, sample_profile, mock_llm):
        """Test a simplified flow through ProfileurAgent."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "domain_scores": {"sciences": 0.8, "tech": 0.85, "lettres": 0.5, "economie": 0.6},
            "learning_style": "mixte",
            "constraints": {"ville": "Casablanca", "langue": "fr", "budget": "public", "mobilite": True},
        })
        mock_llm.ainvoke.return_value = mock_response

        agent = ProfileurAgent(llm=mock_llm)
        result = await agent.run(sample_profile)

        # Verify state update structure
        assert "domain_scores" in result
        assert "current_step" in result
        assert result["current_step"] == "explorateur"

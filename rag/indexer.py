"""
OrientAgent - ChromaDB Indexer

Indexes the Moroccan filières corpus into ChromaDB for semantic retrieval.
Run this script once before starting the API server.

Usage:
    python rag/indexer.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

CORPUS_PATH = Path(__file__).parent / "corpus"
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./rag/chroma_db")
COLLECTION_NAME = "filieres"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Required fields for each filière card
REQUIRED_FIELDS = [
    "id", "nom", "type", "ville", "domaine", "serie_bac_requise",
    "langue_enseignement", "conditions_acces", "duree_annees",
    "frais_annuels_mad", "taux_emploi", "salaire_moyen_premier_emploi_mad",
    "debouches", "description"
]


def filiere_to_document(card: dict) -> str:
    """
    Convert a filière card to a document string for embedding.
    
    This creates a rich text representation that captures all searchable
    aspects of the filière for semantic similarity matching.
    
    Args:
        card: A filière dict following the schema
    
    Returns:
        A formatted document string for embedding
    """
    serie_bac = ", ".join(card.get("serie_bac_requise", []))
    debouches = ", ".join(card.get("debouches", []))
    grandes_ecoles = ", ".join(card.get("grandes_ecoles_accessibles", []))
    
    document = (
        f"{card['nom']} - {card['type']} à {card['ville']}. "
        f"Domaine: {card['domaine']}. "
        f"Série Bac requise: {serie_bac}. "
        f"Langue d'enseignement: {card['langue_enseignement']}. "
        f"Conditions d'accès: {card['conditions_acces']}. "
        f"Durée: {card['duree_annees']} ans. "
        f"Frais annuels: {card['frais_annuels_mad']} MAD. "
        f"Taux d'emploi: {card['taux_emploi']}%. "
        f"Salaire moyen premier emploi: {card['salaire_moyen_premier_emploi_mad']} MAD. "
        f"Débouchés: {debouches}. "
    )
    
    if grandes_ecoles:
        document += f"Grandes écoles accessibles: {grandes_ecoles}. "
    
    document += card['description']
    
    return document


def validate_card(card: dict, filename: str) -> list[str]:
    """
    Validate a filière card against the required schema.
    
    Args:
        card: The filière dict to validate
        filename: Source filename for error messages
    
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append(f"Missing required field '{field}' in {filename}")
    
    # Type validations
    if "serie_bac_requise" in card and not isinstance(card["serie_bac_requise"], list):
        errors.append(f"'serie_bac_requise' must be a list in {filename}")
    
    if "debouches" in card and not isinstance(card["debouches"], list):
        errors.append(f"'debouches' must be a list in {filename}")
    
    if "domaine" in card and card["domaine"] not in ["sciences", "tech", "lettres", "economie"]:
        errors.append(f"Invalid domaine '{card['domaine']}' in {filename}")
    
    if "taux_emploi" in card:
        if not isinstance(card["taux_emploi"], (int, float)) or not 0 <= card["taux_emploi"] <= 100:
            errors.append(f"'taux_emploi' must be between 0 and 100 in {filename}")
    
    return errors


def load_corpus() -> tuple[list[dict], list[str]]:
    """
    Load all JSON files from the corpus directory.
    
    Returns:
        Tuple of (list of all filière cards, list of validation errors)
    """
    all_cards = []
    all_errors = []
    
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Corpus directory not found: {CORPUS_PATH}")
    
    json_files = list(CORPUS_PATH.glob("*.json"))
    
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {CORPUS_PATH}")
    
    print(f"📂 Found {len(json_files)} corpus files")
    
    for json_file in json_files:
        print(f"  📄 Loading {json_file.name}...")
        
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                cards = json.load(f)
            except json.JSONDecodeError as e:
                all_errors.append(f"Invalid JSON in {json_file.name}: {e}")
                continue
        
        if not isinstance(cards, list):
            all_errors.append(f"{json_file.name} must contain a JSON array")
            continue
        
        for card in cards:
            errors = validate_card(card, json_file.name)
            if errors:
                all_errors.extend(errors)
            else:
                all_cards.append(card)
        
        print(f"     ✓ Loaded {len(cards)} cards")
    
    return all_cards, all_errors


def index_corpus(force_reindex: bool = False) -> dict[str, Any]:
    """
    Index the entire corpus into ChromaDB.
    
    Args:
        force_reindex: If True, delete existing collection and reindex
    
    Returns:
        Dict with indexing statistics
    """
    print("🚀 Starting OrientAgent corpus indexing...\n")
    
    # Load and validate corpus
    cards, errors = load_corpus()
    
    if errors:
        print("\n❌ Validation errors found:")
        for error in errors:
            print(f"  • {error}")
        if not cards:
            raise ValueError("No valid cards to index")
        print(f"\n⚠️  Proceeding with {len(cards)} valid cards, skipping invalid ones\n")
    
    print(f"\n📊 Total valid cards: {len(cards)}")
    
    # Initialize embedding model
    print(f"\n🤖 Loading embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    
    # Convert cards to documents
    print("\n📝 Converting cards to documents...")
    documents = []
    ids = []
    metadatas = []
    
    for card in cards:
        doc = filiere_to_document(card)
        documents.append(doc)
        ids.append(card["id"])
        
        # Store filterable metadata
        metadata = {
            "nom": card["nom"],
            "type": card["type"],
            "ville": card["ville"],
            "domaine": card["domaine"],
            "frais_annuels_mad": card["frais_annuels_mad"],
            "langue_enseignement": card["langue_enseignement"],
            "taux_emploi": card["taux_emploi"],
            "salaire_moyen_premier_emploi_mad": card["salaire_moyen_premier_emploi_mad"],
            "duree_annees": card["duree_annees"],
            "serie_bac_requise": ",".join(card["serie_bac_requise"]),
            "debouches": ",".join(card["debouches"][:5]),  # Limit for metadata size
        }
        metadatas.append(metadata)
    
    # Generate embeddings
    print(f"\n🔢 Generating embeddings for {len(documents)} documents...")
    embeddings = model.encode(documents, show_progress_bar=True)
    
    # Initialize ChromaDB
    print(f"\n💾 Initializing ChromaDB at {CHROMA_DB_PATH}")
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Handle existing collection
    existing_collections = [c.name for c in client.list_collections()]
    
    if COLLECTION_NAME in existing_collections:
        if force_reindex:
            print(f"  🗑️  Deleting existing collection '{COLLECTION_NAME}'")
            client.delete_collection(name=COLLECTION_NAME)
        else:
            print(f"  📥 Collection '{COLLECTION_NAME}' exists, upserting...")
    
    # Create or get collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Moroccan higher education filières for OrientAgent"}
    )
    
    # Upsert documents
    print(f"\n📤 Upserting {len(documents)} documents to ChromaDB...")
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )
    
    # Verify
    count = collection.count()
    
    stats = {
        "total_files": len(list(CORPUS_PATH.glob("*.json"))),
        "total_cards": len(cards),
        "validation_errors": len(errors),
        "indexed_documents": count,
        "collection_name": COLLECTION_NAME,
        "chroma_path": CHROMA_DB_PATH,
    }
    
    print("\n" + "=" * 50)
    print("✅ INDEXING COMPLETE")
    print("=" * 50)
    print(f"  📁 Corpus files processed: {stats['total_files']}")
    print(f"  📇 Cards indexed: {stats['indexed_documents']}")
    print(f"  ⚠️  Validation errors: {stats['validation_errors']}")
    print(f"  📂 ChromaDB path: {stats['chroma_path']}")
    print(f"  📦 Collection: {stats['collection_name']}")
    print("=" * 50)
    
    return stats


def main():
    """CLI entry point for indexing."""
    force = "--force" in sys.argv or "-f" in sys.argv
    
    try:
        stats = index_corpus(force_reindex=force)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Indexing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

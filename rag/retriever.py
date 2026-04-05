"""
OrientAgent - ChromaDB Retriever

Provides semantic search over the Moroccan filières knowledge base.
"""

import os
import shutil
from typing import Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# Lazy initialization
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None
_embedding_model: Optional[SentenceTransformer] = None

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./rag/chroma_db")
COLLECTION_NAME = "filieres"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_embedding_model() -> SentenceTransformer:
    """Lazily load the sentence-transformers embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _is_legacy_config_error(error: Exception) -> bool:
    """Detect legacy ChromaDB collection config incompatibility."""
    if isinstance(error, KeyError) and str(error) == "'_type'":
        return True
    return "'_type'" in str(error) or '"_type"' in str(error)


def _is_missing_collection_error(error: Exception) -> bool:
    """Detect missing collection errors across Chroma versions."""
    text = str(error).lower()
    return "does not exist" in text or "not found" in text


def _rebuild_index_from_corpus() -> None:
    """Rebuild the local ChromaDB index from corpus JSON files."""
    global _chroma_client, _collection

    if os.path.exists(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH)

    from rag.indexer import index_corpus

    index_corpus(force_reindex=True)
    _chroma_client = None
    _collection = None


def _get_chroma_collection(_allow_legacy_rebuild: bool = True) -> chromadb.Collection:
    """Lazily initialize ChromaDB client and get the filieres collection."""
    global _chroma_client, _collection
    
    if _collection is not None:
        return _collection
    
    # Check if ChromaDB path exists
    if not os.path.exists(CHROMA_DB_PATH):
        raise RuntimeError(
            f"ChromaDB not initialized at {CHROMA_DB_PATH}. "
            "Run 'python rag/indexer.py' to index the corpus first."
        )
    
    try:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )

        _collection = _chroma_client.get_collection(name=COLLECTION_NAME)
        return _collection

    except Exception as e:
        # Some existing local DBs were created with an older Chroma schema
        # and fail with KeyError('_type') when loading collection metadata.
        if _allow_legacy_rebuild and (_is_legacy_config_error(e) or _is_missing_collection_error(e)):
            if _is_legacy_config_error(e):
                print("⚠️ Detected legacy ChromaDB schema. Rebuilding index from corpus...")
            else:
                print("⚠️ ChromaDB collection missing. Rebuilding index from corpus...")
            _rebuild_index_from_corpus()
            return _get_chroma_collection(_allow_legacy_rebuild=False)

        if _is_missing_collection_error(e):
            raise RuntimeError(
                f"Collection '{COLLECTION_NAME}' not found in ChromaDB. "
                "Run 'python rag/indexer.py' to index the corpus first."
            ) from e

        raise


def chromadb_retrieve(
    query: str,
    k: int = 8,
    filters: Optional[dict] = None
) -> list[dict]:
    """
    Retrieve top-K filières from ChromaDB matching the semantic query.
    
    Args:
        query: Natural language semantic query (e.g., "Formation informatique Casablanca")
        k: Number of results to return (default: 8)
        filters: Optional ChromaDB metadata filters, e.g. {"domaine": "tech"}
    
    Returns:
        List of filière dicts with added "similarity_score" field (0-1, higher is better)
    
    Raises:
        RuntimeError: If ChromaDB is not initialized or collection doesn't exist
    
    Example:
        >>> results = chromadb_retrieve("ingénieur informatique Maroc", k=5)
        >>> for r in results:
        ...     print(f"{r['nom']}: {r['similarity_score']:.2f}")
    """
    collection = _get_chroma_collection()
    embedding_model = _get_embedding_model()
    
    # Generate embedding for query
    query_embedding = embedding_model.encode(query).tolist()
    
    # Build query kwargs
    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"]
    }
    
    # Add filters if provided
    if filters:
        query_kwargs["where"] = filters
    
    # Execute query
    results = collection.query(**query_kwargs)
    
    # Process results into filière dicts
    filieres = []
    
    if results["ids"] and len(results["ids"][0]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            
            # Convert distance to similarity score (ChromaDB uses L2 distance by default)
            # Lower distance = higher similarity, we normalize to 0-1 range
            similarity_score = max(0, 1 - (distance / 2))
            
            filiere = {
                "id": doc_id,
                "document": results["documents"][0][i] if results["documents"] else "",
                "similarity_score": round(similarity_score, 3),
                **metadata
            }
            filieres.append(filiere)
    
    return filieres


def get_filiere_by_id(filiere_id: str) -> Optional[dict]:
    """
    Retrieve a specific filière by its ID.
    
    Args:
        filiere_id: The unique ID of the filière
    
    Returns:
        Filière dict or None if not found
    """
    collection = _get_chroma_collection()
    
    result = collection.get(
        ids=[filiere_id],
        include=["documents", "metadatas"]
    )
    
    if result["ids"] and len(result["ids"]) > 0:
        return {
            "id": result["ids"][0],
            "document": result["documents"][0] if result["documents"] else "",
            **(result["metadatas"][0] if result["metadatas"] else {})
        }
    
    return None


def search_by_domain(domain: str, k: int = 5) -> list[dict]:
    """
    Retrieve filières filtered by domain.
    
    Args:
        domain: One of "sciences", "tech", "lettres", "economie"
        k: Number of results
    
    Returns:
        List of filière dicts matching the domain
    """
    return chromadb_retrieve(
        query=f"Formation {domain} Maroc emploi débouchés",
        k=k,
        filters={"domaine": domain}
    )


def reset_cache() -> None:
    """Reset the cached ChromaDB client and collection (useful for testing)."""
    global _chroma_client, _collection, _embedding_model
    _chroma_client = None
    _collection = None
    _embedding_model = None

"""
Utility script to check similarity between sentences and stored solutions.
"""


import logging
from typing import List, Tuple

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_couchbase.vectorstores import CouchbaseSearchVectorStore

from src.config.config import settings
from setup.couchbase_client import CouchbaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
DEFAULT_INDEX_NAME = "semantic_solutions"
DEFAULT_COLLECTION_NAME = "solutions"
DEFAULT_K = 5
EMBEDDING_MODEL = "models/text-embedding-004"


class SimilarityChecker:
    """Check similarity between queries and stored solutions."""
    
    def __init__(self, index_name: str = DEFAULT_INDEX_NAME, collection_name: str = DEFAULT_COLLECTION_NAME):
        self.index_name = index_name
        self.collection_name = collection_name
        self.embedding_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        self.cb_client = CouchbaseClient()
        self.vector_store = self._initialize_vector_store()
    
    def _initialize_vector_store(self) -> CouchbaseSearchVectorStore:
        """Initialize the Couchbase vector store."""
        return CouchbaseSearchVectorStore(
            cluster=self.cb_client.cluster,
            bucket_name=settings.couchbase_bucket_name,
            scope_name=settings.couchbase_scope_name,
            collection_name=self.collection_name,
            embedding=self.embedding_model,
            index_name=self.index_name,
            text_key="solution_comment",
            embedding_key="embedding",
        )
    
    def similarity_search(self, query: str, k: int = DEFAULT_K) -> List[Tuple[str, float]]:
        """Return the top-k resolution comments most similar to the query.
        
        Args:
            query: The query string to search for
            k: Number of results to return
            
        Returns:
            List of tuples: (resolution_comment, similarity_score)
        """
        try:
            # Perform similarity search with scores
            results = self.vector_store.similarity_search_with_score(query=query, k=k)
            
            # Convert to plain tuples for easy printing
            formatted = [(doc.page_content, score) for doc, score in results]
            return formatted
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []


def main():
    """Main function to run similarity check."""
    # Test query
    test_query = "Inspect motor cable insulation for damage causing ground fault."
    
    checker = SimilarityChecker()
    hits = checker.similarity_search(test_query, k=DEFAULT_K)
    
    if not hits:
        logger.warning("No similar sentences found. Check index name, collection, or embeddings.")
        return

    logger.info("Top results:\n")
    for rank, (text, score) in enumerate(hits, start=1):
        print(f"{rank:02d}.  score={score:.4f} | {text}")


if __name__ == "__main__":
    main() 
"""
Couchbase LangChain Retriever Tool for Manual Semantic Search

This module provides tools for searching through machine manuals stored in Couchbase
using semantic similarity search capabilities.
"""

import logging
from typing import Optional

from langchain_couchbase import CouchbaseSearchVectorStore
from langchain.tools.retriever import create_retriever_tool
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.tools import Tool
from couchbase.cluster import Cluster

from src.config.config import settings

logger = logging.getLogger(__name__)

# Constants
EMBEDDING_MODEL = "models/text-embedding-004"
TEXT_KEY = "content"
EMBEDDING_KEY = "embedding"
DOCUMENT_SEPARATOR = "\n\n"
RESPONSE_FORMAT = "content"


def create_couchbase_manual_tools(cluster: Optional[Cluster] = None) -> Tool:
    """
    Create Couchbase manual retriever tools for semantic search of machine manuals.
    
    Args:
        cluster: Couchbase cluster instance. If None, tool creation will fail.
        
    Returns:
        Tool: A LangChain tool for manual retrieval
        
    Raises:
        ValueError: If cluster is None or required settings are missing
    """
    if cluster is None:
        raise ValueError("Couchbase cluster instance is required")
    
    try:
        # Initialize vector store with Couchbase
        vector_store = CouchbaseSearchVectorStore( 
            embedding=GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL),
            index_name=settings.couchbase_vector_index_name,
            cluster=cluster,
            bucket_name=settings.couchbase_bucket_name,
            scope_name=settings.couchbase_scope_name,
            collection_name=settings.couchbase_collections["manuals"],
            scoped_index=True,
            text_key=TEXT_KEY,
            embedding_key=EMBEDDING_KEY
        )

        # Create retriever from vector store
        retriever = vector_store.as_retriever()
        
        # Create and return the retriever tool
        return create_retriever_tool(
            retriever,
            name="couchbase_manual_retriever",
            description=_get_tool_description(),
            document_separator=DOCUMENT_SEPARATOR,
            response_format=RESPONSE_FORMAT,
        )
        
    except Exception as e:
        logger.error(f"Failed to create Couchbase manual retriever tool: {e}")
        raise


def _get_tool_description() -> str:
    """Get the detailed description for the manual retriever tool."""
    return """
    Retrieve relevant machine manual sections from the Couchbase database using semantic search.
    
    This tool searches through machine manuals to find the most relevant content for:
    • Troubleshooting procedures and error resolution
    • Error codes and details
    • Maintenance instructions and schedules  
    • Alert explanations and corrective actions
    • Installation and setup procedures
    • Operation guidelines and best practices
    • Safety protocols and emergency procedures
    
    The tool uses semantic similarity to find relevant content even when exact keywords 
    don't match, making it effective for natural language queries about machine operations.
    
    Input: A natural language query about any machine-related topic
    Output: Relevant manual sections with context and source information
    """.strip()
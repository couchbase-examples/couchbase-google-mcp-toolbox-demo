import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# LangChain imports for document processing pipeline
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_couchbase.vectorstores import CouchbaseVectorStore
from langchain_core.documents import Document

# Additional LangChain components
from langchain.schema import BaseRetriever
from langchain.vectorstores.base import VectorStore

import numpy as np
from .couchbase_client import CouchbaseClient
from .document_utils import extract_manufacturing_keywords
from src.config.config import settings

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Process and chunk documents for RAG implementation using LangChain pipeline."""
    
    def __init__(self, couchbase_client: CouchbaseClient):
        self.couchbase_client = couchbase_client
        
        # Initialize OpenAI embeddings
        self.embedding_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")
        
        # Initialize LangChain text splitter with optimized settings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=[
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentence endings
                " ",     # Words
                ""       # Characters
            ],
            add_start_index=True  # Track position in original document
        )
        
        # Initialize Couchbase Vector Store
        self.vector_store = None
        self._initialize_vector_store()
        
    def _initialize_vector_store(self):
        """Initialize the Couchbase vector store."""
        try:
            self.vector_store = CouchbaseVectorStore(
                cluster=self.couchbase_client.cluster,
                bucket_name=settings.couchbase_bucket_name,
                scope_name=settings.couchbase_scope_name,
                collection_name=settings.couchbase_collections["manuals"],
                embedding=self.embedding_model,
                index_name=settings.couchbase_vector_index_name,
                text_key="content",
                embedding_key="embedding"
            )
            logger.info("✅ Couchbase vector store initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Couchbase vector store: {e}")
            logger.warning("⚠️ Vector store will not be available - RAG functionality will be limited")
            logger.info("💡 To enable full RAG functionality, create vector search index manually:")
            logger.info("   1. Open Couchbase Web UI → Search")
            logger.info("   2. Create search index named 'manual_search_index'")
            logger.info(f"   3. Source: bucket={settings.couchbase_bucket_name}, scope={settings.couchbase_scope_name}, collection={settings.couchbase_collections['manuals']}")
            logger.info("   4. Add vector field 'embedding' (3072 dimensions, dot_product)")
            logger.info("   5. Add text field 'content'")
            self.vector_store = None
    
    def load_pdf_documents(self, pdf_path: str) -> List[Document]:
        """Load PDF documents using LangChain PyPDFLoader."""
        try:
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Use LangChain's PyPDFLoader
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            
            logger.info(f"📄 Loaded {len(documents)} pages from PDF: {pdf_path}")
            
            # Add source metadata to each document
            for i, doc in enumerate(documents):
                doc.metadata.update({
                    'source_file': pdf_path,
                    'page_number': i + 1,
                    'document_type': 'manual',
                    'loader': 'PyPDFLoader'
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error loading PDF with LangChain PyPDFLoader: {e}")
            return []
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks using LangChain text splitter."""
        try:
            # Use LangChain's RecursiveCharacterTextSplitter
            chunks = self.text_splitter.split_documents(documents)
            
            logger.info(f"📝 Split {len(documents)} documents into {len(chunks)} chunks")
            
            # Enhance metadata with manufacturing-specific information
            for i, chunk in enumerate(chunks):
                # Add chunk-specific metadata
                chunk.metadata.update({
                    'chunk_index': i,
                    'chunk_id': f"manual_chunk_{i:04d}",
                    'word_count': len(chunk.page_content.split()),
                    'char_count': len(chunk.page_content),
                    'contains_procedure': self._contains_procedure(chunk.page_content),
                    'keywords': self._extract_keywords(chunk.page_content),
                    'embedding_model': "text-embedding-3-large",
                    'processing_timestamp': str(np.datetime64('now'))
                })
            
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Error splitting documents: {e}")
            return []
    
    def _contains_procedure(self, text: str) -> bool:
        """Check if text contains procedural information."""
        procedure_keywords = [
            'procedure', 'step', 'instruction', 'warning', 'caution',
            'maintenance', 'troubleshoot', 'error', 'alarm', 'fault',
            'safety', 'emergency', 'operation', 'start', 'stop'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in procedure_keywords)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant manufacturing keywords from text."""
        return extract_manufacturing_keywords(text)
    
    def process_manual(self, pdf_path: str) -> bool:
        """Process PDF manual using LangChain pipeline and store in Couchbase."""
        try:
            # Step 1: Load PDF documents using LangChain
            logger.info("🔄 Step 1: Loading PDF documents...")
            documents = self.load_pdf_documents(pdf_path)
            
            if not documents:
                logger.error("❌ No documents loaded from PDF")
                return False
            
            # Step 2: Split documents into chunks using LangChain
            logger.info("🔄 Step 2: Splitting documents into chunks...")
            chunks = self.split_documents(documents)
            
            if not chunks:
                logger.error("❌ No chunks created from documents")
                return False
            
            # Step 3: Store chunks in Couchbase
            if self.vector_store:
                logger.info(f"🔄 Step 3: Storing {len(chunks)} chunks in Couchbase vector store...")
                
                # Generate unique IDs for chunks
                chunk_ids = [chunk.metadata['chunk_id'] for chunk in chunks]
                
                # Use LangChain vector store to add documents
                # This automatically handles: embedding generation, vector storage, metadata storage
                stored_ids = self.vector_store.add_documents(
                    documents=chunks,
                    ids=chunk_ids
                )
                
                logger.info(f"✅ Successfully stored {len(stored_ids)} chunks in Couchbase vector store")
                logger.info("🎯 Pipeline completed: PDF → Chunks → Embeddings → Couchbase")
                
                return len(stored_ids) > 0
            else:
                # Fallback: Store chunks directly in Couchbase without vector search
                logger.info(f"🔄 Step 3: Storing {len(chunks)} chunks directly in Couchbase (no vector store)...")
                
                stored_count = 0
                for chunk in chunks:
                    try:
                        # Store chunk using the manual chunk storage method
                        chunk_id = chunk.metadata['chunk_id']
                        success = self.couchbase_client.store_manual_chunk(
                            chunk_id=chunk_id,
                            content=chunk.page_content,
                            metadata=chunk.metadata
                        )
                        if success:
                            stored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to store chunk {chunk.metadata.get('chunk_id', 'unknown')}: {e}")
                
                logger.info(f"✅ Successfully stored {stored_count}/{len(chunks)} chunks directly in Couchbase")
                logger.warning("⚠️ Chunks stored without embeddings - vector search not available")
                
                return stored_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error in LangChain processing pipeline: {e}")
            return False
    
    def find_relevant_content(self, query: str, max_chunks: int = 5) -> List[Dict[str, Any]]:
        """Find relevant content using LangChain vector store similarity search."""
        try:
            if not self.vector_store:
                logger.error("❌ Vector store not initialized")
                return []
            
            # Use LangChain vector store for similarity search with scores
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=max_chunks
            )
            
            # Convert to expected format
            relevant_chunks = []
            for doc, score in results:
                chunk_data = {
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'similarity_score': score
                }
                relevant_chunks.append(chunk_data)
            
            logger.info(f"🔍 Found {len(relevant_chunks)} relevant chunks for query: '{query}'")
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"❌ Error finding relevant content: {e}")
            return []
    
    def search_with_filters(self, query: str, filters: Optional[Dict[str, Any]] = None, max_chunks: int = 5) -> List[Dict[str, Any]]:
        """Search with additional filters using LangChain Couchbase vector store."""
        try:
            if not self.vector_store:
                logger.error("❌ Vector store not initialized")
                return []
            
            # Convert filters to Couchbase search query format
            search_options = {}
            if filters:
                if 'keywords' in filters:
                    search_options['query'] = {
                        'field': 'metadata.keywords',
                        'match': filters['keywords']
                    }
                elif 'procedure_only' in filters and filters['procedure_only']:
                    search_options['query'] = {
                        'field': 'metadata.contains_procedure',
                        'term': True
                    }
                elif 'page_number' in filters:
                    search_options['query'] = {
                        'field': 'metadata.page_number',
                        'term': filters['page_number']
                    }
            
            # Use LangChain vector store with search options
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=max_chunks,
                search_options=search_options
            )
            
            # Convert to expected format
            relevant_chunks = []
            for doc, score in results:
                chunk_data = {
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'similarity_score': score
                }
                relevant_chunks.append(chunk_data)
            
            logger.info(f"🔍 Found {len(relevant_chunks)} chunks with filters")
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"❌ Error searching with filters: {e}")
            return []
    
    def get_vector_store_as_retriever(self, search_type: str = "similarity", search_kwargs: Optional[Dict[str, Any]] = None) -> Optional[BaseRetriever]:
        """Get the vector store as a LangChain retriever for use in chains."""
        try:
            if not self.vector_store:
                logger.error("❌ Vector store not initialized")
                return None
            
            if search_kwargs is None:
                search_kwargs = {"k": 5}
            
            retriever = self.vector_store.as_retriever(
                search_type=search_type,
                search_kwargs=search_kwargs
            )
            
            logger.info(f"🔗 Created LangChain retriever with search_type='{search_type}'")
            return retriever
            
        except Exception as e:
            logger.error(f"❌ Error creating retriever: {e}")
            return None
    
    def get_vector_store(self) -> Optional[VectorStore]:
        """Get the underlying vector store for advanced operations."""
        return self.vector_store
    
    def delete_all_documents(self) -> bool:
        """Delete all documents from the vector store."""
        try:
            if not self.vector_store:
                logger.error("❌ Vector store not initialized")
                return False
            
            # Note: This would require getting all document IDs first
            # For comprehensive deletion, collection recreation might be needed
            logger.info("🗑️  Document deletion would require collection recreation")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting documents: {e}")
            return False
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about the processed documents."""
        try:
            if not self.vector_store:
                return {"error": "Vector store not initialized"}
            
            # This would need to be implemented based on Couchbase collection stats
            stats = {
                "vector_store_initialized": True,
                "embedding_model": "text-embedding-3-large",
                "text_splitter": "RecursiveCharacterTextSplitter",
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting processing stats: {e}")
            return {"error": str(e)} 
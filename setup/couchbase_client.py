import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from couchbase.exceptions import CouchbaseException
from couchbase.scope import Scope
from couchbase.management.search import SearchIndex
from src.config.config import settings

logger = logging.getLogger(__name__)

def serialize_datetime(obj):
    """Custom serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    else:
        return obj

class CouchbaseClient:
    """Couchbase client for CPG manufacturing data management with multi-collection support."""
    
    def __init__(self):
        self.cluster = None
        self.bucket = None
        self.scope: Optional[Scope] = None
        self.collections = {}  # Dictionary to store different collections
        self.connect()
    
    def connect(self):
        """Establish connection to Couchbase cluster."""
        try:
            # Create authenticator
            auth = PasswordAuthenticator(
                settings.couchbase_username,
                settings.couchbase_password
            )
            
            # Connect to cluster
            self.cluster = Cluster(
                settings.couchbase_connection_string,
                ClusterOptions(auth)
            )
            
            # Get bucket
            self.bucket = self.cluster.bucket(settings.couchbase_bucket_name)
            
            # Get scope (assuming it exists)
            self.scope = self.bucket.scope(settings.couchbase_scope_name)
            
            # Initialize all collections (assuming they exist)
            for collection_type, collection_name in settings.couchbase_collections.items():
                try:
                    self.collections[collection_type] = self.scope.collection(collection_name)
                except Exception as e:
                    logger.warning(f"Collection '{collection_name}' not accessible: {e}")
                    # Fall back to default collection if specific collection fails
                    self.collections[collection_type] = self.bucket.default_collection()
            
            logger.info(f"Successfully connected to Couchbase bucket: {settings.couchbase_bucket_name}, scope: {settings.couchbase_scope_name}")
            logger.info(f"Initialized collections: {list(settings.couchbase_collections.keys())}")
            
        except CouchbaseException as e:
            logger.error(f"Failed to connect to Couchbase: {e}")
            raise
    
    def setup_collections(self):
        """Create scope and all required collections if they don't exist."""
        try:
            self._ensure_scope_and_collections_exist()
            self._ensure_langgraph_scope_and_collections_exist()
            
            # Re-initialize collections after creation
            for collection_type, collection_name in settings.couchbase_collections.items():
                self.collections[collection_type] = self.scope.collection(collection_name)
            
            logger.info("✅ Collections setup completed")
            
        except Exception as e:
            logger.error(f"❌ Collection setup failed: {e}")
            raise

    def _ensure_scope_and_collections_exist(self):
        """Create scope and all required collections if they don't exist."""
        try:
            bucket_manager = self.bucket.collections()
            
            # Check and create scope if it doesn't exist
            try:
                existing_scopes = bucket_manager.get_all_scopes()
                scope_exists = any(scope.name == settings.couchbase_scope_name for scope in existing_scopes)
                
                if not scope_exists:
                    logger.info(f"Creating scope: {settings.couchbase_scope_name}")
                    bucket_manager.create_scope(settings.couchbase_scope_name)
                    logger.info(f"✅ Scope '{settings.couchbase_scope_name}' created successfully")
                else:
                    logger.info(f"✅ Scope '{settings.couchbase_scope_name}' already exists")
                    
            except Exception as e:
                logger.error(f"❌ Error checking/creating scope: {e}")
                # If we can't create the scope, fall back to default
                if settings.couchbase_scope_name != "_default":
                    logger.warning(f"⚠️ Falling back to _default scope due to error: {e}")
                    settings.couchbase_scope_name = "_default"
            
            # Drop existing collections and create new ones
            try:
                existing_scopes = bucket_manager.get_all_scopes()
                target_scope = next((scope for scope in existing_scopes if scope.name == settings.couchbase_scope_name), None)
                
                if target_scope:
                    existing_collection_names = {coll.name for coll in target_scope.collections}
                    
                    # Drop existing collections first
                    for collection_type, collection_name in settings.couchbase_collections.items():
                        if collection_name in existing_collection_names:
                            logger.info(f"🗑️ Dropping existing collection: {collection_name} (for {collection_type}) in scope: {settings.couchbase_scope_name}")
                            try:
                                bucket_manager.drop_collection(
                                    collection_name=collection_name,
                                    scope_name=settings.couchbase_scope_name
                                )
                                logger.info(f"✅ Collection '{collection_name}' dropped successfully")
                            except Exception as e:
                                logger.error(f"❌ Failed to drop collection '{collection_name}': {e}")
                    
                    # Now create all collections fresh
                    for collection_type, collection_name in settings.couchbase_collections.items():
                        logger.info(f"Creating collection: {collection_name} (for {collection_type}) in scope: {settings.couchbase_scope_name}")
                        try:
                            bucket_manager.create_collection( 
                                collection_name=collection_name,
                                scope_name=settings.couchbase_scope_name
                            )
                            logger.info(f"✅ Collection '{collection_name}' created successfully")
                        except Exception as e:
                            logger.error(f"❌ Failed to create collection '{collection_name}': {e}")
                        
            except Exception as e:
                logger.error(f"❌ Error checking/creating collections: {e}")
                # If we can't create collections, fall back to default
                logger.warning(f"⚠️ Some collections may not be available due to error: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in scope/collection management: {e}")
            logger.warning("⚠️ Falling back to default scope and collection")

    def _ensure_langgraph_scope_and_collections_exist(self):
        """Create LangGraph scope and collections for checkpointing if they don't exist."""
        try:
            bucket_manager = self.bucket.collections()
            
            # Check and create LangGraph scope if it doesn't exist
            try:
                existing_scopes = bucket_manager.get_all_scopes()
                langgraph_scope_exists = any(scope.name == settings.langgraph_scope_name for scope in existing_scopes)
                
                if not langgraph_scope_exists:
                    logger.info(f"Creating LangGraph scope: {settings.langgraph_scope_name}")
                    bucket_manager.create_scope(settings.langgraph_scope_name)
                    logger.info(f"✅ LangGraph scope '{settings.langgraph_scope_name}' created successfully")
                else:
                    logger.info(f"✅ LangGraph scope '{settings.langgraph_scope_name}' already exists")
                    
            except Exception as e:
                logger.error(f"❌ Error checking/creating LangGraph scope: {e}")
                return  # Skip collection creation if scope creation fails
            
            # Create LangGraph collections
            try:
                langgraph_collections = {
                    "checkpoints": settings.langgraph_checkpoints_collection_name,
                    "checkpoint_writes": settings.langgraph_checkpoint_writes_collection_name
                }
                
                existing_scopes = bucket_manager.get_all_scopes()
                langgraph_scope = next((scope for scope in existing_scopes if scope.name == settings.langgraph_scope_name), None)
                
                if langgraph_scope:
                    existing_collection_names = {coll.name for coll in langgraph_scope.collections}
                    
                    # Drop existing LangGraph collections first
                    for collection_type, collection_name in langgraph_collections.items():
                        if collection_name in existing_collection_names:
                            logger.info(f"🗑️ Dropping existing LangGraph collection: {collection_name} (for {collection_type}) in scope: {settings.langgraph_scope_name}")
                            try:
                                bucket_manager.drop_collection(
                                    collection_name=collection_name,
                                    scope_name=settings.langgraph_scope_name
                                )
                                logger.info(f"✅ LangGraph collection '{collection_name}' dropped successfully")
                            except Exception as e:
                                logger.error(f"❌ Failed to drop LangGraph collection '{collection_name}': {e}")
                    
                    # Now create all LangGraph collections fresh
                    for collection_type, collection_name in langgraph_collections.items():
                        logger.info(f"Creating LangGraph collection: {collection_name} (for {collection_type}) in scope: {settings.langgraph_scope_name}")
                        try:
                            bucket_manager.create_collection( 
                                collection_name=collection_name,
                                scope_name=settings.langgraph_scope_name
                            )
                            logger.info(f"✅ LangGraph collection '{collection_name}' created successfully")
                        except Exception as e:
                            logger.error(f"❌ Failed to create LangGraph collection '{collection_name}': {e}")
                        
            except Exception as e:
                logger.error(f"❌ Error checking/creating LangGraph collections: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in LangGraph scope/collection management: {e}")
            logger.warning("⚠️ LangGraph collections may not be available")

    def get_collection(self, collection_type: str):
        """Get a specific collection by type."""
        if collection_type in self.collections:
            return self.collections[collection_type]
        else:
            logger.warning(f"Collection type '{collection_type}' not found, using default collection")
            return self.bucket.default_collection()

    def create_indexes(self):
        """Create primary indexes for all collections."""
        try:
            bucket_name = settings.couchbase_bucket_name
            scope_name = settings.couchbase_scope_name
            
            # Create primary indexes for each collection
            primary_indexes = []
            
            # Primary index for each manufacturing collection
            for collection_type, collection_name in settings.couchbase_collections.items():
                if scope_name == "_default":
                    collection_path = f"`{bucket_name}`"
                else:
                    collection_path = f"`{bucket_name}`.`{scope_name}`.`{collection_name}`"
                
                primary_indexes.append(f"CREATE PRIMARY INDEX ON {collection_path}")
            
            # Create all primary indexes
            for index in primary_indexes:
                try:
                    self.cluster.query(index)
                    logger.info(f"Created primary index: {index}")
                except CouchbaseException as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Failed to create primary index: {e}")
            
            # Create LangGraph indexes
            self.create_langgraph_indexes()
            
            # Create vector search indexes
            self.create_vector_indexes()
                        
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    def create_langgraph_indexes(self):
        """Create primary indexes for LangGraph checkpointing collections."""
        try:
            bucket_name = settings.couchbase_bucket_name
            langgraph_scope_name = settings.langgraph_scope_name
            
            # Create primary indexes for LangGraph collections
            langgraph_collections = [
                settings.langgraph_checkpoints_collection_name,
                settings.langgraph_checkpoint_writes_collection_name
            ]
            
            langgraph_primary_indexes = []
            
            for collection_name in langgraph_collections:
                if langgraph_scope_name == "_default":
                    collection_path = f"`{bucket_name}`"
                else:
                    collection_path = f"`{bucket_name}`.`{langgraph_scope_name}`.`{collection_name}`"
                
                langgraph_primary_indexes.append(f"CREATE PRIMARY INDEX ON {collection_path}")
            
            # Create all LangGraph primary indexes
            for index in langgraph_primary_indexes:
                try:
                    self.cluster.query(index)
                    logger.info(f"Created LangGraph primary index: {index}")
                except CouchbaseException as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Failed to create LangGraph primary index: {e}")
                        
        except Exception as e:
            logger.error(f"Error creating LangGraph indexes: {e}")

    def create_vector_indexes(self):
        """Create vector search indexes for RAG functionality."""
        try:
            manuals_collection = settings.couchbase_collections['manuals']
            
            logger.info("Creating vector search indexes for RAG...")
            
            # ---------- Manuals vector index (text + embeddings) -----------
            self._upsert_vector_index(
                index_name=settings.couchbase_vector_index_name,
                collection_name=manuals_collection,
                embedding_dims=768,
                text_field_name="content",
            )

            # ---------- Solutions vector index (solution_comment + embeddings) -----------
            solutions_collection = settings.couchbase_collections.get("solutions")
            if solutions_collection:
                solutions_vector_index_name = f"semantic_{solutions_collection}"
                self._upsert_vector_index(
                    index_name=solutions_vector_index_name,
                    collection_name=solutions_collection,
                    embedding_dims=768,
                    text_field_name="solution_comment",
                    keyword_fields=["error_code"],
                )
            
        except Exception as e:
            logger.error(f"Error in vector index creation: {e}")

    def _upsert_vector_index(self, index_name: str, collection_name: str, embedding_dims: int = 768, text_field_name: str = "", keyword_fields: Optional[List[str]] = None):
        """Helper to (re)create a vector-search index for a given collection."""
        try:
            bucket_name = settings.couchbase_bucket_name
            scope_name = settings.couchbase_scope_name

            text_field = text_field_name or "content"
            keyword_fields = keyword_fields or []

            vector_index_definition = {
                "type": "fulltext-index",
                "name": index_name,
                "sourceName": bucket_name,
                "sourceType": "gocbcore",
                "planParams": {"index_partitions": 1, "num_replicas": 0},
                "params": {
                    "doc_config": {
                        "docid_prefix_delim": "",
                        "docid_regexp": "",
                        "mode": "scope.collection.type_field",
                        "type_field": "type",
                    },
                    "mapping": {
                        "default_analyzer": "standard",
                        "default_datetime_parser": "dateTimeOptional",
                        "default_field": "_all",
                        "default_mapping": {"dynamic": True, "enabled": False},
                        "default_type": "_default",
                        "docvalues_dynamic": False,
                        "index_dynamic": True,
                        "store_dynamic": True,
                        "type_field": "_type",
                        "types": {
                            f"{scope_name}.{collection_name}": {
                                "dynamic": False,
                                "enabled": True,
                                "properties": {
                                    f"{text_field}": {
                                        "dynamic": False,
                                        "enabled": True,
                                        "fields": [
                                            {
                                                "store": True,
                                                "index": True,
                                                "name": text_field,
                                                "type": "text",
                                            }
                                        ],
                                    },
                                    "embedding": {
                                        "dynamic": False,
                                        "enabled": True,
                                        "fields": [
                                            {
                                                "dims": embedding_dims,
                                                "index": True,
                                                "name": "embedding",
                                                "similarity": "dot_product",
                                                "type": "vector",
                                                "vector_index_optimized_for": "recall",
                                            }
                                        ],
                                    },
                                },
                            }
                        },
                    },
                },
            }

            # Add keyword analyzers for specified fields
            if keyword_fields:
                for kw in keyword_fields:
                    vector_index_definition["params"]["mapping"]["types"][f"{scope_name}.{collection_name}"]["properties"][kw] = {
                        "dynamic": False,
                        "enabled": True,
                        "fields": [
                            {
                                "name": kw,
                                "type": "text",
                                "analyzer": "keyword",
                                "index": True,
                                "store": True,
                            }
                        ],
                    }

            self.scope.search_indexes().upsert_index(SearchIndex.from_json(vector_index_definition))
            logger.info(f"✅ Vector search index '{index_name}' created/updated successfully")
        except Exception as err:
            logger.error(f"Failed to upsert vector index '{index_name}': {err}")

    def store_document(self, key: str, document: Dict[str, Any], collection_type: str = "machines") -> bool:
        """Store a document in the appropriate collection."""
        try:
            # Serialize datetime objects to ISO format strings
            serialized_document = serialize_datetime(document.copy())
            
            # Add metadata
            serialized_document['created_at'] = datetime.utcnow().isoformat()
            serialized_document['updated_at'] = datetime.utcnow().isoformat()
            
            collection = self.get_collection(collection_type)
            collection.upsert(key, serialized_document)
            logger.debug(f"Stored document with key: {key} in {collection_type} collection")
            return True
            
        except CouchbaseException as e:
            logger.error(f"Failed to store document {key} in {collection_type}: {e}")
            return False


    
    
    def store_manual_chunk(self, chunk_id: str, content: str, 
                          metadata: Dict[str, Any]) -> bool:
        """Store a processed manual chunk with embeddings in manuals collection."""
        document = {
            'type': 'manual_chunk',
            'chunk_id': chunk_id,
            'content': content,
            'metadata': metadata,
            'machine_type': metadata.get('machine_type', 'Ultima_SV')
        }
        
        return self.store_document(f"manual_chunk_{chunk_id}", document, collection_type="manuals")
    

    def close(self):
        """Close the Couchbase connection."""
        if self.cluster:
            self.cluster.close()
            logger.info("Disconnected from Couchbase") 
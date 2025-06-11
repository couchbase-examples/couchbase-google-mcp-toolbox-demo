"""
Database connection management for Couchbase.
"""

import logging
from typing import Optional

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from acouchbase.cluster import AsyncCluster
from langgraph_checkpointer_couchbase import AsyncCouchbaseSaver

from config import settings

logger = logging.getLogger(__name__)

# LangGraph Checkpointer Configuration
LANGGRAPH_CHECKPOINTER_COUCHBASE_CONFIG = {
    "bucket_name": settings.couchbase_bucket_name,
    "scope_name": settings.langgraph_scope_name,
    "checkpoints_collection_name": settings.langgraph_checkpoints_collection_name, 
    "checkpoint_writes_collection_name": settings.langgraph_checkpoint_writes_collection_name
}


class DatabaseManager:
    """Manages Couchbase database connections and checkpointer setup."""
    
    def __init__(self):
        self.cluster: Optional[Cluster] = None
        self.async_cluster: Optional[AsyncCluster] = None
        self.checkpointer: Optional[AsyncCouchbaseSaver] = None
        self.is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize Couchbase cluster connections and checkpointer."""
        logger.info("Initializing database connections...")
        
        try:
            await self._initialize_couchbase_connections()
            await self._initialize_checkpointer()
            self.is_initialized = True
            logger.info("✅ Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
            self.is_initialized = False
            raise

    async def _initialize_couchbase_connections(self) -> None:
        """Initialize Couchbase cluster connections."""
        logger.info("Establishing Couchbase connections...")
        
        auth = PasswordAuthenticator(
            settings.couchbase_username,
            settings.couchbase_password
        )
        cluster_options = ClusterOptions(auth)
        
        self.async_cluster = AsyncCluster(
            settings.couchbase_connection_string,
            cluster_options
        )
        self.cluster = Cluster(
            settings.couchbase_connection_string,
            cluster_options
        )
        
        logger.info("✅ Couchbase connections established")

    async def _initialize_checkpointer(self) -> None:
        """Initialize the LangGraph checkpointer with Couchbase."""
        logger.info("Initializing LangGraph checkpointer...")
        
        if not self.async_cluster:
            raise RuntimeError("Async cluster must be initialized before checkpointer")
        async with AsyncCouchbaseSaver.from_cluster(
            cluster=self.async_cluster,
            **LANGGRAPH_CHECKPOINTER_COUCHBASE_CONFIG
        ) as checkpointer:
            self.checkpointer = checkpointer
            logger.info("✅ LangGraph checkpointer initialized")
        


    async def cleanup(self) -> None:
        """Clean up database connections."""
        logger.info("Cleaning up database connections...")
        
        if self.checkpointer:
            try:
                await self.checkpointer.close()
                logger.info("Checkpointer closed")
            except Exception as e:
                logger.warning(f"Error closing checkpointer: {e}")
        
        if self.async_cluster:
            try:
                await self.async_cluster.close()
                logger.info("Async cluster connection closed")
            except Exception as e:
                logger.warning(f"Error closing async cluster: {e}")
            
        if self.cluster:
            try:
                self.cluster.close()
                logger.info("Cluster connection closed")
            except Exception as e:
                logger.warning(f"Error closing cluster: {e}")

    def get_cluster(self) -> Optional[Cluster]:
        """Get the synchronous Couchbase cluster instance."""
        return self.cluster

    def get_async_cluster(self) -> Optional[AsyncCluster]:
        """Get the asynchronous Couchbase cluster instance."""
        return self.async_cluster

    def get_checkpointer(self) -> Optional[AsyncCouchbaseSaver]:
        """Get the LangGraph checkpointer instance."""
        return self.checkpointer


async def initialize_database_connections() -> DatabaseManager:
    """
    Factory function to initialize and return a configured DatabaseManager.
    
    Returns:
        DatabaseManager: Configured database manager instance
        
    Raises:
        Exception: If database initialization fails
    """
    db_manager = DatabaseManager()
    await db_manager.initialize()
    return db_manager 
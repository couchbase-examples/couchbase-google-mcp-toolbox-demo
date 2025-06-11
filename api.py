import logging
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from src.db import DatabaseManager
from src.agents.enhanced_manufacturing_agent import (
    EnhancedManufacturingAgent,
    create_manufacturing_agent as actual_create_agent
)
from src.models.api_models import QueryRequest, QueryResponse
from src.models.manufacturing_models import OperatorQuery

# Constants
API_TITLE = "Manufacturing AI Assistant API"
API_DESCRIPTION = "API for interacting with the Enhanced Manufacturing AI Agent."
API_VERSION = "1.0.0"
TOOLBOX_URL = "http://127.0.0.1:5000"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemState:
    """Manages the global system state including database connections and AI agent."""
    
    def __init__(self):
        self.db_manager: Optional[DatabaseManager] = None
        self.agent: Optional[EnhancedManufacturingAgent] = None
        self.system_online: bool = False

    async def initialize(self) -> None:
        """Initialize all system components."""
        logger.info("Starting system initialization...")
        
        try:
            await self._initialize_database()
            await self._initialize_agent()
            self.system_online = True
            logger.info("✅ System initialization completed successfully")
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}", exc_info=True)
            self.system_online = False
            raise

    async def _initialize_database(self) -> None:
        """Initialize database connections using DatabaseManager."""
        logger.info("Initializing database manager...")
        
        self.db_manager = DatabaseManager()
        await self.db_manager.initialize()
        
        logger.info("✅ Database manager initialized")

    async def _initialize_agent(self) -> None:
        """Initialize the manufacturing AI agent."""
        logger.info("Initializing EnhancedManufacturingAgent...")
        
        if not self.db_manager or not self.db_manager.is_initialized:
            raise RuntimeError("Database manager must be initialized before agent")
        
        self.agent = actual_create_agent(
            toolbox_url=TOOLBOX_URL,
            cluster=self.db_manager.get_cluster(),
            checkpointer=self.db_manager.get_checkpointer(),
        )
        
        logger.info("✅ EnhancedManufacturingAgent initialized successfully")

    async def cleanup(self) -> None:
        """Clean up system resources."""
        logger.info("Shutting down system...")
        
        if self.db_manager:
            await self.db_manager.cleanup()


# Initialize FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# Global system state
system_state = SystemState()


@app.on_event("startup")
async def startup_event():
    """Initialize system components on startup."""
    await system_state.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    await system_state.cleanup()


@app.get("/status")
async def get_status():
    """Check the system status."""
    return {"system_online": system_state.system_online}


@app.post("/process_query", response_model=QueryResponse)
async def process_query_endpoint(request: QueryRequest):
    """
    Process a user query and return the AI's response.
    
    Args:
        request: The query request containing user input and context
        
    Returns:
        QueryResponse: The AI agent's response
        
    Raises:
        HTTPException: If system is offline or processing fails
    """
    if not system_state.system_online or not system_state.agent:
        raise HTTPException(
            status_code=503, 
            detail="System is not online or AI agent is not available"
        )

    try:
        operator_query = OperatorQuery(
            query_id=str(uuid.uuid4()),
            operator_id=f"chat_{request.chat_session_id}",
            production_line_id=request.selected_line,
            machine_id=request.machine_id,
            query_text=request.user_input,
            query_type=request.query_type
        )

        response = await system_state.agent.process_query(operator_query)
        return QueryResponse(response_text=response.response_text)

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 
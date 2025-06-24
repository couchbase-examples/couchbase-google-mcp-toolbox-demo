import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Couchbase Configuration
    couchbase_connection_string: str = os.getenv("COUCHBASE_CONNECTION_STRING", "couchbase://localhost")
    couchbase_username: str = os.getenv("COUCHBASE_USERNAME", "Administrator")
    couchbase_password: str = os.getenv("COUCHBASE_PASSWORD", "password")
    couchbase_bucket_name: str = os.getenv("COUCHBASE_BUCKET_NAME", "cpg_manufacturing")
    couchbase_scope_name: str = os.getenv("COUCHBASE_SCOPE_NAME", "manufacturing")
    couchbase_vector_index_name: str = os.getenv("COUCHBASE_VECTOR_INDEX_NAME", "semantic_manual")
    
    # LangGraph Configuration
    langgraph_scope_name: str = os.getenv("LANGGRAPH_SCOPE_NAME", "langgraph")
    langgraph_checkpoints_collection_name: str = os.getenv("LANGGRAPH_CHECKPOINTS_COLLECTION_NAME", "langgraph_checkpoints")
    langgraph_checkpoint_writes_collection_name: str = os.getenv("LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME", "checkpoint_writes")
    
    # Collection Configuration for different data types
    couchbase_collections: dict = {
        "manuals": os.getenv("COUCHBASE_COLLECTION_MANUALS", "manuals"),
        "machines": os.getenv("COUCHBASE_COLLECTION_MACHINES", "machines"),
        "production_lines": os.getenv("COUCHBASE_COLLECTION_PROD_LINES", "production_lines"),
        "alerts": os.getenv("COUCHBASE_COLLECTION_ALERTS", "alerts"),
        "maintenance": os.getenv("COUCHBASE_COLLECTION_MAINTENANCE", "maintenance"),
        "metrics": os.getenv("COUCHBASE_COLLECTION_METRICS", "metrics"),
        "solutions": os.getenv("COUCHBASE_COLLECTION_SOLUTIONS", "solutions")
    }
    
    # Application Configuration
    app_name: str = os.getenv("APP_NAME", "CPG Manufacturing AI Assistant")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Demo Configuration
    production_line_count: int = int(os.getenv("PRODUCTION_LINE_COUNT", "5"))
    shift_duration_hours: int = int(os.getenv("SHIFT_DURATION_HOURS", "8"))

settings = Settings() 
#!/usr/bin/env python3
"""
CPG Manufacturing AI Assistant - System Setup Script
Handles document processing and sample data generation.
"""

import asyncio
import logging
from pathlib import Path

from setup.couchbase_client import CouchbaseClient
from setup.document_processor import DocumentProcessor
from setup.sample_data_generator import SampleDataGenerator
from config import settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemSetup:
    """Handles system initialization, document processing, and sample data generation."""
    
    def __init__(self):
        self.couchbase_client = None
        self.document_processor = None
        self.sample_data_generator = None
    
    async def initialize_components(self):
        """Initialize all setup components."""
        logger.info("🔧 Initializing setup components...")
        
        try:
            # Initialize Couchbase client
            logger.info("Connecting to Couchbase...")
            self.couchbase_client = CouchbaseClient()
            
            # Setup collections (drop and recreate)
            logger.info("Setting up collections...")
            self.couchbase_client.setup_collections()
            
            # Create indexes
            logger.info("Creating database indexes...")
            self.couchbase_client.create_indexes()
            
            # Initialize document processor
            logger.info("Initializing document processor...")
            self.document_processor = DocumentProcessor(self.couchbase_client)
            
            # Initialize sample data generator
            logger.info("Initializing sample data generator...")
            self.sample_data_generator = SampleDataGenerator(self.couchbase_client)
            
            logger.info("✅ Setup components initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup component initialization failed: {e}")
            return False
    
    async def process_manual_documents(self, manual_path: str = "manual.txt"):
        """Process and store manual documents."""
        logger.info("📚 Processing manual documents...")
        
        try:
            manual_file = Path(manual_path)
            if not manual_file.exists():
                logger.warning(f"Manual file not found: {manual_path}")
                logger.info("Skipping manual processing - you can add manual.txt later")
                return True
            
            logger.info(f"Processing manual: {manual_path}")
            success = self.document_processor.process_manual(manual_path)
            
            if success:
                logger.info("✅ Manual processed and stored successfully!")
                return True
            else:
                logger.warning("⚠️ Manual processing failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Manual processing failed: {e}")
            return False
    
    async def generate_sample_data(self):
        """Generate sample manufacturing data."""
        logger.info("🏭 Generating sample manufacturing data...")
        
        try:
            summary = self.sample_data_generator.generate_all_sample_data()
            logger.info(f"✅ Sample data generated successfully: {summary}")
            return summary
        except Exception as e:
            logger.error(f"❌ Sample data generation failed: {e}")
            return None
    
    async def run_full_setup(self, manual_path: str = "manual.txt"):
        """Run the complete system setup process."""
        logger.info("🚀 Starting full system setup...")
        
        try:
            # Initialize components (includes collection setup and index creation)
            if not await self.initialize_components():
                return False
            
            # Process manual documents
            await self.process_manual_documents(manual_path)
            
            # Generate sample data
            sample_data_summary = await self.generate_sample_data()
            
            if sample_data_summary:
                logger.info("🎉 Full system setup completed successfully!")
                logger.info(f"Generated data summary: {sample_data_summary}")
                return True
            else:
                logger.error("❌ Sample data generation failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Full system setup failed: {e}")
            return False
        finally:
            # Cleanup
            if self.couchbase_client:
                self.couchbase_client.close()
    
    def cleanup(self):
        """Clean up resources."""
        if self.couchbase_client:
            self.couchbase_client.close()

async def main():
    """Main setup function."""
    print(f"""
    🔧 CPG Manufacturing AI Assistant - System Setup
    ===============================================
    
    This script will:
    1. Initialize Couchbase database and create indexes
    2. Process manual documents (if available)
    3. Generate sample manufacturing data
    
    Prerequisites:
    • Couchbase Server running and accessible
    • Valid configuration in config.py
    • Optional: manual.txt file for document processing
    
    """)
    
    setup = SystemSetup()
    
    try:
        success = await setup.run_full_setup()
        
        if success:
            print(f"""
            ✅ System setup completed successfully!
            
            Next steps:
            1. Run the main application: python main.py
            2. Or start the web interface: streamlit run streamlit_app.py
            
            The system is now ready for use!
            """)
        else:
            print(f"""
            ❌ System setup failed!
            
            Please check:
            1. Couchbase Server is running
            2. Configuration in config.py is correct
            3. Network connectivity to Couchbase
            """)
    
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        print("\n🛑 Setup interrupted by user")
    except Exception as e:
        logger.error(f"Setup failed with unexpected error: {e}")
        print(f"\n❌ Setup failed: {e}")
    finally:
        setup.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 
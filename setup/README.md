# Setup Module

This folder contains the setup and initialization components for the CPG Manufacturing AI Assistant.

## Components

### 🔧 setup_system.py
Main setup script that handles:
- Database initialization and index creation
- Document processing (manual PDFs)
- Sample data generation
- System validation

### 📚 document_processor.py
Handles PDF document processing:
- Text extraction from manual PDFs
- Text chunking for RAG
- OpenAI embedding generation (text-embedding-3-small)
- Storage in Couchbase vector store

### 🏭 sample_data_generator.py
Generates sample manufacturing data:
- Production lines and machines
- Alerts and maintenance records
- Production metrics
- Operator and technician data

## Usage

### 1. First-time Setup
Run the complete system setup:
```bash
python setup/setup_system.py
```

This will:
- Initialize Couchbase database
- Create necessary indexes
- Process manual documents (if available) using OpenAI embeddings
- Generate sample manufacturing data

### 2. Individual Components

#### Database Setup Only
```python
from setup.setup_system import SystemSetup

setup = SystemSetup()
await setup.initialize_components()
await setup.setup_database_indexes()
```

#### Document Processing Only
```python
from setup.document_processor import DocumentProcessor
from setup.couchbase_client import CouchbaseClient

couchbase_client = CouchbaseClient()
processor = DocumentProcessor(couchbase_client)
processor.process_manual("path/to/manual.pdf")
```

#### Sample Data Generation Only
```python
from setup.sample_data_generator import SampleDataGenerator
from setup.couchbase_client import CouchbaseClient

couchbase_client = CouchbaseClient()
generator = SampleDataGenerator(couchbase_client)
summary = generator.generate_all_sample_data()
```

## Prerequisites

1. **Couchbase Server** running and accessible
2. **OpenAI API Key** configured in `config.py` or environment
3. **Configuration** properly set in `config.py`
4. **Dependencies** installed: `pip install -r requirements.txt`
5. **Optional**: `manual.pdf` file for document processing

## File Structure

```
setup/
├── __init__.py                 # Setup module initialization
├── README.md                   # This documentation
├── setup_system.py            # Main setup script
├── document_processor.py      # PDF processing and RAG setup (OpenAI embeddings)
└── sample_data_generator.py   # Sample data creation
```

## After Setup

Once setup is complete, run the main application:

```bash
# Interactive demo
python main.py

# Web interface (if available)
streamlit run streamlit_app.py
```

## Troubleshooting

### Common Issues

1. **OpenAI API Key Missing**
   - Set `OPENAI_API_KEY` environment variable
   - Or configure in `config.py`
   - Ensure API key has sufficient credits

2. **Couchbase Connection Failed**
   - Ensure Couchbase Server is running
   - Check connection settings in `config.py`
   - Verify network connectivity

3. **Manual Processing Failed**
   - Check if `manual.pdf` exists
   - Verify PDF is not corrupted
   - Ensure sufficient disk space
   - Check OpenAI API rate limits

4. **Dependency Issues**
   - Update packages: `pip install --upgrade -r requirements.txt`
   - Check Python version compatibility
   - Resolve any version conflicts

### Logs

Setup processes are logged with detailed information. Check console output for:
- ✅ Success indicators
- ⚠️ Warning messages  
- ❌ Error messages with details

For debugging, enable DEBUG logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### OpenAI Embeddings

The system uses OpenAI's `text-embedding-3-small` model for generating embeddings:
- High quality semantic search capabilities
- 1536-dimensional embeddings
- Cost-effective for document processing
- Better performance than open-source alternatives 
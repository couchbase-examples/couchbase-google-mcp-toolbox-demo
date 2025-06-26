# Multi-Collection Structure for CPG Manufacturing AI Assistant

## Overview

The system now uses multiple Couchbase collections to organize different types of manufacturing data. This provides better data organization, improved query performance, and cleaner separation of concerns.

## Collection Structure

### Scope: `manufacturing` (configurable via `COUCHBASE_SCOPE_NAME`)

#### Collections:

1. **`manuals`** - Stores processed manual chunks and documentation
   - Document types: `manual_chunk`
   - Used for: RAG-based troubleshooting and manual searches
   - Indexed on: content, machine_type, chunk_id

2. **`production`** - Stores production lines and machine data
   - Document types: `production_line`, `machine`
   - Used for: Production monitoring and machine management
   - Indexed on: machine_id, production_line_id, machine_status

3. **`alerts`** - Stores all alert and alarm data
   - Document types: `alert`
   - Used for: Alert monitoring and troubleshooting
   - Indexed on: severity, status, machine_id, timestamp

4. **`maintenance`** - Stores maintenance records and history
   - Document types: `maintenance_record`
   - Used for: Maintenance planning and history tracking
   - Indexed on: machine_id, status, scheduled_date

5. **`metrics`** - Stores production metrics and KPIs
   - Document types: `production_metrics`
   - Used for: Performance analysis and reporting
   - Indexed on: line_id, timestamp

6. **`solutions`** - Stores optimized manufacturing solutions and knowledge base
   - Document types: `solution`
   - Used for: AI-powered solution retrieval and knowledge management
   - Indexed on: error_code, type
   - Vector indexed on: solution_comment (for semantic similarity search)

## AI-Powered Solution Optimization

The system includes an intelligent solution optimization process that automatically:

1. **Extracts Solutions**: Processes alert data to extract solution comments
2. **Vector Similarity Search**: Uses semantic embeddings to find similar solutions filtered by error code
3. **Smart Deduplication**: Applies intelligent decision-making:
   - Score > 0.95 → Duplicate detected, ignores redundant solutions
   - Score 0.8-0.95 → Uses LLM to determine if solutions should be merged or one is a subset
   - Score < 0.8 → Inserts as new solution if not a subset of existing solutions
4. **Solution Merging**: Combines complementary solutions without duplication using LLM evaluation

This creates an optimized, non-redundant knowledge base of manufacturing solutions accessible through vector similarity search.

## Configuration

Set the following environment variables to customize collection names:

```bash
# Scope
COUCHBASE_SCOPE_NAME=manufacturing

# Collections
COUCHBASE_COLLECTION_MANUALS=manuals
COUCHBASE_COLLECTION_PRODUCTION=production
COUCHBASE_COLLECTION_ALERTS=alerts
COUCHBASE_COLLECTION_MAINTENANCE=maintenance
COUCHBASE_COLLECTION_METRICS=metrics
COUCHBASE_COLLECTION_SOLUTIONS=solutions
```

## Automatic Creation

The system will automatically:
1. Create the scope if it doesn't exist
2. Create all required collections if they don't exist
3. Create appropriate indexes for each collection
4. Create vector search indexes for semantic search (manuals and solutions)
5. Run AI-powered solution optimization during setup

## Benefits

- **Better Organization**: Each data type has its own collection
- **Improved Performance**: Targeted indexes per collection type
- **Intelligent Knowledge Management**: AI-powered solution optimization prevents redundancy
- **Semantic Search**: Vector embeddings enable natural language solution retrieval
- **Easier Maintenance**: Clear separation of data types
- **Scalability**: Collections can be individually managed and scaled
- **Security**: Fine-grained access control per collection type 
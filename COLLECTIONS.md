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
```

## Automatic Creation

The system will automatically:
1. Create the scope if it doesn't exist
2. Create all required collections if they don't exist
3. Create appropriate indexes for each collection
4. Fall back to default scope/collection if creation fails

## Benefits

- **Better Organization**: Each data type has its own collection
- **Improved Performance**: Targeted indexes per collection type
- **Easier Maintenance**: Clear separation of data types
- **Scalability**: Collections can be individually managed and scaled
- **Security**: Fine-grained access control per collection type 
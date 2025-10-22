# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference

  **Default Response Language**: Chinese (Simplified)
  - All responses, explanations, and documentation
  should be in Chinese
  - Thinking process can remain in English
  - Code comments and variable names should follow
  standard English conventions
  - Git commits should be in Chinese

## Project Overview

This is a multimodal RAG (Retrieval-Augmented Generation) API service built with FastAPI, combining RAG-Anything and LightRAG for document processing and intelligent querying.

**Key Architecture**: Single LightRAG + Multiple Parsers
- **Shared LightRAG instance**: Core knowledge graph shared by all parsers
- **MinerU parser**: Powerful multimodal parsing (OCR, tables, equations) with high memory usage
- **Docling parser**: Lightweight fast parsing for simple documents
- **Direct LightRAG query**: Bypasses parsers for 95% of text queries, optimizing performance

## Development Commands

### Local Development
```bash
# Install dependencies
uv sync

# Start development server with hot reload
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Test API endpoints
uv run python scripts/test_api.py
```

### Docker Deployment
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop services
docker compose down
```

### Testing & Monitoring
```bash
# Monitor service health
./scripts/monitor.sh

# Backup data
./scripts/backup.sh

# Update deployment
./scripts/update.sh

# Performance monitoring
./scripts/monitor_performance.sh

# Concurrent performance test
./scripts/test_concurrent_perf.sh
```

## Remote Deployment

### Production Server
- **Host**: 45.78.223.205
- **SSH Access**: `ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205`
- **Deployment Method**: Git-based deployment via GitHub

### Deployment Workflow

**Three-Way Sync Architecture**:
```
Local Machine ──git push──> GitHub ──git pull──> Remote Server (45.78.223.205)
```

All code changes must be pushed to GitHub first to ensure synchronization across all three endpoints:
1. Local development machine
2. GitHub repository (central source of truth)
3. Production server

### Deploying Code to Production

```bash
# 1. From local machine: Commit and push changes to GitHub
git add .
git commit -m "feat: 描述你的更改"
git push origin feature/your-branch  # or main

# 2. SSH into production server
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205

# 3. On production server: Pull latest changes
cd /path/to/rag-api  # Navigate to project directory
git pull origin main  # or your target branch

# 4. Restart services (if needed)
docker compose down
docker compose up -d
```

### Quick Deployment Commands

```bash
# Deploy from local to production (requires SSH key setup)
git push && ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205 "cd /path/to/rag-api && git pull && docker compose restart"
```

**Important Notes**:
- Always push to GitHub before deploying to production
- Never commit directly on the production server
- Use feature branches for development and merge to main after review
- The SSH key `/Users/chengjie/Downloads/chengjie.pem` should have proper permissions (`chmod 600`)

## Configuration

Environment variables are managed through `.env` (copy from `env.example`):

### Required Configuration
- **ARK_API_KEY / ARK_BASE_URL / ARK_MODEL**: LLM for text generation and entity extraction
- **SF_API_KEY / SF_BASE_URL / SF_EMBEDDING_MODEL**: Embedding service (4096-dim vectors)
- **RERANK_MODEL**: Optional reranker model to improve retrieval relevance

### MinerU Modes
- **local**: Runs MinerU locally (requires GPU, high memory)
- **remote**: Uses remote MinerU API (recommended, saves resources)
  - Requires **MINERU_API_TOKEN** and **FILE_SERVICE_BASE_URL**
  - Model version: `pipeline` (stable) or `vlm` (faster, more accurate, recommended)

### Performance Tuning
- **TOP_K**: Number of entities/relations to retrieve (default: 20, was 60)
- **CHUNK_TOP_K**: Number of text chunks to retrieve (default: 10, was 20)
- **MAX_ASYNC**: LLM concurrent requests (default: 8, optimized from 4)
- **DOCUMENT_PROCESSING_CONCURRENCY**: Concurrent document processing (1 for local, 10+ for remote)

## Architecture Notes

### Single LightRAG + Multiple Parsers Pattern

The system uses a **shared LightRAG instance** (`global_lightrag_instance` in `src/rag.py:26`) that all parsers write to:

1. **Document Insertion** (`/insert` endpoint in `api/insert.py`):
   - Routes through RAGAnything parsers (MinerU or Docling)
   - Parser selection: automatic based on file type/size, or manual
   - Text files (.txt, .md) bypass parsers and insert directly to LightRAG
   - Remote MinerU mode: uploads file to file service, calls remote API, processes markdown result

2. **Query** (`/query` endpoint in `api/query.py`):
   - **Directly accesses LightRAG** via `get_lightrag_instance()`
   - Bypasses all parsers for optimal query performance
   - Solves read/write concurrency conflicts
   - Query modes: `naive` (fastest, 15-20s), `local`, `global`, `hybrid`, `mix` (slowest, most comprehensive)

3. **Task Management** (`api/task.py`, `api/task_store.py`):
   - Async background processing with FastAPI BackgroundTasks
   - Task statuses: `pending`, `processing`, `completed`, `failed`
   - Shared in-memory `TASK_STORE` for status tracking
   - Semaphore-based concurrency control (`DOCUMENT_PROCESSING_SEMAPHORE`)

### File Service for Remote MinerU

When `MINERU_MODE=remote`, the system:
1. Uploads files to temporary HTTP-accessible storage (`src/file_url_service.py`)
2. Passes file URLs to remote MinerU API (`src/mineru_client.py`)
3. Polls for completion and processes markdown results (`src/mineru_result_processor.py`)
4. Auto-cleanup of temporary files after configurable retention period

### Parser Selection Logic

Implemented in `src/rag.py:select_parser_by_file()`:
- **Images (.jpg, .png)**: MinerU (OCR capability)
- **Text files (.txt, .md)**: Direct LightRAG insertion (no parser)
- **PDF/Office < 500KB**: Docling (fast)
- **PDF/Office > 500KB**: MinerU (powerful)

## API Routes

All routes are organized in `api/` directory and registered via `api/__init__.py`:

- **Document Processing**: `api/insert.py`
  - `POST /insert`: Single document upload (returns task_id)
  - `POST /batch`: Batch document upload (up to 100 files)
  - `GET /batch/{batch_id}`: Check batch progress

- **Query**: `api/query.py`
  - `POST /query`: Query the knowledge graph

- **Task Management**: `api/task.py`
  - `GET /task/{task_id}`: Get task status

- **File Service**: `api/files.py`
  - `GET /files/{file_id}/{filename}`: Download temporary files (for remote MinerU)

- **Performance Monitoring**: `api/monitor.py`
  - System metrics collection via `src/metrics.py`

## Important Implementation Details

### Lifespan Management
Application startup/shutdown logic in `src/rag.py:lifespan()`:
- Creates single shared LightRAG instance
- Initializes MinerU and Docling parsers (both share LightRAG)
- Starts file cleanup background task
- Starts performance monitoring
- Configures rerank function if `RERANK_MODEL` is set

### Logging
Unified logging via `src/logger.py` using loguru:
- Structured JSON logs for production
- Automatic log rotation based on `LOG_RETENTION_DAYS`
- Log level controlled by `LOG_LEVEL` env var

### Error Handling in Document Processing
`api/insert.py:process_document_task()` handles:
- **MineruExecutionError**: Unsupported file format
- **ValueError**: Empty files, validation errors
- **OSError**: File system errors
- Always cleans up temporary files in `finally` block

### Performance Optimizations Applied
1. Reduced `TOP_K` from 60 to 20 (fewer entities retrieved)
2. Reduced `CHUNK_TOP_K` from 20 to 10 (fewer text chunks)
3. Increased `MAX_ASYNC` from 4 to 8 (faster entity merging)
4. Enabled rerank for better relevance (adds 2-3s but improves quality)
5. Direct LightRAG query path (bypasses parser overhead)

## Cursor Rules

From `.cursor/rules/docs-rules.mdc`:
- All documentation files must be placed in `docs/` folder

## Common Pitfalls

1. **multimodal_processed errors**: Delete `./rag_local_storage` to clear corrupted state
2. **Remote MinerU failures**: Verify `FILE_SERVICE_BASE_URL` is set to public IP:8000, not localhost
3. **Memory issues with local MinerU**: Switch to `MINERU_MODE=remote` or reduce `DOCUMENT_PROCESSING_CONCURRENCY` to 1
4. **Slow queries (75s+)**: Increase `MAX_ASYNC` in `.env` or use `naive` query mode instead of `mix`
5. **Empty file uploads**: API returns 400 with detailed error message

## File Structure

```
rag-api/
├── main.py              # FastAPI app entry point
├── api/                 # API route modules
│   ├── __init__.py      # Router aggregation
│   ├── insert.py        # Document insertion endpoints
│   ├── query.py         # Query endpoints
│   ├── task.py          # Task status endpoints
│   ├── files.py         # File service endpoints
│   ├── monitor.py       # Performance monitoring endpoints
│   ├── models.py        # Pydantic models
│   └── task_store.py    # In-memory task tracking
├── src/                 # Core business logic
│   ├── rag.py           # LightRAG lifecycle and parser management
│   ├── logger.py        # Unified logging
│   ├── metrics.py       # Performance metrics collection
│   ├── file_url_service.py        # Temporary file HTTP service
│   ├── mineru_client.py           # Remote MinerU API client
│   └── mineru_result_processor.py # MinerU result processor
├── scripts/             # Maintenance and test scripts
├── docs/                # Documentation (per Cursor rules)
└── rag_local_storage/   # LightRAG working directory (git-ignored)
```

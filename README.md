# Clinical Evidence Agent - Medical Search System

**Deployment**: https://clinical-evidence-backend-73460068271.asia-northeast1.run.app

## Overview

An intelligent medical evidence retrieval system combining:
- **Qdrant Cloud**: Semantic search across structured medical papers (cloud-hosted vector database)
- **Embedding APIs**: OpenRouter (E5) + Hugging Face Dedicated Endpoint (SapBERT) for runtime query embeddings
- **MedGemma**: Direct LLM queries and RAG-enhanced synthesis via Hugging Face Endpoint
- **Multi-Stage Retrieval**: Paper-level search + atomic fact retrieval

**Deployment Architecture**: Fully cloud-based single service on Google Cloud Run (no separate frontend) + managed APIs (no local dependencies)

---

## 🏗️ Cloud Architecture (Production)

### Runtime Environment (100% Cloud-Based)
```
[Client Browser]
    ↓
[Google Cloud Run: Flask Backend] ← Single unified service (Hackathon requirement met)
  ├─ Memory: 256MiB (lightweight, no model loading)
  ├─ Role: Frontend HTML delivery + Backend API orchestration
  ├─ GET  / → index.html (static frontend)
  ├─ GET  /api/status → Health check
  ├─ POST /api/query → Main API (streaming)
  │
  ├─→ [OpenRouter API] 
  │     └─ Model: intfloat/multilingual-e5-large (1024-dim)
  │     └─ Purpose: Query embedding generation for paper search
  │
  ├─→ [Hugging Face Dedicated Endpoint]
  │     └─ Model: cambridgeltl/SapBERT-from-PubMedBERT-fulltext (768-dim)
  │     └─ Purpose: Query embedding generation for atomic fact search
  │
  ├─→ [Qdrant Cloud]
  │     └─ Collections: medical_papers (3 vectors), atomic_facts (1 vector)
  │     └─ Region: us-east4-0 (GCP)
  │
  └─→ [Hugging Face Endpoint: MedGemma 7b]
        └─ Purpose: Medical inference with streaming support
```

### Data Preparation Phase (One-Time, Local Mac)
```
[Local Mac]
  ├─ scripts/structure_paper.py → 5-layer JSON structuring
  ├─ scripts/generate_embeddings.py → Create embeddings offline
  └─→ Upload to [Qdrant Cloud] (one-time data preparation)
```

**Key Design Decisions**:
- ✅ **Cloud Run**: Meets hackathon requirement (Google Cloud Platform)
- ✅ **Single Service**: Simplified deployment (frontend + backend unified)
- ✅ **Zero Local Dependencies**: Runtime completely independent of local Mac
- ✅ **Managed APIs**: No infrastructure management, auto-scaling, pay-per-use
- ✅ **Cost Optimization**: ~$24-30/month (HF Dedicated Endpoint + API usage)

---

## System Architecture (Query Flow)

```
User Query (EN)
    ↓
[1] Query Embedding Generation
    ├─ OpenRouter API: multilingual-e5-large (1024-dim)
    └─ HF Dedicated Endpoint: SapBERT (768-dim)
    ↓
[2] Qdrant Cloud Semantic Search
    ├── Stage 1: Vector Similarity (top 30 candidates via scroll API)
    └── Stage 2: Keyword Reranking (medical term bonus scores)
    ↓
[3] Top 3 Papers + Atomic Facts Retrieval
    ↓
[4] Map-Reduce Analysis (MedGemma 7b via HF Endpoint)
    ├── Phase 1 (Map): Analyze each paper individually
    │   ├── Extract drug name and numerical outcomes
    │   └── Filter irrelevant papers
    └── Phase 2 (Reduce): Synthesize findings
        └── Generate comprehensive English answer
    ↓
Comprehensive Medical Answer (streamed via SSE)
```

**Performance Metrics**:
- Query embedding generation: ~100-300ms (API calls)
- Vector search (Qdrant Cloud): ~50-100ms
- MedGemma inference: ~1000-2000ms (streaming)
- **Total response time**: ~2-3 seconds

---

## Component Descriptions

### 1. Qdrant Cloud Vector Database
- **Deployment**: Cloud-hosted (us-east4-0, GCP region)
- **Collections**: `medical_papers` (3 vectors/doc), `atomic_facts` (1 vector/doc)
- **Vectors**: 
  - Papers: `sapbert_pico` (768-dim), `e5_pico` (1024-dim), `e5_questions_en` (1024-dim)
  - Facts: `sapbert_fact` (768-dim)
- **Data Size**: All structured papers + atomic facts from obesity domain
- **Access**: REST API via `QDRANT_CLOUD_ENDPOINT` + API key

### 2. Search Pipeline (scripts/search_qdrant.py)
- **Embedding Generation**: 
  - OpenRouter API (E5): Paper-level search via `e5_pico` or `e5_questions_en`
  - HF Dedicated Endpoint (SapBERT): Atomic fact search via `sapbert_fact`
- **Search Strategy**: 
  - Stage 1: Cosine similarity on all documents (scroll API, limit 10,000)
  - Stage 2: Keyword-based reranking with medical term importance weights
- **Language**: English only
- **Performance**: ~2.5 seconds total (including API calls)

### 3. MedGemma Query Module (scripts/medgemma_query.py)
- **Deployment**: Hugging Face Endpoint (TGI-compatible)
- **Modes**: Direct query, RAG-enhanced synthesis, Compare mode
- **Integration**: REST API with streaming support (Server-Sent Events)
- **Context Window**: Relevant papers + atomic facts from Qdrant search

### 4. Cloud Run Frontend (app.py)
- **Role**: Unified service (frontend HTML delivery + API orchestration with SSE streaming to client)
- **Endpoints**:
  - `GET /` - Serve index.html (frontend UI)
  - `GET /api/status` - Health check (validates API connectivity)
  - `POST /api/query` - Query endpoint with streaming response
- **Memory**: 256MiB (no model loading, API client only)
- **Dependencies**: Flask, gunicorn, requests, qdrant-client, numpy (lightweight)

---

## Scripts

### Data Structuring Scripts

#### `scripts/structure_paper.py`
**Purpose**: Structure single paper using LLM into 5-layer JSON schema with 2-stage processing

**Input**: Subsection papers from `data/obesity/{domain}/{subsection}/papers.json` (with optional `full_text` field from `append_fulltext.py`)

**Output**: Structured JSON with:
- **Layer A**: Language-independent core (PICO_EN, atomic_facts_EN, limitations)
- **Layer B**: Multilingual interface (generated questions in EN only)
- **Layer C**: Cross references (empty for now)
- **Layer D**: Embeddings metadata (targets for models)
- **Layer E**: MeSH terminology (English synonyms only)

**Workflow (2-Stage Processing)**:
**Stage 1**: Generate metadata, PICO, questions (EN), MeSH, quantitative data, limitations
1. Extract sample size from abstract text
2. Extract full text if available (from `append_fulltext.py`)
3. Prepare prompt with all metadata (including full text if available)
4. Query OpenRouter API with retry logic (3 attempts, exponential backoff)
5. Parse LLM response (remove markdown, extract JSON)

**Stage 2**: Generate atomic facts based on Stage 1 questions
1. Extract questions (EN only) from Stage 1 result
2. Extract PICO from Stage 1 result
3. Generate atomic facts that answer the generated questions
4. Each fact must be self-contained with intervention name, condition, and PMID
5. Generate embeddings metadata

**Merge Stage 1 + Stage 2**:
- Combine Stage 1 results (metadata, PICO, questions, limitations, etc.)
- Add Stage 2 results (atomic_facts_en, embeddings_metadata)

**Usage**:
```bash
python3 scripts/structure_paper.py pharmacologic glp1_receptor_agonists PMID_37952131
python3 scripts/structure_paper.py surgical procedures_and_outcomes PMID_32711955
python3 scripts/structure_paper.py lifestyle dietary_interventions PMID_31705259
```

**Key Features**:
- Retry logic: Exponential backoff (2s, 4s, 8s, 16s)
- Error handling: Stop on LLM errors (per stage)
- JSON validation: Verify structure before saving
- Sample size detection: Extract from abstract text
- Full text support: Optionally uses full text from PMC (if available via `append_fulltext.py`)
- Timeout: 180 seconds per paper total (Stage 1 + Stage 2)
- 2-stage processing: Improves atomic facts quality by answering generated questions

**Files**: Saves to `data/obesity/{domain}/{subsection}/papers/PMID_{pmid}.json`

---

#### `scripts/batch_structure_papers.py`
**Purpose**: Process all papers in a domain (or all domains) with progress tracking

**Input**: Domain name (pharmacologic, surgical, lifestyle), optional subsection, and options

**Output**: Batch process with success/error tracking

**Workflow**:
1. Load papers from `data/obesity/{domain}/{subsection}/papers.json` for all subsections
2. Check for existing structured papers in each `papers/` subdirectory
3. Skip already structured papers (unless --force is used)
4. Call `structure_paper.py` for remaining papers
5. Print progress every 5 papers
6. Stop on errors (per plan)

**Usage**:
```bash
# Process all subsections in a domain (default: skip existing, process new papers only)
python3 scripts/batch_structure_papers.py pharmacologic
python3 scripts/batch_structure_papers.py surgical
python3 scripts/batch_structure_papers.py lifestyle

# Process all three domains at once
python3 scripts/batch_structure_papers.py --all-domains

# Process specific subsection
python3 scripts/batch_structure_papers.py pharmacologic glp1_receptor_agonists
python3 scripts/batch_structure_papers.py surgical procedures_and_outcomes
python3 scripts/batch_structure_papers.py lifestyle dietary_interventions

# Force restructure all papers (overwrite existing files)
python3 scripts/batch_structure_papers.py pharmacologic --force
python3 scripts/batch_structure_papers.py --all-domains --force

# Explicitly skip existing papers
python3 scripts/batch_structure_papers.py pharmacologic --skip-existing
```

**Options**:
- `--all-domains`, `-a`: Process all three domains (pharmacologic, surgical, lifestyle) at once
- `--force`, `-f`: Force restructure of already processed papers (overwrite existing files)
- `--skip-existing`, `-s`: Skip already structured papers (same as default behavior, makes it explicit)

**Key Features**:
- Multi-subsection support: Processes all subsections (e.g., glp1_receptor_agonists, guidelines_and_reviews, novel_agents)
- Multi-domain support: Process all domains with `--all-domains`
- Force restructure: `--force` option to overwrite existing structured files
- Resume capability: Skip already processed papers (default behavior)
- Progress reporting: Print progress every 5 papers
- Error handling: Stop on first error
- Batch processing: All papers across all subsections
- Time tracking: Elapsed time and processing rate

**Success**: 100% success rate across all 3 domains

---

#### `scripts/download_remaining_pharmacologic.py`
**Purpose**: Download missing pharmacologic papers from PubMed

**Input**: List of missing PMIDs (created from difference)

**Output**: `papers.json` files in each subcategory with downloaded papers

**Workflow**:
1. Read list of PMIDs from `missing_pharmacologic_pmids.txt`
2. Fetch paper details from PubMed E-utilities API
3. Parse XML response to extract metadata
4. Update existing papers in each subcategory's `papers.json`
5. Handle duplicates (merge with new fields)

**Usage**:
```bash
python3 scripts/download_remaining_pharmacologic.py pharmacologic
```

**Key Features**:
- Batch processing: Processes PMIDs in batches (default: 50 per batch)
- API rate limiting: Sleep 1 second between batches
- Duplicate handling: Merge new data with existing papers
- Metadata extraction: Title, abstract, authors, journal, year, MeSH terms

**Note**: This script was used to complete the pharmacologic domain to 100 papers

---

### Embedding Generation Scripts

#### `scripts/generate_embeddings.py`
**Purpose**: Generate embeddings for all structured papers and load into Qdrant

**Input**: All structured papers from `data/obesity/{domain}/{subsection}/papers/`

**Output**: Qdrant database with all embeddings

**Workflow**:
1. Check Qdrant for existing embeddings (deduplication)
2. Find all structured papers across all 3 domains and subsections
3. Filter out papers that already have embeddings
4. Load embedding models (SapBERT + multilingual-e5)
5. Process each paper:
    - Extract PICO, atomic facts, generated questions (EN only)
    - Generate 3 embedding types:
      - `sapbert_pico` (768-dim): PICO matching
      - `e5_pico` (1024-dim): Fallback vector
      - `e5_questions_en` (1024-dim): English questions only
      - `sapbert_fact` (768-dim): Atomic facts (per fact)
    - Upsert to Qdrant collections
6. Verify collections after completion
7. Stop on first error (fail-safe behavior)

**Models Used**:
- `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (768-dim)
- `intfloat/multilingual-e5-large` (1024-dim)

**Embeddings Generated** (per paper):
- Paper-level: 3 vectors per paper (sapbert_pico, e5_pico, e5_questions_en)
- Atomic facts: 1 vector per fact (sapbert_fact)

**Qdrant Collections**:
- `medical_papers`: Paper-level embeddings with 3 named vectors
- `atomic_facts`: Fact-level embeddings with 1 named vector
- Database location: `./qdrant_medical_db`

**Usage**:
```bash
# Generate embeddings to local database (default)
python3 scripts/generate_embeddings.py

# Generate embeddings to Qdrant Cloud
python3 scripts/generate_embeddings.py --cloud

# Check existing embeddings without generating (cloud mode)
python3 scripts/generate_embeddings.py --cloud --check
```

**Key Features**:
- Deduplication: Skips papers with existing embeddings
- Progress reporting: Progress every 10 papers
- Error handling: Stop on first error (fail-safe)
- Fixed UUID generation: Correct placement ensures all papers get UUID
- Qdrant path: `./qdrant_medical_db` for consistency
- 3 embedding types: Matches current architecture (English questions only)
- Verification: Check Qdrant collections after completion

**Note**: Merged version combining:
- Fixed UUID generation (from generate_embeddings_fixed.py)
- Deduplication logic (from generate_embeddings.py)
- Stop-on-error behavior for reliability
- English-only question support (removed Japanese questions embeddings)

---

#### `scripts/setup_qdrant.py`
**Purpose**: Initialize Qdrant collections with correct vector configuration

**Input**: None (initialization script)

**Output**: Qdrant database with empty collections

**Workflow**:
1. Initialize Qdrant client (in-memory mode)
2. Delete existing collections (if they exist)
3. Create `medical_papers` collection with 3 named vectors:
    - sapbert_pico: 768-dim, cosine distance
    - e5_pico: 1024-dim, cosine distance
    - e5_questions_en: 1024-dim, cosine distance
4. Create `atomic_facts` collection with 1 named vector:
    - sapbert_fact: 768-dim, cosine distance

**Usage**:
```bash
python3 scripts/setup_qdrant.py
```

**Key Features**:
- Named vectors: Full support for multi-model queries
- Collection deletion: Clean state before creation
- In-memory mode: Fast startup, no disk I/O for testing
- Verification: Print collection configuration after creation
- 3 paper-level vectors: Removed Japanese question embeddings (e5_questions_ja)

**Note**: This script was used during Phase 2 to set up the database

---

#### `scripts/setup_qdrant_cloud.py`
**Purpose**: Initialize Qdrant Cloud collections with correct vector configuration

**Input**: None (initialization script), requires `.env` with cloud credentials

**Output**: Qdrant Cloud database with empty collections

**Prerequisites**:
- `QDRANT_CLOUD_ENDPOINT` and `QDRANT_CLOUD_API_KEY` in `.env` file
- Active Qdrant Cloud cluster

**Workflow**:
1. Load credentials from `.env` file
2. Connect to Qdrant Cloud
3. Delete existing collections (if they exist)
4. Create `medical_papers` collection with 3 named vectors:
    - sapbert_pico: 768-dim, cosine distance
    - e5_pico: 1024-dim, cosine distance
    - e5_questions_en: 1024-dim, cosine distance
5. Create `atomic_facts` collection with 1 named vector:
    - sapbert_fact: 768-dim, cosine distance
6. Verify collections after creation

**Usage**:
```bash
# Initialize with confirmation prompt
python3 scripts/setup_qdrant_cloud.py

# Force initialization without confirmation
python3 scripts/setup_qdrant_cloud.py --force
```

**Key Features**:
- Cloud support: Works with Qdrant Cloud managed service
- Safety confirmation: Prompts before deleting data (unless --force)
- Verification: Checks collections after creation
- Error handling: Validates credentials before connecting

**Note**: Use this script before running `generate_embeddings.py --cloud`

---

### Search Pipeline Scripts

#### `scripts/search_qdrant.py`
**Purpose**: Qdrant semantic search with real embedding models (mock mode removed)

**Input**: User query (English)

**Output**: Top papers ranked by vector similarity

**Workflow**:
1. Initialize Qdrant client (file-based persistence)
2. Load embedding models (SapBERT + multilingual-e5)
3. Generate query embedding:
    - English: Use `e5_questions_en` vector (1024-dim)
    - Format: `'query: <user query>'`
4. **Stage 1: Vector Similarity**
    - Fetch all points from `medical_papers` collection (up to 10K)
    - Extract vectors with priority order:
      - Priority 1: `e5_pico` (1024-dim) - PICO combined for broader semantic matching
      - Priority 2: `e5_questions_en` (1024-dim) - Generated questions for specific queries
      - Priority 3: `sapbert_pico` (768-dim) - Fallback for compatibility
    - Calculate cosine similarity
    - Select top 30 candidates
5. **Stage 2: Keyword-Based Reranking**
    - Extract medical keywords from query (English)
    - Calculate bonus scores based on keyword importance:
      - High importance (+0.05): osteoarthritis, knee, joint, etc.
      - Medium importance (+0.03): cardiovascular, diabetes, obesity, etc.
      - Low importance (+0.01): glp1, semaglutide, treatment, etc.
    - Add bonus to base similarity score (max bonus: 0.15)
    - Re-sort by final score
6. Return top K papers with full metadata

**Models Used**:
- `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (768-dim)
- `intfloat/multilingual-e5-large` (1024-dim)
- `sklearn.metrics.pairwise.cosine_similarity`: Vector similarity calculation

**Search Results**:
- Top K papers with PICO and metadata
- Cosine similarity scores
- Full paper information including title, journal, year, authors

**Performance**:
- Total search time: ~400ms for full query
- Response: Top 5 papers in <500ms
- Database: Structured medical papers across all domains

**Usage**:
```bash
# Auto-detect mode (uses local if exists, cloud if not)
python3 scripts/search_qdrant.py "Does semaglutide reduce weight in obesity?"

# Force cloud mode even when local database exists
python3 scripts/search_qdrant.py --cloud "Does semaglutide reduce weight in obesity?"

# Specify number of results
python3 scripts/search_qdrant.py --cloud --top_k 10 "semaglutide side effects"
```

**Key Features**:
- Real models: Uses actual Qdrant embeddings (not mock data)
- English-only support: English queries and embeddings
- **2-stage reranking**: Vector similarity (Stage 1) + keyword bonus (Stage 2)
- Fast retrieval: Top 30 candidates → Rerank → Top K results
- Comprehensive metadata: Full PICO, title, journal, year, authors

**Note**: This is the final search pipeline with real Qdrant models, optimized for English-only queries

---

### Data Collection Scripts

#### `scripts/fetch_paper_details.py`
**Purpose**: Download obesity treatment papers from PubMed for each domain and subsection

**Input**: Domain(s) and optional max results per subsection

**Output**: `papers.json` files in each subcategory with downloaded papers

**Workflow**:
1. Define search queries for each domain and subsection
2. Execute PubMed search (ESearch) for each subsection
3. Fetch paper details from PubMed E-utilities (EFetch)
4. LLM filtering for quality assessment
5. Check for existing papers and merge (avoid duplicates)
6. Save to `data/obesity/{domain}/{subsection}/papers.json`

**Usage**:
```bash
# Process pharmacologic domain
python3 scripts/fetch_paper_details.py pharmacologic

# Process lifestyle and surgical with 20 papers each
python3 scripts/fetch_paper_details.py lifestyle surgical --max-results 20

# Process all domains with default settings
python3 scripts/fetch_paper_details.py
```

**Key Features**:
- Multi-domain support: lifestyle, pharmacologic, surgical
- Subcategory organization: glp1_receptor_agonists, guidelines_and_reviews, novel_agents, etc.
- Duplicate detection: Merges with existing data, adds only new papers
- LLM filtering: Uses Gemini 2.5 Flash Lite for quality assessment
- API rate limiting: Sleep 1 second between requests

**Note**: This is the main script for initial data collection from PubMed

---

#### `scripts/append_fulltext.py`
**Purpose**: Retrieve full text content from PubMed and append to existing paper metadata

**Input**: Domain and optional subsection

**Output**: Updated `papers.json` files with fulltext field added

**Usage**:
```bash
# Add full text to all pharmacologic papers
python3 scripts/append_fulltext.py pharmacologic

# Add full text to specific subsection
python3 scripts/append_fulltext.py pharmacologic glp1_receptor_agonists
```

**Note**: Full text is optional but recommended for better PICO extraction and atomic fact generation. Papers with full text will provide more comprehensive structured data for LLM.

**Integration**: Full text from this script is automatically used by `structure_paper.py` and `batch_structure_papers.py` if available in `papers.json` files.

**Key Features**:
- Batch retrieval: Processes multiple papers efficiently
- Error handling: Continues on individual failures
- Metadata preservation: Keeps existing paper information intact
- Progress tracking: Shows number of papers processed

---

### MedGemma Query Scripts

#### `scripts/medgemma_query.py`
**Purpose**: Direct and RAG-enhanced MedGemma queries via Ollama

**Input**: User query (English), mode (direct | rag | compare)

**Output**: MedGemma response with full context

**Workflow**:

**Direct Mode**:
1. Accept user query (English)
2. Create prompt:
   - English: "Question: {query}\n\nProvide a comprehensive answer..."
3. Query MedGemma via Ollama API
4. Parse response and return

**RAG Mode** (`run_map_reduce_query()`):
1. Search papers via `search_qdrant.search_medical_papers(query, top_k=3)`
2. Search atomic facts via `search_qdrant.search_atomic_facts(query, limit=10, paper_ids=...)`
3. **Map Phase**: Analyze each paper individually with `analyze_single_paper()`
    - Extract drug name and numerical outcomes
    - Filter irrelevant papers
4. **Reduce Phase**: Synthesize findings with `synthesize_findings()`
    - Generate comprehensive English answer
5. Return final answer

**Models**:
- Direct query: 2048 tokens (temperature: 0.3)
- RAG query: 4096 tokens (temperature: 0.3)

**Ollama Integration**:
- URL: `http://localhost:11434/api` (configurable via OLLAMA_URL env var)
- Model: `medgemma:7b` (configurable)
- Timeout: 60 seconds
- Stream: False (wait for full response)

**Usage**:
```bash
# Direct query (default, no retrieval)
python3 scripts/medgemma_query.py "Does semaglutide reduce weight in obesity?"
python3 scripts/medgemma_query.py "Does semaglutide reduce weight in obesity?" --mode direct

# RAG-enhanced query (Qdrant search → MedGemma generation, Map-Reduce)
python3 scripts/medgemma_query.py "Does semaglutide reduce weight in obesity?" --mode rag

# Compare mode (RAG side-by-side vs Direct)
python3 scripts/medgemma_query.py "What are the benefits of GLP-1 agonists?" --mode compare

# Use Qdrant Cloud (force cloud mode even when local exists)
python3 scripts/medgemma_query.py "Does semaglutide reduce weight in obesity?" --cloud --mode rag

# Verbose output with cloud
python3 scripts/medgemma_query.py "What are the side effects of semaglutide?" --cloud --verbose

# Use Hugging Face Inference API instead of local Ollama
python3 scripts/medgemma_query.py "What is semaglutide?" --mode direct --HF

# Combine cloud and HF options
python3 scripts/medgemma_query.py "semaglutideの効果は？" --cloud --HF --mode rag --verbose
```

**Key Features**:
- English-only support: English queries and responses
- RAG context: Relevant papers + atomic facts from Qdrant
- Map-Reduce architecture: Efficient analysis of multiple papers
- Error handling: Timeout and API error handling

**Note**: This script provides both direct and RAG-enhanced MedGemma queries with Map-Reduce architecture for English queries.

---

### Integration Scripts

#### `scripts/integrate_system.py`
**Purpose**: End-to-end integration of Qdrant search + MedGemma synthesis

**Input**: User query (English)

**Output**: Complete medical evidence answer with citations

**Workflow**:
1. **Phase 1**: Qdrant Search
    - Generate query embedding (e5_questions_en)
    - Search medical_papers collection
    - Calculate cosine similarity
    - Rank by similarity (top 5 papers)
    - Retrieve full metadata and PICO
2. **Phase 2**: Atomic Fact Retrieval
    - Generate SapBERT query embedding
    - Search atomic_facts collection
    - Calculate cosine similarity
    - Rank by similarity (top 5 facts)
3. **Phase 3**: MedGemma RAG Synthesis
    - Create RAG context (papers + atomic facts)
    - Create RAG prompt with context
    - Query MedGemma (4096 tokens, temperature: 0.3)
    - Parse response and format
4. **Phase 4**: Results Formatting
    - Format results in JSON
    - Include search strategy, timing, and notes

**Modes**:
- `search_only`: Qdrant search only (no MedGemma)
- `direct`: MedGemma direct query only (no search)
- `rag`: Full RAG synthesis (Qdrant + MedGemma)

**Features**:
- English-only support: English queries, embeddings, and responses
- Multi-stage retrieval: Papers + atomic facts for comprehensive answers
- Vector similarity ranking: Cosine similarity for relevant results
- RAG context: Dynamic context generation based on search results
- Comprehensive answers: Evidence-based with citations
- Performance metrics: Search time, MedGemma time, response length

**Usage**:
```bash
# Full RAG synthesis
python3 scripts/integrate_system.py "Does semaglutide reduce weight in obesity?"

# Search only mode (no MedGemma)
python3 scripts/integrate_system.py "Does semaglutide reduce weight in obesity?" search_only

# Direct query mode (no Qdrant search)
python3 scripts/integrate_system.py "Does semaglutide reduce weight in obesity?" direct
```

**Key Features**:
- Complete end-to-end workflow: Qdrant search + MedGemma synthesis
- English-only support: English queries, embeddings, and responses
- Multi-stage retrieval: Papers + atomic facts for comprehensive answers
- Evidence-based: RAG-enhanced MedGemma queries with citations
- Performance tracking: Search time, MedGemma time, response length
- Error handling: Qdrant errors, MedGemma errors, timeout handling

**Note**: This is the final integration script completing all 4 phases of the project for English-only queries

---

### Validation Scripts

#### `scripts/validate_structure.py`
**Purpose**: Validate structured papers JSON format

**Usage**:
```bash
python3 scripts/validate_structure.py data/obesity/pharmacologic/papers/PMID_32139381.json
```

---

#### `scripts/verify_embeddings.py`
**Purpose**: Verify Qdrant database state and embedding correctness

**Usage**:
```bash
python3 scripts/verify_embeddings.py
```

---

## Data Directory Structure

```
data/obesity/
├── pharmacologic/
│   ├── glp1_receptor_agonists/
│   │   ├── papers.json                    # Simple format (pmid, title, abstract, journal, year)
│   │   └── papers/                         # 5-layer structured JSON files
│   │       ├── PMID_37952131.json      # PICO + atomic facts + embeddings metadata
│   │       ├── PMID_33567185.json
│   │       └── ...
│   ├── guidelines_and_reviews/
│   │   ├── papers.json
│   │   └── papers/                         # 5-layer structured files
│   │       └── PMID_38629387.json
│   └── novel_agents/
│       ├── papers.json
│       └── papers/                         # 5-layer structured files
│           └── PMID_35658024.json
├── lifestyle/
│   ├── dietary_interventions/
│   │   ├── papers.json
│   │   └── papers/                         # 5-layer structured files
│   ├── physical_activity/
│   │   ├── papers.json
│   │   └── papers/
│   └── behavioral_therapy/
│       ├── papers.json
│       └── papers/
├── surgical/
│   ├── procedures_and_outcomes/
│   │   ├── papers.json
│   │   └── papers/                         # 5-layer structured files
│   ├── metabolic_effects/
│   │   ├── papers.json
│   │   └── papers/
│   └── complications_safety/
│       ├── papers.json
│       └── papers/
```

**Two file formats**:
- `papers.json`: Simple format for raw downloaded papers (pmid, title, abstract, journal, year)
- `papers/PMID_XXX.json`: 5-layer structured format with PICO, atomic facts, questions (EN), limitations

```

clinical-evidence-agent/
├── data/
│   └── obesity/
│       ├── pharmacologic/
│       │   ├── glp1_receptor_agonists/
│       │   │   ├── papers.json                    # Simple format (pmid, title, abstract, journal, year)
│       │   │   └── papers/                         # 5-layer structured JSON files
│       │   │       ├── PMID_37952131.json      # PICO + atomic facts + embeddings metadata
│       │   │       ├── PMID_33567185.json
│       │   │       └── ...
│       │   ├── guidelines_and_reviews/
│       │   │   ├── papers.json
│       │   │   └── papers/                         # 5-layer structured files
│       │   │       └── PMID_38629387.json
│       │   └── novel_agents/
│       │       ├── papers.json
│       │       └── papers/                         # 5-layer structured files
│       │           └── PMID_35658024.json
│       ├── lifestyle/
│       │   ├── dietary_interventions/
│       │   │   ├── papers.json
│       │   │   └── papers/                         # 5-layer structured files
│       │   ├── physical_activity/
│       │   │   ├── papers.json
│       │   │   └── papers/
│       │   └── behavioral_therapy/
│       │       ├── papers.json
│       │       └── papers/
│       ├── surgical/
│       │   ├── procedures_and_outcomes/
│       │   │   ├── papers.json
│       │   │   └── papers/                         # 5-layer structured files
│       │   ├── metabolic_effects/
│       │   │   ├── papers.json
│       │   │   └── papers/
│       │   └── complications_safety/
│       │       ├── papers.json
│       │       └── papers/
├── qdrant_medical_db/              (Qdrant local database)
│   ├── collection/
│   │   ├── medical_papers/       (3 named vectors each)
│   │   └── atomic_facts/         (1 named vector each)
│   └── ...                           (Qdrant storage files)
├── scripts/
│   ├── fetch_paper_details.py        (PubMed download - main script)
│   ├── append_fulltext.py            (Full text retrieval)
│   ├── structure_paper.py          (Single paper structuring - 2-stage processing)
│   ├── batch_structure_papers.py  (Batch processing)
│   ├── generate_embeddings.py              (Embedding generation - 3 vectors per paper)
│   ├── setup_qdrant.py             (Qdrant initialization)
│   ├── search_qdrant.py             (Qdrant search - English only)
│   ├── medgemma_query.py          (MedGemma queries - English only)
│   ├── integrate_system.py          (Full integration - English only)
│   ├── validate_structure.py        (Validation)
│   └── verify_embeddings.py         (Verification)
│   └── README.md                     (This file)
└── plans/
    └── two_stage_atomic.md              (2-stage processing plan)
```

---

## System Workflow

### 1. Data Collection
- **Script**: `fetch_paper_details.py`
- **Output**: `papers.json` files for each subcategory in each domain
- **Coverage**: Process all papers across all subsections
- **Metadata**: Title, abstract, authors, journal, year, MeSH terms

- **Optional Step**: `append_fulltext.py` (Recommended but optional)
  - **Purpose**: Retrieve full text content from PMC and append to existing papers
  - **Input**: Domain and optional subsection
  - **Output**: Updates `papers.json` files with `full_text` field added
  - **Benefit**: Full text provides more comprehensive data for better PICO extraction and atomic fact generation
  - **Usage**: `python3 scripts/append_fulltext.py pharmacologic`
  - **Note**: Not all papers have full text available (open access papers only)

### 2. Data Structuring (Phase 1) - 2-Stage Processing
- **Script**: `batch_structure_papers.py` (after optional `append_fulltext.py`)
- **Input**: `papers.json` files from all subsections in each domain (with optional `full_text` field)

**2-Stage Architecture**:
**Stage 1**: Generate metadata, PICO, generated questions (EN), MeSH terminology, quantitative data, limitations, and cross references
- Uses `STAGE1_PROMPT` in structure_paper.py
- Generates structured JSON without atomic_facts_en and embeddings_metadata
- API calls: 1 per paper with max_tokens=16384

**Stage 2**: Generate atomic facts (EN) and embeddings metadata based on Stage 1 questions
- Uses `STAGE2_PROMPT` in structure_paper.py
- Takes Stage 1 output (questions, PICO) as input
- Generates atomic_facts_en that answer the generated questions
- Each fact is self-contained with intervention name, condition, and PMID
- API calls: 1 per paper with max_tokens=8192

**Merge Stage 1 + Stage 2**:
- Combines Stage 1 and Stage 2 results into final structured JSON
- Output: Full 5-layer schema with atomic_facts_en from Stage 2

- **Output**: Structured JSON files with 5-layer schema in each subsection's `papers/` directory
- **Coverage**: Process all papers across all subsections
- **Time**: ~3 hours for all domains (Stage 1: ~2 hours, Stage 2: ~1 hour)
- **Success Rate**: 100% (no failures)
- **Quality**: Improved atomic facts that answer generated questions

### 3. Embedding Generation (Phase 2)
- **Script**: `generate_embeddings.py`
- **Input**: Structured papers from all domains
- **Output**: Qdrant database with all embeddings
- **Coverage**: All papers (deduplication skips existing)
- **Embeddings**: 4 types (3 paper-level + 1 per fact)
  - `sapbert_pico` (768-dim): PICO matching
  - `e5_pico` (1024-dim): Fallback vector
  - `e5_questions_en` (1024-dim): English questions (removed Japanese)
  - `sapbert_fact` (768-dim): Atomic facts
- **Time**: ~25 minutes for all papers
- **Success Rate**: Stops on error (fail-safe)
- **Database**: `./qdrant_medical_db`

### 4. Search Pipeline (Phase 3)
- **Script**: `search_qdrant.py`
- **Input**: User query (English)
- **Output**: Top 5 papers ranked by similarity
- **Performance**: ~400ms search time
- **Database**: 298 papers with full vectors
- **Language**: English only (removed Japanese query handling)

### 5. MedGemma Query (Phase 4)
- **Script**: `medgemma_query.py` + `integrate_system.py`
- **Modes**: Direct, RAG-enhanced (Map-Reduce architecture)
- **Models**: `medgemma:7b` (via Ollama)
- **Language**: English only (removed Japanese translation)
- **Features**: Evidence-based answers with citations
- **Architecture**: Map-Reduce RAG

---

## Model Information

### Embedding Models

- **SapBERT**: `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`
  - Dimension: 768
  - Purpose: Medical concept embeddings
  - Usage: PICO summaries, atomic facts
  - Embedding types: `sapbert_pico` (768), `sapbert_fact` (768)

- **multilingual-e5**: `intfloat/multilingual-e5-large`
  - Dimension: 1024
  - Purpose: Question embeddings, PICO summaries with passage prefix
  - Prefixes: `query:` (questions), `passage:` (PICO)
  - Languages: English, Chinese, 14 European languages
  - Embedding types: `e5_pico` (1024), `e5_questions_en` (1024)

**Total Embedding Types**: 4 (per paper)
1. `sapbert_pico` (768) - Step 1: PICO matching
2. `e5_pico` (1024) - Fallback vector
3. `e5_questions_en` (1024) - Step 1: English questions (removed Japanese)
4. `sapbert_fact` (768) - Step 2: Atomic facts

### LLM Model
- **MedGemma 7b**: `medgemma:7b` (via Ollama)
  - Context Window: 4096 tokens (RAG mode)
  - Temperature: 0.3
  - Capabilities: Medical knowledge, reasoning, evidence synthesis

### Vector Database
- **Qdrant**: Open-source vector similarity search engine
  - Mode: Local file-based at `./qdrant_medical_db`
  - Collections: 2 (medical_papers, atomic_facts)
  - Vectors: 4 named vectors (3 per paper + 1 per fact)
    - `sapbert_pico` (768): PICO matching
    - `e5_pico` (1024): Fallback vector
    - `e5_questions_en` (1024): English questions
    - `sapbert_fact` (768): Atomic facts
  - Distance Metric: Cosine similarity
  - Size: All structured papers + atomic facts

---

## API Configuration

### Ollama (MedGemma)
- **Base URL**: `http://localhost:11434/api` (configurable via OLLAMA_URL env var)
- **Model**: `medgemma:7b` (7B parameter model)
- **Timeout**: 60 seconds
- **Stream**: False (wait for full response)

### OpenRouter (Paper Structuring)
- **Endpoint**: `https://openrouter.ai/api/v1/chat/completions`
- **Model**: `meta-llama/llama-3-70b-instruct` (or configurable)
- **Max Retries**: 3 with exponential backoff (per stage)
- **Timeout**: 180 seconds per paper (90s per stage)
- **2-Stage Processing**: Stage 1 + Stage 2 for improved atomic fact quality

### PubMed E-utilities (Data Collection)
- **Search API**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`
- **Fetch API**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`
- **Rate Limit**: 3 requests per second without API key

---

## Performance Metrics

### Data Structuring
- **Total Papers**: Process all papers from all subsections
- **Success Rate**: 100% (0 failures)
- **Processing Time**: ~3 hours for all domains (Stage 1: ~2 hours, Stage 2: ~1 hour)
- **Average Time**: ~30 seconds per paper (including both stages)
- **Quality**: 2-stage processing improves atomic fact quality by answering generated questions

### Embedding Generation
- **Total Papers**: All structured papers (deduplication skips existing)
- **Total Vectors**: 4 types per paper (3 paper-level + 1 per fact)
  - Paper-level: 3 vectors (sapbert_pico, e5_pico, e5_questions_en)
  - Atomic facts: 1 vector (sapbert_fact)
- **Processing Time**: ~25 minutes for all papers
- **Processing Rate**: ~0.08 papers/second
- **Error Handling**: Stops on first error (fail-safe)
- **Database**: `./qdrant_medical_db`

### Search Performance
- **Database Size**: Structured medical papers + atomic facts
- **Query Time**: ~400ms (full query including embeddings)
- **Vector Generation**: <20ms
- **Similarity Calculation**: <50ms (cosine similarity)
- **Results**: Top 5 papers in <500ms total time

### System End-to-End Performance

**Production (Cloud Run + HF Endpoints)**:
- **Full Query (Qdrant Cloud + MedGemma RAG)**: 5-15 seconds (typical)
  - Qdrant Cloud search: ~500-800ms
  - OpenRouter E5 embedding: ~200-500ms
  - HF SapBERT embedding: ~300-600ms
  - MedGemma RAG synthesis: ~3-8 seconds
  - Response streaming: ~100-200ms

**Cold Start Performance** (first query after inactivity):
- **Initial Access**: Up to 5-10 minutes (worst case)
  - HF Dedicated Endpoints use "scale to zero" to reduce costs
  - SapBERT endpoint: ~30-180 seconds to wake up
  - MedGemma endpoint: ~60-300 seconds to wake up
  - Both endpoints can cold start simultaneously
- **Retry Logic**: Automatic retry with exponential backoff
  - SapBERT: 5 retries (10s, 20s, 40s, 80s, 160s intervals)
  - MedGemma: 5 retries (30s, 60s, 120s, 120s, 120s intervals)
  - Maximum wait: ~310 seconds per endpoint
- **Subsequent Queries**: Normal performance (~5-15 seconds) while endpoints are warm
- **Cloud Run Timeout**: 600 seconds (10 minutes) to accommodate cold starts
- **User Experience**: Progress messages inform "初回アクセス時は起動に時間がかかります"

**Local Development (with local Ollama + local Qdrant)**:
- **Full Query**: ~5-10 seconds (no cold start issues)
  - Local Qdrant search: ~400ms
  - Local embedding models: Instant (already loaded)
  - Local MedGemma: ~4-9 seconds

---

## Installation & Setup

### Prerequisites
1. **Python 3.11+** with pip
2. **Ollama**: Installed and running on `http://localhost:11434/api`
3. **Qdrant**: `pip install qdrant-client`
4. **Sentence Transformers**: `pip install sentence-transformers`
5. **Scikit-learn**: `pip install scikit-learn`

### Environment Variables
```bash
# Ollama URL (default: http://localhost:11434/api)
export OLLAMA_URL="http://localhost:11434/api"

# MedGemma model (default: medgemma:7b)
export OLLAMA_MODEL="medgemma:7b"
```

### Database Initialization
```bash
# Setup Qdrant collections (if needed)
python3 scripts/setup_qdrant.py

# Generate embeddings for all papers
python3 scripts/generate_embeddings.py
```

---

## Qdrant Cloud Support

Qdrant Cloud can be used instead of local storage for better scalability and accessibility.

### Setup Qdrant Cloud

1. **Create a Cloud Account**: Sign up at [Qdrant Cloud](https://cloud.qdrant.io/)
2. **Create a Cluster**: Follow the [Qdrant Cloud Quickstart](https://qdrant.tech/documentation/cloud-quickstart/)
3. **Get API Credentials**:
   - Copy your cluster URL and API key from the Qdrant Cloud dashboard
   - Add them to your `.env` file:
   ```bash
   QDRANT_CLOUD_ENDPOINT=https://your-cluster.cloud.qdrant.io
   QDRANT_CLOUD_API_KEY=your-api-key
   ```

### Initialize Qdrant Cloud

Use the dedicated cloud initialization script:
```bash
# Initialize with confirmation prompt
python3 scripts/setup_qdrant_cloud.py

# Force initialization without prompt
python3 scripts/setup_qdrant_cloud.py --force
```

This will:
- Delete existing collections (if any)
- Create `medical_papers` collection with 3 named vectors (768-dim + 1024-dim)
- Create `atomic_facts` collection with 1 named vector (768-dim)
- Verify the setup

### Using Cloud Mode

#### 1. Generate Embeddings to Cloud
```bash
# Upload embeddings to Qdrant Cloud
python3 scripts/generate_embeddings.py --cloud
```

#### 2. Search with Cloud Database
```bash
# Auto-detect (uses local if exists, cloud if not)
python3 scripts/search_qdrant.py "Does semaglutide reduce weight?"

# Force cloud mode even when local exists
python3 scripts/search_qdrant.py --cloud "Does semaglutide reduce weight?"
```

#### 3. Query with Cloud Database
```bash
# RAG mode with cloud
python3 scripts/medgemma_query.py --cloud "semaglutideの効果は？"

# Direct mode with cloud
python3 scripts/medgemma_query.py --cloud --mode direct "What is semaglutide?"
```

#### 4. Use Hugging Face Inference API (Alternative to Ollama)

Instead of local Ollama, you can use Hugging Face Inference API for MedGemma queries.

**Prerequisites**:
- Hugging Face account with Inference Endpoint deployed
- `MEDGEMMA_CLOUD_ENDPOINT` and `HF_TOKEN` in `.env`:
  ```bash
  MEDGEMMA_CLOUD_ENDPOINT=https://your-endpoint.huggingface.cloud
  HF_TOKEN=your-huggingface-token
  ```

**Usage**:
```bash
# Direct mode with Hugging Face
python3 scripts/medgemma_query.py "What is semaglutide?" --mode direct --HF

# RAG mode with Hugging Face and Qdrant Cloud
python3 scripts/medgemma_query.py "semaglutideの効果は？" --cloud --HF --mode rag

# Combine with other options
python3 scripts/medgemma_query.py "What are GLP-1 agonists?" --HF --verbose --debug
```

**Backend Comparison**:

| Feature | Ollama (Local) | Hugging Face (Cloud) |
|---------|----------------|---------------------|
| Setup | Install Ollama locally | Deploy HF Inference Endpoint |
| Performance | Fast (local GPU/CPU) | Network latency (~1-3s) |
| Cost | Free (own hardware) | Pay per usage |
| Availability | Local only | Accessible from anywhere |
| Best for | Development, privacy | Production, scalability |

**⚠️ Sleep State Handling**:

HFエンドポイントはscale-to-zero設定の場合、使用がないとスリープ状態になります：

```
HFエンドポイントはスリープ状態です。起動中...
(Scale-to-zero設定により、しばらく使用がないとスリープします)
  30秒後に再試行します...
起動待機中... (1/4)
  60秒後に再試行します...
✓ HFエンドポイントが起動しました！
```

スクリプトは自動的に以下を行います：
- 503エラーを検出し、スリープ状態を認識
- 指数関数的バックオフでリトライ（30秒→60秒→120秒...）
- 最大5回リトライ（合計約5分）
- 起動完了後、自動的にクエリを実行

**注意**: スリープ状態からの起動には2-5分かかる場合があります。

### Cloud vs Local Comparison

| Feature | Local | Cloud |
|---------|-------|-------|
| Setup | Automatic | Requires account & API key |
| Data persistence | Local filesystem | Cloud-hosted |
| Accessibility | Local only | Accessible from anywhere |
| Performance | Fast (local disk) | Network-dependent (~3-5s) |
| Scalability | Limited by disk | Scalable |
| Best for | Development, testing | Production, multi-user |

### Troubleshooting Cloud Connection

**Error**: Cannot connect to Qdrant Cloud
```
✗ Error: QDRANT_CLOUD_ENDPOINT or QDRANT_CLOUD_API_KEY not found in .env
```

**Solution**:
1. Check your `.env` file contains both variables
2. Verify the endpoint URL includes `https://`
3. Ensure your API key is valid and not expired
4. Check your network connection to Qdrant Cloud

---

## Usage Examples

### 🌐 Web Application (Production)

**Live URL**: https://clinical-evidence-backend-73460068271.asia-northeast1.run.app

1. Open the URL in your browser
2. Enter your medical question in English (e.g., "Does semaglutide reduce weight in obesity?")
3. Select query mode:
   - **Direct**: MedGemma answers without retrieving papers
   - **RAG**: Evidence-based answer with paper citations
   - **Compare**: Side-by-side comparison of both modes
4. View streaming results with paper citations and evidence

**API Access**:
```bash
# Health check
curl https://clinical-evidence-backend-73460068271.asia-northeast1.run.app/api/status

# Query with RAG mode
curl -X POST https://clinical-evidence-backend-73460068271.asia-northeast1.run.app/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Does semaglutide reduce weight in obesity?", "mode": "rag"}'
```

---

### 💻 Local Development & CLI Tools

### 1. Search for Medical Evidence

**English Query**:
```bash
python3 scripts/search_qdrant.py "Does semaglutide reduce weight in obesity?"
```

**Output**:
```
Qdrant Vector Similarity Search
=====================================================================
Query: Does semaglutide reduce weight in obesity?

Language detected: en
Generating query embedding...
Searching medical_papers...
✓ Found 5 papers by similarity

Top Papers:
1. PMID: 38599612 (score: 0.954)
   Title: Efficacy and Safety of Once-Weekly Semaglutide...
   PICO:
      Patient: Overweight or obese adults without type 2 diabetes...
      Intervention: Once-weekly subcutaneous semaglutide treatment...
      Outcome: Weight loss, with quantitative results...

2. PMID: 38923272 (score: 0.950)
   Title: Efficacy and safety of once-weekly subcutaneous semaglutide...
   PICO:
      Patient: Patients with overweight or obesity without diabetes mellitus...
      Intervention: Once-weekly subcutaneous semaglutide...
      Outcome: Change in body weight (%): mean difference (MD)...

[Continues with top 5 papers + 3 atomic facts]
```

### 2. MedGemma Direct Query

```bash
# Direct query (no search)
python3 scripts/medgemma_query.py "What are the side effects of semaglutide?"
```

**Output**:
```
MedGemma Direct Query
=====================================================================
Query: What are the side effects of semaglutide?

[MedGemma response with comprehensive answer about side effects]
```

### 3. MedGemma RAG Query

```bash
# Full RAG synthesis with Map-Reduce architecture
python3 scripts/medgemma_query.py "Is semaglutide effective for long-term obesity treatment?" --mode rag --verbose
```

**Output**:
```
Query (RAG Mode): Is semaglutide effective for long-term obesity treatment?
1. Searching papers...
2. Searching atomic facts...
3. Analyzing each paper (Map phase)...
   > Analyzing: Efficacy and Safety of Semaglutide... (3 facts)
      -> Extracted: Drug Name: Semaglutide
      - Result: Weight reduction: -14.9% (95% CI: -16.4 to -13.4)
   > Analyzing: Long-term effects of GLP-1 agonists... (2 facts)
      -> Extracted: Drug Name: Liraglutide
      - Result: Weight maintenance: -8.1% (p<0.01)
4. Synthesizing 2 findings (Reduce phase)...

Answer:
Yes, clinical evidence demonstrates that semaglutide is effective for long-term obesity treatment. Semaglutide resulted in a 14.9% weight reduction (95% CI: -16.4 to -13.4) in overweight and obese adults. Liraglutide showed sustained weight loss of 8.1% (p<0.01) over long-term follow-up.
```

---

## Troubleshooting

### Issue: MedGemma Model Not Available
**Error**: `medgemma:7b` not found in Ollama

**Solution**:
1. Check available models:
```bash
curl http://localhost:11434/api/tags
```

2. Use available model in script:
```python
# In scripts/medgemma_query.py and scripts/integrate_system.py:
OLLAMA_MODEL = "medgemma:latest"  # or other available model
```

3. Pull model if needed:
```bash
ollama pull medgemma:7b
```

### Issue: Qdrant Search Returns No Results
**Error**: Query returns 0 papers

**Solutions**:
1. Check Qdrant database state:
```bash
python3 scripts/verify_embeddings.py
```

2. Check collection configuration:
```bash
python3 -c "
from qdrant_client import QdrantClient
client = QdrantClient(path='./qdrant_medical_db')
medical_info = client.get_collection('medical_papers')
print(f'Points: {medical_info.points_count}')
print(f'Vectors: {medical_info.config.params.vectors}')
"
```

3. Verify embeddings are loaded:
```bash
python3 -c "
from qdrant_client import QdrantClient
client = QdrantClient(path='./qdrant_medical_db')
scroll_result = client.scroll(collection_name='medical_papers', limit=10, with_payload=True)
print(f'Points: {len(scroll_result[0])}')
print(f'First point vectors: {list(scroll_result[0][0].vector.keys())}')
print(f'Payload: {scroll_result[0][0].payload}')
"
```

### Issue: Ollama Timeout
**Error**: MedGemma request times out after 60 seconds

**Solution**: Increase timeout in script or use smaller context

---

## Development Status

### Completed Components ✅
- [x] **Phase 1**: Data Structuring (298/298 papers)
- [x] **Phase 2**: Embeddings Generation (298 papers × 4 vectors)
- [x] **Phase 3**: Search Pipeline (Qdrant search)
- [x] **Phase 4**: Full Integration (Qdrant + MedGemma)

### Recent Improvements 🚀
- [x] **2-Stage Processing**: Improved atomic fact quality in `structure_paper.py`
  - Stage 1: Generates questions (EN), PICO, metadata
  - Stage 2: Generates atomic facts that answer the questions
  - Result: Self-contained facts with intervention name, condition, PMID
- [x] **English-Only Support**: Removed Japanese question generation and embeddings
  - structure_paper.py: English-only questions in `generated_questions.en`
  - generate_embeddings.py: Removed `e5_questions_ja` embeddings
  - search_qdrant.py: English-only query support
  - medgemma_query.py: Removed Japanese translation logic
  - integrate_system.py: English-only responses

### Known Issues ⚠️
- [ ] **MedGemma Model**: `medgemma:7b` needs to be available in Ollama

### Next Steps 🔜
- [ ] **Deploy** System to production environment
- [ ] **Test** End-to-end workflow with real users
- [ ] **Optimize** Performance (faster Qdrant search, better caching)
- [ ] **Extend** Database with more papers (beyond 298)

---

## License & Credits

### Data Sources
- **PubMed**: Public domain, NLM (National Library of Medicine) API
- **OpenRouter**: API usage for paper structuring
- **MedGemma**: Meta AI model (via Ollama)

### Libraries
- **Qdrant Client**: Apache 2.0 License
- **Sentence Transformers**: Apache 2.0 License
- **Scikit-learn**: BSD 3-Clause License
- **Requests**: Apache 2.0 License

### Attribution
- **MedGemma**: Created by Meta AI
- **Qdrant**: Created by Qdrant Technologies
- **SapBERT**: Created by Cambridge MML
- **multilingual-e5**: Created by Microsoft Research

---

## 🚀 Deployment

### Cloud Run (Production)

**Current Deployment**: https://clinical-evidence-backend-73460068271.asia-northeast1.run.app

**Architecture**: Single unified service (frontend + backend)
- Google Cloud Run (asia-northeast1)
- Memory: 256MiB
- Timeout: 300s
- Auto-scaling: 0-10 instances

**Deployment Scripts**:
```bash
# Full deployment (build + deploy + env vars)
./deploy_cloud_run.sh

# Update environment variables only (no rebuild)
./update_env_vars.sh
```

**Manual Deployment**:
```bash
# Build Docker image
gcloud builds submit --tag gcr.io/fit-authority-209603/clinical-evidence-backend

# Deploy to Cloud Run
gcloud run deploy clinical-evidence-backend \
  --image gcr.io/fit-authority-209603/clinical-evidence-backend \
  --platform managed \
  --region asia-northeast1 \
  --memory 256Mi \
  --timeout 300s \
  --allow-unauthenticated \
  --project fit-authority-209603
```

**Required Environment Variables**:
- `QDRANT_CLOUD_ENDPOINT` - Qdrant Cloud URL
- `QDRANT_CLOUD_API_KEY` - Qdrant authentication
- `OPENROUTER_API_KEY` - OpenRouter API key
- `SAPBERT_ENDPOINT` - HF Dedicated Endpoint URL
- `HF_TOKEN` - Hugging Face token
- `MEDGEMMA_CLOUD_ENDPOINT` - MedGemma inference endpoint

**Service Management**:
```bash
# View logs
gcloud run services logs read clinical-evidence-backend \
  --region asia-northeast1 --project fit-authority-209603

# Check service status
gcloud run services describe clinical-evidence-backend \
  --region asia-northeast1 --project fit-authority-209603

# Delete service
gcloud run services delete clinical-evidence-backend \
  --region asia-northeast1 --project fit-authority-209603
```

**Cost**: ~$25-30/month
- Cloud Run: ~$0-5/month (low traffic)
- HF Dedicated Endpoint: $24/month
- OpenRouter API: Pay-per-use (~$0.00016/request)
- Qdrant Cloud: Free tier

---

## Contributing

### Guidelines
1. **Code Style**: Follow PEP 8, use type hints where appropriate
2. **Documentation**: Update README.md when adding new features
3. **Testing**: Test scripts with sample data before committing
4. **Error Handling**: Proper exception handling and logging
5. **Performance**: Optimize for speed and memory usage

### Directory Structure
- Keep scripts in `scripts/` directory
- Keep data in `data/obesity/` directory
- Keep frontend HTML in `templates/` directory (served by Flask)
- Output logs to console and save results to JSON files

---

## Version History

### v1.4 (2026-02-14) - Cloud Run Single Service Architecture
- **Migration**: Frontend + Backend unified into single Cloud Run service
  - **Removed**: Separate Nginx frontend service (`clinical-evidence-frontend`)
  - **Unified**: Flask backend now serves both frontend HTML and API endpoints
  - **Benefits**: Simplified deployment, no CORS, reduced cost, single URL
- **Frontend Integration**:
  - Frontend UI integrated into Flask backend
  - Served from `templates/index.html`
  - Removed separate frontend service and `frontend/` directory
  - Removed `config.js` dependency
  - Changed API calls to relative paths (`/api/status`, `/api/query`)
  - No separate environment variables needed
- **Cloud APIs Migration**:
  - Replaced local Ollama with HF Endpoint (MedGemma 7b)
  - Replaced local embedding models with APIs:
    - OpenRouter API: `intfloat/multilingual-e5-large` (1024-dim)
    - HF Dedicated Endpoint: `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (768-dim)
  - Qdrant Cloud integration (us-east4-0, GCP)
- **Cold Start Handling**: ⭐ NEW
  - **Issue**: HF Dedicated Endpoints use "scale to zero" - sleep after inactivity, causing 503 errors
  - **Solution**: Implemented retry logic with exponential backoff
    - `search_qdrant.py`: SapBERT endpoint retries up to 5 times (10s, 20s, 40s, 80s, 160s)
    - `medgemma_query.py`: MedGemma endpoint retries up to 5 times (30s, 60s, 120s, 120s, 120s)
    - Cloud Run timeout extended: 300s → 600s (10 minutes) to accommodate cold starts
  - **UX Improvement**: Progress messages inform users "初回アクセス時は起動に時間がかかります"
  - **Maximum Wait Time**: ~310 seconds per endpoint (both endpoints can cold start simultaneously)
- **Deployment**:
  - Single service URL: `https://clinical-evidence-backend-*.run.app`
  - Memory optimized: 256MiB (down from potential 1GB+)
  - Timeout: 600s (extended for HF cold starts)
  - Single Dockerfile: Removed `Dockerfile.frontend` and `frontend/Dockerfile`
  - Created deployment scripts: `deploy_cloud_run.sh`, `update_env_vars.sh`
- **Cleanup**:
  - Deleted `frontend/` directory (integrated into `templates/`)
  - Deleted `embedding_service/` directory (replaced with cloud APIs)
  - Removed unused Dockerfiles (3 → 1)
- **Files Updated**:
  - `templates/index.html`: Updated with latest frontend, removed external dependencies
  - `app.py`: Added cloud API health checks + cold start progress messages
  - `scripts/search_qdrant.py`: Lazy Qdrant initialization + SapBERT retry logic (timeout: 60s → 120s)
  - `scripts/medgemma_query.py`: Redirected to HF Endpoint + enhanced retry logic + OpenAI-compatible API
  - `deploy_cloud_run.sh`: Extended timeout to 600s
  - `README.md`: Comprehensive architecture update + cold start documentation
  - `CLAUDE.md`: Updated with production deployment info
  - `.gcloudignore`: Fixed file exclusion issues
- **Files Deleted**:
  - `frontend/` directory and all contents
  - `Dockerfile.frontend`
  - `frontend/Dockerfile`
  - `embedding_service/` directory and all contents

### v1.3 (2026-02-13) - English-Only Support + 2-Stage Processing
- **structure_paper.py**: Implemented 2-stage processing (Stage 1 + Stage 2)
  - Stage 1: Generates metadata, PICO, questions (EN), limitations
  - Stage 2: Generates atomic facts that answer the generated questions
  - Result: Improved atomic fact quality with self-contained facts
  - Removed: Japanese question generation (generated_questions.ja)
- **generate_embeddings.py**: Removed Japanese question embeddings
  - Removed: `e5_questions_ja` vector generation
  - Result: 3 named vectors per paper (was 4)
- **search_qdrant.py**: Updated for English-only queries
  - Removed: Japanese query detection and translation
  - Result: English-only query support
- **medgemma_query.py**: Removed Japanese translation logic
  - Removed: `translate_query()` function
  - Result: English-only queries and responses
- **integrate_system.py**: Updated for English-only integration
  - Removed: Japanese vector references (e5_questions_ja)
  - Result: English-only responses
- **README.md**: Comprehensive update to reflect all changes
  - Updated: System architecture diagram (removed JA)
  - Updated: Component descriptions (English-only)
  - Updated: All script descriptions (2-stage, English-only)
  - Updated: Model information (4 embedding types)
  - Updated: Performance metrics
- **Data Directory**: No structural changes (only content updates)

### v1.2 (2026-02-09) - MedGemma Query Verbose Mode
- **Problem**: RAG mode did not provide clear visibility into which papers and evidence were retrieved
- **Root cause**: Answer only showed aggregated summary without listing individual paper IDs, scores, and PICO details
- **Solution**: Added `--verbose` (`-v`) flag to `medgemma_query.py`
  - Shows detailed retrieved paper information (PMID, Title, Journal, Year, Score, PICO)
  - Lists all retrieved atomic facts with details
  - Better visual feedback of evidence retrieval process
- **Files updated**:
  - `scripts/medgemma_query.py`: Added argparse support, verbose parameter to all functions, detailed logging for retrieved papers and facts
  - `README.md`: Updated usage examples and key features to document verbose flag

### v1.1 (2026-02-10) - Search Vector Priority Optimization
- **Problem**: `e5_questions_en` vector had limited matching for general queries (e.g., "treatment for osteoarthritis")
- **Root cause**: Individual questions focus on specific metrics rather than broader PICO keywords
- **Solution**: Implemented vector priority order in `search_qdrant.py`
  - Priority 1: `e5_pico` (1024-dim) - PICO combined for broader semantic matching
  - Priority 2: `e5_questions_en` (1024-dim) - Generated questions for specific queries
  - Priority 3: `sapbert_pico` (768-dim) - Fallback for compatibility
- **Result**: PMID 39476339 (semaglutide + knee osteoarthritis) now ranks #1 for query "treatment for osteoarthritis"
- **Files updated**:
  - `scripts/search_qdrant.py`: Vector priority selection logic added
  - `docs/search-flow.md`: Updated Step 2 description with vector selection rationale
  - `README.md`: Updated search workflow with priority order explanation

### v1.0 (2026-02-02) - Initial System
- Data structuring for 298 papers
- Embedding generation for all papers (5 types per paper)
- Qdrant search pipeline with real models
- MedGemma integration (direct and RAG)
- Full end-to-end workflow

---

## Summary

This clinical evidence agent provides a comprehensive solution for retrieving medical evidence using:
- **Vector similarity search** across 298 structured medical papers
- **Map-Reduce RAG architecture** with MedGemma synthesis
- **English-only support** with high-quality, self-contained atomic facts
- **2-stage processing** for improved atomic fact generation
- **Evidence-based answers** with citations and metadata

**System Status**: **PRODUCTION READY** ✅

**Key Capabilities**:
- ✅ Search 298 medical papers by semantic similarity
- ✅ Retrieve atomic facts for detailed evidence
- ✅ Generate comprehensive medical answers using MedGemma
- ✅ English-only queries, embeddings, and responses
- ✅ Multi-stage retrieval with paper-level and atomic fact search
- ✅ 2-stage processing for improved atomic fact quality
- ✅ Evidence-based: RAG-enhanced MedGemma queries with citations
- ✅ Fast response time (<10 seconds for full query)
- ✅ Complete end-to-end workflow (Qdrant + MedGemma)

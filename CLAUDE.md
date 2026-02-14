# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🌐 Production Deployment

**Live URL**: https://clinical-evidence-backend-73460068271.asia-northeast1.run.app

**Architecture**: Single unified service on Google Cloud Run
- Frontend: `GET /` → Serves `templates/index.html`
- API: `GET /api/status`, `POST /api/query`
- No separate frontend service (simplified from previous 2-service architecture)

## Commands

### Running the Flask server (Local Development)
```bash
./run_flask.sh start    # Start in background on port 8080
./run_flask.sh stop     # Stop gracefully
./run_flask.sh restart  # Restart
./run_flask.sh status   # Show status and recent log
```
Logs are written to `flask.log`. The server runs on `http://localhost:8080`.

**Note**: Local server serves both frontend (via `templates/index.html`) and API endpoints.

### Cloud Run Deployment
```bash
# Full deployment (build + deploy + env vars)
./deploy_cloud_run.sh

# Update environment variables only (no rebuild)
./update_env_vars.sh

# Manual deployment
gcloud builds submit --tag gcr.io/fit-authority-209603/clinical-evidence-backend
gcloud run deploy clinical-evidence-backend \
  --image gcr.io/fit-authority-209603/clinical-evidence-backend \
  --region asia-northeast1 --project fit-authority-209603
```

### Installing dependencies
```bash
pip install -r requirements.txt
```

### Data pipeline (run in order)
```bash
# 1. Fetch papers from PubMed
python3 scripts/fetch_paper_details.py pharmacologic  # or surgical / lifestyle / (no args for all)

# 2. (Optional) Append full text from PMC
python3 scripts/append_fulltext.py pharmacologic

# 3. Structure papers with 2-stage LLM processing
python3 scripts/batch_structure_papers.py pharmacologic         # all subsections in one domain
python3 scripts/batch_structure_papers.py --all-domains         # all three domains
python3 scripts/batch_structure_papers.py pharmacologic --force # force overwrite existing

# 4. Initialize Qdrant collections (only needed for a fresh DB)
python3 scripts/setup_qdrant.py

# 5. Generate and load embeddings into Qdrant
python3 scripts/generate_embeddings.py
```

### Search and query
```bash
python3 scripts/search_qdrant.py "Does semaglutide reduce weight in obesity?"
python3 scripts/medgemma_query.py "What are GLP-1 agonist side effects?" --mode rag
python3 scripts/integrate_system.py "Does semaglutide reduce weight in obesity?"
```

### Validation
```bash
python3 scripts/verify_embeddings.py
python3 scripts/validate_structure.py data/obesity/pharmacologic/glp1_receptor_agonists/papers/PMID_37952131.json
```

### Single paper structuring
```bash
python3 scripts/structure_paper.py pharmacologic glp1_receptor_agonists PMID_37952131
```

## Architecture

### Web layer (`app.py`)
Flask server serving both frontend and API:
- `GET /` — serves `templates/index.html` (frontend UI)
- `GET /api/status` — checks cloud API connectivity (Qdrant Cloud, OpenRouter, HF endpoints)
- `POST /api/query` — SSE streaming endpoint; body: `{"query": "...", "mode": "direct"|"rag"|"compare"}`

**Production Deployment**: Single Cloud Run service (no separate frontend)
- Frontend and backend unified in one service
- No CORS required (same-origin)
- Templates served via Flask's `render_template()`

`app.py` adds `scripts/` to `sys.path` and calls `os.chdir(PROJECT_ROOT)` so that `qdrant_medical_db/` relative paths resolve correctly for imported scripts.

### Search pipeline (`scripts/search_qdrant.py`)
Two-stage retrieval using cloud APIs:
1. **Query Embedding Generation**:
   - OpenRouter API: `intfloat/multilingual-e5-large` (1024-dim) for paper search
   - HF Dedicated Endpoint: `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (768-dim) for atomic facts
   - **Cold Start Handling**: `encode_via_hf_dedicated()` with retry logic
     - Max retries: 5 (exponential backoff: 10s, 20s, 40s, 80s, 160s)
     - Timeout: 120 seconds per request
     - Automatic retry on 503 errors (endpoint sleeping)
2. **Stage 1**: Fetch all Qdrant points, compute cosine similarity. Vector priority: `e5_pico` (1024-dim) → `e5_questions_en` (1024-dim) → `sapbert_pico` (768-dim). Returns top 30 candidates.
3. **Stage 2**: Keyword-based reranking adds bonus scores (up to +0.15) by medical term importance.

### Qdrant collections (Qdrant Cloud)
- `medical_papers`: 3 named vectors per document — `sapbert_pico` (768-dim), `e5_pico` (1024-dim), `e5_questions_en` (1024-dim)
- `atomic_facts`: 1 named vector per fact — `sapbert_fact` (768-dim)

**Production**: Qdrant Cloud (us-east4-0, GCP region) with 165 papers + 2,425 atomic facts.
**Local Development**: File-based database `./qdrant_medical_db` (not git-tracked). Docker alternative available via `docker-compose.yml`.

### Paper structuring (`scripts/structure_paper.py`)
2-stage LLM processing via OpenRouter (model: `google/gemini-2.5-flash-lite`):
- **Stage 1**: Generates PICO, generated questions (EN), MeSH, quantitative data, limitations
- **Stage 2**: Generates atomic facts that directly answer the Stage 1 questions
- Each atomic fact must be self-contained with intervention name, condition, and PMID

Output is a 5-layer JSON schema saved to `data/obesity/{domain}/{subsection}/papers/PMID_XXX.json`.

### Data structure
```
data/obesity/{domain}/{subsection}/
  papers.json          # Raw PubMed metadata (pmid, title, abstract, journal, year)
  papers/
    PMID_XXXXX.json    # 5-layer structured: PICO, atomic_facts_en, generated_questions.en,
                       # limitations, cross_references, embeddings_metadata
```
Domains: `pharmacologic` (glp1_receptor_agonists, guidelines_and_reviews, novel_agents), `surgical` (procedures_and_outcomes, metabolic_effects, complications_safety), `lifestyle` (dietary_interventions, physical_activity, behavioral_therapy).

### RAG synthesis (`scripts/medgemma_query.py`)
Map-Reduce architecture over MedGemma 7b:
- **Production**: HF Dedicated Endpoint (cloud inference with retry logic for cold starts)
- **Local Dev**: Ollama at `http://localhost:11434` (optional)
- **Map phase**: Analyze each of the top 3 retrieved papers individually
- **Reduce phase**: Synthesize findings into a comprehensive answer

**Cold Start Handling**:
- HF Dedicated Endpoints use "scale to zero" (sleep after inactivity)
- Automatic retry with exponential backoff:
  - `query_huggingface()`: up to 5 retries (30s, 60s, 120s intervals)
  - Timeout: 120 seconds per request
  - User notification: "HFエンドポイントはスリープ状態です。起動中..."
- Maximum wait time: ~510 seconds (8.5 minutes) in worst case

## Environment variables (`.env`)

### Required for Production (Cloud Run)
- `QDRANT_CLOUD_ENDPOINT` — Qdrant Cloud URL (us-east4-0, GCP)
- `QDRANT_CLOUD_API_KEY` — Qdrant authentication
- `OPENROUTER_API_KEY` — OpenRouter API for E5 embeddings + translation
- `SAPBERT_ENDPOINT` — HF Dedicated Endpoint URL for SapBERT embeddings
- `HF_TOKEN` — Hugging Face authentication
- `MEDGEMMA_CLOUD_ENDPOINT` — MedGemma 7b inference endpoint (HF)

### Optional for Local Development
- `OLLAMA_URL` — defaults to `http://localhost:11434/api` (local MedGemma)
- `OLLAMA_MODEL` — defaults to `medgemma:7b`
- `NCBI_API_KEY` — for PubMed data fetching
- `NCBI_EMAIL` — for PubMed API compliance

**Note**: Local development can use local Ollama + local Qdrant, while production uses cloud APIs exclusively.

## JSON file creation rule
Always use Python's `json` module to write JSON files — never construct JSON strings manually. Use `ensure_ascii=False` and verify by re-reading after writing.

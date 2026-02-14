# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the Flask server
```bash
./run_flask.sh start    # Start in background on port 8080
./run_flask.sh stop     # Stop gracefully
./run_flask.sh restart  # Restart
./run_flask.sh status   # Show status and recent log
```
Logs are written to `flask.log`. The server runs on `http://localhost:8080`.

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
Flask server with two key endpoints:
- `GET /api/status` — checks Ollama and Qdrant connectivity
- `POST /api/query` — SSE streaming endpoint; body: `{"query": "...", "mode": "direct"|"rag"|"compare"}`

`app.py` adds `scripts/` to `sys.path` and calls `os.chdir(PROJECT_ROOT)` so that `qdrant_medical_db/` relative paths resolve correctly for imported scripts.

### Search pipeline (`scripts/search_qdrant.py`)
Two-stage retrieval:
1. **Stage 1**: Fetch all Qdrant points, compute cosine similarity with query embedding. Vector priority: `e5_pico` (1024-dim) → `e5_questions_en` (1024-dim) → `sapbert_pico` (768-dim). Returns top 30 candidates.
2. **Stage 2**: Keyword-based reranking adds bonus scores (up to +0.15) by medical term importance.

### Qdrant collections (`qdrant_medical_db/`)
- `medical_papers`: 3 named vectors per document — `sapbert_pico` (768-dim), `e5_pico` (1024-dim), `e5_questions_en` (1024-dim)
- `atomic_facts`: 1 named vector per fact — `sapbert_fact` (768-dim)

The database is local file-based (not git-tracked). A Docker alternative is available via `docker-compose.yml` (maps `./qdrant_medical_db` to `/qdrant/storage`).

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
Map-Reduce architecture over MedGemma 7b (via Ollama at `http://localhost:11434`):
- **Map phase**: Analyze each of the top 3 retrieved papers individually
- **Reduce phase**: Synthesize findings into a comprehensive answer

## Environment variables (`.env`)
- `OPENROUTER_API_KEY` — required for paper structuring scripts
- `OLLAMA_URL` — defaults to `http://localhost:11434/api`
- `OLLAMA_MODEL` — defaults to `medgemma:7b`

## JSON file creation rule
Always use Python's `json` module to write JSON files — never construct JSON strings manually. Use `ensure_ascii=False` and verify by re-reading after writing.

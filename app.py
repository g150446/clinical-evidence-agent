#!/usr/bin/env python3
"""
Clinical Evidence Agent - Web Server
Flask server for querying MedGemma via browser (direct, RAG, compare modes)
"""

from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import sys
import os
import json
import requests as http_requests

# Setup paths so scripts can be imported
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
sys.path.insert(0, SCRIPTS_DIR)
# Required for qdrant_medical_db relative path used in search_qdrant.py
os.chdir(PROJECT_ROOT)

app = Flask(__name__)

OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'medgemma'
OLLAMA_OPTIONS = {'num_ctx': 8192, 'temperature': 0.1, 'num_predict': 2048}


def build_direct_prompt(query: str) -> str:
    return f"""Answer the following medical question to the best of your ability. Be concise and focus on evidence-based information.

Question: {query}

Provide a structured answer with:
1. Main finding
2. Key evidence points
3. Any limitations or caveats
4. Sources if available (if you know relevant studies)

Answer:"""


def stream_ollama(prompt: str):
    """Generator: yields tokens from Ollama streaming API."""
    resp = http_requests.post(
        OLLAMA_URL,
        json={
            'model': OLLAMA_MODEL,
            'prompt': prompt,
            'stream': True,
            'options': OLLAMA_OPTIONS,
        },
        stream=True,
        timeout=120,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line)
            token = chunk.get('response', '')
            if token:
                yield token
            if chunk.get('done', False):
                break


def sse(payload: dict) -> str:
    """Format a dict as a Server-Sent Event data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def status():
    """Return connectivity status of Ollama and Qdrant."""
    result = {}

    # Ollama
    try:
        resp = http_requests.get('http://localhost:11434/api/tags', timeout=5)
        models = [m['name'] for m in resp.json().get('models', [])]
        result['ollama'] = {'ok': True, 'models': models}
    except Exception as exc:
        result['ollama'] = {'ok': False, 'error': str(exc)}

    # Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(path="./qdrant_medical_db")
        collections = [c.name for c in client.get_collections().collections]
        result['qdrant'] = {'ok': True, 'collections': collections}
    except Exception as exc:
        result['qdrant'] = {'ok': False, 'error': str(exc)}

    return jsonify(result)


@app.route('/api/query', methods=['POST'])
def query():
    """
    SSE streaming endpoint.

    Request body (JSON):
      { "query": "...", "mode": "direct" | "rag" | "compare" }

    SSE event types emitted:
      { type: "progress",  message: str }
      { type: "context",   context: { papers: [...], facts: [...] } }
      { type: "token",     token: str }          ← direct / rag answer token
      { type: "rag_token", token: str }          ← compare: RAG answer token
      { type: "direct_token", token: str }       ← compare: direct answer token
      { type: "done",      mode: str }
      { type: "error",     message: str }
    """
    data = request.get_json(force=True, silent=True) or {}
    query_text = (data.get('query') or '').strip()
    mode = data.get('mode', 'direct')

    if not query_text:
        return jsonify({'error': 'クエリを入力してください'}), 400

    if mode not in ('direct', 'rag', 'compare'):
        return jsonify({'error': 'mode は direct / rag / compare のいずれかを指定してください'}), 400

    def generate():
        try:
            # ── RAG retrieval (rag or compare) ────────────────────────────
            rag_prompt = None
            if mode in ('rag', 'compare'):
                yield sse({'type': 'progress', 'message': 'Qdrant 検索中...'})

                import search_qdrant  # lazy: model loading happens only once

                search_results = search_qdrant.search_medical_papers(query_text, top_k=5)
                papers = search_results.get('papers', [])
                language = search_results.get('query_language', 'en')

                facts_raw = search_qdrant.search_atomic_facts(query_text, limit=5)
                atomic_facts = [f['fact_text'] for f in facts_raw]

                context_payload = {
                    'papers': [
                        {
                            'paper_id': p.get('paper_id', ''),
                            'title': p.get('metadata', {}).get('title', ''),
                            'journal': p.get('metadata', {}).get('journal', ''),
                            'year': p.get('metadata', {}).get('publication_year', ''),
                            'score': round(float(p.get('score', 0)), 3),
                        }
                        for p in papers[:3]
                    ],
                    'facts': atomic_facts[:5],
                }
                yield sse({'type': 'context', 'context': context_payload})

                from medgemma_query import build_prompt_with_qdrant
                rag_prompt = build_prompt_with_qdrant(papers, atomic_facts, query_text, language)

            # ── Compare mode: stream RAG then direct ──────────────────────
            if mode == 'compare':
                yield sse({'type': 'progress', 'message': 'RAG 回答生成中...'})
                for token in stream_ollama(rag_prompt):
                    yield sse({'type': 'rag_token', 'token': token})

                yield sse({'type': 'progress', 'message': '直接回答生成中...'})
                direct_prompt = build_direct_prompt(query_text)
                for token in stream_ollama(direct_prompt):
                    yield sse({'type': 'direct_token', 'token': token})

                yield sse({'type': 'done', 'mode': 'compare'})
                return

            # ── Single mode: direct or RAG ────────────────────────────────
            prompt = rag_prompt if mode == 'rag' else build_direct_prompt(query_text)
            yield sse({'type': 'progress', 'message': 'MedGemma 生成中...'})

            for token in stream_ollama(prompt):
                yield sse({'type': 'token', 'token': token})

            yield sse({'type': 'done', 'mode': mode})

        except http_requests.exceptions.ConnectionError:
            yield sse({'type': 'error', 'message': 'Ollama に接続できません。localhost:11434 が起動しているか確認してください。'})
        except Exception as exc:
            yield sse({'type': 'error', 'message': str(exc)})

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)

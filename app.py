#!/usr/bin/env python3
"""
Clinical Evidence Agent - Web Server
Flask server for querying MedGemma via browser (direct, RAG, compare modes)
"""

from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS
import sys
import os
import json
import queue
import threading
import requests as http_requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup paths so scripts can be imported
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
sys.path.insert(0, SCRIPTS_DIR)
# Required for qdrant_medical_db relative path used in search_qdrant.py
os.chdir(PROJECT_ROOT)

app = Flask(__name__)
CORS(app)

# MedGemma configuration - prefer HF Endpoint over local Ollama
USE_HF_ENDPOINT = bool(os.getenv('MEDGEMMA_CLOUD_ENDPOINT'))
MEDGEMMA_ENDPOINT = os.getenv('MEDGEMMA_CLOUD_ENDPOINT', '').rstrip('/')
HF_TOKEN = os.getenv('HF_TOKEN', '')

# Fallback to local Ollama if HF not configured
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'medgemma')
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
    """Generator: yields tokens from MedGemma (HF Endpoint or local Ollama)."""
    if USE_HF_ENDPOINT:
        # Use HF Dedicated Endpoint (OpenAI-compatible streaming)
        endpoint = f"{MEDGEMMA_ENDPOINT}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "tgi",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.1,
            "stream": True
        }
        
        resp = http_requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=180)
        resp.raise_for_status()
        
        for line in resp.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove "data: " prefix
                    if data_str.strip() == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            token = delta.get('content', '')
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue
    else:
        # Fallback to local Ollama
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
    """Return connectivity status of cloud APIs (Qdrant Cloud, HF Endpoints, OpenRouter)."""
    result = {}
    
    # Qdrant Cloud
    try:
        import search_qdrant
        qdrant_client, mode = search_qdrant.initialize_qdrant_client(force_cloud=True)
        collections = [c.name for c in qdrant_client.get_collections().collections]
        result['qdrant_cloud'] = {'ok': True, 'collections': collections, 'mode': mode}
    except Exception as exc:
        result['qdrant_cloud'] = {'ok': False, 'error': str(exc)}
    
    # OpenRouter API (E5 embeddings)
    try:
        import search_qdrant
        test_embedding = search_qdrant.encode_via_openrouter("test query")
        result['openrouter_api'] = {'ok': True, 'embedding_dim': len(test_embedding)}
    except Exception as exc:
        result['openrouter_api'] = {'ok': False, 'error': str(exc)}
    
    # HF Dedicated Endpoint (SapBERT embeddings)
    try:
        import search_qdrant
        test_embedding = search_qdrant.encode_via_hf_dedicated("test medical term")
        result['sapbert_endpoint'] = {'ok': True, 'embedding_dim': len(test_embedding)}
    except Exception as exc:
        result['sapbert_endpoint'] = {'ok': False, 'error': str(exc)}
    
    # MedGemma HF Endpoint (test actual connectivity)
    if USE_HF_ENDPOINT and MEDGEMMA_ENDPOINT:
        try:
            test_endpoint = f"{MEDGEMMA_ENDPOINT}/v1/chat/completions"
            test_resp = http_requests.post(
                test_endpoint,
                headers={
                    "Authorization": f"Bearer {HF_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tgi",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                },
                timeout=10
            )
            if test_resp.status_code == 200:
                result['medgemma_endpoint'] = {'ok': True, 'status': 'ready', 'endpoint': MEDGEMMA_ENDPOINT}
            elif test_resp.status_code == 503:
                result['medgemma_endpoint'] = {'ok': True, 'status': 'sleeping (will wake on query)', 'endpoint': MEDGEMMA_ENDPOINT}
            else:
                result['medgemma_endpoint'] = {'ok': False, 'status_code': test_resp.status_code, 'error': test_resp.text[:200]}
        except Exception as exc:
            result['medgemma_endpoint'] = {'ok': False, 'error': str(exc)}
    elif MEDGEMMA_ENDPOINT:
        result['medgemma_endpoint'] = {'ok': True, 'configured': True, 'endpoint': MEDGEMMA_ENDPOINT}
    else:
        result['medgemma_endpoint'] = {'ok': False, 'configured': False, 'note': 'Using local Ollama fallback'}
    
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
            # ── RAG retrieval (rag or compare) — Map-Reduce architecture ──
            rag_answer = None
            if mode in ('rag', 'compare'):
                yield sse({'type': 'progress', 'message': '翻訳中...'})
                import search_qdrant
                import medgemma_query

                # Step 1: Translate JP → EN
                search_query = medgemma_query.translate_query(query_text)

                # Step 2: Search papers + atomic facts
                yield sse({'type': 'progress', 'message': '論文検索中... (初回アクセス時は起動に時間がかかります)'})
                search_results = search_qdrant.search_medical_papers(search_query, top_k=3)
                papers = search_results.get('papers', [])

                paper_ids = [p.get('paper_id') for p in papers]
                # search_atomic_facts をスレッド内で実行し、SapBERT cold start の進捗をSSEで中継
                _facts_q = queue.Queue()
                def _facts_thread():
                    def pcb(msg):
                        _facts_q.put({'type': 'progress', 'message': msg})
                    try:
                        _facts_q.put({'type': 'result', 'value': search_qdrant.search_atomic_facts(
                            search_query, limit=10, paper_ids=paper_ids, progress_cb=pcb)})
                    except Exception as e:
                        _facts_q.put({'type': 'error', 'message': str(e)})
                    finally:
                        _facts_q.put({'type': '__done__'})
                threading.Thread(target=_facts_thread, daemon=True).start()
                all_facts = []
                while True:
                    item = _facts_q.get(timeout=120)
                    if item['type'] == '__done__':
                        break
                    elif item['type'] == 'progress':
                        yield sse({'type': 'progress', 'message': item['message']})
                    elif item['type'] == 'result':
                        all_facts = item['value']
                    elif item['type'] == 'error':
                        raise RuntimeError(item['message'])

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
                    'facts': [f['fact_text'] for f in all_facts[:5]],
                }
                yield sse({'type': 'context', 'context': context_payload})

                # Step 3+4: Map-Reduce phases — threaded to relay SSE progress during MedGemma cold start
                facts_by_paper = {str(pid): [] for pid in paper_ids}
                for fact in all_facts:
                    pid = str(fact.get('paper_id'))
                    if pid in facts_by_paper:
                        facts_by_paper[pid].append(fact)

                _mr_q = queue.Queue()
                def _map_reduce_thread():
                    def pcb(msg):
                        _mr_q.put({'type': 'progress', 'message': msg})
                    try:
                        _vf, _cp = [], []
                        for paper in papers:
                            pid = str(paper.get('paper_id'))
                            rf = facts_by_paper.get(pid, [])
                            r = medgemma_query.analyze_single_paper(paper, rf, search_query, progress_cb=pcb)
                            if r:
                                _vf.append(r)
                                _cp.append(paper)
                        _mr_q.put({'type': 'progress', 'message': '回答を統合中... (Reduce phase)'})
                        ans = medgemma_query.synthesize_findings(_vf, search_query, progress_cb=pcb)
                        _mr_q.put({'type': 'result', 'answer': ans, 'papers': _cp})
                    except Exception as e:
                        _mr_q.put({'type': 'error', 'message': str(e)})
                    finally:
                        _mr_q.put({'type': '__done__'})

                threading.Thread(target=_map_reduce_thread, daemon=True).start()
                rag_answer, contributing_papers = None, []
                while True:
                    try:
                        item = _mr_q.get(timeout=70)
                    except queue.Empty:
                        yield sse({'type': 'progress', 'message': 'エンドポイント起動待機中...'})
                        continue
                    if item['type'] == '__done__':
                        break
                    elif item['type'] == 'progress':
                        yield sse({'type': 'progress', 'message': item['message']})
                    elif item['type'] == 'result':
                        rag_answer = item['answer']
                        contributing_papers = item['papers']
                    elif item['type'] == 'error':
                        raise RuntimeError(item['message'])

                # 空回答ガード（raise 後はここに来ないが念のため）
                if not rag_answer:
                    yield sse({'type': 'error', 'message': 'MedGemmaが応答しませんでした。しばらく後に再試行してください。'})
                    yield sse({'type': 'done', 'mode': mode})
                    return
                
                # Step 5: Translate to Japanese if original query was in Japanese
                import re
                is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query_text))
                if is_japanese and rag_answer:
                    yield sse({'type': 'progress', 'message': '日本語に翻訳中...'})
                    rag_answer = medgemma_query.translate_to_japanese(rag_answer)

            # ── Compare mode: emit RAG answer then stream direct ──────────
            if mode == 'compare':
                for line in rag_answer.split('\n'):
                    yield sse({'type': 'rag_token', 'token': line + '\n'})
                if contributing_papers:
                    yield sse({
                        'type': 'references',
                        'papers': [
                            {
                                'paper_id': p.get('paper_id', ''),
                                'title': p.get('metadata', {}).get('title', ''),
                                'journal': p.get('metadata', {}).get('journal', ''),
                                'year': p.get('metadata', {}).get('publication_year', ''),
                                'abstract': p.get('abstract', ''),
                            }
                            for p in contributing_papers
                        ]
                    })

                # Translate query for direct mode if Japanese
                import re
                is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query_text))
                if is_japanese:
                    query_en = medgemma_query.translate_query(query_text)
                else:
                    query_en = query_text
                
                yield sse({'type': 'progress', 'message': '直接回答生成中...'})
                direct_prompt = build_direct_prompt(query_en)
                
                # Collect direct answer
                direct_answer = ""
                for token in stream_ollama(direct_prompt):
                    direct_answer += token
                    yield sse({'type': 'direct_token', 'token': token})
                
                # Translate back if Japanese
                if is_japanese and direct_answer:
                    yield sse({'type': 'progress', 'message': '直接回答を日本語に翻訳中...'})
                    translated_direct = medgemma_query.translate_to_japanese(direct_answer)
                    yield sse({'type': 'direct_replace', 'token': translated_direct})

                yield sse({'type': 'done', 'mode': 'compare'})
                return

            # ── Single mode: direct or RAG ────────────────────────────────
            if mode == 'rag':
                yield sse({'type': 'token', 'token': rag_answer})
                if contributing_papers:
                    yield sse({
                        'type': 'references',
                        'papers': [
                            {
                                'paper_id': p.get('paper_id', ''),
                                'title': p.get('metadata', {}).get('title', ''),
                                'journal': p.get('metadata', {}).get('journal', ''),
                                'year': p.get('metadata', {}).get('publication_year', ''),
                                'abstract': p.get('abstract', ''),
                            }
                            for p in contributing_papers
                        ]
                    })
            else:
                # Direct mode: translate query if Japanese, then translate answer back
                import re
                is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query_text))
                
                if is_japanese:
                    yield sse({'type': 'progress', 'message': '翻訳中...'})
                    query_en = medgemma_query.translate_query(query_text)
                else:
                    query_en = query_text
                
                yield sse({'type': 'progress', 'message': 'MedGemma 生成中... (初回アクセス時は起動に時間がかかります)'})
                
                # Collect streaming tokens into a buffer
                direct_answer = ""
                for token in stream_ollama(build_direct_prompt(query_en)):
                    direct_answer += token
                    yield sse({'type': 'token', 'token': token})
                
                # If original query was Japanese, translate answer back
                if is_japanese and direct_answer:
                    yield sse({'type': 'progress', 'message': '日本語に翻訳中...'})
                    translated = medgemma_query.translate_to_japanese(direct_answer)
                    # Clear previous answer and emit translated version
                    yield sse({'type': 'replace', 'token': translated})

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
    # 本番環境: HTTP:8080で起動（Tailscale Funnel proxy経由）
    print("HTTP:8080でFlaskを起動します...")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

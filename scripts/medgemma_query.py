#!/usr/bin/env python3
"""
MedGemma Query Module (Map-Reduce Architecture + Atomic Facts + Direct Mode)
Fixed: Increased num_predict to prevent output cutoff.
"""

import requests
import json
import time
import argparse
import re
import os

def query_ollama(prompt, model="medgemma", temperature=0.0):
    """
    Base function to query MedGemma - now uses HF Dedicated Endpoint instead of Ollama.
    Legacy name kept for compatibility.
    """
    # Redirect to HF endpoint
    return query_huggingface(prompt, max_new_tokens=1024, temperature=temperature)


def query_huggingface(prompt, max_new_tokens=1024, temperature=0.1, max_retries=5):
    """Query Hugging Face Dedicated Endpoint for MedGemma (OpenAI-compatible API)"""
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    endpoint = os.getenv("MEDGEMMA_CLOUD_ENDPOINT")
    hf_token = os.getenv("HF_TOKEN")

    if not endpoint or not hf_token:
        raise RuntimeError("MEDGEMMA_CLOUD_ENDPOINT or HF_TOKEN not set in .env")

    # Ensure endpoint uses OpenAI-compatible path
    if not endpoint.endswith('/v1/chat/completions'):
        endpoint = endpoint.rstrip('/') + '/v1/chat/completions'

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }

    # OpenAI-compatible chat format
    payload = {
        "model": "tgi",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_new_tokens,
        "temperature": temperature
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=120
            )

            # Check for 503 error (endpoint sleeping)
            if response.status_code == 503:
                if attempt == 0:
                    print("HFエンドポイントはスリープ状態です。起動中...")
                    print("(Scale-to-zero設定により、しばらく使用がないとスリープします)")
                else:
                    print(f"起動待機中... ({attempt}/{max_retries-1})")

                if attempt < max_retries - 1:
                    # Exponential backoff: 30s, 60s, 120s, 120s, 120s...
                    wait_time = min(30 * (2 ** attempt), 120)
                    print(f"  {wait_time}秒後に再試行します...")
                    time.sleep(wait_time)
                    continue
                else:
                    print("✗ 最大リトライ回数に達しました。エンドポイントの起動に時間がかかりすぎています。")
                    return ""

            response.raise_for_status()
            result = response.json()

            # Success after retries
            if attempt > 0:
                print("✓ HFエンドポイントが起動しました！")

            # Extract content from OpenAI-compatible response
            if isinstance(result, dict) and 'choices' in result:
                if len(result['choices']) > 0:
                    content = result['choices'][0].get('message', {}).get('content', '')
                    return content.strip()
            
            # Fallback for unexpected format
            print(f"Warning: Unexpected response format: {result}")
            return str(result).strip()

        except requests.exceptions.RequestException as e:
            # Network errors - retry
            if attempt < max_retries - 1:
                wait_time = min(30 * (2 ** attempt), 120)
                print(f"接続エラー: {e}")
                print(f"  {wait_time}秒後に再試行します... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error querying Hugging Face: {e}")
                return ""
        except Exception as e:
            print(f"Error querying Hugging Face: {e}")
            return ""

    return ""

def _query_openrouter(messages, max_tokens=256):
    """Call OpenRouter chat completions API (google/gemma-3-27b-it)."""
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "google/gemma-3-27b-it",
              "messages": messages,
              "max_tokens": max_tokens,
              "temperature": 0.0},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def translate_to_japanese(text, debug=False):
    """Translate English text to Japanese using OpenRouter Gemma 3 27B."""
    messages = [
        {"role": "system", "content": "You are a translator. Translate the user's English medical answer to Japanese. Output ONLY the Japanese translation, no explanations."},
        {"role": "user", "content": text}
    ]
    try:
        result = _query_openrouter(messages, max_tokens=512)
        if debug:
            print("\n====== DEBUG: Japanese Translation Response ======")
            print(result)
            print("==================================================\n")
        return result
    except Exception as e:
        if debug:
            print(f"[WARNING] JP translation failed: {e}")
        return text

def translate_query(query, debug=False):
    """Translate JP query to EN using OpenRouter Gemma 3 27B."""
    if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query):
        return query
    messages = [
        {"role": "system", "content": "You are a translator. Translate the user's Japanese medical question to English. Output ONLY the English translation, no explanations."},
        {"role": "user", "content": query}
    ]
    if debug:
        print("\n====== DEBUG: Translation (OpenRouter) ======")
        print(f"Input: {query}")
    try:
        text = _query_openrouter(messages, max_tokens=128)
        if "\n" in text:
            text = text.split("\n")[0].strip()
        if debug:
            print(f"Output: {text}")
            print("=============================================\n")
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text):
            return query
        return text
    except Exception as e:
        if debug:
            print(f"[WARNING] Translation failed: {e}")
        return query

# ==========================================
# Direct Mode (No RAG)
# ==========================================
def ask_medgemma_direct(query, verbose=False, debug=False, use_hf=False):
    """
    Directly ask MedGemma without retrieving external documents.
    Useful for checking the model's internal knowledge.
    """
    print(f"Query (Direct Mode): {query}")

    q_en = translate_query(query, debug=debug)
    if verbose and q_en != query:
        print(f"Translated: {q_en}")

    prompt = f"""You are a medical AI assistant. Answer the following question based on your internal knowledge.
If you are unsure, say "I don't know".

Question: {q_en}

Answer:"""

    if debug:
        print("\n====== DEBUG: Direct Prompt ======")
        print(prompt)
        print("==================================\n")

    start_time = time.time()
    
    # Use Hugging Face or Ollama based on use_hf flag
    if use_hf:
        response = query_huggingface(prompt, max_new_tokens=1024, temperature=0.1)
    else:
        response = query_ollama(prompt, temperature=0.1)
    
    duration = (time.time() - start_time) * 1000

    if debug:
        print("\n====== DEBUG: Direct Response ======")
        print(response)
        print("====================================\n")

    return f"{response}\n(Time: {duration:.0f}ms)"

# ==========================================
# Phase 1: Map (Individual Paper Analysis)
# ==========================================
def analyze_single_paper(paper, related_facts, query, verbose=False, debug=False, use_hf=False):
    """
    MAP FUNCTION: Analyzes ONE paper + its Atomic Facts.
    """
    metadata = paper.get('metadata', {})
    pico = paper.get('pico_en', {})
    
    facts_text = ""
    if related_facts:
        facts_text = "Key Facts from Text:\n" + "\n".join([f"- {f['fact_text']}" for f in related_facts])

    content = f"""Title: {metadata.get('title')}
Intervention: {pico.get('intervention')}
{facts_text}"""

    prompt = f"""Task: Check if the study below answers the question.
If YES, extract the specific drug name and numerical outcome (e.g., %, score change).
If NO or Irrelevant, output "IRRELEVANT".

Question: {query}

Study Data:
{content}

IMPORTANT: Extract numbers ONLY from the "Key Facts from Text" section.
If "Key Facts from Text" is empty, or its facts do not address the question, output "IRRELEVANT".

Output Format:
- Drug Name: [Name]
- Result: [Numbers from Key Facts only]

Answer:"""

    if debug:
        print(f"\n====== DEBUG: Map Prompt ({metadata.get('title','')[:50]}) ======")
        print(prompt)
        print("========================================\n")

    if verbose:
        print(f"   > Analyzing: {metadata.get('title')[:30]}... ({len(related_facts)} facts)")

    # Use Hugging Face or Ollama based on use_hf flag
    if use_hf:
        response = query_huggingface(prompt, max_new_tokens=1024, temperature=0.1)
    else:
        response = query_ollama(prompt)

    if debug:
        print(f"\n====== DEBUG: Map Response ({metadata.get('title','')[:50]}) ======")
        print(response)
        print("========================================\n")

    if "IRRELEVANT" in response.upper() or len(response) < 10:
        return None
    
    if verbose: print(f"     -> Extracted: {response.replace(chr(10), ' ' )[:50]}...")
    return response

# ==========================================
# Phase 2: Reduce (Synthesis)
# ==========================================
def _truncate_at_repetition(text):
    """Remove trailing repetition from LLM output.
    Stops at the first line that has already appeared in the response."""
    lines = text.split('\n')
    seen = set()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped in seen:
            break   # first repeated non-empty line — stop here
        result.append(line)
        if stripped:
            seen.add(stripped)
    return '\n'.join(result).strip()

def synthesize_findings(findings, query_en, debug=False, use_hf=False):
    if not findings:
        return "No relevant evidence was found."

    bullet_points = "\n".join([f"- {f}" for f in findings])

    prompt = f"""You are a medical assistant. Summarize the following findings to answer the user's question.

User Question: {query_en}

Extracted Findings:
{bullet_points}

Instructions:
1. Answer "Yes" or "No" first.
2. List ONLY the specific evidence (Drug names and Numbers) that appear in the Extracted Findings above.
3. Do NOT add information from your own knowledge. If a finding does not address the user's question, omit it.
4. Provide a complete sentence, do not stop in the middle.

Output:"""

    if debug:
        print("\n====== DEBUG: Reduce Prompt ======")
        print(prompt)
        print("==================================\n")

    # Use Hugging Face or Ollama based on use_hf flag
    if use_hf:
        raw = query_huggingface(prompt, max_new_tokens=1024, temperature=0.1)
    else:
        raw = query_ollama(prompt)

    if debug:
        print("\n====== DEBUG: Reduce Response ======")
        print(raw)
        print("====================================\n")

    return _truncate_at_repetition(raw)

# ==========================================
# RAG Main Workflow
# ==========================================
def run_map_reduce_query(query, verbose=False, debug=False, use_cloud=False, use_hf=False):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_qdrant

    # Initialize Qdrant client if not already done (models are loaded via APIs, not locally)
    if search_qdrant.client is None:
        search_qdrant.client, search_qdrant.qdrant_mode = search_qdrant.initialize_qdrant_client(force_cloud=use_cloud)

    print(f"Query (RAG Mode): {query}")

    # 1. 翻訳 & 検索
    query_en = translate_query(query, debug=debug)

    if debug and re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query_en):
        print("[WARNING] Translation failed — query_en still contains Japanese")

    if verbose: print(f"Translated: {query_en}")

    print("1. Searching papers...")
    search_results = search_qdrant.search_medical_papers(query_en, top_k=3)
    papers = search_results['papers']

    if not papers:
        is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query))
        msg = "関連する論文が見つかりませんでした。" if is_japanese else "No relevant papers were found."
        return msg, []

    # 2. Atomic Facts検索
    print("2. Searching atomic facts...")
    paper_ids = [p.get('paper_id') for p in papers]
    # Retrieve top-5 facts per paper to ensure fair representation across papers.
    # A single global limit=10 causes high-fact-count papers to crowd out others.
    all_facts = []
    for pid in paper_ids:
        paper_facts = search_qdrant.search_atomic_facts(query_en, limit=5, paper_ids=[str(pid)])
        all_facts.extend(paper_facts)

    facts_by_paper = {str(pid): [] for pid in paper_ids}
    seen_facts = {str(pid): set() for pid in paper_ids}
    for fact in all_facts:
        pid = str(fact.get('paper_id'))
        text = fact.get('fact_text', '')
        if pid in facts_by_paper and text not in seen_facts[pid]:
            facts_by_paper[pid].append(fact)
            seen_facts[pid].add(text)

    # 3. Mapフェーズ
    print("3. Analyzing each paper (Map phase)...")
    valid_findings = []
    contributing_papers = []
    for paper in papers:
        pid = str(paper.get('paper_id'))
        related_facts = facts_by_paper.get(pid, [])
        result = analyze_single_paper(paper, related_facts, query_en, verbose, debug=debug, use_hf=use_hf)
        if result:
            valid_findings.append(result)
            contributing_papers.append(paper)

    # 4. Reduceフェーズ（英語クエリでプロンプト作成）
    print(f"4. Synthesizing {len(valid_findings)} findings (Reduce phase)...")
    is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query))
    final_answer = synthesize_findings(valid_findings, query_en, debug=debug, use_hf=use_hf)

    # 5. 日本語クエリの場合は回答を日本語に翻訳
    if is_japanese and final_answer:
        print("5. Translating answer to Japanese...")
        final_answer = translate_to_japanese(final_answer, debug=debug)

    return final_answer, contributing_papers

def main():
    parser = argparse.ArgumentParser(description='Query MedGemma with optional RAG')
    parser.add_argument('query', help='Medical question')
    parser.add_argument('--mode', choices=['rag', 'direct'], default='rag', help='Choose "rag" (default) or "direct"')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--debug', action='store_true', help='Print full prompts sent to MedGemma')
    parser.add_argument('--cloud', action='store_true', help='Force Qdrant Cloud usage even if local database exists')
    parser.add_argument('--HF', action='store_true', help='Use Hugging Face Inference API instead of local Ollama')
    args = parser.parse_args()

    if args.mode == 'rag':
        answer, sources = run_map_reduce_query(args.query, verbose=args.verbose, debug=args.debug, use_cloud=args.cloud, use_hf=args.HF)
    else:
        answer = ask_medgemma_direct(args.query, verbose=args.verbose, debug=args.debug, use_hf=args.HF)
        sources = []

    print(f"\nAnswer:\n{answer}")
    if sources:
        print("\n参考論文:")
        for i, p in enumerate(sources, 1):
            meta = p.get('metadata', {})
            print(f"  [{i}] {meta.get('title', p.get('paper_id'))}")
            print(f"      {p.get('paper_id')} | {meta.get('journal', '')} | {meta.get('publication_year', '')}")


if __name__ == '__main__':
    main()

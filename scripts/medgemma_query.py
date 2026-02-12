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

def query_ollama(prompt, model="medgemma", temperature=0.0):
    """Base function to query Ollama"""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_ctx': 4096,
                    'temperature': temperature,
                    # 修正箇所: 生成長を256から1024に拡張し、回答切れを防止
                    'num_predict': 1024,
                    'repetition_penalty': 1.1,
                }
            },
            timeout=120 # 生成が長くなるためタイムアウトも延長
        )
        response.raise_for_status()
        return response.json().get('response', '').strip()
    except Exception as e:
        print(f"Error querying Ollama: {e}")
        return ""

def translate_query(query):
    """Translate JP query to EN"""
    if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query):
        return query

    # 翻訳プロンプトを少し強化（余計な解説を出させないようにする）
    prompt = f"""Task: Translate this Japanese medical question to English.
Rules: Output ONLY the English translation text. No explanations.

Japanese: {query}
English:"""
    
    # 翻訳時は余計なことを言わないよう短めに制限
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': "medgemma",
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': 128, 
                    'temperature': 0.0
                }
            },
            timeout=30
        )
        text = response.json().get('response', '').strip()
        # "The question is..." などの余計な枕詞がついた場合、改行で区切って最初の行だけ取るなど簡易クリーニング
        if "\n" in text:
            text = text.split("\n")[0]
        # Explanationなどが残っていたら削除する正規表現処理などを入れても良いが、まずはシンプルに
        return text
    except:
        return query

# ==========================================
# Direct Mode (No RAG)
# ==========================================
def ask_medgemma_direct(query, verbose=False):
    """
    Directly ask MedGemma without retrieving external documents.
    Useful for checking the model's internal knowledge.
    """
    print(f"Query (Direct Mode): {query}")
    
    q_en = translate_query(query)
    if verbose and q_en != query:
        print(f"Translated: {q_en}")

    prompt = f"""You are a medical AI assistant. Answer the following question based on your internal knowledge.
If you are unsure, say "I don't know".

Question: {q_en}

Answer:"""
    
    start_time = time.time()
    response = query_ollama(prompt, temperature=0.1)
    duration = (time.time() - start_time) * 1000
    
    return f"{response}\n(Time: {duration:.0f}ms)"

# ==========================================
# Phase 1: Map (Individual Paper Analysis)
# ==========================================
def analyze_single_paper(paper, related_facts, query, verbose=False):
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
Outcome (Summary): {pico.get('outcome')}
{facts_text}"""

    prompt = f"""Task: Check if the study below answers the question.
If YES, extract the specific drug name and numerical outcome (e.g., %, score change).
If NO or Irrelevant, output "IRRELEVANT".

Question: {query}

Study Data:
{content}

Output Format:
- Drug Name: [Name]
- Result: [Specific numbers from Outcome or Facts]

Answer:"""

    if verbose:
        print(f"   > Analyzing: {metadata.get('title')[:30]}... ({len(related_facts)} facts)")

    response = query_ollama(prompt)
    
    if "IRRELEVANT" in response.upper() or len(response) < 10:
        return None
    
    if verbose: print(f"     -> Extracted: {response.replace(chr(10), ' ' )[:50]}...")
    return response

# ==========================================
# Phase 2: Reduce (Synthesis)
# ==========================================
def synthesize_findings(findings, original_query_jp):
    if not findings:
        return "申し訳ありません。関連する有効なエビデンスが見つかりませんでした。"

    bullet_points = "\n".join([f"- {f}" for f in findings])

    prompt = f"""You are a medical assistant. Summarize the following findings to answer the user's question in Japanese.

User Question: {original_query_jp}

Extracted Findings:
{bullet_points}

Instructions:
1. Answer "Yes" or "No" first.
2. List the specific evidence (Drug names and Numbers) from the findings.
3. Use Japanese.
4. Provide a complete sentence, do not stop in the middle.

Output:"""

    return query_ollama(prompt)

# ==========================================
# RAG Main Workflow
# ==========================================
def run_map_reduce_query(query, verbose=False):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_qdrant

    print(f"Query (RAG Mode): {query}")

    # 1. 翻訳 & 検索
    search_query = translate_query(query)
    # 翻訳が長文解説を含んでしまった場合のクリーニング (ログを見て簡易対策)
    if "Explanation:" in search_query:
        search_query = search_query.split("Explanation:")[0].strip()
    if "The translation is:" in search_query:
        search_query = search_query.split("The translation is:")[-1].strip()

    if verbose: print(f"Translated: {search_query}")
    
    print("1. Searching papers...")
    search_results = search_qdrant.search_medical_papers(search_query, top_k=3)
    papers = search_results['papers']
    
    if not papers:
        return "関連する論文が見つかりませんでした。"

    # 2. Atomic Facts検索
    print("2. Searching atomic facts...")
    paper_ids = [p.get('paper_id') for p in papers]
    all_facts = search_qdrant.search_atomic_facts(search_query, limit=10, paper_ids=paper_ids)
    
    facts_by_paper = {str(pid): [] for pid in paper_ids}
    for fact in all_facts:
        pid = str(fact.get('paper_id'))
        if pid in facts_by_paper:
            facts_by_paper[pid].append(fact)

    # 3. Mapフェーズ
    print("3. Analyzing each paper (Map phase)...")
    valid_findings = []
    for paper in papers:
        pid = str(paper.get('paper_id'))
        related_facts = facts_by_paper.get(pid, [])
        result = analyze_single_paper(paper, related_facts, search_query, verbose)
        if result:
            valid_findings.append(result)

    # 4. Reduceフェーズ
    print(f"4. Synthesizing {len(valid_findings)} findings (Reduce phase)...")
    final_answer = synthesize_findings(valid_findings, query)

    return final_answer

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('query', help='Medical question')
    parser.add_argument('--mode', choices=['rag', 'direct'], default='rag', help='Choose "rag" (default) or "direct"')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    if args.mode == 'rag':
        answer = run_map_reduce_query(args.query, verbose=args.verbose)
    else:
        answer = ask_medgemma_direct(args.query, verbose=args.verbose)
        
    print(f"\nAnswer:\n{answer}")

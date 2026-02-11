#!/usr/bin/env python3
"""
MedGemma Query Module
Standalone module for querying local Ollama MedGemma model
Can be imported by other scripts or run directly
"""

import requests
import json
import time
import argparse


def query_ollama(prompt, model="medgemma", temperature=0.1, timeout=120, stream=False):
    """
    Query local Ollama MedGemma model
    
    Args:
        prompt: Input prompt for the model
        model: Model name (default: "medgemma")
        temperature: Temperature for generation (default: 0.1 for accuracy)
        timeout: Timeout in seconds (default: 120)
        stream: Whether to stream responses (default: False)
    
    Returns:
        dict with 'response', 'duration_ms', 'error'
    """
    start_time = time.time()
    
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': stream,
                'options': {
                    'num_ctx': 8192,
                    'temperature': temperature,
                    'num_predict': 512,
                }
            },
            timeout=timeout
        )
        
        response.raise_for_status()
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if stream:
            full_response = ""
            for chunk in response.iter_lines():
                if chunk:
                    try:
                        chunk_json = json.loads(chunk)
                        full_response += chunk_json.get('response', '')
                    except json.JSONDecodeError:
                        continue
            return {
                'response': full_response,
                'duration_ms': elapsed_ms,
                'error': None
            }
        else:
            result = response.json()
            return {
                'response': result.get('response', ''),
                'duration_ms': elapsed_ms,
                'error': None
            }
            
    except requests.exceptions.Timeout:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            'response': '',
            'duration_ms': elapsed_ms,
            'error': f'Timeout after {timeout}s'
        }
    except requests.exceptions.ConnectionError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            'response': '',
            'duration_ms': elapsed_ms,
            'error': f'Connection error: {str(e)}'
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            'response': '',
            'duration_ms': elapsed_ms,
            'error': f'Error: {str(e)}'
        }


def translate_query_to_english(query, model="medgemma", timeout=30):
    """
    Translate Japanese medical query to English using MedGemma
    
    Args:
        query: Japanese query string
        model: Model name (default: "medgemma")
        timeout: Timeout in seconds (default: 30 for quick translation)
    
    Returns:
        dict with 'translation', 'duration_ms', 'error'
    """
    prompt = f"""Translate this Japanese medical question to English. Output ONLY the English translation, no explanations or additional text.

Japanese: {query}
English:"""
    
    result = query_ollama(
        prompt=prompt,
        model=model,
        temperature=0.1,
        timeout=timeout
    )
    
    if result['error']:
        return {
            'original': query,
            'translation': query,
            'duration_ms': result['duration_ms'],
            'error': result['error']
        }
    
    translation = result['response'].strip()
    
    # クリーンアップ：余計なテキストを削除
    translation = translation.replace('English:', '').strip()
    translation = translation.replace('The English translation is:', '').strip()
    translation = translation.replace('The translation is:', '').strip()
    translation = translation.replace('"', '').strip()
    translation = translation.replace("'", '').strip()
    
    # 改行で区切って最初の有効な行を使用
    lines = translation.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('Japanese:') and not line.startswith('The '):
            clean_lines.append(line)
    
    if clean_lines:
        translation = clean_lines[0]
    
    # 文で終わらない場合は補完
    if translation and not translation.endswith('?') and not translation.endswith('.'):
        translation += '?'
    
    return {
        'original': query,
        'translation': translation,
        'duration_ms': result['duration_ms'],
        'error': None
    }


def ask_medgemma_direct(query, model="medgemma", temperature=0.1, timeout=120, verbose=False):
    """
    Query MedGemma directly without retrieval (baseline comparison)
    
    Args:
        query: User question
        model: Model name (default: "medgemma")
        temperature: Temperature (default: 0.1 for accuracy)
        timeout: Timeout in seconds (default: 120)
        verbose: Show detailed information (default: False)
    
    Returns:
        dict with answer, timing, error
    """
    prompt = f"""Answer the following medical question to the best of your ability. Be concise and focus on evidence-based information.

Question: {query}

Provide a structured answer with:
1. Main finding
2. Key evidence points
3. Any limitations or caveats
4. Sources if available (if you know relevant studies)

Answer:"""

    result = query_ollama(
        prompt=prompt,
        model=model,
        temperature=temperature,
        timeout=timeout
    )
    
    return {
        'mode': 'direct',
        'query': query,
        'answer': result['response'],
        'duration_ms': result['duration_ms'],
        'error': result['error']
    }


def build_prompt_with_qdrant(papers, atomic_facts, query, language='en', verbose=False):
    """
    Build prompt for MedGemma using retrieved Qdrant data
    
    Args:
        papers: List of retrieved papers with PICO and metadata
        atomic_facts: List of relevant atomic facts
        query: Original user query
        language: Query language ('en' or 'ja')
        verbose: Show detailed evidence information
    
    Returns:
        Formatted prompt string
    """
    
    # Build papers summary
    if verbose:
        print("\n検索された論文詳細:")
        for i, paper in enumerate(papers, 1):
            metadata = paper.get('metadata', {})
            pico = paper.get('pico_en', {})
            print(f"\n論文 {i}:")
            print(f"  PMID: {paper.get('paper_id', 'Unknown')}")
            print(f"  Title: {metadata.get('title', 'Unknown')}")
            print(f"  Journal: {metadata.get('journal', 'Unknown')} ({metadata.get('publication_year', 'Unknown')})")
            print(f"  Score: {paper.get('score', 'N/A')}")
            print(f"  PICO Patient: {pico.get('patient', 'N/A')}")
            print(f"  PICO Intervention: {pico.get('intervention', 'N/A')}")
            print(f"  PICO Outcome: {pico.get('outcome', 'N/A')}")
        
        print(f"\nアトミックファクト ({len(atomic_facts)} 件):")
        for i, fact in enumerate(atomic_facts[:5], 1):
            print(f"  {i+1}. {fact}")
    
    papers_summary = ""
    for i, paper in enumerate(papers[:3], 1):
        metadata = paper.get('metadata', {})
        pico = paper.get('pico_en', {})
        
        papers_summary += f"""Paper {i}: {metadata.get('title', 'Unknown')}
PMID: {paper.get('paper_id', 'Unknown')}
Patient: {pico.get('patient', 'N/A')}
Intervention: {pico.get('intervention', 'N/A')}
Outcome: {pico.get('outcome', 'N/A')}

"""
    
    facts_summary = "\n".join(f"• {fact}" for fact in atomic_facts[:5])
    
    if language == 'ja':
        template = f"""以下の医療エビデンスに基づいて、質問に簡潔に回答してください。

回答のガイドライン:
- 結論を1つの段落で簡潔に述べる（100文字以内）
- 重要ポイントを3〜5個の箇条書きでまとめる
- 繰り返しを避け、新しい情報だけを追加する

質問: {query}

関連論文:
{papers_summary}

主要な発見:
{facts_summary}

回答:"""
    else:
        template = f"""Based on the following medical evidence, answer the question concisely.

Query: {query}

Relevant Papers:
{papers_summary}

Key Findings:
{facts_summary}

Answer:"""
    
    return template


def ask_medgemma_with_qdrant(papers, atomic_facts, query, language='en', model="medgemma", temperature=0.1, timeout=120, verbose=False):
    """
    Query MedGemma with Qdrant retrieval (RAG - Retrieval Augmented Generation)
    
    Args:
        papers: List of retrieved papers from Qdrant
        atomic_facts: List of retrieved atomic facts
        query: Original user query
        language: Query language ('en' or 'ja')
        model: Model name (default: "medgemma")
        temperature: Temperature (default: 0.1)
        timeout: Timeout in seconds (default: 120)
        verbose: Show detailed evidence information (default: False)
    
    Returns:
        dict with answer, timing, retrieved_context, error
    """
    prompt = build_prompt_with_qdrant(papers, atomic_facts, query, language, verbose=verbose)
    
    result = query_ollama(
        prompt=prompt,
        model=model,
        temperature=temperature,
        timeout=timeout
    )
    
    return {
        'mode': 'qdrant_augmented',
        'query': query,
        'answer': result['response'],
        'duration_ms': result['duration_ms'],
        'retrieved_papers_count': len(papers),
        'retrieved_facts_count': len(atomic_facts),
        'error': result['error']
    }


def run_rag_query(query, verbose=False):
    """RAGモード: Qdrant検索 → MedGemma生成
    
    日本語クエリの場合は、まずMedGemmaで英語に翻訳してから検索を実行
    （SapBERTは英語訓練済みのため、英語クエリで高精度な検索が可能）
    """
    import os, sys
    import re
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_qdrant  # lazy import
    
    # 言語検出
    is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query))
    language = 'ja' if is_japanese else 'en'
    
    # 日本語の場合は英語に翻訳して検索
    search_query = query
    if is_japanese:
        print("0. 日本語クエリを英語に翻訳...")
        translation_result = translate_query_to_english(query)
        if translation_result.get('error'):
            print(f"   ✗ 翻訳エラー: {translation_result['error']}")
            print(f"   ⚠ 元のクエリで検索を続行")
        else:
            search_query = translation_result['translation']
            if verbose:
                print(f"   ✓ 翻訳完了: {query}")
                print(f"   → 英語: {search_query}")
    
    print("1. Qdrant検索実行...")
    search_results = search_qdrant.search_medical_papers(search_query, top_k=5)
    papers = search_results['papers']
    
    if verbose:
        print(f"   ✓ 言語検出: {language}")
        print(f"   ✓ 検索クエリ: {search_query}")
        print(f"   ✓ 論文数: {len(papers)}")
    
    # 上位3論文のpaper_idsを取得して、関連性の高いatomic factsのみを取得
    paper_ids = [p.get('paper_id') for p in papers[:3]]
    
    print("2. Atomic Facts検索実行...")
    facts_raw = search_qdrant.search_atomic_facts(search_query, limit=5, paper_ids=paper_ids)
    atomic_facts = [f['fact_text'] for f in facts_raw]  # 文字列リストに変換
    
    if verbose:
        print(f"   ✓ アトミックファクト数: {len(atomic_facts)}")
    
    print("3. MedGemma生成実行...")
    # 回答は元の言語で生成（日本語クエリなら日本語で回答）
    return ask_medgemma_with_qdrant(papers, atomic_facts, query, language=language, verbose=verbose)


def compare_approaches(query, model="medgemma", verbose=False):
    """
    Run both direct and Qdrant-augmented queries for comparison
    
    Args:
        query: User question
        model: Model name (default: "medgemma")
        verbose: Show detailed information (default: False)
    
    Returns:
        dict with direct_result, qdrant_result, comparison
    """
    if verbose:
        print("\n比較モードの詳細ログを有効にしています\n")
    
    print("="*70)
    print(f"Comparing MedGemma Approaches")
    print("="*70)
    print(f"Query: {query}\n")
    
    # Direct query (baseline)
    print("1. Direct Query (No Retrieval)...")
    direct_result = ask_medgemma_direct(query, model=model, verbose=verbose)
    
    if direct_result.get('error'):
        print(f"   ✗ Error: {direct_result.get('error')}")
        return {
            'query': query,
            'direct_result': direct_result,
            'qdrant_result': None,
            'comparison': 'failed'
        }
    
    print(f"   ✓ Answer: {direct_result.get('answer', '')[:100]}...")
    print(f"   ✓ Time: {direct_result.get('duration_ms', 0):.1f}ms\n")
    
    # Qdrant-augmented query (with retrieval)
    print("2. Qdrant-Augmented Query (RAG)...")
    try:
        qdrant_result = run_rag_query(query, verbose=verbose)
        if qdrant_result.get('error'):
            print(f"   ✗ Error: {qdrant_result.get('error')}")
        else:
            print(f"   ✓ Answer: {qdrant_result.get('answer', '')[:100]}...")
            print(f"   ✓ Time: {qdrant_result.get('duration_ms', 0):.1f}ms")
            print(f"   ✓ Papers: {qdrant_result.get('retrieved_papers_count', 0)}, Facts: {qdrant_result.get('retrieved_facts_count', 0)}\n")
    except Exception as e:
        print(f"   ✗ RAG query failed: {e}")
        qdrant_result = {'error': str(e)}
    
    return {
        'query': query,
        'direct_result': direct_result,
        'qdrant_result': qdrant_result,
        'comparison': 'completed'
    }


def main():
    """Main entry point for direct usage"""
    import sys
    
    parser = argparse.ArgumentParser(description='MedGemma Query Module - Direct and RAG modes')
    parser.add_argument('query', help='Medical question to ask MedGemma')
    parser.add_argument('--mode', choices=['direct', 'rag', 'compare'], default='direct', help='Query mode (default: direct)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed evidence information')
    
    args = parser.parse_args()
    query = args.query
    mode = args.mode
    verbose = args.verbose
    
    if not query:
        print("Error: No query provided")
        parser.print_help()
        return
    
    if mode == 'compare':
        result = compare_approaches(query, verbose=verbose)
    elif mode == 'rag':
        result = run_rag_query(query, verbose=verbose)
    else:
        result = ask_medgemma_direct(query, verbose=verbose)
    
    # Print result
    print(f"\n{'='*70}")
    if result.get('error'):
        print(f"✗ Error: {result.get('error')}")
    else:
        print(f"✓ Mode: {result.get('mode')}")
        print(f"✓ Query: {result.get('query')}")
        if result.get('answer'):
            print(f"✓ Time: {result.get('duration_ms', 0):.1f}ms")
            print(f"\nAnswer:\n{result.get('answer', '')}")
    
    print(f"{'='*70}")


if __name__ == '__main__':
    main()

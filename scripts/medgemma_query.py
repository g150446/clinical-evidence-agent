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
                    'num_ctx': 8192,  # Large context for medical papers
                    'temperature': temperature,
                    'num_predict': 2048,  # Max output tokens
                }
            },
            timeout=timeout
        )
        
        response.raise_for_status()
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if stream:
            # Handle streaming response
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
    for i, paper in enumerate(papers[:3], 1):  # Top 3 papers
        metadata = paper.get('metadata', {})
        pico = paper.get('pico_en', {})
        
        papers_summary += f"""
Paper {i}: {metadata.get('title', 'Unknown')}
PMID: {paper.get('paper_id', 'Unknown')}
Journal: {metadata.get('journal', 'Unknown')} ({metadata.get('publication_year', 'Unknown')})
PICO:
  Patient: {pico.get('patient', 'N/A')}
  Intervention: {pico.get('intervention', 'N/A')}
  Comparison: {pico.get('comparison', 'N/A')}
  Outcome: {pico.get('outcome', 'N/A')}

"""
    
    # Build atomic facts summary
    facts_summary = "\n".join(f"• {fact}" for fact in atomic_facts[:5])  # Top 5 facts
    
    # Language-specific template
    if language == 'ja':
        template = f"""以下の医療エビデンスに基づいて、質問に回答してください。

質問: {query}

関連論文 ({len(papers)} 件):
{papers_summary}

主要な発見:
{facts_summary}

上記のエビデンスを考慮して、質問に対する構造化された回答を提供してください。
1. 主要な発見
2. エビデンスレベル
3. 注意点や制限事項
4. 利益相反情報

回答:"""
    else:  # Default to English
        template = f"""Based on the following medical evidence, answer the question.

Query: {query}

Relevant Papers ({len(papers)} 件):
{papers_summary}

Key Findings (Atomic Facts):
{facts_summary}

Considering the above evidence, provide a structured answer to the query that includes:
1. Main finding
2. Evidence level
3. Any limitations or caveats
4. Conflicts of interest

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
    """RAGモード: Qdrant検索 → MedGemma生成"""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_qdrant  # lazy import
    
    print("1. Qdrant検索実行...")
    search_results = search_qdrant.search_medical_papers(query, top_k=5)
    papers = search_results['papers']
    language = search_results.get('query_language', 'en')
    
    if verbose:
        print(f"   ✓ 言語検出: {language}")
        print(f"   ✓ 論文数: {len(papers)}")
    
    print("2. Atomic Facts検索実行...")
    facts_raw = search_qdrant.search_atomic_facts(query, limit=5)
    atomic_facts = [f['fact_text'] for f in facts_raw]  # 文字列リストに変換
    
    if verbose:
        print(f"   ✓ アトミックファクト数: {len(atomic_facts)}")
    
    print("3. MedGemma生成実行...")
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

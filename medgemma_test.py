#!/usr/bin/env python3
"""
Test script for MedGemma Ollama server
Tests connection and basic medical query capabilities
Supports both test mode and interactive mode
"""

import requests
import json
import time
import sys


def test_ollama_connection():
    """Test if Ollama server is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get('models', [])
            print("✓ Ollama server is running")
            print(f"✓ Available models: {len(models)}")

            # Check if medgemma is available
            medgemma_models = [m for m in models if 'medgemma' in m.get('name', '').lower()]
            if medgemma_models:
                print(f"✓ MedGemma model found: {medgemma_models[0]['name']}")
                return True
            else:
                print("✗ MedGemma model not found")
                return False
        else:
            print(f"✗ Ollama server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to Ollama server at localhost:11434")
        print("  Make sure Ollama is running: ollama serve")
        return False
    except Exception as e:
        print(f"✗ Error checking Ollama: {e}")
        return False


def query_medgemma(prompt, model="medgemma:latest", stream=True):
    """
    Send a query to MedGemma model

    Args:
        prompt: The medical question or prompt
        model: Model name (default: medgemma:latest)
        stream: Whether to stream the response
    """
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }

    print(f"\n{'='*70}")
    print(f"Query: {prompt}")
    print(f"{'='*70}\n")

    try:
        start_time = time.time()

        if stream:
            # Streaming response
            response = requests.post(url, json=payload, stream=True)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        print(chunk['response'], end='', flush=True)
                        full_response += chunk['response']
                    if chunk.get('done', False):
                        print("\n")
                        elapsed = time.time() - start_time
                        print(f"\n{'='*70}")
                        print(f"Response time: {elapsed:.2f} seconds")
                        if 'total_duration' in chunk:
                            print(f"Total duration: {chunk['total_duration'] / 1e9:.2f} seconds")
                        if 'eval_count' in chunk and 'eval_duration' in chunk:
                            tokens = chunk['eval_count']
                            duration = chunk['eval_duration'] / 1e9
                            print(f"Tokens generated: {tokens}")
                            print(f"Tokens/second: {tokens/duration:.2f}")
                        print(f"{'='*70}\n")

            return full_response
        else:
            # Non-streaming response
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            elapsed = time.time() - start_time
            print(result.get('response', ''))
            print(f"\nResponse time: {elapsed:.2f} seconds\n")

            return result.get('response', '')

    except requests.exceptions.RequestException as e:
        print(f"✗ Error querying MedGemma: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


def interactive_mode():
    """
    Interactive mode for asking questions to MedGemma
    """
    print("\n" + "="*70)
    print("MEDGEMMA INTERACTIVE MODE")
    print("="*70 + "\n")

    # Test connection first
    if not test_ollama_connection():
        return

    print("\n" + "="*70)
    print("対話モードを開始します")
    print("質問を入力してください (終了: 'exit', 'quit', 'q')")
    print("="*70 + "\n")

    while True:
        try:
            # Get user input
            question = input("\n質問 > ").strip()

            # Check for exit commands
            if question.lower() in ['exit', 'quit', 'q', '終了', 'やめる']:
                print("\n対話モードを終了します。")
                break

            # Skip empty questions
            if not question:
                continue

            # Query MedGemma
            query_medgemma(question)

        except KeyboardInterrupt:
            print("\n\n対話モードを終了します。")
            break
        except EOFError:
            print("\n\n対話モードを終了します。")
            break
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            continue


def run_test_queries():
    """Run a series of test queries to evaluate MedGemma"""

    test_cases = [
        {
            "name": "Simple Medical Query",
            "prompt": "What are the common symptoms of type 2 diabetes?"
        },
        {
            "name": "Drug Information",
            "prompt": "What is metformin and what is it used for?"
        },
        {
            "name": "Clinical Guideline",
            "prompt": "What are the first-line treatment options for hypertension?"
        }
    ]

    print("\n" + "="*70)
    print("MEDGEMMA OLLAMA TEST SUITE")
    print("="*70 + "\n")

    # Test connection first
    if not test_ollama_connection():
        return

    print("\n" + "="*70)
    print("RUNNING TEST QUERIES")
    print("="*70)

    # Run test queries
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\nTest {i}/{len(test_cases)}: {test_case['name']}")
        query_medgemma(test_case['prompt'])

        # Add a small delay between queries
        if i < len(test_cases):
            time.sleep(1)

    print("\n" + "="*70)
    print("TEST SUITE COMPLETE")
    print("="*70 + "\n")


def print_usage():
    """Print usage information"""
    print("使用方法:")
    print("  python3 medgemma_test.py                # 対話モード (デフォルト)")
    print("  python3 medgemma_test.py -i, --interactive  # 対話モード")
    print("  python3 medgemma_test.py -t, --test         # テストスイート実行")
    print("  python3 medgemma_test.py -h, --help         # ヘルプ表示")


if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        if arg in ['-h', '--help']:
            print_usage()
        elif arg in ['-t', '--test']:
            # Run test suite
            run_test_queries()
        elif arg in ['-i', '--interactive']:
            # Run interactive mode
            interactive_mode()
        else:
            print(f"不明なオプション: {sys.argv[1]}\n")
            print_usage()
    else:
        # Default: interactive mode
        interactive_mode()

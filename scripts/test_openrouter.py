#!/usr/bin/env python3
"""
Simple test script for OpenRouter API using google/gemini-2.5-flash-lite model.
"""

import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables from .env file in project root
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

def test_openrouter():
    """Send a test request to OpenRouter API."""

    # Get API key from environment
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in .env file")
        sys.exit(1)

    # OpenRouter API endpoint
    url = "https://openrouter.ai/api/v1/chat/completions"

    # Request headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Request payload
    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": [
            {
                "role": "user",
                "content": "Hello! This is a test message. Please respond with a brief greeting."
            }
        ]
    }

    print("Sending test request to OpenRouter...")
    print(f"Model: {payload['model']}")
    print(f"Message: {payload['messages'][0]['content']}\n")

    try:
        # Send request
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        # Parse response
        result = response.json()

        # Print response
        print("Response received successfully!")
        print("-" * 50)

        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0]["message"]["content"]
            print(f"Assistant: {message}")
        else:
            print("Unexpected response format:")
            print(result)

        print("-" * 50)

        # Print usage info if available
        if "usage" in result:
            print(f"\nToken usage:")
            print(f"  Prompt tokens: {result['usage'].get('prompt_tokens', 'N/A')}")
            print(f"  Completion tokens: {result['usage'].get('completion_tokens', 'N/A')}")
            print(f"  Total tokens: {result['usage'].get('total_tokens', 'N/A')}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = test_openrouter()
    sys.exit(0 if success else 1)

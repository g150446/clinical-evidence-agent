#!/usr/bin/env python3
"""
Test script to verify the implementation changes
Tests that:
1. 10 papers are retrieved by default
2. Only 3 citations are displayed
3. The "Showing top N out of M papers" message appears
"""

import os
from dotenv import load_dotenv
from pubmed_client import PubMedClient
from evidence_service import EvidenceService
from medgemma_test import format_output_with_citations

# Load environment variables
load_dotenv()

def test_default_values():
    """Test that default values are set correctly"""
    print("Test 1: Verify default max_papers value")
    client = PubMedClient()
    service = EvidenceService(client)
    assert service.max_papers == 10, f"Expected max_papers=10, got {service.max_papers}"
    print("✓ Default max_papers is 10\n")

def test_evidence_retrieval():
    """Test that evidence retrieval works with 10 papers"""
    print("Test 2: Verify evidence retrieval")
    email = os.getenv('NCBI_EMAIL')
    api_key = os.getenv('NCBI_API_KEY')

    client = PubMedClient(email=email, api_key=api_key)
    service = EvidenceService(client, max_papers=10)

    # Simple test query
    question = "What is metformin used for?"
    evidence = service.retrieve_evidence(question)

    if evidence['status'] == 'success':
        paper_count = len(evidence['papers'])
        print(f"✓ Retrieved {paper_count} papers")
        assert paper_count <= 10, f"Expected at most 10 papers, got {paper_count}"
        print(f"✓ Paper count is within expected range\n")
        return evidence
    else:
        print(f"⚠️ Evidence retrieval failed: {evidence['status']}\n")
        return None

def test_citation_display(evidence):
    """Test that citation display is limited to 3 papers"""
    if not evidence or evidence['status'] != 'success':
        print("Test 3: Skipped (no evidence available)\n")
        return

    print("Test 3: Verify citation display limit")

    # Capture output to check the message
    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    # Call format_output_with_citations with display_count=3
    result = format_output_with_citations("Test answer", evidence, display_count=3)

    # Restore stdout
    sys.stdout = old_stdout
    output = captured_output.getvalue()

    # Check that the header contains the expected message
    total_papers = len(evidence['papers'])
    expected_message = f"Showing top 3 out of {total_papers} papers"
    assert expected_message in output, f"Expected '{expected_message}' in output"
    print(f"✓ Citation display header shows: '{expected_message}'")

    # Count how many citations are in the output
    citation_count = output.count("PMID:")
    assert citation_count == min(3, total_papers), f"Expected 3 citations, got {citation_count}"
    print(f"✓ Exactly {citation_count} citations displayed (max 3)\n")

def test_custom_display_count(evidence):
    """Test that custom display_count works"""
    if not evidence or evidence['status'] != 'success':
        print("Test 4: Skipped (no evidence available)\n")
        return

    print("Test 4: Verify custom display_count parameter")

    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    # Call with display_count=2
    result = format_output_with_citations("Test answer", evidence, display_count=2)

    sys.stdout = old_stdout
    output = captured_output.getvalue()

    # Count citations
    citation_count = output.count("PMID:")
    total_papers = len(evidence['papers'])
    expected_count = min(2, total_papers)
    assert citation_count == expected_count, f"Expected {expected_count} citations, got {citation_count}"
    print(f"✓ Custom display_count=2 works correctly ({citation_count} citations)\n")

if __name__ == "__main__":
    print("="*70)
    print("Testing Implementation Changes")
    print("="*70 + "\n")

    try:
        # Test 1: Default values
        test_default_values()

        # Test 2: Evidence retrieval
        evidence = test_evidence_retrieval()

        # Test 3: Citation display limit
        test_citation_display(evidence)

        # Test 4: Custom display count
        test_custom_display_count(evidence)

        print("="*70)
        print("All tests passed!")
        print("="*70)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

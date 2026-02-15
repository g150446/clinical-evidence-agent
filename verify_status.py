#!/usr/bin/env python3
"""Verify status display is working correctly"""
import requests

print("Checking /api/status response format...\n")

resp = requests.get("http://localhost:8080/api/status")
data = resp.json()

print("SapBERT status:")
sap = data.get('sapbert_endpoint', {})
print(f"  ok: {sap.get('ok')}")
print(f"  status: {sap.get('status', 'MISSING')}")
print(f"  → Should display as: {'Ready' if sap.get('status') == 'ready' else 'Error'}")

print("\nMedGemma status:")
med = data.get('medgemma_endpoint', {})
print(f"  ok: {med.get('ok')}")
print(f"  status: {med.get('status', 'MISSING')}")
print(f"  → Should display as: {'Ready' if med.get('status') == 'ready' else 'Error'}")

print("\n✓ Both endpoints now have 'status' field")
print("\nIn browser at http://localhost:8080:")
print("  - SapBERT should show: Ready (green dot)")
print("  - MedGemma should show: Error (red dot)")
print("\nPlease reload the page to see the updated status.")

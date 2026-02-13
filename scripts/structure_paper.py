#!/usr/bin/env python3
"""
Paper Structuring Script
Structure a single obesity treatment paper using LLM
Follows prepare.md 5-layer schema and JSON_ERROR_HANDLING.md guidelines
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Model configuration
MODEL = "google/gemini-2.5-flash-lite"


def compress_full_text_with_llm(full_text, max_length=5000):
    """
    Use LLM to compress full text while preserving important information
    """
    compression_prompt = f"""Compress the following medical paper full text to approximately {max_length} characters.

CRITICAL INSTRUCTIONS:
1. PRESERVE all key information:
   - Study design and methodology
   - Patient population characteristics
   - Intervention details (dosage, duration, frequency)
   - Primary and secondary outcomes with quantitative data
   - Statistical significance (p-values, confidence intervals)
   - Sample sizes
   - Adverse events and safety data

2. OMIT unnecessary details:
   - Background literature review
   - Extended discussion sections
   - Detailed statistical methods
   - Acknowledgments
   - References

3. Maintain medical accuracy:
   - Keep all numbers, units, and measurements
   - Preserve clinical significance
   - Keep dose ranges and follow-up periods
   - Maintain statistical values

4. Return ONLY the compressed text, no explanations or notes.

Full Text ({len(full_text)} characters):
{full_text}

Compressed text:"""

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash-lite",
            messages=[
                {"role": "user", "content": compression_prompt}
            ],
            temperature=0.1,
            max_tokens=6000
        )

        compressed = response.choices[0].message.content

        # Remove any markdown or explanations
        if compressed.startswith('```'):
            compressed = compressed.split('\n', 1)[-1]
        if compressed.endswith('```'):
            compressed = compressed.rsplit('\n', 1)[0]

        compressed = compressed.strip()

        # Ensure max length
        if len(compressed) > max_length:
            compressed = compressed[:max_length]

        print(f"  ! Compressed from {len(full_text)} to {len(compressed)} chars")
        return compressed

    except Exception as e:
        print(f"  ! Compression failed: {e}, using simple truncation")
        return full_text[:max_length] + "\n\n[Simple truncation - LLM compression failed]"

# Prompts
STAGE1_PROMPT = """You are a medical research expert specializing in evidence synthesis. Structure the following paper according to schema below.

NOTE: Do NOT generate atomic_facts_en or embeddings_metadata in this step. They will be generated separately.

IMPORTANT: 
- Return ONLY valid JSON, no markdown formatting
- Use quantitative data with units, confidence intervals, and p-values
- Avoid ambiguous terms (use "24 weeks" not "short term")
- Follow the exact JSON structure provided

 Paper Information:
Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
DOI: {doi}
PMID: {pmid}
Abstract: {abstract}
Full Text: {full_text}
Publication Types: {publication_types}
MeSH Terms: {mesh_terms}

IMPORTANT INSTRUCTIONS:
{source_instruction}
- Include only 3-5 most relevant MeSH terms (intervention, disease, outcome), not all terms
- Keep JSON concise and focused
- Do not list every single MeSH term found in abstract

Return valid JSON in this exact format:
{{
  "paper_id": "PMID_{pmid}",
  "metadata": {{
    "title": "{title}",
    "authors": ["Author1 Last FM", "Author2 Last FM", "et al."],
    "journal": "{journal}",
    "publication_year": {year},
    "doi": "{doi}",
    "study_type": "RCT" or "Meta-Analysis" or "Systematic Review",
    "evidence_level": "1a" (for meta-analysis) or "1b" (for RCT) or "2a" (for systematic review),
    "sample_size": {sample_size_from_text},
    "mesh_terms": ["D00XXXXX", "D00YYYYY"]
  }},
  "language_independent_core": {{
    "pico_en": {{
      "patient": "Detailed patient characteristics with quantitative data",
      "intervention": "Intervention details with dosage and duration",
      "comparison": "Comparison group details",
      "outcome": "Primary outcome with quantitative results, 95% CI, p-value"
    }},
    "quantitative_data": {{
      "primary_outcome": {{
        "metric": "outcome_measure",
        "intervention_group": {{"mean": numeric_value, "sd": numeric_value, "n": sample_n}},
        "control_group": {{"mean": numeric_value, "sd": numeric_value, "n": sample_n}},
        "difference": numeric_difference,
        "ci_95": [lower_value, upper_value],
        "p_value": "p_value_string"
      }}
    }}
  }},
  "multilingual_interface": {{
    "generated_questions": {{
      "en": [
        "Question 1 in natural English",
        "Question 2...",
        ...
      ]
    }},
    "mesh_terminology": {{
      "D00XXXXX": {{
        "preferred_en": "Preferred English term",
        "synonyms": {{
          "en": ["Synonym1", "Synonym2"]
        }}
      }}
    }}
  }},
  "limitations": {{
    "study_limitations": [
      "Specific limitation with quantitative detail (e.g., '24-week follow-up')"
    ],
    "author_noted_constraints": [
      "Limitations noted by authors"
    ],
    "grade_certainty": "high" or "moderate" or "low",
    "generalizability_notes": "Notes on applicability to other populations",
    "conflicts_of_interest": "Funding sources, author disclosures"
  }},
  "cross_references": {{
    "supports": [],
    "contradicts": [],
    "extends": [],
    "superseded_by": null
  }}
}}

Rules for each layer:

**Layer A: PICO (English only)**
- Extract exact quantitative data from abstract
- Include sample size, means, standard deviations, confidence intervals, p-values
- Preserve original terminology
- Avoid vague descriptions

**Layer C: Generated Questions (English only)**
- Generate 10-20 questions in English
- Use natural, user-facing language (not mechanical translation)
- Cover: efficacy, safety, duration, comparisons, side effects

**Layer D: Limitations**
- List study limitations with specific quantitative details
- Include author-noted constraints
- Assign GRADE certainty (high/moderate/low)
- Note conflicts of interest and funding sources

**Layer E: Cross References**
- Leave empty arrays [] for now (will be filled later)

**MeSH Terminology**
- Map ONLY 3-5 most relevant MeSH IDs to English synonyms
- Include English terms for key concepts (intervention, disease, outcome)
- Do NOT include every single MeSH term

Return ONLY the JSON object, no markdown or explanation."""


STAGE2_PROMPT = """You are a medical research expert. Generate atomic facts and embeddings metadata for the following paper.

Paper Information:
Title: {title}
PMID: {pmid}
Abstract: {abstract}
Full Text: {full_text}

The following questions have already been generated for this paper:

English Questions:
{questions_en}

PICO (already extracted):
{pico_en}

YOUR TASK: Generate atomic_facts_en and embeddings_metadata.

CRITICAL RULES FOR atomic_facts_en:
1. Create 10-20 facts that collectively ANSWER the generated questions above
2. Each fact must be a SINGLE, SELF-CONTAINED sentence that is understandable WITHOUT any other context
3. NEVER use "The study", "The participants", "The trial", "The authors" as the sole subject
4. ALWAYS include in each fact: (1) the specific intervention name and dosage, (2) the condition/population, and (3) the PMID
5. Each fact must pass the "isolation test": reading ONLY that one sentence, the reader must know WHAT study, WHAT intervention, WHAT population, and WHAT was measured
6. After writing facts that answer the questions, add additional facts for important information NOT covered by any question (e.g., dropout rates, demographic details, safety data)
7. Include quantitative data (numbers, units, confidence intervals, p-values) wherever available

Examples:
- BAD:  "The mean age of participants was 56 years."
- GOOD: "In the semaglutide 2.4mg trial for obesity with knee osteoarthritis (PMID_39476339), the mean age of participants was 56 years."
- BAD:  "The reduction was statistically significant (p<0.001)."
- GOOD: "The body weight reduction with semaglutide 2.4mg vs placebo was statistically significant (p<0.001) in the 68-week RCT (PMID_39476339)."
- BAD:  "Gastrointestinal disorders were the most common reason for discontinuation."
- GOOD: "Gastrointestinal disorders were the most common reason for trial discontinuation in the semaglutide 2.4mg group in the obesity/knee osteoarthritis trial (PMID_39476339)."

Return ONLY valid JSON in this exact format:
{{
  "atomic_facts_en": [
    "Self-contained fact 1 answering a generated question, with intervention name, condition, PMID, and quantitative data",
    "Self-contained fact 2...",
    ...
  ],
    "embeddings_metadata": {{
    "sapbert_targets": [
      "PICO combined text for SapBERT embedding (copy from PICO data above)",
      "Each atomic fact listed individually for SapBERT embedding"
    ],
    "multilingual_e5_targets": [
      "passage: PICO combined text with passage: prefix",
      "query: Each English question with query: prefix"
    ]
  }}
}}

Return ONLY the JSON object, no markdown or explanation."""


def clean_llm_json_response(content):
    """Extract and clean JSON from LLM response"""
    if content is None:
        raise ValueError("Empty response from LLM")
    
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith('```json'):
        content = content[7:]
    elif content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()

    # Remove control characters
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)

    # Remove system-reminder injection
    if '<system-reminder>' in content or '</system-reminder>' in content:
        print(f"  ! Warning: system-reminder tags detected in response")
        content = re.sub(r'<system-reminder>.*?</system-reminder>', '', content, flags=re.DOTALL)
        content = content.strip()

    return json.loads(content)


def safe_write_json(data, filepath):
    """Safely write JSON with validation"""
    temp_path = str(filepath) + '.tmp'
    try:
        # Write to temporary file
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Validate by reading
        with open(temp_path, 'r', encoding='utf-8') as f:
            json.load(f)
        
        # Rename to final file
        import shutil
        shutil.move(temp_path, str(filepath))
        return True
    except Exception as e:
        print(f"Error writing JSON: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def structure_paper(paper_data, max_retries=3):
    """Structure a single paper using LLM in 2 stages"""
    
    # === 前処理（既存のまま） ===
    abstract_text = paper_data.get('abstract', '')
    full_text = paper_data.get('full_text', '')
    sample_size = extract_sample_size(abstract_text)

    if full_text and len(full_text) > 5000:
        print(f"  ! Full text is {len(full_text)} chars, compressing to preserve key information...")
        full_text = compress_full_text_with_llm(full_text, max_length=5000)

    # source_instruction の準備（既存のまま）
    if full_text and full_text.strip():
        source_instruction = "Use the FULL TEXT for comprehensive PICO extraction, detailed atomic facts, and accurate quantitative data extraction."
    else:
        source_instruction = "Full text is NOT AVAILABLE. Use the ABSTRACT ONLY. Note that limited information may affect accuracy and completeness of PICO extraction and atomic facts. Focus on extracting available information from the abstract."

    # authors_str の準備（既存のまま）
    authors_list = paper_data.get('authors', [])
    if isinstance(authors_list, list) and len(authors_list) > 0:
        if isinstance(authors_list[0], dict):
            author_names = []
            for author in authors_list[:3]:
                last_name = author.get('last_name', '')
                first_initial = author.get('initials', '')
                if last_name and first_initial:
                    author_names.append(f"{first_initial} {last_name}")
                elif last_name:
                    author_names.append(last_name)
            authors_str = ', '.join(author_names)
    # Handle empty list case explicitly
    if not authors_list or len(authors_list) == 0:
        authors_str = ''
    elif isinstance(authors_list, list):
        authors_str = ', '.join(authors_list)
    else:
        authors_str = str(authors_list)

    # =============================================
    # Stage 1: PICO, Questions, Limitations 等の生成
    # =============================================
    print(f"  Stage 1: Generating PICO, questions, limitations...")
    
    stage1_prompt = STAGE1_PROMPT.format(
        title=paper_data.get('title', ''),
        authors=authors_str,
        journal=paper_data.get('journal', ''),
        year=paper_data.get('year', 0),
        doi=paper_data.get('doi', ''),
        pmid=paper_data.get('pmid', ''),
        abstract=paper_data.get('abstract', ''),
        full_text=full_text,
        source_instruction=source_instruction,
        publication_types=', '.join(paper_data.get('publication_types', [])),
        mesh_terms=', '.join(paper_data.get('mesh_terms', [])),
        sample_size_from_text=sample_size
    )

    stage1_result = None
    for attempt in range(max_retries):
        try:
            print(f"    Stage 1 attempt {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a medical research expert. Return only valid JSON."},
                    {"role": "user", "content": stage1_prompt}
                ],
                temperature=0.1,
                max_tokens=16384
            )
            content = response.choices[0].message.content
            
            stage1_result = clean_llm_json_response(content)
            print(f"    ✓ Stage 1 complete")
            break
        except json.JSONDecodeError as e:
            print(f"    ✗ Stage 1 JSON error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"    ✗ Stage 1 error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    if not stage1_result:
        print(f"  ✗ Stage 1 failed after {max_retries} attempts")
        return None

    # =============================================
    # Stage 2: Atomic Facts + Embeddings Metadata 生成
    # =============================================
    print(f"  Stage 2: Generating atomic facts based on generated questions...")

    # Stage 1 の結果から質問とPICOを取得
    multilingual_interface = stage1_result.get('multilingual_interface', {})
    if not isinstance(multilingual_interface, dict):
        multilingual_interface = {}
    generated_questions = multilingual_interface.get('generated_questions', {})
    if not isinstance(generated_questions, dict):
        generated_questions = {}
    generated_questions_en = generated_questions.get('en', [])
    # Handle case where questions_en might be None or empty
    if not generated_questions_en or len(generated_questions_en) == 0:
        questions_en = []
    else:
        questions_en = generated_questions_en
    language_independent_core = stage1_result.get('language_independent_core', {})
    if not isinstance(language_independent_core, dict):
        language_independent_core = {}
    pico_en = language_independent_core.get('pico_en', {})

    stage2_prompt = STAGE2_PROMPT.format(
        title=paper_data.get('title', ''),
        pmid=paper_data.get('pmid', ''),
        abstract=paper_data.get('abstract', ''),
        full_text=full_text,
        questions_en='\n'.join(f"  - {q}" for q in questions_en),
        pico_en=json.dumps(pico_en, indent=2, ensure_ascii=False)
    )

    stage2_result = None
    for attempt in range(max_retries):
        try:
            print(f"    Stage 2 attempt {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a medical research expert. Return only valid JSON. IMPORTANT: Every atomic_facts_en entry must be a fully self-contained sentence that includes the intervention name, condition, and PMID. Never use 'The study' or 'The participants' without specifying which study."},
                    {"role": "user", "content": stage2_prompt}
                ],
                temperature=0.1,
                max_tokens=8192
            )
            content = response.choices[0].message.content
            
            stage2_result = clean_llm_json_response(content)
            print(f"    ✓ Stage 2 complete")
            break
        except json.JSONDecodeError as e:
            print(f"    ✗ Stage 2 JSON error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"    ✗ Stage 2 error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    if not stage2_result:
        print(f"  ✗ Stage 2 failed after {max_retries} attempts")
        return None

    # =============================================
    # Stage 1 + Stage 2 の結果をマージ
    # =============================================
    print(f"  Merging Stage 1 + Stage 2 results...")

    # atomic_facts_en を language_independent_core に追加
    if 'language_independent_core' not in stage1_result or not isinstance(stage1_result['language_independent_core'], dict):
        stage1_result['language_independent_core'] = {}
    stage1_result['language_independent_core']['atomic_facts_en'] = stage2_result.get('atomic_facts_en', [])

    # embeddings_metadata を追加
    stage1_result['embeddings_metadata'] = stage2_result.get('embeddings_metadata', {})

    print(f"  ✓ Successfully structured (2-stage)")
    return stage1_result



def extract_sample_size(text):
    """Extract sample size from text"""
    if not text:
        return 0
    
    # Look for patterns like "n=500", "500 participants", "1961 adults"
    patterns = [
        r'n\s*=\s*(\d+)',
        r'(\d+)\s*(?:participants|subjects|patients|adults)',
        r'(?:participants|subjects|patients|adults)\s*[=:]\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return 0


def main():
    """Main entry point"""
    if len(sys.argv) < 4:
        print("Usage: python3 structure_paper.py <domain> <subsection> <pmid>")
        print("  domains: pharmacologic, surgical, lifestyle")
        print("  subsections: glp1_receptor_agonists, guidelines_and_reviews, novel_agents (pharmacologic)")
        print("              procedures_and_outcomes, metabolic_effects, complications_safety (surgical)")
        print("              dietary_interventions, physical_activity, behavioral_therapy (lifestyle)")
        print("  example: python3 structure_paper.py pharmacologic glp1_receptor_agonists 37952131")
        return
    
    domain = sys.argv[1]
    subsection = sys.argv[2]
    pmid = sys.argv[3]
    
    # Validate domain
    if domain not in ['pharmacologic', 'surgical', 'lifestyle']:
        print(f"Invalid domain: {domain}")
        return
    
    # Validate subsection
    SUBSECTIONS = {
        'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
        'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
        'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
    }
    if subsection not in SUBSECTIONS.get(domain, []):
        print(f"Invalid subsection for {domain}: {subsection}")
        print(f"Valid subsections: {SUBSECTIONS[domain]}")
        return
    
    # Load raw paper data
    raw_file = Path(f'data/obesity/{domain}/{subsection}/papers.json')
    
    if not raw_file.exists():
        print(f"Raw data file not found: {raw_file}")
        return
    
    with open(raw_file, 'r', encoding='utf-8') as f:
        papers = json.load(f)
    
    # Find paper
    paper = next((p for p in papers if p['pmid'] == pmid), None)
    
    if not paper:
        print(f"Paper PMID {pmid} not found in {domain}/{subsection} papers")
        return
    
    print(f"Structuring paper: PMID_{pmid}")
    print(f"  Title: {paper['title'][:80]}...")
    
    # Structure the paper
    structured_data = structure_paper(paper)
    
    if not structured_data:
        print("Failed to structure paper")
        return
    
    # Save structured data
    output_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"PMID_{pmid}.json"
    
    print(f"Saving to: {output_file}")
    
    if safe_write_json(structured_data, output_file):
        print(f"✓ Successfully saved structured data")
    else:
        print(f"✗ Failed to save structured data")


if __name__ == '__main__':
    main()

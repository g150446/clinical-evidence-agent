#!/usr/bin/env python3
"""
Structure Validation Script
Validate structured paper data against schema requirements
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def validate_paper(paper_file: Path) -> Dict[str, Any]:
    """Validate a single structured paper"""
    
    # Load JSON
    try:
        with open(paper_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {'valid': False, 'error': f'JSON loading error: {e}'}
    
    errors = []
    warnings = []
    
    # Check required top-level fields
    required_fields = ['paper_id', 'metadata', 'language_independent_core', 
                     'multilingual_interface', 'limitations', 'cross_references']
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate paper_id format
    if 'paper_id' in data and not data['paper_id'].startswith('PMID_'):
        errors.append(f"Invalid paper_id format: {data['paper_id']}")
    
    # Validate metadata
    if 'metadata' in data:
        metadata = data['metadata']
        metadata_required = ['title', 'authors', 'journal', 'publication_year', 
                         'doi', 'study_type', 'evidence_level', 'sample_size', 
                         'mesh_terms']
        for field in metadata_required:
            if field not in metadata:
                errors.append(f"metadata missing: {field}")
        
        # Validate evidence_level
        if 'evidence_level' in metadata:
            valid_levels = ['1a', '1b', '2a', '2b', '3a', '3b', '4', '5']
            if metadata['evidence_level'] not in valid_levels:
                errors.append(f"Invalid evidence_level: {metadata['evidence_level']}")
    
    # Validate language_independent_core
    if 'language_independent_core' in data:
        core = data['language_independent_core']
        
        # Check PICO
        if 'pico_en' not in core:
            errors.append("Missing pico_en")
        else:
            pico = core['pico_en']
            pico_required = ['patient', 'intervention', 'comparison', 'outcome']
            for field in pico_required:
                if field not in pico:
                    errors.append(f"pico_en missing: {field}")
                elif not pico[field]:
                    warnings.append(f"pico_en.{field} is empty")
        
        # Check atomic_facts
        if 'atomic_facts_en' not in core:
            errors.append("Missing atomic_facts_en")
        else:
            facts = core['atomic_facts_en']
            if not isinstance(facts, list):
                errors.append("atomic_facts_en should be a list")
            elif len(facts) < 10:
                warnings.append(f"atomic_facts_en has only {len(facts)} facts (recommended 10-20)")
            elif len(facts) > 25:
                warnings.append(f"atomic_facts_en has {len(facts)} facts (recommended 10-20)")
        
        # Check quantitative_data
        if 'quantitative_data' not in core:
            warnings.append("Missing quantitative_data")
        else:
            quant = core['quantitative_data']
            if 'primary_outcome' in quant:
                primary = quant['primary_outcome']
                if 'metric' in primary and 'difference' in primary:
                    pass  # Basic structure OK
                else:
                    errors.append("primary_outcome missing required fields")
    
    # Validate multilingual_interface
    if 'multilingual_interface' in data:
        interface = data['multilingual_interface']
        
        # Check generated_questions
        if 'generated_questions' not in interface:
            errors.append("Missing generated_questions")
        else:
            questions = interface['generated_questions']
            if 'en' not in questions:
                errors.append("Missing generated_questions.en")
            elif not isinstance(questions['en'], list):
                errors.append("generated_questions.en should be a list")
            elif len(questions['en']) < 10:
                warnings.append(f"Only {len(questions['en'])} English questions (recommended 10-20)")
            
            if 'ja' not in questions:
                errors.append("Missing generated_questions.ja")
            elif not isinstance(questions['ja'], list):
                errors.append("generated_questions.ja should be a list")
            elif len(questions['ja']) < 10:
                warnings.append(f"Only {len(questions['ja'])} Japanese questions (recommended 10-20)")
        
        # Check mesh_terminology
        if 'mesh_terminology' in interface:
            terms = interface['mesh_terminology']
            for mesh_id, term_data in terms.items():
                if 'preferred_en' not in term_data:
                    errors.append(f"mesh_terminology[{mesh_id}] missing preferred_en")
                if 'synonyms' not in term_data:
                    errors.append(f"mesh_terminology[{mesh_id}] missing synonyms")
                elif not isinstance(term_data['synonyms'], dict):
                    errors.append(f"mesh_terminology[{mesh_id}].synonyms should be a dict")
    
    # Validate limitations
    if 'limitations' in data:
        lim = data['limitations']
        
        lim_fields = ['study_limitations', 'author_noted_constraints', 
                     'grade_certainty']
        for field in lim_fields:
            if field not in lim:
                errors.append(f"limitations missing: {field}")
        
        if 'grade_certainty' in lim:
            valid_grades = ['high', 'moderate', 'low']
            if lim['grade_certainty'] not in valid_grades:
                errors.append(f"Invalid grade_certainty: {lim['grade_certainty']}")
    
    # Validate cross_references
    if 'cross_references' in data:
        refs = data['cross_references']
        required_refs = ['supports', 'contradicts', 'extends', 'superseded_by']
        for field in required_refs:
            if field not in refs:
                errors.append(f"cross_references missing: {field}")
    
    # Result
    result = {
        'valid': len(errors) == 0,
        'paper_id': data.get('paper_id', 'Unknown'),
        'title': data.get('metadata', {}).get('title', 'Unknown'),
        'errors': errors,
        'warnings': warnings,
        'error_count': len(errors),
        'warning_count': len(warnings)
    }
    
    return result


def validate_domain(domain: str) -> Dict[str, Any]:
    """Validate all papers in a domain (all subsections)"""
    
    SUBSECTIONS = {
        'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
        'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
        'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
    }
    
    if domain not in SUBSECTIONS:
        return {'error': f'Invalid domain: {domain}'}
    
    print(f"\n{'='*70}")
    print(f"Validating domain: {domain}")
    print(f"{'='*70}")
    
    # Find all JSON files across all subsections
    paper_files = []
    total_errors = 0
    total_warnings = 0
    valid_count = 0
    all_results = []
    
    for subsection in SUBSECTIONS[domain]:
        papers_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
        
        if not papers_dir.exists():
            print(f"  Subsection {subsection}: Directory not found, skipping")
            continue
        
        subsection_files = list(papers_dir.glob('PMID_*.json'))
        paper_files.extend(subsection_files)
        
        print(f"  Subsection {subsection}: Found {len(subsection_files)} papers")
    
    if not paper_files:
        return {'error': f'No papers found in {domain}'}
    
    print(f"\nTotal papers to validate: {len(paper_files)}\n")
    
    # Validate each paper
    all_results = []
    total_errors = 0
    total_warnings = 0
    valid_count = 0
    
    for paper_file in sorted(paper_files):
        result = validate_paper(paper_file)
        all_results.append(result)
        
        total_errors += result['error_count']
        total_warnings += result['warning_count']
        
        if result['valid']:
            valid_count += 1
            print(f"✓ {result['paper_id']}: Valid ({result['title'][:50]}...)")
        else:
            print(f"✗ {result['paper_id']}: {result['error_count']} errors ({result['title'][:50]}...)")
            for error in result['errors'][:3]:  # Show first 3 errors
                print(f"    - {error}")
        
        if result['warning_count'] > 0:
            print(f"  ! {result['warning_count']} warnings")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Validation Summary: {domain}")
    print(f"{'='*70}")
    print(f"Total papers: {len(paper_files)}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {len(paper_files) - valid_count}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")
    print(f"{'='*70}\n")
    
    return {
        'domain': domain,
        'total_papers': len(paper_files),
        'valid_count': valid_count,
        'invalid_count': len(paper_files) - valid_count,
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'results': all_results
    }


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 validate_structure.py <domain>")
        print("  domains: pharmacologic, surgical, lifestyle")
        print("  or: 'all' to validate all domains")
        return
    
    domain = sys.argv[1]
    
    if domain == 'all':
        # Validate all domains
        for d in ['pharmacologic', 'surgical', 'lifestyle']:
            validate_domain(d)
    elif domain in ['pharmacologic', 'surgical', 'lifestyle']:
        validate_domain(domain)
    else:
        print(f"Invalid domain: {domain}")


if __name__ == '__main__':
    main()

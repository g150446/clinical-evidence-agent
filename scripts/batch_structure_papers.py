#!/usr/bin/env python3
"""
Batch Paper Structuring Script
Process all papers in a domain (or all domains) with options
"""

import argparse
import json
import time
import sys
import shutil
from pathlib import Path

# Import structure function
sys.path.insert(0, str(Path(__file__).parent))
from structure_paper import structure_paper, safe_write_json


def clear_papers_directory(papers_dir):
    """Delete all structured papers in a directory"""
    if not papers_dir.exists():
        return
    
    file_count = len(list(papers_dir.glob('PMID_*.json')))
    if file_count == 0:
        return
    
    print(f"  ! Deleting {file_count} structured papers from {papers_dir}...")
    
    try:
        shutil.rmtree(papers_dir)
        papers_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Deleted all structured papers")
    except Exception as e:
        print(f"  ✗ Failed to delete: {e}")


def batch_structure_papers(domain, subsection=None, force=False, skip_existing=False):
    """
    Batch process all papers in a domain (or specific subsection)

    Args:
        domain: 'pharmacologic', 'surgical', or 'lifestyle'
        subsection: Optional specific subsection to process (e.g., 'glp1_receptor_agonists')
                   If None, process all subsections in domain
        force: If True, restructure all papers including already processed ones (overwrite)
        skip_existing: If True, skip all already processed papers
    """
    
    # Validate domain
    if domain not in ['pharmacologic', 'surgical', 'lifestyle']:
        print(f"Invalid domain: {domain}")
        return

    # Subsections configuration
    SUBSECTIONS = {
        'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
        'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
        'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
    }

    # Determine which subsections to process
    if subsection:
        if subsection not in SUBSECTIONS[domain]:
            print(f"Invalid subsection for {domain}: {subsection}")
            print(f"Valid subsections: {SUBSECTIONS[domain]}")
            return
        subsections_to_process = [subsection]
    else:
        subsections_to_process = SUBSECTIONS[domain]
    
    # Process all subsections
    total_success = 0
    total_failed = 0
    total_skipped = 0
    
    for subsection in subsections_to_process:
        print(f"\n{'='*70}")
        print(f"Processing Subsection: {domain}/{subsection}")
        print(f"{'='*70}")
        
        # Load raw paper data
        raw_file = Path(f'data/obesity/{domain}/{subsection}/papers.json')
        
        if not raw_file.exists():
            print(f"  No papers.json found, skipping...")
            continue
        
        with open(raw_file, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        
        total_papers = len(papers)
        print(f"  Total papers: {total_papers}")
        
        # Get already processed PMIDs
        papers_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
        papers_dir.mkdir(parents=True, exist_ok=True)
        
        processed_pmids = set()
        for json_file in papers_dir.glob('PMID_*.json'):
            pmid = json_file.stem.replace('PMID_', '')
            processed_pmids.add(pmid)

        already_processed = len(processed_pmids)
        remaining = total_papers - already_processed

        if skip_existing and already_processed > 0:
            print(f"  Skipping {already_processed} already processed papers (--skip-existing)")
            total_skipped += already_processed
            continue

        print(f"  Already processed: {already_processed}")
        print(f"  Remaining to process: {remaining}\n")

        # Process papers in this subsection
        subsection_success = 0
        subsection_failed = 0
        subsection_skipped = 0
        
        for idx, paper in enumerate(papers):
            pmid = paper['pmid']

            # Skip if already processed (unless force is True)
            if pmid in processed_pmids and not force:
                subsection_skipped += 1
                continue

            # Process this paper
            print(f"  [{idx+1}/{total_papers}] Processing PMID_{pmid}")
            print(f"    Title: {paper['title'][:60]}...")

            # Call structure_paper with subsection argument
            from structure_paper import structure_paper

            structured_data = structure_paper(paper)

            if not structured_data:
                print(f"    ✗ Failed to structure paper")
                subsection_failed += 1
                print(f"\n  ✗ Error detected. Deleting all structured papers and retrying...")
                clear_papers_directory(papers_dir)
                # Retry this paper after clearing
                print(f"  -> Retrying PMID_{pmid}...")
                structured_data = structure_paper(paper)

                if not structured_data:
                    print(f"    ✗ Failed to structure paper on retry")
                    subsection_failed += 1
                    # Continue to next paper even if retry fails
                    continue
            else:
                # Save structured data
                output_file = papers_dir / f"PMID_{pmid}.json"

                if safe_write_json(structured_data, output_file):
                    print(f"    ✓ Saved to {output_file}")
                    subsection_success += 1
                else:
                    print(f"    ✗ Failed to save")
                    subsection_failed += 1
            
            # Rate limiting
            if idx < len(papers) - 1:
                time.sleep(1)
        
        total_success += subsection_success
        total_failed += subsection_failed
        total_skipped += subsection_skipped

        print(f"\n  Subsection Summary:")
        print(f"    Processed: {subsection_success + subsection_failed} papers")
        print(f"    Success: {subsection_success}")
        print(f"    Failed: {subsection_failed}")
        print(f"    Skipped: {subsection_skipped}")

    # Overall summary
    print(f"\n{'='*70}")
    print(f"Domain Processing Complete: {domain}")
    print(f"{'='*70}")
    print(f"Total Success: {total_success} papers")
    print(f"Total Failed: {total_failed} papers")
    print(f"Total Skipped: {total_skipped} papers")
    print(f"{'='*70}\n")
    
    return {
        'success': total_success,
        'failed': total_failed,
        'skipped': total_skipped
    }


def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='Batch structure obesity treatment papers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all subsections in pharmacologic domain (only new papers)
  python3 scripts/batch_structure_papers.py pharmacologic

  # Process all subsections in pharmacologic domain (skip existing)
  python3 scripts/batch_structure_papers.py pharmacologic --skip-existing

  # Process all subsections in pharmacologic domain (restructure all papers)
  python3 scripts/batch_structure_papers.py pharmacologic --force

  # Process specific subsection in pharmacologic domain
  python3 scripts/batch_structure_papers.py pharmacologic glp1_receptor_agonists

  # Process all three domains
  python3 scripts/batch_structure_papers.py --all-domains

  # Process all three domains with force restructure
  python3 scripts/batch_structure_papers.py --all-domains --force
"""
    )

    parser.add_argument('domain', nargs='?',
                    help='Domain (pharmacologic, surgical, lifestyle). Use --all-domains to process all domains.')
    parser.add_argument('subsection', nargs='?',
                    help='Specific subsection to process. If omitted, processes all subsections in domain.')
    parser.add_argument('--all-domains', '-a', action='store_true',
                    help='Process all three domains: pharmacologic, surgical, lifestyle')
    parser.add_argument('--force', '-f', action='store_true',
                    help='Force restructure of already processed papers (overwrite existing files)')
    parser.add_argument('--skip-existing', '-s', action='store_true',
                    help='Skip already structured papers (default behavior)')

    args = parser.parse_args()

    # Validate arguments
    if args.all_domains:
        if args.domain or args.subsection:
            parser.print_help()
            print("\nError: --all-domains cannot be used with domain or subsection arguments")
            return

        # Process all domains
        domains = ['pharmacologic', 'surgical', 'lifestyle']

        for domain in domains:
            batch_structure_papers(domain, subsection=None, force=args.force, skip_existing=args.skip_existing)

        return

    else:
        if not args.domain:
            parser.print_help()
            print("\nError: Either <domain> or --all-domains is required")
            return

        # Process domain (or domain + subsection)
        batch_structure_papers(args.domain, subsection=args.subsection, force=args.force, skip_existing=args.skip_existing)


if __name__ == '__main__':
    main()

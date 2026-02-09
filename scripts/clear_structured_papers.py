#!/usr/bin/env python3
"""
Clear all structured paper data (papers/PMID_XXX.json files)
This script will DELETE ALL structured paper data without backup.
Use with caution!
"""

import shutil
import sys
from pathlib import Path

SUBSECTIONS = {
    'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
    'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
    'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
}


def get_all_papers_dirs():
    """Get list of all papers/ directories across all domains"""
    dirs_to_clear = []

    for domain, subsections in SUBSECTIONS.items():
        for subsection in subsections:
            papers_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
            if papers_dir.exists():
                dirs_to_clear.append(papers_dir)

    return dirs_to_clear


def clear_papers_dirs(dirs_to_clear, confirm=True):
    """Clear all specified papers/ directories"""

    # Show summary
    total_files = 0
    for papers_dir in dirs_to_clear:
        json_files = list(papers_dir.glob('PMID_*.json'))
        total_files += len(json_files)

    print(f"\n{'='*70}")
    print(f"WARNING: DESTRUCTIVE OPERATION")
    print(f"{'='*70}")
    print(f"This will delete ALL structured paper files without backup.")
    print(f"Files to delete: {total_files}")
    print(f"\nDirectories:")
    for papers_dir in dirs_to_clear:
        file_count = len(list(papers_dir.glob('PMID_*.json')))
        print(f"  - {papers_dir} ({file_count} files)")

    # Confirmation
    response = input(f"\nType 'DELETE ALL' to confirm deletion: ")
    if response != 'DELETE ALL':
        print("Cancelled.")
        return False

    # Delete directories
    print(f"\nDeleting directories...")
    deleted_count = 0
    for papers_dir in dirs_to_clear:
        try:
            shutil.rmtree(papers_dir)
            print(f"  ✓ Deleted: {papers_dir}")
            deleted_count += 1
        except Exception as e:
            print(f"  ✗ Failed to delete {papers_dir}: {e}")

    # Summary
    print(f"\n{'='*70}")
    print(f"Deletion Complete")
    print(f"{'='*70}")
    print(f"Deleted: {deleted_count}/{len(dirs_to_clear)} directories")

    return deleted_count == len(dirs_to_clear)


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("CLEAR STRUCTURED PAPERS SCRIPT")
    print("="*70)
    print("⚠️  WARNING: This will delete ALL structured data!")
    print("⚠️  No backup will be created!")
    print("⚠️  This operation cannot be undone!")

    # Get all papers directories
    dirs_to_clear = get_all_papers_dirs()

    if len(dirs_to_clear) == 0:
        print("\nNo papers/ directories found to clear.")
        return

    # Clear directories
    success = clear_papers_dirs(dirs_to_clear)

    if not success:
        print("\nWarning: Some directories were not deleted successfully.")
        sys.exit(1)

    print("\n✓ All structured papers deleted.")


if __name__ == '__main__':
    main()

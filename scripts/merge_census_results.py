#!/usr/bin/env python3
"""
Merge Census geocoding results into the geocode cache.

This script reads the census_geocode_results.json file and adds all successful
Census geocoding results to the geocode_cache.json file under the 'census' key.
"""

import json
from pathlib import Path

# Paths
CENSUS_RESULTS_FILE = Path(__file__).parent.parent / 'workspace' / 'lebanonnh' / 'census_geocode_results.json'
GEOCODE_CACHE_FILE = Path(__file__).parent.parent / 'lebdata' / 'lebdata' / 'geocode_cache.json'

def main():
    print("Merging Census geocoding results into geocode cache...")
    print(f"Census results: {CENSUS_RESULTS_FILE}")
    print(f"Geocode cache: {GEOCODE_CACHE_FILE}")
    print()

    # Load Census results
    with open(CENSUS_RESULTS_FILE, 'r') as f:
        census_data = json.load(f)

    census_results = census_data['results']
    stats = census_data['stats']

    print(f"Census results stats:")
    print(f"  Total addresses: {stats['total']}")
    print(f"  Census success: {stats['census_success']} ({stats['census_success']*100//stats['total']}%)")
    print(f"  Census failed: {stats['census_failed']} ({stats['census_failed']*100//stats['total']}%)")
    print()

    # Load existing geocode cache
    with open(GEOCODE_CACHE_FILE, 'r') as f:
        geocode_cache = json.load(f)

    # Initialize census section if it doesn't exist
    if 'census' not in geocode_cache:
        geocode_cache['census'] = {}

    # Count statistics
    added = 0
    updated = 0
    skipped_null = 0
    skipped_exists = 0

    # Merge Census results
    for address, coords in census_results.items():
        if coords is None:
            # Skip null results (failed geocodes)
            skipped_null += 1
            continue

        if address in geocode_cache['census']:
            # Address already exists in census cache
            existing = geocode_cache['census'][address]
            if existing is not None and isinstance(existing, dict) and 'lat' in existing:
                # Already has valid coordinates
                skipped_exists += 1
                continue
            else:
                # Update null or invalid entry
                geocode_cache['census'][address] = coords
                updated += 1
        else:
            # Add new entry
            geocode_cache['census'][address] = coords
            added += 1

    print("Merge results:")
    print(f"  Added new entries: {added}")
    print(f"  Updated entries: {updated}")
    print(f"  Skipped (already exists): {skipped_exists}")
    print(f"  Skipped (null results): {skipped_null}")
    print()

    # Save updated cache
    print(f"Saving updated cache to: {GEOCODE_CACHE_FILE}")
    with open(GEOCODE_CACHE_FILE, 'w') as f:
        json.dump(geocode_cache, f, indent=2)

    print()
    print("Cache update complete!")
    print()
    print("Summary:")
    print(f"  Total census entries now: {len([v for v in geocode_cache['census'].values() if v is not None])}")
    print(f"  Legacy entries: {len(geocode_cache.get('legacy', {}))}")
    print(f"  Nominatim entries: {len(geocode_cache.get('nominatim', {}))}")
    print()
    print("Tip: You can now use the 'census' geocoding source in the web interface!")

if __name__ == '__main__':
    main()

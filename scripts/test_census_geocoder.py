#!/usr/bin/env python3
"""
Test script to compare US Census Geocoder vs Nominatim for Lebanon, NH addresses.

This script reads the parcel_details.csv file and attempts to geocode all unique
addresses using the US Census Geocoding API, then compares results with the
existing Nominatim geocode cache.
"""

import json
import time
import requests
from pathlib import Path
from collections import defaultdict
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
CSV_FILE = Path(__file__).parent.parent / 'workspace' / 'lebanonnh' / 'parcel_details.csv'
NOMINATIM_CACHE = Path(__file__).parent.parent / 'lebdata' / 'lebdata' / 'geocode_cache.json'
OUTPUT_FILE = Path(__file__).parent.parent / 'workspace' / 'lebanonnh' / 'census_geocode_results.json'

# US Census Geocoding API
CENSUS_BASE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def normalize_address(address):
    """Remove unit numbers from addresses to improve geocoding success."""
    import re
    # Remove patterns like "#123", "Unit 5", "APT 2A", etc.
    patterns = [
        r'\s+#[\w-]+$',
        r'\s+Unit\s+[\w-]+$',
        r'\s+APT\s+[\w-]+$',
        r'\s+Apt\s+[\w-]+$',
        r'\s+\d+[A-Z]?$'  # trailing unit numbers
    ]
    normalized = address
    for pattern in patterns:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    return normalized.strip()


def geocode_with_census(address):
    """
    Geocode an address using the US Census Geocoding API.

    Returns:
        dict: {'lat': float, 'lon': float} or None if geocoding fails
    """
    # Try multiple zip codes for Lebanon area
    zip_codes = ['03766', '03756', '03784']

    for zip_code in zip_codes:
        full_address = f"{address}, Lebanon, NH {zip_code}"

        params = {
            'address': full_address,
            'benchmark': 'Public_AR_Current',  # Current address ranges
            'format': 'json'
        }

        try:
            response = requests.get(CENSUS_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check if we got a match
            if data.get('result', {}).get('addressMatches'):
                match = data['result']['addressMatches'][0]
                coords = match['coordinates']
                return {
                    'lat': coords['y'],
                    'lon': coords['x'],
                    'zip': zip_code,
                    'matched_address': match.get('matchedAddress', '')
                }

            # Rate limiting - be nice to the free API
            time.sleep(0.5)

        except Exception as e:
            print(f"Error geocoding {full_address}: {e}")
            time.sleep(1)

    return None


def load_nominatim_cache():
    """Load existing Nominatim geocode cache."""
    if NOMINATIM_CACHE.exists():
        with open(NOMINATIM_CACHE, 'r') as f:
            return json.load(f)
    return {}


def extract_unique_addresses():
    """Extract unique addresses from the parcel details CSV."""
    addresses = set()

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        # Skip header
        next(f)
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                address = parts[1].strip()
                if address:
                    addresses.add(address)

    return sorted(addresses)


def main():
    print("Census Geocoder Test Script for Lebanon, NH")
    print("=" * 70)
    print()

    # Load existing data
    print("Loading Nominatim cache...")
    nominatim_cache = load_nominatim_cache()
    print(f"  Found {len(nominatim_cache)} cached addresses")
    print()

    # Extract addresses
    print("Extracting unique addresses from CSV...")
    addresses = extract_unique_addresses()
    print(f"  Found {len(addresses)} unique addresses")
    print()

    # Statistics
    stats = {
        'total': len(addresses),
        'census_success': 0,
        'census_failed': 0,
        'nominatim_success': 0,
        'nominatim_failed': 0,
        'both_success': 0,
        'only_census': 0,
        'only_nominatim': 0,
        'both_failed': 0
    }

    # Results
    census_results = {}
    comparison = []

    print("Geocoding addresses with US Census API...")
    print("(This will take a while - rate limited to ~2 requests/second)")
    print()

    for i, address in enumerate(addresses, 1):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(addresses)} ({i*100//len(addresses)}%)")

        # Try normalized address first
        normalized = normalize_address(address)

        # Geocode with Census API
        census_result = geocode_with_census(normalized)
        census_results[address] = census_result

        # Check Nominatim cache
        nominatim_result = nominatim_cache.get(address) or nominatim_cache.get(normalized)

        # Update statistics
        if census_result:
            stats['census_success'] += 1
        else:
            stats['census_failed'] += 1

        if nominatim_result and nominatim_result is not None:
            stats['nominatim_success'] += 1
        else:
            stats['nominatim_failed'] += 1

        # Comparison
        if census_result and nominatim_result:
            stats['both_success'] += 1
        elif census_result and not nominatim_result:
            stats['only_census'] += 1
        elif not census_result and nominatim_result:
            stats['only_nominatim'] += 1
        else:
            stats['both_failed'] += 1

        comparison.append({
            'address': address,
            'normalized': normalized if normalized != address else None,
            'census': census_result,
            'nominatim': nominatim_result,
            'census_only': census_result and not nominatim_result,
            'nominatim_only': not census_result and nominatim_result
        })

    print()
    print("Geocoding complete!")
    print()

    # Save results
    output_data = {
        'stats': stats,
        'results': census_results,
        'comparison': comparison
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Results saved to: {OUTPUT_FILE}")
    print()

    # Print statistics
    print("=" * 70)
    print("GEOCODING COMPARISON RESULTS")
    print("=" * 70)
    print()
    print(f"Total addresses:               {stats['total']:4d}")
    print()
    print(f"Census Geocoder:")
    print(f"  Success:                     {stats['census_success']:4d} ({stats['census_success']*100//stats['total']:2d}%)")
    print(f"  Failed:                      {stats['census_failed']:4d} ({stats['census_failed']*100//stats['total']:2d}%)")
    print()
    print(f"Nominatim (OpenStreetMap):")
    print(f"  Success:                     {stats['nominatim_success']:4d} ({stats['nominatim_success']*100//stats['total']:2d}%)")
    print(f"  Failed:                      {stats['nominatim_failed']:4d} ({stats['nominatim_failed']*100//stats['total']:2d}%)")
    print()
    print(f"Comparison:")
    print(f"  Both succeeded:              {stats['both_success']:4d} ({stats['both_success']*100//stats['total']:2d}%)")
    print(f"  Only Census succeeded:       {stats['only_census']:4d} ({stats['only_census']*100//stats['total']:2d}%)")
    print(f"  Only Nominatim succeeded:    {stats['only_nominatim']:4d} ({stats['only_nominatim']*100//stats['total']:2d}%)")
    print(f"  Both failed:                 {stats['both_failed']:4d} ({stats['both_failed']*100//stats['total']:2d}%)")
    print()

    # Show some examples
    if stats['only_census'] > 0:
        print("Sample addresses where Census succeeded but Nominatim failed:")
        count = 0
        for item in comparison:
            if item['census_only']:
                print(f"  - {item['address']}")
                count += 1
                if count >= 5:
                    break
        print()

    if stats['only_nominatim'] > 0:
        print("Sample addresses where Nominatim succeeded but Census failed:")
        count = 0
        for item in comparison:
            if item['nominatim_only']:
                print(f"  - {item['address']}")
                count += 1
                if count >= 5:
                    break
        print()

    # Recommendation
    print("=" * 70)
    print("RECOMMENDATION:")
    print("=" * 70)

    improvement = stats['only_census'] - stats['only_nominatim']

    if improvement > 50:
        print(f"✓ Census Geocoder performs SIGNIFICANTLY better (+{improvement} more addresses)")
        print("  Recommendation: Switch to Census Geocoder")
    elif improvement > 0:
        print(f"✓ Census Geocoder performs slightly better (+{improvement} more addresses)")
        print("  Recommendation: Consider switching to Census Geocoder")
    elif improvement < -50:
        print(f"✗ Nominatim performs SIGNIFICANTLY better (+{abs(improvement)} more addresses)")
        print("  Recommendation: Keep using Nominatim")
    elif improvement < 0:
        print(f"✗ Nominatim performs slightly better (+{abs(improvement)} more addresses)")
        print("  Recommendation: Keep using Nominatim")
    else:
        print("= Both geocoders perform equally well")
        print("  Recommendation: Either is fine; Census is free without rate limits")

    print()


if __name__ == '__main__':
    main()

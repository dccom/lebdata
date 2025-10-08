#!/usr/bin/env python3
"""Flask web application for Lebanon NH assessment data visualization."""

import json
import csv
from pathlib import Path
from flask import Flask, render_template, jsonify
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

app = Flask(__name__)

# Configuration
RETRY_FAILED_GEOCODES = False  # Set to True to retry addresses that previously failed

# Cache for geocoded addresses
GEOCODE_CACHE_FILE = Path(__file__).parent / 'geocode_cache.json'
geocode_cache = {}

# Cache for processed parcels (in-memory only)
parcels_result_cache = None

def load_geocode_cache():
    """Load geocode cache from file."""
    global geocode_cache
    if not geocode_cache and GEOCODE_CACHE_FILE.exists():
        with open(GEOCODE_CACHE_FILE, 'r') as f:
            geocode_cache = json.load(f)
            print(f"Loaded {len(geocode_cache)} addresses from geocode cache")
    elif not geocode_cache:
        print("No geocode cache file found, starting fresh")

def save_geocode_cache():
    """Save geocode cache to file."""
    try:
        print(f"Attempting to save cache to: {GEOCODE_CACHE_FILE}")
        with open(GEOCODE_CACHE_FILE, 'w') as f:
            json.dump(geocode_cache, f, indent=2)
        print(f"Successfully saved {len(geocode_cache)} entries to cache file")
    except Exception as e:
        print(f"ERROR saving cache: {e}")
        import traceback
        traceback.print_exc()

def normalize_address(address):
    """Normalize address for cache lookup (remove unit numbers)."""
    # Remove unit/apartment numbers like #47, APT 2, etc.
    import re
    # Remove patterns like #47, #50, APT 2, UNIT 3, etc.
    normalized = re.sub(r'\s*#?\s*\d+\s*$', '', address)
    normalized = re.sub(r'\s+(APT|UNIT|STE|SUITE)\s+\d+\s*$', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()

def geocode_address(address):
    """Geocode an address to lat/lon, using cache if available."""
    global geocode_cache

    # Try exact match first
    if address in geocode_cache:
        cached_value = geocode_cache[address]
        # If cached value is None (failed geocode) and we're not retrying, skip
        if cached_value is None and not RETRY_FAILED_GEOCODES:
            return None
        # If cached value has coordinates, return it
        if cached_value is not None:
            return cached_value

    # Try normalized version (without unit number)
    normalized = normalize_address(address)
    if normalized != address and normalized in geocode_cache:
        cached_value = geocode_cache[normalized]
        # If cached value is None (failed geocode) and we're not retrying, skip
        if cached_value is None and not RETRY_FAILED_GEOCODES:
            return None
        # Use cached coordinates from base address
        # Also save this specific address variant to cache for faster future lookups
        if cached_value is not None:
            geocode_cache[address] = cached_value
            return cached_value

    # Cache miss - need to geocode
    print(f"Cache miss (will geocode): {address}")

    # Try multiple zip codes for Lebanon area
    zip_codes = [
        ("Lebanon, NH 03766", "Lebanon 03766"),
        ("Lebanon, NH 03756", "Lebanon 03756"),
        ("West Lebanon, NH 03784", "West Lebanon 03784"),
    ]

    try:
        geolocator = Nominatim(user_agent="lebdata-app")

        for location_suffix, location_name in zip_codes:
            full_address = f"{address}, {location_suffix}"
            location = geolocator.geocode(full_address, timeout=10)

            if location:
                result = {'lat': location.latitude, 'lon': location.longitude}
                geocode_cache[address] = result

                # Also cache the normalized version if different
                if normalized != address:
                    geocode_cache[normalized] = result

                save_geocode_cache()
                print(f"Saved {address} to cache as {location_name} (total: {len(geocode_cache)} addresses)")
                time.sleep(1)  # Rate limiting
                return result

            time.sleep(0.5)  # Small delay between attempts

        # No results from any zip code - save null to cache to avoid retrying
        print(f"Nominatim returned no results for: {address} (tried all zip codes)")
        geocode_cache[address] = None
        if normalized != address:
            geocode_cache[normalized] = None
        save_geocode_cache()

    except Exception as e:
        print(f"Error geocoding {address}: {e}")
        # Save null to cache to avoid retrying failed geocodes
        geocode_cache[address] = None
        save_geocode_cache()

    return None

def load_parcel_data():
    """Load parcel data from CSV."""
    # Path from lebdata/lebdata/app.py to vgsi/workspace/lebanonnh/parcel_details.csv
    csv_path = Path(__file__).parent.parent.parent / 'workspace' / 'lebanonnh' / 'parcel_details.csv'

    parcels = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Calculate percent change in assessment
            try:
                assessment_2025 = float(row['assessment_2025'].replace('$', '').replace(',', '')) if row['assessment_2025'] else 0
                assessment_2024 = float(row['assessment_2024'].replace('$', '').replace(',', '')) if row['assessment_2024'] else 0

                if assessment_2024 > 0:
                    pct_change = ((assessment_2025 - assessment_2024) / assessment_2024) * 100
                else:
                    pct_change = 0
            except (ValueError, ZeroDivisionError):
                pct_change = 0

            row['pct_change'] = round(pct_change, 2)
            parcels.append(row)

    return parcels

@app.route('/')
def index():
    """Render the main map page."""
    return render_template('index.html')

@app.route('/api/parcels')
def get_parcels():
    """API endpoint to get parcel data with geocoding."""
    global parcels_result_cache

    # If we have cached results, return them immediately
    if parcels_result_cache is not None:
        print(f"Returning {len(parcels_result_cache)} parcels from result cache")
        return jsonify(parcels_result_cache)

    try:
        load_geocode_cache()
        parcels = load_parcel_data()

        print(f"Loaded {len(parcels)} parcels from CSV")

        # Geocode addresses (only those not in geocode cache)
        parcels_with_coords = []
        count = 0
        new_geocodes = 0

        for parcel in parcels:
            location = parcel.get('location', '').strip()
            if location:
                was_in_cache = location in geocode_cache
                coords = geocode_address(location)
                if coords:
                    parcel['lat'] = coords['lat']
                    parcel['lon'] = coords['lon']
                    parcels_with_coords.append(parcel)
                    count += 1
                    if not was_in_cache:
                        new_geocodes += 1
                    if count % 100 == 0:
                        print(f"Processed {count} parcels ({new_geocodes} new geocodes)...")

        print(f"Processed {len(parcels_with_coords)} parcels ({new_geocodes} new geocodes)")

        # Save geocode cache (always save since normalization may have added entries)
        save_geocode_cache()

        # Cache the result for future requests
        parcels_result_cache = parcels_with_coords

        return jsonify(parcels_with_coords)
    except Exception as e:
        print(f"Error in get_parcels: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

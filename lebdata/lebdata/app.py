#!/usr/bin/env python3
"""Flask web application for Lebanon NH assessment data visualization."""

import json
import csv
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from geopy.geocoders import Nominatim
import requests
import time
from abc import ABC, abstractmethod

app = Flask(__name__)

# Configuration
RETRY_FAILED_GEOCODES = False  # Set to True to retry addresses that previously failed

# Cache for geocoded addresses (organized by source)
GEOCODE_CACHE_FILE = Path(__file__).parent / 'geocode_cache.json'
geocode_cache = {}

# Cache for processed parcels (in-memory only)
parcels_result_cache = {}  # Key: source combo, Value: parcel list

def load_geocode_cache():
    """Load geocode cache from file."""
    global geocode_cache
    if not geocode_cache and GEOCODE_CACHE_FILE.exists():
        with open(GEOCODE_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            # Handle legacy format (flat cache) and new format (source-based)
            if isinstance(cache_data, dict) and any(k in cache_data for k in ['nominatim', 'census', 'legacy']):
                geocode_cache = cache_data
            else:
                # Legacy format - migrate to new format
                geocode_cache = {'legacy': cache_data}

            total_entries = sum(len(v) for v in geocode_cache.values() if isinstance(v, dict))
            print(f"Loaded {total_entries} addresses from geocode cache")
    elif not geocode_cache:
        geocode_cache = {'nominatim': {}, 'census': {}}
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
    import re
    # Remove patterns like #47, #50, APT 2, UNIT 3, etc.
    normalized = re.sub(r'\s*#?\s*\d+\s*$', '', address)
    normalized = re.sub(r'\s+(APT|UNIT|STE|SUITE)\s+\d+\s*$', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()


# ============================================================================
# Geocoder Base Class and Implementations
# ============================================================================

class Geocoder(ABC):
    """Abstract base class for geocoding sources."""

    @abstractmethod
    def geocode(self, address):
        """
        Geocode an address.

        Returns:
            dict: {'lat': float, 'lon': float, 'source': str} or None
        """
        pass

    @abstractmethod
    def get_name(self):
        """Return the name of this geocoding source."""
        pass


class NominatimGeocoder(Geocoder):
    """OpenStreetMap Nominatim geocoder."""

    def __init__(self):
        self.geolocator = Nominatim(user_agent="lebdata-app")
        self.zip_codes = [
            ("Lebanon, NH 03766", "Lebanon 03766"),
            ("Lebanon, NH 03756", "Lebanon 03756"),
            ("West Lebanon, NH 03784", "West Lebanon 03784"),
        ]

    def get_name(self):
        return "nominatim"

    def geocode(self, address):
        """Geocode using Nominatim."""
        for location_suffix, location_name in self.zip_codes:
            full_address = f"{address}, {location_suffix}"
            try:
                location = self.geolocator.geocode(full_address, timeout=10)
                if location:
                    return {
                        'lat': location.latitude,
                        'lon': location.longitude,
                        'source': 'nominatim',
                        'matched_address': location_name
                    }
                time.sleep(0.5)
            except Exception as e:
                print(f"Nominatim error for {address}: {e}")
                time.sleep(1)
        return None


class CensusGeocoder(Geocoder):
    """US Census Geocoding API."""

    def __init__(self):
        self.base_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
        self.zip_codes = ['03766', '03756', '03784']

    def get_name(self):
        return "census"

    def geocode(self, address):
        """Geocode using US Census API."""
        for zip_code in self.zip_codes:
            full_address = f"{address}, Lebanon, NH {zip_code}"
            params = {
                'address': full_address,
                'benchmark': 'Public_AR_Current',
                'format': 'json'
            }
            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get('result', {}).get('addressMatches'):
                    match = data['result']['addressMatches'][0]
                    coords = match['coordinates']
                    return {
                        'lat': coords['y'],
                        'lon': coords['x'],
                        'source': 'census',
                        'matched_address': match.get('matchedAddress', '')
                    }
                time.sleep(0.5)
            except Exception as e:
                print(f"Census error for {address}: {e}")
                time.sleep(1)
        return None


# Registry of available geocoders
GEOCODERS = {
    'nominatim': NominatimGeocoder,
    'census': CensusGeocoder,
}


def geocode_address_multi_source(address, sources=['nominatim']):
    """
    Geocode an address using multiple sources with fallback.

    Args:
        address: Address string to geocode
        sources: List of source names to try in order (e.g., ['census', 'nominatim'])

    Returns:
        dict: {'lat': float, 'lon': float, 'source': str} or None
    """
    global geocode_cache

    normalized = normalize_address(address)

    # Try each source in order
    for source_name in sources:
        # Check legacy cache first
        if 'legacy' in geocode_cache:
            cached_value = geocode_cache['legacy'].get(address) or geocode_cache['legacy'].get(normalized)
            if cached_value is not None and isinstance(cached_value, dict) and 'lat' in cached_value:
                # Migrate to new format
                if source_name not in geocode_cache:
                    geocode_cache[source_name] = {}
                geocode_cache[source_name][address] = {**cached_value, 'source': 'legacy'}
                return {**cached_value, 'source': 'legacy'}
            elif cached_value is None and not RETRY_FAILED_GEOCODES:
                continue  # Try next source

        # Check source-specific cache
        if source_name in geocode_cache:
            cached_value = geocode_cache[source_name].get(address) or geocode_cache[source_name].get(normalized)
            if cached_value is not None and isinstance(cached_value, dict):
                # Cache hit with coordinates
                return cached_value
            elif cached_value is None and not RETRY_FAILED_GEOCODES:
                continue  # Try next source

        # Cache miss - try geocoding with this source
        if source_name in GEOCODERS:
            print(f"Geocoding {address} with {source_name}...")
            geocoder = GEOCODERS[source_name]()
            result = geocoder.geocode(normalized if normalized != address else address)

            # Initialize cache for this source if needed
            if source_name not in geocode_cache:
                geocode_cache[source_name] = {}

            if result:
                # Success - cache and return
                geocode_cache[source_name][address] = result
                if normalized != address:
                    geocode_cache[source_name][normalized] = result
                save_geocode_cache()
                print(f"  Success! Cached {address} from {source_name}")
                return result
            else:
                # Failed - cache null for this source
                geocode_cache[source_name][address] = None
                if normalized != address:
                    geocode_cache[source_name][normalized] = None
                save_geocode_cache()
                print(f"  Failed with {source_name}, trying next source...")

    # All sources failed
    print(f"All geocoding sources failed for: {address}")
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

    # Get geocoding sources from query parameters
    sources_param = request.args.get('sources', 'nominatim')
    sources = [s.strip() for s in sources_param.split(',')]

    # Validate sources
    valid_sources = [s for s in sources if s in GEOCODERS]
    if not valid_sources:
        valid_sources = ['nominatim']  # Default fallback

    # Create cache key from sources
    cache_key = ','.join(valid_sources)

    # If we have cached results for this source combination, return them
    if cache_key in parcels_result_cache:
        print(f"Returning {len(parcels_result_cache[cache_key])} parcels from result cache (sources: {cache_key})")
        return jsonify(parcels_result_cache[cache_key])

    try:
        load_geocode_cache()
        parcels = load_parcel_data()

        print(f"Loaded {len(parcels)} parcels from CSV")
        print(f"Using geocoding sources: {valid_sources}")

        # Geocode addresses
        parcels_with_coords = []
        count = 0
        new_geocodes = 0
        source_stats = {s: 0 for s in valid_sources}

        for parcel in parcels:
            location = parcel.get('location', '').strip()
            if location:
                coords = geocode_address_multi_source(location, valid_sources)
                if coords:
                    parcel['lat'] = coords['lat']
                    parcel['lon'] = coords['lon']
                    parcel['geocode_source'] = coords.get('source', 'unknown')
                    parcels_with_coords.append(parcel)

                    # Track which source provided the result
                    source = coords.get('source', 'unknown')
                    if source in source_stats:
                        source_stats[source] += 1
                    elif source == 'legacy':
                        source_stats['legacy'] = source_stats.get('legacy', 0) + 1

                    count += 1
                    if count % 100 == 0:
                        print(f"Processed {count} parcels...")

        print(f"Processed {len(parcels_with_coords)} parcels with coordinates")
        print(f"Source breakdown: {source_stats}")

        # Save geocode cache
        save_geocode_cache()

        # Cache the result for future requests with this source combination
        parcels_result_cache[cache_key] = parcels_with_coords

        return jsonify(parcels_with_coords)
    except Exception as e:
        print(f"Error in get_parcels: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/geocoders')
def get_geocoders():
    """API endpoint to get available geocoding sources."""
    return jsonify({
        'available': list(GEOCODERS.keys()),
        'descriptions': {
            'nominatim': 'OpenStreetMap Nominatim (free, community-maintained)',
            'census': 'US Census Geocoding API (free, official government data)'
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

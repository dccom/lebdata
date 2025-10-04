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

# Cache for geocoded addresses
GEOCODE_CACHE_FILE = Path(__file__).parent / 'geocode_cache.json'
geocode_cache = {}

def load_geocode_cache():
    """Load geocode cache from file."""
    global geocode_cache
    if GEOCODE_CACHE_FILE.exists():
        with open(GEOCODE_CACHE_FILE, 'r') as f:
            geocode_cache = json.load(f)

def save_geocode_cache():
    """Save geocode cache to file."""
    with open(GEOCODE_CACHE_FILE, 'w') as f:
        json.dump(geocode_cache, f, indent=2)

def geocode_address(address):
    """Geocode an address to lat/lon, using cache if available."""
    if address in geocode_cache:
        return geocode_cache[address]

    # Add Lebanon, NH to the address for better geocoding
    full_address = f"{address}, Lebanon, NH 03766"

    try:
        geolocator = Nominatim(user_agent="lebdata-app")
        location = geolocator.geocode(full_address, timeout=10)

        if location:
            result = {'lat': location.latitude, 'lon': location.longitude}
            geocode_cache[address] = result
            save_geocode_cache()
            time.sleep(1)  # Rate limiting
            return result
    except Exception as e:
        print(f"Error geocoding {address}: {e}")

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
    try:
        load_geocode_cache()
        parcels = load_parcel_data()

        print(f"Loaded {len(parcels)} parcels from CSV")

        # Geocode addresses (only those not in cache)
        parcels_with_coords = []
        count = 0
        for parcel in parcels:
            location = parcel.get('location', '').strip()
            if location:
                coords = geocode_address(location)
                if coords:
                    parcel['lat'] = coords['lat']
                    parcel['lon'] = coords['lon']
                    parcels_with_coords.append(parcel)
                    count += 1
                    if count % 10 == 0:
                        print(f"Geocoded {count} parcels...")

        print(f"Returning {len(parcels_with_coords)} parcels with coordinates")
        return jsonify(parcels_with_coords)
    except Exception as e:
        print(f"Error in get_parcels: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# Lebanon NH Assessment Data Visualization

This project downloads and visualizes property assessment data for Lebanon, NH.

## For Non-Programmers: Running with Docker Desktop

### Prerequisites
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Download this entire `vgsi` folder

### Steps to Run

1. **Open Terminal/Command Prompt**
   - **Mac**: Open Terminal (press Cmd+Space, type "Terminal")
   - **Windows**: Open Command Prompt or PowerShell

2. **Navigate to the vgsi folder**
   ```bash
   cd path/to/vgsi
   ```
   (Replace `path/to/vgsi` with the actual path to the folder)

3. **Start the server**
   ```bash
   docker-compose up
   ```

4. **Open your browser**
   - Go to: http://localhost:5050
   - You should see an interactive map with property data

5. **To stop the server**
   - Press `Ctrl+C` in the terminal
   - Or run: `docker-compose down`

### Troubleshooting

- **Port 5050 already in use**: Change the port in `docker-compose.yml` from `5050:5000` to `8080:5000`, then visit http://localhost:8080
- **Docker not found**: Make sure Docker Desktop is installed and running
- **Loading takes too long**: The first time, it geocodes all addresses which can take a while. Subsequent loads will be faster.

## Project Structure

- `scripts/` - Python scripts for downloading and processing data
- `lebdata/` - Flask web application for visualization
- `workspace/` - Downloaded data and CSV files
- `.devcontainer/` - VS Code development container configuration

## For Developers

### Geocoding System

The web application supports multiple geocoding sources with automatic fallback. Users can select which sources to use via the UI control panel.

#### Available Geocoding Sources

- **Nominatim** - OpenStreetMap geocoding (free, community-maintained)
- **Census** - US Census Geocoding API (free, official government data)

#### Using the Geocoding UI

1. Access the map at http://localhost:5050
2. Use the control panel in the top-right corner to select geocoding sources
3. Click "Load Data" to geocode parcels with the selected sources
4. View statistics showing which source provided each parcel's coordinates

#### Adding New Geocoding Sources

The geocoding system is designed to be extensible. To add a new geocoding source (e.g., Google Maps, Mapbox, Bing Maps):

**1. Create a new geocoder class in `lebdata/lebdata/app.py`:**

```python
class GoogleMapsGeocoder(Geocoder):
    """Google Maps Geocoding API."""

    def __init__(self):
        self.api_key = "YOUR_API_KEY"  # Load from environment variable
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    def get_name(self):
        return "google"

    def geocode(self, address):
        """Geocode using Google Maps API."""
        params = {
            'address': f"{address}, Lebanon, NH",
            'key': self.api_key
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'OK' and data.get('results'):
                location = data['results'][0]['geometry']['location']
                return {
                    'lat': location['lat'],
                    'lon': location['lng'],
                    'source': 'google',
                    'matched_address': data['results'][0].get('formatted_address', '')
                }
        except Exception as e:
            print(f"Google Maps error for {address}: {e}")
        return None
```

**2. Register the geocoder in the `GEOCODERS` registry:**

```python
# Registry of available geocoders
GEOCODERS = {
    'nominatim': NominatimGeocoder,
    'census': CensusGeocoder,
    'google': GoogleMapsGeocoder,  # Add your new geocoder here
}
```

**3. Add a description in the `/api/geocoders` endpoint:**

```python
@app.route('/api/geocoders')
def get_geocoders():
    """API endpoint to get available geocoding sources."""
    return jsonify({
        'available': list(GEOCODERS.keys()),
        'descriptions': {
            'nominatim': 'OpenStreetMap Nominatim (free, community-maintained)',
            'census': 'US Census Geocoding API (free, official government data)',
            'google': 'Google Maps Geocoding API (requires API key)'  # Add description
        }
    })
```

**4. Rebuild the Docker container:**

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

The UI will automatically display a checkbox for the new geocoding source!

#### Geocoding Source Priority

When multiple sources are selected, they are tried in the order they appear in the `sources` parameter. For example:

- `?sources=census,nominatim` - Try Census first, fall back to Nominatim
- `?sources=nominatim,census` - Try Nominatim first, fall back to Census
- `?sources=google,census,nominatim` - Try Google, then Census, then Nominatim

#### Cache Format

The geocode cache (`lebdata/lebdata/geocode_cache.json`) is organized by source:

```json
{
  "nominatim": {
    "123 MAIN ST": {"lat": 43.642, "lon": -72.251, "source": "nominatim"},
    "456 ELM ST": null
  },
  "census": {
    "123 MAIN ST": {"lat": 43.642, "lon": -72.251, "source": "census"},
    "789 OAK ST": {"lat": 43.643, "lon": -72.252, "source": "census"}
  }
}
```

- `null` values indicate the address failed to geocode with that source
- Each source maintains its own cache to avoid conflicts
- Legacy caches are automatically migrated to the new format

### Testing Geocoding Sources

Use the test script to compare geocoding sources:

```bash
docker-compose exec lebdata-web python3 /app/scripts/test_census_geocoder.py
```

This script will:
- Geocode all addresses using the US Census API
- Compare results with the existing Nominatim cache
- Generate a detailed comparison report
- Save results to `workspace/lebanonnh/census_geocode_results.json`

See individual README files in subdirectories for more details on each component.

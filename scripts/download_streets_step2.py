#!/usr/bin/env python3
"""Download individual street pages from Lebanon NH VGSI."""

import os
import re
from pathlib import Path
import requests
import urllib3
from urllib.parse import quote

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def extract_street_urls(html_content):
    """Extract street URLs from the HTML content."""
    # Pattern to match: href='Streets.aspx?Name=STREET_NAME'
    pattern = r"href='Streets\.aspx\?Name=([^']+)'"
    matches = re.findall(pattern, html_content)
    return matches


def download_street_pages():
    """Download individual street pages based on letter HTML files."""
    base_url = "https://gis.vgsi.com/lebanonnh/Streets.aspx?Name={name}"
    input_dir = Path("/workspaces/vgsi/workspace/lebanonnh/streets/letter")
    output_dir = Path("/workspaces/vgsi/workspace/lebanonnh/streets/streets")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all letter HTML files
    letter_files = sorted(input_dir.glob("*.html"))

    total_streets = 0
    successful_downloads = 0

    for letter_file in letter_files:
        print(f"\nProcessing {letter_file.name}...")

        # Read the letter HTML file
        html_content = letter_file.read_text(encoding="utf-8")

        # Extract street names
        street_names = extract_street_urls(html_content)

        print(f"  Found {len(street_names)} streets")

        for street_name in street_names:
            total_streets += 1

            # Create safe filename (replace spaces and special chars)
            safe_filename = street_name.strip().replace(" ", "_").replace("/", "_")
            output_file = output_dir / f"{safe_filename}.html"

            # Skip if already downloaded
            if output_file.exists():
                print(f"  ✓ Skipping {street_name} (already exists)")
                successful_downloads += 1
                continue

            # Build URL
            url = base_url.format(name=street_name)

            print(f"  Downloading {street_name}... ", end="", flush=True)

            try:
                response = requests.get(url, timeout=30, verify=False)
                response.raise_for_status()

                # Save the HTML content
                output_file.write_text(response.text, encoding="utf-8")
                print(f"✓")
                successful_downloads += 1

            except requests.RequestException as e:
                print(f"✗ Failed: {e}")

    print(f"\n{'='*60}")
    print(f"Summary: {successful_downloads}/{total_streets} streets downloaded successfully")
    print(f"{'='*60}")


if __name__ == "__main__":
    download_street_pages()

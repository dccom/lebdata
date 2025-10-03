#!/usr/bin/env python3
"""Download individual parcel pages from Lebanon NH VGSI."""

import os
import re
from pathlib import Path
import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def extract_parcel_pids(html_content):
    """Extract parcel PIDs from the HTML content."""
    # Pattern to match: href='Parcel.aspx?pid=NUMBER'
    pattern = r"href='Parcel\.aspx\?pid=(\d+)'"
    matches = re.findall(pattern, html_content)
    return matches


def download_parcel_pages():
    """Download individual parcel pages based on street HTML files."""
    base_url = "https://gis.vgsi.com/lebanonnh/Parcel.aspx?pid={pid}"
    input_dir = Path("/workspaces/vgsi/workspace/lebanonnh/streets/streets")
    output_dir = Path("/workspaces/vgsi/workspace/lebanonnh/parcels")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all street HTML files
    street_files = sorted(input_dir.glob("*.html"))

    total_parcels = 0
    successful_downloads = 0
    all_pids = set()

    # First pass: collect all unique PIDs
    print("Collecting parcel IDs from street files...")
    for street_file in street_files:
        html_content = street_file.read_text(encoding="utf-8")
        pids = extract_parcel_pids(html_content)
        all_pids.update(pids)

    print(f"Found {len(all_pids)} unique parcels to download\n")

    # Second pass: download each parcel
    for idx, pid in enumerate(sorted(all_pids), 1):
        total_parcels += 1
        output_file = output_dir / f"{pid}.html"

        # Skip if already downloaded
        if output_file.exists():
            print(f"[{idx}/{len(all_pids)}] ✓ Skipping PID {pid} (already exists)")
            successful_downloads += 1
            continue

        # Build URL
        url = base_url.format(pid=pid)

        print(f"[{idx}/{len(all_pids)}] Downloading PID {pid}... ", end="", flush=True)

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
    print(f"Summary: {successful_downloads}/{total_parcels} parcels downloaded successfully")
    print(f"{'='*60}")


if __name__ == "__main__":
    download_parcel_pages()

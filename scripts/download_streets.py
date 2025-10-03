#!/usr/bin/env python3
"""Download Lebanon NH streets data from VGSI by letter."""

import os
from pathlib import Path
import requests
import string
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def download_streets():
    """Download streets data for each letter A-Z from VGSI."""
    base_url = "https://gis.vgsi.com/lebanonnh/Streets.aspx?Letter={letter}"
    output_dir = Path("/workspaces/vgsi/workspace/lebanonnh/streets/letter")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download for each capital letter A-Z
    for letter in string.ascii_uppercase:
        url = base_url.format(letter=letter)
        output_file = output_dir / f"{letter}.html"

        print(f"Downloading {letter}... ", end="", flush=True)

        try:
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()

            # Save the HTML content
            output_file.write_text(response.text, encoding="utf-8")
            print(f"✓ Saved to {output_file}")

        except requests.RequestException as e:
            print(f"✗ Failed: {e}")


if __name__ == "__main__":
    download_streets()

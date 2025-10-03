#!/usr/bin/env python3
"""Extract parcel details from HTML files and save to CSV."""

import csv
import re
from pathlib import Path
from html.parser import HTMLParser


class ParcelParser(HTMLParser):
    """HTML parser to extract parcel details."""

    def __init__(self):
        super().__init__()
        self.data = {}
        self.in_location = False
        self.in_assessment = False
        self.in_appraisal = False
        self.in_model = False
        self.in_valuation_table = False
        self.current_tag = None
        self.table_headers = []
        self.table_row = []
        self.valuation_years = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Location
        if attrs_dict.get('id') == 'MainContent_lblLocation':
            self.in_location = True

        # Current Assessment
        elif attrs_dict.get('id') == 'MainContent_lblGenAssessment':
            self.in_assessment = True

        # Current Appraisal
        elif attrs_dict.get('id') == 'MainContent_lblGenAppraisal':
            self.in_appraisal = True

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        # Capture location
        if self.in_location:
            self.data['location'] = data
            self.in_location = False

        # Capture current assessment
        elif self.in_assessment:
            self.data['assessment_2025'] = data
            self.in_assessment = False

        # Capture current appraisal
        elif self.in_appraisal:
            self.data['appraisal_2025'] = data
            self.in_appraisal = False

        # Capture model (property type)
        elif data == 'RESIDENTIAL' or data == 'COMMERCIAL' or data == 'INDUSTRIAL':
            if 'property_type' not in self.data:
                self.data['property_type'] = data


def extract_parcel_info(html_file):
    """Extract parcel information from an HTML file."""
    pid = html_file.stem  # filename without extension

    html_content = html_file.read_text(encoding='utf-8')

    # Initialize parser
    parser = ParcelParser()
    parser.feed(html_content)

    # Extract location with regex as backup
    location = parser.data.get('location', '')
    if not location:
        location_match = re.search(r'<span id="MainContent_lblLocation">([^<]+)</span>', html_content)
        if location_match:
            location = location_match.group(1).strip()

    # Extract current assessment
    assessment = parser.data.get('assessment_2025', '')
    if not assessment:
        assess_match = re.search(r'<span id="MainContent_lblGenAssessment">([^<]+)</span>', html_content)
        if assess_match:
            assessment = assess_match.group(1).strip()

    # Extract current appraisal
    appraisal = parser.data.get('appraisal_2025', '')
    if not appraisal:
        appr_match = re.search(r'<span id="MainContent_lblGenAppraisal">([^<]+)</span>', html_content)
        if appr_match:
            appraisal = appr_match.group(1).strip()

    # Extract property type
    property_type = parser.data.get('property_type', '')
    if not property_type:
        # Look for Model field with RESIDENTIAL/COMMERCIAL
        model_match = re.search(r'<td>Model</td><td>(RESIDENTIAL|COMMERCIAL|INDUSTRIAL)</td>', html_content)
        if model_match:
            property_type = model_match.group(1)

    # Extract historical valuation data
    appraisal_years = {}
    assessment_years = {}

    # Find Appraisal history table
    appraisal_table_match = re.search(
        r'id="MainContent_grdHistoryValuesAppr"[^>]*>.*?<caption>\s*Appraisal\s*</caption>(.*?)</table>',
        html_content, re.DOTALL
    )
    if appraisal_table_match:
        table_content = appraisal_table_match.group(1)
        # Pattern for table rows: year, improvements, land, total
        row_pattern = r'<td>(\d{4})</td><td align="right">\$([^<]+)</td><td align="right">\$([^<]+)</td><td align="right">\$([^<]+)</td>'
        for match in re.finditer(row_pattern, table_content):
            year = match.group(1)
            total = match.group(4).replace(',', '')
            appraisal_years[year] = total

    # Find Assessment history table
    assessment_table_match = re.search(
        r'id="MainContent_grdHistoryValuesAsmt"[^>]*>.*?<caption>\s*Assessment\s*</caption>(.*?)</table>',
        html_content, re.DOTALL
    )
    if assessment_table_match:
        table_content = assessment_table_match.group(1)
        row_pattern = r'<td>(\d{4})</td><td align="right">\$([^<]+)</td><td align="right">\$([^<]+)</td><td align="right">\$([^<]+)</td>'
        for match in re.finditer(row_pattern, table_content):
            year = match.group(1)
            total = match.group(4).replace(',', '')
            assessment_years[year] = total

    return {
        'pid': pid,
        'location': location,
        'property_type': property_type,
        'assessment_2025': assessment,
        'appraisal_2025': appraisal,
        'appraisal_2024': appraisal_years.get('2024', ''),
        'appraisal_2023': appraisal_years.get('2023', ''),
        'appraisal_2022': appraisal_years.get('2022', ''),
        'appraisal_2021': appraisal_years.get('2021', ''),
        'assessment_2024': assessment_years.get('2024', ''),
        'assessment_2023': assessment_years.get('2023', ''),
        'assessment_2022': assessment_years.get('2022', ''),
        'assessment_2021': assessment_years.get('2021', ''),
    }


def extract_all_parcels():
    """Extract data from all parcel HTML files and save to CSV."""
    input_dir = Path("/workspaces/vgsi/workspace/lebanonnh/parcels")
    output_file = Path("/workspaces/vgsi/workspace/lebanonnh/parcel_details.csv")

    # Get all parcel HTML files
    parcel_files = sorted(input_dir.glob("*.html"), key=lambda x: int(x.stem))

    print(f"Processing {len(parcel_files)} parcel files...\n")

    # Extract data from each file
    parcel_data = []
    for idx, parcel_file in enumerate(parcel_files, 1):
        if idx % 100 == 0:
            print(f"Processed {idx}/{len(parcel_files)} files...")

        try:
            data = extract_parcel_info(parcel_file)
            parcel_data.append(data)
        except Exception as e:
            print(f"Error processing {parcel_file.name}: {e}")

    # Write to CSV
    if parcel_data:
        fieldnames = [
            'pid',
            'location',
            'property_type',
            'appraisal_2025',
            'assessment_2025',
            'appraisal_2024',
            'assessment_2024',
            'appraisal_2023',
            'assessment_2023',
            'appraisal_2022',
            'assessment_2022',
            'appraisal_2021',
            'assessment_2021',
        ]

        with output_file.open('w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parcel_data)

        print(f"\n{'='*60}")
        print(f"Extracted {len(parcel_data)} parcels")
        print(f"Saved to: {output_file}")
        print(f"{'='*60}")
    else:
        print("No parcel data extracted!")


if __name__ == "__main__":
    extract_all_parcels()

#!/usr/bin/env python3
"""Pull PhantomBuster results and push to Odoo LinkedIn webhook.

Usage:
    python phantombuster_sync.py

Environment variables (or edit the constants below):
    PHANTOMBUSTER_API_KEY  - Your PhantomBuster API key
    PHANTOM_ID             - The ID of your LinkedIn scraper phantom
    ODOO_WEBHOOK_URL       - Your Odoo webhook URL
    ODOO_WEBHOOK_API_KEY   - The API key you set in CRM > Settings
"""
import json
import os
import sys
import urllib.request

# --- Configuration ---
PB_API_KEY = os.environ.get('PHANTOMBUSTER_API_KEY', '')
PHANTOM_ID = os.environ.get('PHANTOM_ID', '')
ODOO_WEBHOOK_URL = os.environ.get('ODOO_WEBHOOK_URL', 'http://localhost:8069/linkedin/webhook')
ODOO_API_KEY = os.environ.get('ODOO_WEBHOOK_API_KEY', '')
ODOO_DB = os.environ.get('ODOO_DB', '')


def get_phantom_results():
    """Fetch the latest result from PhantomBuster."""
    if not PHANTOM_ID:
        print("ERROR: Set PHANTOM_ID (find it in your PhantomBuster phantom's URL)")
        sys.exit(1)

    url = f'https://api.phantombuster.com/api/v2/agents/fetch-output?id={PHANTOM_ID}'
    req = urllib.request.Request(url, headers={
        'X-Phantombuster-Key': PB_API_KEY,
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    # PhantomBuster stores results as S3 files referenced in the console output
    # First check resultObject, then parse the JSON URL from the output log
    result_url = data.get('resultObject')
    if not result_url:
        import re
        output = data.get('output', '')
        # Look for the JSON URL in the output log
        match = re.search(r'JSON saved at (https://\S+\.json)', output)
        if not match:
            # Also try CSV
            match = re.search(r'CSV saved at (https://\S+\.csv)', output)
        if not match:
            print("No results found. Has the phantom run yet?")
            print("Output:", output[:500])
            sys.exit(0)
        result_url = match.group(1)

    print(f"Fetching results from: {result_url}")
    with urllib.request.urlopen(result_url) as resp:
        content = resp.read()
        if result_url.endswith('.json'):
            records = json.loads(content)
        else:
            # CSV - parse it
            import csv, io
            reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
            records = list(reader)

    return records if isinstance(records, list) else [records]


def push_to_odoo(records):
    """Send records to the Odoo LinkedIn webhook."""
    payload = json.dumps(records).encode('utf-8')
    req = urllib.request.Request(
        ODOO_WEBHOOK_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': ODOO_API_KEY,
            'X-Odoo-Database': ODOO_DB,
        },
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    print(f"Pushed {len(records)} records to Odoo:")
    print(json.dumps(result, indent=2))
    return result


def main():
    print(f"Fetching results from PhantomBuster phantom {PHANTOM_ID}...")
    records = get_phantom_results()
    print(f"Got {len(records)} records")

    if not records:
        print("No records to push.")
        return

    # Push in batches of 100
    for i in range(0, len(records), 100):
        batch = records[i:i+100]
        print(f"\nPushing batch {i//100 + 1} ({len(batch)} records)...")
        push_to_odoo(batch)


if __name__ == '__main__':
    main()

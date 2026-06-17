#!/usr/bin/env python3
"""
Script to update estimate_price_batman_test_request.json with the contents of batman.ldr
"""
import json
from pathlib import Path

def update_json_with_ldr():
    # Define file paths
    ldr_file = Path("test-files/ldr/batman.ldr")
    json_file = Path("test-files/json/estimate_price_batman_test_request.json")
    
    # Check if files exist
    if not ldr_file.exists():
        print(f"Error: {ldr_file} not found")
        return False
    
    if not json_file.exists():
        print(f"Error: {json_file} not found")
        return False
    
    # Read LDR file content
    print(f"Reading LDR content from {ldr_file}")
    with open(ldr_file, 'r', encoding='utf-8') as f:
        ldr_content = f.read()
    
    # Read existing JSON
    print(f"Reading JSON from {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    # Update the ldr_content field
    json_data["ldr_content"] = ldr_content
    
    # Write back to JSON file
    print(f"Updating {json_file} with LDR content")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)
    
    print("✅ Successfully updated JSON file with LDR content")
    print(f"   LDR content length: {len(ldr_content)} characters")
    print(f"   Lines in LDR: {ldr_content.count(chr(10)) + 1}")
    
    return True

if __name__ == "__main__":
    update_json_with_ldr()
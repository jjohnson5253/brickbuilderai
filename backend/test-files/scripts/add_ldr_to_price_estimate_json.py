#!/usr/bin/env python3
"""
Script to update estimate_price_test_request.json with the contents of any .ldr file
"""
import json
import sys
from pathlib import Path

def update_json_with_ldr(ldr_file_path):
    # Define file paths
    ldr_file = Path(ldr_file_path)
    json_file = Path("test-files/json/estimate_price_test_request.json")
    
    # Check if files exist
    if not ldr_file.exists():
        print(f"Error: {ldr_file} not found")
        return False
    
    if not ldr_file.suffix.lower() == '.ldr':
        print(f"Error: {ldr_file} is not a .ldr file")
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
    print(f"   LDR file: {ldr_file}")
    print(f"   LDR content length: {len(ldr_content)} characters")
    print(f"   Lines in LDR: {ldr_content.count(chr(10)) + 1}")
    
    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python add_ldr_to_price_estimate_json.py <path_to_ldr_file>")
        print("Example: python add_ldr_to_price_estimate_json.py test-files/ldr/batman.ldr")
        sys.exit(1)
    
    ldr_file_path = sys.argv[1]
    success = update_json_with_ldr(ldr_file_path)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
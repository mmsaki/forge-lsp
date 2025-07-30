#!/usr/bin/env python3
"""
Test script to analyze linting messages and ensure all information is captured.
"""

import asyncio
import sys
import os
import json
import subprocess

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def analyze_lint_messages():
    """Analyze linting messages to ensure all information is captured."""
    provider = ForgeDiagnosticsProvider()
    
    # Test file with linting issues
    test_file = "/Users/meek/Developer/forge_lsp/examples/src/TestLint.sol"
    examples_dir = "/Users/meek/Developer/forge_lsp/examples"
    
    print("=== Raw Forge Lint Output ===")
    
    # Get raw forge lint output
    try:
        result = subprocess.run(
            ["forge", "lint", "src/TestLint.sol", "--json"],
            cwd=examples_dir,
            capture_output=True,
            text=True
        )
        
        raw_output = result.stderr.strip()
        print(f"Raw JSONC output:\n{raw_output}\n")
        
        # Parse each line as JSON
        raw_diagnostics = []
        for line in raw_output.split('\n'):
            if line.strip():
                try:
                    data = json.loads(line)
                    raw_diagnostics.append(data)
                    print(f"Parsed JSON structure:")
                    print(f"  Message: {data.get('message', 'N/A')}")
                    print(f"  Level: {data.get('level', 'N/A')}")
                    print(f"  Code: {data.get('code', {}).get('code', 'N/A')}")
                    print(f"  Children: {len(data.get('children', []))}")
                    
                    # Examine children for additional info
                    for i, child in enumerate(data.get('children', [])):
                        print(f"    Child {i+1}:")
                        print(f"      Level: {child.get('level', 'N/A')}")
                        print(f"      Message: {repr(child.get('message', 'N/A'))}")
                    
                    # Check rendered field
                    rendered = data.get('rendered', '')
                    if rendered:
                        print(f"  Rendered field (length: {len(rendered)}):")
                        print(f"    {repr(rendered[:200])}...")
                    
                    print()
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON line: {e}")
                    print(f"Line: {repr(line)}")
        
    except Exception as e:
        print(f"Error running forge lint: {e}")
        return False
    
    print("\n=== Our Processed Output ===")
    
    # Get our processed diagnostics
    diagnostics = await provider.get_diagnostics_for_file_async(test_file, use_cache=False)
    lint_diagnostics = [d for d in diagnostics if d.source == "forge-lint"]
    
    print(f"Found {len(lint_diagnostics)} processed lint diagnostics:")
    
    for i, diag in enumerate(lint_diagnostics):
        print(f"\nDiagnostic {i+1}:")
        print(f"  Message: {repr(diag.message)}")
        print(f"  Code: {diag.code}")
        print(f"  Severity: {diag.severity}")
        print(f"  Source: {diag.source}")
        if hasattr(diag, 'data') and diag.data and 'help_url' in diag.data:
            print(f"  Help URL: {diag.data['help_url']}")
    
    print("\n=== Comparison Analysis ===")
    
    # Compare raw vs processed
    if raw_diagnostics and lint_diagnostics:
        raw_diag = raw_diagnostics[0]
        processed_diag = lint_diagnostics[0]
        
        print("Raw message:", repr(raw_diag.get('message', '')))
        print("Processed message:", repr(processed_diag.message))
        
        # Check if we're missing any information
        raw_children = raw_diag.get('children', [])
        print(f"\nRaw diagnostic has {len(raw_children)} children")
        
        for i, child in enumerate(raw_children):
            print(f"  Child {i+1} level: {child.get('level')}")
            print(f"  Child {i+1} message: {repr(child.get('message', ''))}")
        
        # Check rendered field for additional context
        rendered = raw_diag.get('rendered', '')
        if rendered:
            print(f"\nRendered field contains additional context:")
            lines = rendered.split('\n')
            for line in lines:
                if line.strip() and not line.startswith(' '):
                    print(f"  {repr(line)}")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(analyze_lint_messages())
    sys.exit(0 if success else 1)
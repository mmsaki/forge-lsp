#!/usr/bin/env python3
"""
Debug script to see exactly what's happening in lint message parsing.
"""

import asyncio
import sys
import os
import json
import subprocess

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def debug_lint_parsing():
    """Debug lint message parsing step by step."""
    provider = ForgeDiagnosticsProvider()
    
    # Test file with linting issues
    examples_dir = "/Users/meek/Developer/forge_lsp/examples"
    
    print("=== Getting Raw JSONC Output ===")
    
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
        
        # Parse the JSON manually to see what we get
        for line in raw_output.split('\n'):
            if line.strip():
                try:
                    data = json.loads(line)
                    print("=== Parsed JSON Data ===")
                    print(f"Message field: {repr(data.get('message', ''))}")
                    print(f"Code field: {data.get('code', {})}")
                    print(f"Level field: {data.get('level', '')}")
                    
                    # Now let's manually call the parser method
                    print("\n=== Manual Parser Call ===")
                    runner = provider.forge_runner
                    parser = runner.parser
                    diagnostic = parser._parse_lint_jsonc_diag(data, examples_dir)
                    
                    if diagnostic:
                        print(f"Parsed diagnostic message: {repr(diagnostic.message)}")
                        print(f"Parsed diagnostic code: {diagnostic.code}")
                        print(f"Parsed diagnostic help_url: {diagnostic.help_url}")
                    else:
                        print("Parser returned None")
                        
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON line: {e}")
        
    except Exception as e:
        print(f"Error running forge lint: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(debug_lint_parsing())
    sys.exit(0 if success else 1)
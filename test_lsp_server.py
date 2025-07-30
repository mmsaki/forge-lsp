#!/usr/bin/env python3
"""
Test script for the Forge LSP server.
Tests the diagnostic functionality with a sample Solidity file.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider


async def test_diagnostics():
    """Test the diagnostics functionality."""
    print("Testing Forge LSP diagnostics...")
    
    # Initialize the diagnostics provider
    provider = ForgeDiagnosticsProvider()
    
    # Test with the example Counter.sol file
    example_file = Path(__file__).parent / "examples" / "src" / "Counter.sol"
    
    if not example_file.exists():
        print(f"Example file not found: {example_file}")
        return
    
    print(f"Testing diagnostics for: {example_file}")
    
    try:
        # Get diagnostics for the file
        diagnostics = await provider.get_diagnostics_for_file_async(str(example_file))
        
        print(f"Found {len(diagnostics)} diagnostics:")
        for i, diag in enumerate(diagnostics, 1):
            print(f"  {i}. Line {diag.range.start.line + 1}: {diag.message}")
            print(f"     Severity: {diag.severity}")
            print(f"     Source: {diag.source}")
            if diag.code:
                print(f"     Code: {diag.code}")
            print()
        
        if len(diagnostics) == 0:
            print("✅ No compilation errors found!")
        else:
            print(f"ℹ️  Found {len(diagnostics)} diagnostic(s)")
            
    except Exception as e:
        print(f"❌ Error getting diagnostics: {e}")
        import traceback
        traceback.print_exc()


def test_project_detection():
    """Test project root detection."""
    print("Testing project root detection...")
    
    provider = ForgeDiagnosticsProvider()
    example_file = Path(__file__).parent / "examples" / "src" / "Counter.sol"
    
    if not example_file.exists():
        print(f"Example file not found: {example_file}")
        return
    
    project_root = provider.get_project_root(str(example_file))
    print(f"Detected project root: {project_root}")
    
    if project_root:
        foundry_toml = Path(project_root) / "foundry.toml"
        if foundry_toml.exists():
            print("✅ Found foundry.toml in project root")
        else:
            print("❌ foundry.toml not found in detected project root")
    else:
        print("❌ Could not detect project root")


async def main():
    """Main test function."""
    print("🔧 Forge LSP Server Test")
    print("=" * 50)
    
    # Test project detection first
    test_project_detection()
    print()
    
    # Test diagnostics
    await test_diagnostics()
    
    print("=" * 50)
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
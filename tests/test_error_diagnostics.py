#!/usr/bin/env python3
"""
Test script for the Forge LSP server with error diagnostics.
Tests the diagnostic functionality with a Solidity file that has errors.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider


async def test_error_diagnostics():
    """Test the diagnostics functionality with a file that has errors."""
    print("Testing Forge LSP error diagnostics...")
    
    # Initialize the diagnostics provider
    provider = ForgeDiagnosticsProvider()
    
    # Test with the TestErrors.sol file
    error_file = Path(__file__).parent / "examples" / "src" / "TestErrors.sol"
    
    if not error_file.exists():
        print(f"Error test file not found: {error_file}")
        return
    
    print(f"Testing diagnostics for: {error_file}")
    
    try:
        # Get diagnostics for the file
        diagnostics = await provider.get_diagnostics_for_file_async(str(error_file))
        
        print(f"Found {len(diagnostics)} diagnostics:")
        for i, diag in enumerate(diagnostics, 1):
            print(f"  {i}. Line {diag.range.start.line + 1}, Column {diag.range.start.character + 1}")
            print(f"     Message: {diag.message}")
            print(f"     Severity: {diag.severity}")
            print(f"     Source: {diag.source}")
            if diag.code:
                print(f"     Code: {diag.code}")
            print()
        
        if len(diagnostics) == 0:
            print("⚠️  No diagnostics found - this might indicate an issue with error detection")
        else:
            print(f"✅ Successfully detected {len(diagnostics)} diagnostic(s)")
            
    except Exception as e:
        print(f"❌ Error getting diagnostics: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    print("🔧 Forge LSP Server Error Diagnostics Test")
    print("=" * 60)
    
    # Test error diagnostics
    await test_error_diagnostics()
    
    print("=" * 60)
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
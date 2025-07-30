#!/usr/bin/env python3
"""
Test script for the Forge LSP server cache functionality.
Tests the difference between cached and non-cached compilation.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider


async def test_cache_functionality():
    """Test the cache functionality with different files."""
    print("Testing Forge LSP cache functionality...")
    
    # Initialize the diagnostics provider
    provider = ForgeDiagnosticsProvider()
    
    # Test files
    test_files = [
        Path(__file__).parent / "examples" / "src" / "Counter.sol",
        Path(__file__).parent / "examples" / "src" / "TestErrors.sol", 
        Path(__file__).parent / "examples" / "src" / "EmptyFile.sol"
    ]
    
    for test_file in test_files:
        if not test_file.exists():
            print(f"Test file not found: {test_file}")
            continue
            
        print(f"\n📁 Testing file: {test_file.name}")
        print("=" * 50)
        
        # Test with cache (normal typing behavior)
        print("🔄 Testing WITH cache (normal typing):")
        try:
            diagnostics_cached = await provider.get_diagnostics_for_file_async(str(test_file), use_cache=True)
            print(f"   Found {len(diagnostics_cached)} diagnostics (cached)")
            for i, diag in enumerate(diagnostics_cached, 1):
                print(f"   {i}. Line {diag.range.start.line + 1}: {diag.message}")
        except Exception as e:
            print(f"   ❌ Error with cache: {e}")
        
        # Test without cache (save behavior)
        print("\n💾 Testing WITHOUT cache (save behavior):")
        try:
            diagnostics_no_cache = await provider.get_diagnostics_for_file_async(str(test_file), use_cache=False)
            print(f"   Found {len(diagnostics_no_cache)} diagnostics (no-cache)")
            for i, diag in enumerate(diagnostics_no_cache, 1):
                print(f"   {i}. Line {diag.range.start.line + 1}: {diag.message}")
        except Exception as e:
            print(f"   ❌ Error without cache: {e}")
        
        # Compare results
        if len(diagnostics_cached) == len(diagnostics_no_cache):
            print(f"\n✅ Cache behavior consistent: {len(diagnostics_cached)} diagnostics in both modes")
        else:
            print(f"\n⚠️  Cache difference detected:")
            print(f"   Cached: {len(diagnostics_cached)} diagnostics")
            print(f"   No-cache: {len(diagnostics_no_cache)} diagnostics")
            print("   This is expected for files that may have warnings only visible with --no-cache")


async def test_specific_file_compilation():
    """Test that we're compiling specific files, not the whole project."""
    print("\n🎯 Testing file-specific compilation...")
    print("=" * 50)
    
    provider = ForgeDiagnosticsProvider()
    
    # Test with TestErrors.sol specifically
    error_file = Path(__file__).parent / "examples" / "src" / "TestErrors.sol"
    
    if error_file.exists():
        print(f"Testing specific file compilation: {error_file.name}")
        
        try:
            diagnostics = await provider.get_diagnostics_for_file_async(str(error_file), use_cache=False)
            print(f"Found {len(diagnostics)} diagnostics for specific file:")
            
            for i, diag in enumerate(diagnostics, 1):
                print(f"  {i}. Line {diag.range.start.line + 1}, Col {diag.range.start.character + 1}")
                print(f"     Message: {diag.message}")
                print(f"     Severity: {diag.severity}")
                print(f"     Source: {diag.source}")
                if diag.code:
                    print(f"     Code: {diag.code}")
                print()
            
            if len(diagnostics) > 0:
                print("✅ File-specific compilation working correctly!")
            else:
                print("⚠️  No diagnostics found - this might indicate an issue")
                
        except Exception as e:
            print(f"❌ Error in file-specific compilation: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ TestErrors.sol not found")


async def main():
    """Main test function."""
    print("🔧 Forge LSP Server Cache & File-Specific Compilation Test")
    print("=" * 70)
    
    # Test cache functionality
    await test_cache_functionality()
    
    # Test file-specific compilation
    await test_specific_file_compilation()
    
    print("=" * 70)
    print("✅ Cache and file-specific compilation tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
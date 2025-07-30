#!/usr/bin/env python3
"""
Test script to verify that linting messages are properly cleaned up and formatted.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def test_message_cleanup():
    """Test that linting messages are properly cleaned up and formatted."""
    provider = ForgeDiagnosticsProvider()
    
    # Test file with linting issues
    test_file = "/Users/meek/Developer/forge_lsp/examples/src/TestLint.sol"
    
    print(f"Testing message cleanup for: {test_file}")
    
    # Get diagnostics (should include both compilation and linting)
    diagnostics = await provider.get_diagnostics_for_file_async(test_file, use_cache=False)
    
    print(f"Found {len(diagnostics)} diagnostics:")
    
    for i, diag in enumerate(diagnostics):
        print(f"  {i+1}. [{diag.source}] {diag.message}")
        print(f"      Line: {diag.range.start.line + 1}, Column: {diag.range.start.character + 1}")
        print(f"      Severity: {diag.severity}")
        if diag.code:
            print(f"      Code: {diag.code}")
        if hasattr(diag, 'data') and diag.data and 'help_url' in diag.data:
            print(f"      Help: {diag.data['help_url']}")
        print()
    
    # Check that we have linting diagnostics with proper formatting
    lint_diagnostics = [d for d in diagnostics if d.source == "forge-lint"]
    compile_diagnostics = [d for d in diagnostics if d.source == "forge-compile"]
    
    print(f"Compilation diagnostics: {len(compile_diagnostics)}")
    print(f"Linting diagnostics: {len(lint_diagnostics)}")
    
    success = True
    
    # Verify linting messages are properly formatted
    for diag in lint_diagnostics:
        if not diag.message.startswith("[forge lint]"):
            print(f"❌ Linting message doesn't start with [forge lint]: {diag.message}")
            success = False
        
        # Check for ANSI escape sequences (should be cleaned)
        if '\x1b' in diag.message or '\033' in diag.message:
            print(f"❌ Linting message contains ANSI escape sequences: {repr(diag.message)}")
            success = False
        
        # Check that message is not empty after [forge lint] prefix
        clean_message = diag.message.replace("[forge lint]", "").strip()
        if not clean_message:
            print(f"❌ Linting message is empty after prefix: {diag.message}")
            success = False
    
    if success and lint_diagnostics:
        print("✅ Linting messages are properly formatted and cleaned!")
        return True
    elif not lint_diagnostics:
        print("ℹ️  No linting diagnostics found (may be using forge stable)")
        return True
    else:
        print("❌ Some linting messages have formatting issues!")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_message_cleanup())
    sys.exit(0 if success else 1)
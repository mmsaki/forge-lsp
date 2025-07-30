#!/usr/bin/env python3
"""
Test script for the enhanced Solidity parser implementation.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from forge_lsp.antlr_solidity_parser import ANTLRSolidityParser
    from lsprotocol.types import Position
    print("✓ Successfully imported ANTLRSolidityParser")
except ImportError as e:
    print(f"✗ Failed to import ANTLRSolidityParser: {e}")
    sys.exit(1)


def test_parser_with_file(file_path: str):
    """Test the parser with a specific Solidity file."""
    print(f"\n=== Testing parser with {file_path} ===")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"File content ({len(content)} characters):")
        print("-" * 50)
        print(content)
        print("-" * 50)
        
        # Initialize parser
        parser = ANTLRSolidityParser()
        document_uri = f"file://{os.path.abspath(file_path)}"
        
        # Test diagnostics
        print("\n1. Testing diagnostics...")
        diagnostics = parser.get_diagnostics(content)
        print(f"Found {len(diagnostics)} diagnostics:")
        for i, diag in enumerate(diagnostics):
            severity = diag.severity.name if hasattr(diag.severity, 'name') else str(diag.severity)
            print(f"  {i+1}. [{severity}] Line {diag.range.start.line + 1}: {diag.message}")
        
        # Test symbol indexing
        print("\n2. Testing symbol indexing...")
        parser._index_file_symbols(content, document_uri)
        
        if document_uri in parser.file_symbols:
            symbols = parser.file_symbols[document_uri]
            print(f"Found {len(symbols)} symbol types:")
            for symbol_name, definitions in symbols.items():
                for definition in definitions:
                    print(f"  - {symbol_name} ({definition.symbol_type}) at line {definition.location.range.start.line + 1}")
        else:
            print("  No symbols found")
        
        # Test completions at different positions
        print("\n3. Testing completions...")
        lines = content.split('\n')
        
        # Test completion at end of file
        if lines:
            last_line = len(lines) - 1
            last_char = len(lines[last_line])
            position = Position(line=last_line, character=last_char)
            
            completions = parser.get_completions(content, position)
            print(f"Completions at end of file: {len(completions)} items")
            for i, comp in enumerate(completions[:5]):  # Show first 5
                print(f"  {i+1}. {comp.label} ({comp.kind.name if hasattr(comp.kind, 'name') else comp.kind})")
            if len(completions) > 5:
                print(f"  ... and {len(completions) - 5} more")
        
        # Test hover info
        print("\n4. Testing hover info...")
        if lines and len(lines) > 3:  # Test on line 4 if it exists
            test_line = 3
            test_char = 5
            position = Position(line=test_line, character=test_char)
            
            hover_info = parser.get_hover_info(content, position)
            if hover_info:
                print(f"Hover info at line {test_line + 1}, char {test_char + 1}: {hover_info}")
            else:
                print(f"No hover info at line {test_line + 1}, char {test_char + 1}")
        
        # Test go-to-definition
        print("\n5. Testing go-to-definition...")
        if lines and len(lines) > 3:
            test_line = 3
            test_char = 5
            position = Position(line=test_line, character=test_char)
            
            definitions = parser.get_definitions(content, position, document_uri)
            print(f"Definitions at line {test_line + 1}, char {test_char + 1}: {len(definitions)} found")
            for i, defn in enumerate(definitions):
                print(f"  {i+1}. {defn.uri} at line {defn.range.start.line + 1}")
        
        print(f"\n✓ Successfully tested {file_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error testing {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("Solidity Parser Test Suite")
    print("=" * 50)
    
    # Test files to check
    test_files = [
        "examples/src/Counter.sol",
        "examples/src/ExampleContract.sol",
        "examples/A.sol",
        "examples/B.sol",
    ]
    
    success_count = 0
    total_count = 0
    
    for test_file in test_files:
        file_path = Path(__file__).parent / test_file
        if file_path.exists():
            total_count += 1
            if test_parser_with_file(str(file_path)):
                success_count += 1
        else:
            print(f"⚠ Test file not found: {file_path}")
    
    # Test with a simple inline example
    print(f"\n=== Testing with inline example ===")
    inline_code = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleTest {
    uint256 public value;
    
    function setValue(uint256 _value) public {
        value = _value;
    }
    
    function getValue() public view returns (uint256) {
        return value;
    }
}'''
    
    try:
        parser = ANTLRSolidityParser()
        diagnostics = parser.get_diagnostics(inline_code)
        print(f"Inline test diagnostics: {len(diagnostics)}")
        
        completions = parser.get_completions(inline_code, Position(line=5, character=4))
        print(f"Inline test completions: {len(completions)}")
        
        total_count += 1
        success_count += 1
        print("✓ Inline test passed")
        
    except Exception as e:
        print(f"✗ Inline test failed: {e}")
        total_count += 1
    
    # Summary
    print(f"\n" + "=" * 50)
    print(f"Test Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
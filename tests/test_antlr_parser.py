#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forge_lsp.antlr_solidity_parser import ANTLRSolidityParser
from lsprotocol.types import Position


def test_antlr_parser():
    """Test the ANTLR4-based Solidity parser."""

    # Sample Solidity code with using directive
    solidity_code = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./SafeMath.sol";

using SafeMath for uint256;
using MyLibrary for *;

library MyLibrary {
    function doSomething(uint256 x) internal pure returns (uint256) {
        return x * 2;
    }
    
    function anotherFunction(address addr) internal pure returns (bool) {
        return addr != address(0);
    }
}

contract TestContract {
    uint256 public value;
    
    function setValue(uint256 newValue) public {
        value = newValue.add(10); // This should resolve to SafeMath.add
    }
    
    function processValue() public {
        uint256 result = value.doSomething(); // This should resolve to MyLibrary.doSomething
    }
}
"""

    print("Testing ANTLR4 Solidity Parser...")

    try:
        parser = ANTLRSolidityParser()
        document_uri = "file:///test.sol"

        # Test parsing and symbol indexing
        print("1. Testing symbol indexing...")
        parser._index_file_symbols(solidity_code, document_uri)

        if document_uri in parser.file_symbols:
            print(f"   Found {len(parser.file_symbols[document_uri])} symbol types")
            for symbol_name, definitions in parser.file_symbols[document_uri].items():
                for definition in definitions:
                    print(
                        f"   - {definition.symbol_type}: {symbol_name} (scope: {definition.scope})"
                    )

        # Test using directives
        print("\\n2. Testing using directives...")
        if document_uri in parser.using_directives:
            print(
                f"   Found {len(parser.using_directives[document_uri])} using directives"
            )
            for directive in parser.using_directives[document_uri]:
                print(
                    f"   - using {directive.library_name} for {directive.target_type} (global: {directive.is_global})"
                )

        # Test library functions
        print("\\n3. Testing library functions...")
        if document_uri in parser.library_functions:
            for library_name, functions in parser.library_functions[
                document_uri
            ].items():
                print(f"   Library {library_name}: {functions}")

        # Test go-to-definition for a library method
        print("\\n4. Testing go-to-definition for 'doSomething'...")
        position = Position(
            line=25, character=30
        )  # Position of 'doSomething' in the contract
        definitions = parser.get_definitions(solidity_code, position, document_uri)
        print(f"   Found {len(definitions)} definitions")
        for definition in definitions:
            print(f"   - {definition.uri} at line {definition.range.start.line}")

        # Test diagnostics
        print("\\n5. Testing diagnostics...")
        diagnostics = parser.get_diagnostics(solidity_code)
        print(f"   Found {len(diagnostics)} diagnostics")
        for diagnostic in diagnostics:
            print(f"   - {diagnostic.severity.name}: {diagnostic.message}")

        print("\\n✅ ANTLR4 parser test completed successfully!")
        return True

    except Exception as e:
        print(f"\\n❌ ANTLR4 parser test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_antlr_parser()
    sys.exit(0 if success else 1)


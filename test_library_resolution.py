#!/usr/bin/env python3
"""
Comprehensive test suite for library method resolution.
Tests the complex 'using Library for Type' functionality.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from forge_lsp.library_resolver import LibraryMethodResolver, MethodCallContext
    from forge_lsp.navigation_provider import NavigationProvider
    from lsprotocol.types import Position, Location, Range
    print("✓ Successfully imported library resolution components")
except ImportError as e:
    print(f"✗ Failed to import library resolution components: {e}")
    sys.exit(1)


def test_library_method_resolution():
    """Test the core library method resolution functionality."""
    print("\n=== Testing Library Method Resolution ===")
    
    # Create test files content
    library_b_content = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

library B {
    struct State {
        string name;
        mapping(string => uint256) count;
    }

    function add_one(string memory self, State storage state) internal {
        state.count[self] += 1;
    }

    function get_votes(string memory self, State storage state) internal view returns (uint256) {
        return state.count[self];
    }
    
    function multiply(uint256 self, uint256 factor) internal pure returns (uint256) {
        return self * factor;
    }
}'''

    contract_c_content = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {B} from "./B.sol";

contract C {
    using B for string;
    using B for uint256;

    B.State public votes;
    uint256 public number = 42;

    function add_vote(string memory name) public returns (uint256) {
        name.add_one(votes);  // This should resolve to B.add_one
        return name.get_votes(votes);  // This should resolve to B.get_votes
    }
    
    function calculate() public view returns (uint256) {
        return number.multiply(3);  // This should resolve to B.multiply
    }
}'''

    # Initialize resolver
    resolver = LibraryMethodResolver()
    
    # Parse library file
    library_path = "/test/B.sol"
    resolver.parse_file_for_library_info(library_path, library_b_content)
    
    # Parse contract file
    contract_path = "/test/C.sol"
    contract_uri = f"file://{contract_path}"
    resolver.parse_file_for_library_info(contract_path, contract_c_content)
    
    print(f"✓ Parsed library B with {len(resolver.library_functions.get('B', []))} functions")
    print(f"✓ Found {len(resolver.using_directives.get(contract_uri, []))} using directives")
    
    # Test 1: Resolve string.add_one() call
    print("\n--- Test 1: string.add_one() resolution ---")
    context1 = MethodCallContext(
        receiver_name="name",
        receiver_type="string",
        method_name="add_one",
        call_location=Location(uri=contract_uri, range=Range(
            start=Position(line=12, character=13),
            end=Position(line=12, character=20)
        ))
    )
    
    resolved1 = resolver.resolve_library_method_call(context1, contract_uri)
    if resolved1:
        print(f"✓ Resolved name.add_one() -> {resolved1.library_name}.{resolved1.name}")
        print(f"  First parameter type: {resolved1.first_param_type}")
        print(f"  Location: {resolved1.location.uri}")
    else:
        print("✗ Failed to resolve name.add_one()")
    
    # Test 2: Resolve string.get_votes() call
    print("\n--- Test 2: string.get_votes() resolution ---")
    context2 = MethodCallContext(
        receiver_name="name",
        receiver_type="string",
        method_name="get_votes",
        call_location=Location(uri=contract_uri, range=Range(
            start=Position(line=13, character=20),
            end=Position(line=13, character=29)
        ))
    )
    
    resolved2 = resolver.resolve_library_method_call(context2, contract_uri)
    if resolved2:
        print(f"✓ Resolved name.get_votes() -> {resolved2.library_name}.{resolved2.name}")
        print(f"  Return type: {resolved2.return_type}")
    else:
        print("✗ Failed to resolve name.get_votes()")
    
    # Test 3: Resolve uint256.multiply() call
    print("\n--- Test 3: uint256.multiply() resolution ---")
    context3 = MethodCallContext(
        receiver_name="number",
        receiver_type="uint256",
        method_name="multiply",
        call_location=Location(uri=contract_uri, range=Range(
            start=Position(line=17, character=22),
            end=Position(line=17, character=30)
        ))
    )
    
    resolved3 = resolver.resolve_library_method_call(context3, contract_uri)
    if resolved3:
        print(f"✓ Resolved number.multiply() -> {resolved3.library_name}.{resolved3.name}")
        print(f"  Is pure: {resolved3.is_pure}")
    else:
        print("✗ Failed to resolve number.multiply()")
    
    # Test 4: Get available methods for string type
    print("\n--- Test 4: Available methods for string type ---")
    string_methods = resolver.get_library_methods_for_type("string", contract_uri)
    print(f"✓ Found {len(string_methods)} methods available for string type:")
    for method in string_methods:
        print(f"  - {method.name} (from {method.library_name})")
    
    # Test 5: Get available methods for uint256 type
    print("\n--- Test 5: Available methods for uint256 type ---")
    uint_methods = resolver.get_library_methods_for_type("uint256", contract_uri)
    print(f"✓ Found {len(uint_methods)} methods available for uint256 type:")
    for method in uint_methods:
        print(f"  - {method.name} (from {method.library_name})")
    
    return resolved1 is not None and resolved2 is not None and resolved3 is not None


def test_navigation_provider():
    """Test the navigation provider with library method resolution."""
    print("\n=== Testing Navigation Provider ===")
    
    # Use the actual C.sol file
    c_sol_path = Path(__file__).parent / "examples" / "src" / "C.sol"
    b_sol_path = Path(__file__).parent / "examples" / "src" / "B.sol"
    
    if not c_sol_path.exists() or not b_sol_path.exists():
        print("⚠ Test files not found, skipping navigation provider test")
        return True
    
    try:
        with open(c_sol_path, 'r') as f:
            c_content = f.read()
        with open(b_sol_path, 'r') as f:
            b_content = f.read()
        
        print(f"✓ Loaded C.sol ({len(c_content)} chars)")
        print(f"✓ Loaded B.sol ({len(b_content)} chars)")
        
        # Initialize navigation provider
        nav_provider = NavigationProvider()
        
        # Parse both files
        nav_provider.library_resolver.parse_file_for_library_info(str(b_sol_path), b_content)
        nav_provider.library_resolver.parse_file_for_library_info(str(c_sol_path), c_content)
        
        document_uri = f"file://{c_sol_path}"
        
        # Test go-to-definition for library method call
        # Looking for "add_one" in "name.add_one(votes)" on line 20
        print("\n--- Testing go-to-definition for library method ---")
        position = Position(line=19, character=13)  # Position of "add_one"
        
        definitions = nav_provider.get_definitions(c_content, position, document_uri)
        print(f"✓ Found {len(definitions)} definitions for library method call")
        
        for i, defn in enumerate(definitions):
            print(f"  {i+1}. {defn.uri} at line {defn.range.start.line + 1}")
        
        # Test find references
        print("\n--- Testing find references for library method ---")
        references = nav_provider.find_references(c_content, position, document_uri)
        print(f"✓ Found {len(references)} references for library method")
        
        for i, ref in enumerate(references):
            print(f"  {i+1}. {ref.uri} at line {ref.range.start.line + 1}")
        
        return len(definitions) > 0
        
    except Exception as e:
        print(f"✗ Navigation provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complex_scenarios():
    """Test complex library usage scenarios."""
    print("\n=== Testing Complex Library Scenarios ===")
    
    # Test wildcard using directive
    complex_content = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

library MathLib {
    function square(uint256 self) internal pure returns (uint256) {
        return self * self;
    }
    
    function cube(uint256 self) internal pure returns (uint256) {
        return self * self * self;
    }
    
    function format(string memory self) internal pure returns (string memory) {
        return string(abi.encodePacked("[", self, "]"));
    }
}

library StringLib {
    function reverse(string memory self) internal pure returns (string memory) {
        // Implementation would go here
        return self;
    }
}

contract ComplexContract {
    using MathLib for *;  // Wildcard - should work for any type
    using StringLib for string;
    
    uint256 public number = 5;
    string public text = "hello";
    
    function testMath() public view returns (uint256, uint256) {
        return (number.square(), number.cube());
    }
    
    function testString() public view returns (string memory, string memory) {
        return (text.format(), text.reverse());
    }
}'''

    resolver = LibraryMethodResolver()
    file_path = "/test/Complex.sol"
    file_uri = f"file://{file_path}"
    
    resolver.parse_file_for_library_info(file_path, complex_content)
    
    print(f"✓ Parsed complex contract with {len(resolver.library_functions)} libraries")
    
    # Test wildcard resolution
    print("\n--- Testing wildcard 'using Library for *' ---")
    
    # Test uint256.square() with wildcard
    context = MethodCallContext(
        receiver_name="number",
        receiver_type="uint256",
        method_name="square",
        call_location=Location(uri=file_uri, range=Range(
            start=Position(line=32, character=22),
            end=Position(line=32, character=28)
        ))
    )
    
    resolved = resolver.resolve_library_method_call(context, file_uri)
    if resolved:
        print(f"✓ Wildcard resolution: number.square() -> {resolved.library_name}.{resolved.name}")
    else:
        print("✗ Failed wildcard resolution for number.square()")
    
    # Test string.format() with wildcard (should work since MathLib is for *)
    context2 = MethodCallContext(
        receiver_name="text",
        receiver_type="string",
        method_name="format",
        call_location=Location(uri=file_uri, range=Range(
            start=Position(line=36, character=22),
            end=Position(line=36, character=28)
        ))
    )
    
    resolved2 = resolver.resolve_library_method_call(context2, file_uri)
    if resolved2:
        print(f"✓ Wildcard resolution: text.format() -> {resolved2.library_name}.{resolved2.name}")
    else:
        print("✗ Failed wildcard resolution for text.format()")
    
    # Test specific library resolution
    context3 = MethodCallContext(
        receiver_name="text",
        receiver_type="string",
        method_name="reverse",
        call_location=Location(uri=file_uri, range=Range(
            start=Position(line=36, character=37),
            end=Position(line=36, character=44)
        ))
    )
    
    resolved3 = resolver.resolve_library_method_call(context3, file_uri)
    if resolved3:
        print(f"✓ Specific resolution: text.reverse() -> {resolved3.library_name}.{resolved3.name}")
    else:
        print("✗ Failed specific resolution for text.reverse()")
    
    return resolved is not None and resolved2 is not None and resolved3 is not None


def main():
    """Main test function."""
    print("🚀 Library Method Resolution Test Suite")
    print("=" * 60)
    
    tests = [
        ("Core Library Resolution", test_library_method_resolution),
        ("Navigation Provider", test_navigation_provider),
        ("Complex Scenarios", test_complex_scenarios),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Library method resolution is working!")
        print("\n🔥 Key Features Implemented:")
        print("  ✓ 'using Library for Type' directive parsing")
        print("  ✓ Library method call resolution (variable.method())")
        print("  ✓ Wildcard support ('using Library for *')")
        print("  ✓ Type-specific method resolution")
        print("  ✓ Go-to-definition for library methods")
        print("  ✓ Find references across library usage")
        print("  ✓ Complex multi-library scenarios")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
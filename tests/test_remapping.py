#!/usr/bin/env python3
"""
Test script for the remapping resolver functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from forge_lsp.remapping_resolver import RemappingResolver


def test_remapping_resolver():
    """Test the remapping resolver with the example project."""

    # Use the examples directory as the project root
    project_root = Path(__file__).parent / "examples"

    print(f"Testing remapping resolver with project: {project_root}")

    # Initialize resolver
    resolver = RemappingResolver(project_root)

    # Test remappings
    print("\n=== Remappings ===")
    for prefix, path in resolver.remappings.items():
        print(f"{prefix} -> {path}")

    # Test import resolution
    print("\n=== Import Resolution ===")
    test_imports = [
        "forge-std/Test.sol",
        "forge-std/console.sol",
        "forge-std/Vm.sol",
        "./Counter.sol",
        "src/Counter.sol",
    ]

    for import_path in test_imports:
        resolved = resolver.resolve_import(import_path)
        print(f"{import_path} -> {resolved}")

    # Test file cache
    print(f"\n=== File Cache ({len(resolver.file_cache)} files) ===")
    for file_path, info in list(resolver.file_cache.items())[:5]:  # Show first 5
        imports = info.get("imports", [])
        print(f"{file_path}: {len(imports)} imports")
        for imp in imports[:3]:  # Show first 3 imports
            print(f"  - {imp}")

    # Test completion candidates
    print("\n=== Completion Candidates ===")
    test_prefixes = ["forge-std/", "src/", ""]

    for prefix in test_prefixes:
        candidates = resolver.get_completion_candidates(prefix)
        print(f"'{prefix}' -> {candidates[:5]}")  # Show first 5

    # Test symbol finding
    print("\n=== Symbol Finding ===")
    test_symbols = ["Counter", "Test", "console"]

    for symbol in test_symbols:
        definitions = resolver.find_symbol_definition(symbol)
        print(f"{symbol} -> {len(definitions)} definitions")
        for file_path, line_num in definitions[:2]:  # Show first 2
            print(f"  - {file_path}:{line_num}")


if __name__ == "__main__":
    test_remapping_resolver()

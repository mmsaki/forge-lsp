#!/usr/bin/env python3
"""
Test script for forge diagnostics integration.
Tests both forge build and forge lint diagnostics.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider, ForgeRunner, ForgeOutputParser
    from lsprotocol.types import DiagnosticSeverity
    print("✓ Successfully imported forge diagnostics components")
except ImportError as e:
    print(f"✗ Failed to import forge diagnostics components: {e}")
    sys.exit(1)


def test_forge_build_diagnostics():
    """Test forge build diagnostics parsing."""
    print("\n=== Testing Forge Build Diagnostics ===")
    
    examples_dir = Path(__file__).parent / "examples"
    if not examples_dir.exists():
        print("⚠ Examples directory not found")
        return False
    
    try:
        runner = ForgeRunner()
        diagnostics = runner.run_forge_build_sync(str(examples_dir))
        
        print(f"✓ Found {len(diagnostics)} diagnostics from forge build")
        
        # Group diagnostics by type
        errors = [d for d in diagnostics if d.severity == DiagnosticSeverity.Error]
        warnings = [d for d in diagnostics if d.severity == DiagnosticSeverity.Warning]
        info = [d for d in diagnostics if d.severity == DiagnosticSeverity.Information]
        
        print(f"  - {len(errors)} errors")
        print(f"  - {len(warnings)} warnings")
        print(f"  - {len(info)} info/lint messages")
        
        # Show some examples
        if errors:
            print(f"\n  Example error:")
            error = errors[0]
            print(f"    {error.file_path}:{error.line + 1}:{error.column + 1}")
            print(f"    {error.message}")
            if error.code:
                print(f"    Code: {error.code}")
        
        if info:
            print(f"\n  Example lint message:")
            lint_msg = info[0]
            print(f"    {lint_msg.file_path}:{lint_msg.line + 1}:{lint_msg.column + 1}")
            print(f"    {lint_msg.message}")
            if lint_msg.code:
                print(f"    Code: {lint_msg.code}")
            if lint_msg.help_url:
                print(f"    Help: {lint_msg.help_url}")
        
        return len(diagnostics) > 0
        
    except Exception as e:
        print(f"✗ Error testing forge build: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_forge_lint_diagnostics():
    """Test forge lint diagnostics parsing."""
    print("\n=== Testing Forge Lint Diagnostics ===")
    
    examples_dir = Path(__file__).parent / "examples"
    if not examples_dir.exists():
        print("⚠ Examples directory not found")
        return False
    
    try:
        runner = ForgeRunner()
        diagnostics = await runner.run_forge_lint(str(examples_dir))
        
        print(f"✓ Found {len(diagnostics)} lint diagnostics")
        
        # Group by lint code
        lint_codes = {}
        for diag in diagnostics:
            code = diag.code or "unknown"
            if code not in lint_codes:
                lint_codes[code] = []
            lint_codes[code].append(diag)
        
        print(f"  Lint codes found:")
        for code, diags in lint_codes.items():
            print(f"    - {code}: {len(diags)} occurrences")
        
        # Show examples of each lint type
        for code, diags in list(lint_codes.items())[:3]:  # Show first 3 types
            diag = diags[0]
            print(f"\n  Example {code}:")
            print(f"    {diag.file_path}:{diag.line + 1}:{diag.column + 1}")
            print(f"    {diag.message}")
            if diag.help_url:
                print(f"    Help: {diag.help_url}")
        
        return len(diagnostics) > 0
        
    except Exception as e:
        print(f"✗ Error testing forge lint: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_diagnostics_provider():
    """Test the full diagnostics provider."""
    print("\n=== Testing Forge Diagnostics Provider ===")
    
    examples_dir = Path(__file__).parent / "examples"
    test_file = examples_dir / "src" / "C.sol"
    
    if not test_file.exists():
        print("⚠ Test file C.sol not found")
        return False
    
    try:
        provider = ForgeDiagnosticsProvider()
        diagnostics = provider.get_diagnostics_for_file(str(test_file))
        
        print(f"✓ Found {len(diagnostics)} diagnostics for C.sol")
        
        # Show diagnostics for this specific file
        for i, diag in enumerate(diagnostics[:5]):  # Show first 5
            severity_name = diag.severity.name if hasattr(diag.severity, 'name') else str(diag.severity)
            print(f"  {i+1}. [{severity_name}] Line {diag.range.start.line + 1}: {diag.message}")
            if diag.code:
                print(f"      Code: {diag.code}")
            if hasattr(diag, 'data') and diag.data and 'help_url' in diag.data:
                print(f"      Help: {diag.data['help_url']}")
        
        if len(diagnostics) > 5:
            print(f"  ... and {len(diagnostics) - 5} more")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing diagnostics provider: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_project_diagnostics():
    """Test getting diagnostics for the entire project."""
    print("\n=== Testing Project-wide Diagnostics ===")
    
    examples_dir = Path(__file__).parent / "examples"
    if not examples_dir.exists():
        print("⚠ Examples directory not found")
        return False
    
    try:
        provider = ForgeDiagnosticsProvider()
        diagnostics_by_file = provider.get_project_diagnostics(str(examples_dir))
        
        print(f"✓ Found diagnostics for {len(diagnostics_by_file)} files")
        
        total_diagnostics = sum(len(diags) for diags in diagnostics_by_file.values())
        print(f"  Total diagnostics: {total_diagnostics}")
        
        # Show breakdown by file
        for file_uri, diags in list(diagnostics_by_file.items())[:5]:  # Show first 5 files
            file_name = Path(file_uri.replace('file://', '')).name
            print(f"  {file_name}: {len(diags)} diagnostics")
        
        if len(diagnostics_by_file) > 5:
            print(f"  ... and {len(diagnostics_by_file) - 5} more files")
        
        return len(diagnostics_by_file) > 0
        
    except Exception as e:
        print(f"✗ Error testing project diagnostics: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_json_parsing():
    """Test JSON parsing with sample data."""
    print("\n=== Testing JSON Parsing ===")
    
    # Sample forge build JSON output
    build_json = '''
{
  "errors": [
    {
      "sourceLocation": {
        "file": "src/Test.sol",
        "start": 100,
        "end": 110
      },
      "type": "ParserError",
      "component": "general",
      "severity": "error",
      "errorCode": "6275",
      "message": "Source not found",
      "formattedMessage": "ParserError: Source not found\\n --> src/Test.sol:5:1:\\n"
    }
  ]
}
'''
    
    # Sample forge lint JSON output
    lint_json = '''
{"$message_type":"diag","message":"function names should use mixedCase","code":{"code":"mixed-case-function","explanation":null},"level":"note","spans":[{"file_name":"src/Test.sol","byte_start":100,"byte_end":110,"line_start":5,"line_end":5,"column_start":14,"column_end":22,"is_primary":true,"text":[{"text":"    function test_function() public {","highlight_start":14,"highlight_end":22}],"label":null}],"children":[{"message":"https://book.getfoundry.sh/reference/forge/forge-lint#mixed-case-function","code":null,"level":"help","spans":[],"children":[],"rendered":null}],"rendered":"note[mixed-case-function]: function names should use mixedCase"}
'''
    
    try:
        parser = ForgeOutputParser()
        
        # Test build JSON parsing
        build_diagnostics = parser.parse_forge_json_output(build_json, "/test")
        print(f"✓ Parsed {len(build_diagnostics)} diagnostics from build JSON")
        
        if build_diagnostics:
            diag = build_diagnostics[0]
            print(f"  Example: {diag.message} (code: {diag.code})")
        
        # Test lint JSON parsing
        lint_diagnostics = parser.parse_forge_lint_json(lint_json, "/test")
        print(f"✓ Parsed {len(lint_diagnostics)} diagnostics from lint JSON")
        
        if lint_diagnostics:
            diag = lint_diagnostics[0]
            print(f"  Example: {diag.message} (code: {diag.code})")
            if diag.help_url:
                print(f"  Help URL: {diag.help_url}")
        
        return len(build_diagnostics) > 0 and len(lint_diagnostics) > 0
        
    except Exception as e:
        print(f"✗ Error testing JSON parsing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🔧 Forge Diagnostics Test Suite")
    print("=" * 50)
    
    tests = [
        ("Forge Build Diagnostics", test_forge_build_diagnostics),
        ("Diagnostics Provider", test_diagnostics_provider),
        ("Project Diagnostics", test_project_diagnostics),
        ("JSON Parsing", test_json_parsing),
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
    
    print(f"\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Forge diagnostics are working!")
        print("\n🔥 Features Implemented:")
        print("  ✅ Forge build error parsing (JSON format)")
        print("  ✅ Forge lint diagnostics (JSON format)")
        print("  ✅ Comprehensive error categorization")
        print("  ✅ Help URL extraction for lint messages")
        print("  ✅ File-specific and project-wide diagnostics")
        print("  ✅ LSP diagnostic format conversion")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
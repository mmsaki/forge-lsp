# Testing and Debugging Guide

This guide covers comprehensive testing and debugging procedures for the Forge LSP server, including the diagnostic message processing improvements.

## Table of Contents

- [Quick Start Testing](#quick-start-testing)
- [Diagnostic Message Testing](#diagnostic-message-testing)
- [Debug Tools and Scripts](#debug-tools-and-scripts)
- [LSP Server Debugging](#lsp-server-debugging)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Performance Testing](#performance-testing)

## Quick Start Testing

### Prerequisites

```bash
# Ensure you have Python 3.8+ and forge installed
python3 --version
forge --version

# Install dependencies
pip install -r requirements.txt  # or use uv
```

### Basic Functionality Test

```bash
# Test basic diagnostics functionality
python3 test_forge_diagnostics.py

# Test message cleanup and formatting
python3 test_message_cleanup.py

# Test comprehensive lint message analysis
python3 test_lint_message_analysis.py
```

## Diagnostic Message Testing

### 1. Lint Message Cleanup Test

**Purpose**: Verify that linting messages are properly cleaned and formatted with original content.

```bash
python3 test_message_cleanup.py
```

**Expected Output**:
```
Testing message cleanup for: /Users/.../examples/src/TestLint.sol
Found 2 diagnostics:
  1. [forge-compile] Unused local variable.
      Line: 11, Column: 9
      Severity: 2
      Code: 2072

  2. [forge-lint] [forge lint] constants should use SCREAMING_SNAKE_CASE
      Line: 7, Column: 22
      Severity: 3
      Code: screaming-snake-case-const
      Help: https://book.getfoundry.sh/reference/forge/forge-lint#screaming-snake-case-const

✅ Linting messages are properly formatted and cleaned!
```

**What it tests**:
- Original message preservation
- ANSI escape sequence cleaning
- `[forge lint]` prefix addition
- Help URL cleaning
- Plain string text output

### 2. Comprehensive Message Analysis

**Purpose**: Deep analysis of raw vs processed lint messages to ensure completeness.

```bash
python3 test_lint_message_analysis.py
```

**Expected Output**:
```
=== Raw Forge Lint Output ===
Raw JSONC output:
{"$message_type":"diag","message":"constants should use SCREAMING_SNAKE_CASE",...}

=== Our Processed Output ===
Found 1 processed lint diagnostics:
Diagnostic 1:
  Message: '[forge lint] constants should use SCREAMING_SNAKE_CASE'
  Code: screaming-snake-case-const
  Help URL: https://book.getfoundry.sh/reference/forge/forge-lint#screaming-snake-case-const

=== Comparison Analysis ===
Raw message: 'constants should use SCREAMING_SNAKE_CASE'
Processed message: '[forge lint] constants should use SCREAMING_SNAKE_CASE'
```

**What it tests**:
- Raw forge output parsing
- Message field extraction
- Children element processing
- Help URL extraction from ANSI sequences
- Rendered field analysis

### 3. Debug Lint Parsing

**Purpose**: Step-by-step debugging of the lint parsing pipeline.

```bash
python3 debug_lint_parsing.py
```

**What it shows**:
- Raw JSONC structure from forge
- Manual parser method calls
- Message field contents
- Code extraction
- Rendered field analysis

## Debug Tools and Scripts

### 1. Manual Forge Command Testing

Test forge commands directly to understand output formats:

```bash
# Test forge lint directly
cd examples
forge lint src/TestLint.sol --json

# Test forge compile with linting
forge compile src/TestLint.sol --format-json

# Compare outputs
forge lint src/TestLint.sol --json 2>&1 | jq '.message'
forge compile src/TestLint.sol --format-json 2>&1 | grep '"message"'
```

### 2. JSONC Output Analysis

Analyze the structure of forge's JSONC output:

```bash
# Extract specific lint diagnostic
cd examples
forge compile src/TestLint.sol --format-json 2>&1 | \
  grep -A 1 -B 1 "screaming-snake-case-const"

# Check message fields
forge compile src/TestLint.sol --format-json 2>&1 | \
  grep -E '"message":|"rendered":'
```

### 3. ANSI Sequence Testing

Test ANSI escape sequence cleaning:

```python
# In Python REPL
from src.forge_lsp.forge_diagnostics import clean_ansi_sequences

# Test with actual forge output
test_message = "\u001b]8;;https://example.com\u001b\\link text\u001b]8;;\u001b\\"
cleaned = clean_ansi_sequences(test_message)
print(repr(cleaned))
```

## LSP Server Debugging

### 1. Server Startup and Initialization

```bash
# Start LSP server with debug logging
python3 -m src.forge_lsp --log-level DEBUG

# Test initialization
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}' | \
  python3 -m src.forge_lsp
```

### 2. Diagnostic Request Testing

```bash
# Test textDocument/didOpen
cat << 'EOF' | python3 -m src.forge_lsp
{"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"file:///path/to/test.sol","languageId":"solidity","version":1,"text":"contract Test {}"}}}
EOF
```

### 3. Cache Testing

Test diagnostic caching functionality:

```bash
python3 test_cache_functionality.py
```

**What it tests**:
- Cache hit/miss behavior
- Performance improvements
- Cache invalidation
- File modification detection

## Common Issues and Solutions

### Issue 1: Empty Lint Messages

**Symptom**: Lint messages show code-based fallback instead of descriptive text.

**Debug Steps**:
```bash
# Check if forge compile includes message field
cd examples
forge compile src/TestLint.sol --format-json 2>&1 | \
  grep -A 5 -B 5 '"message":""'

# Compare with forge lint direct output
forge lint src/TestLint.sol --json 2>&1 | \
  grep -A 5 -B 5 '"message":'
```

**Solution**: The issue was that `forge compile` outputs empty message fields, while `forge lint` includes descriptive messages. Fixed by:
1. Extracting from `rendered` field when `message` is empty
2. Adding descriptive fallback mapping for common lint codes

### Issue 2: ANSI Escape Sequences in URLs

**Symptom**: Help URLs contain weird characters like `8;;` or escape sequences.

**Debug Steps**:
```bash
# Check raw URL content
cd examples
forge compile src/TestLint.sol --format-json 2>&1 | \
  grep -o '\u001b]8;;[^\\]*\u001b\\[^\\]*\u001b]8;;\u001b\\'
```

**Solution**: Enhanced URL cleaning regex to handle OSC sequences and duplicated fragments.

### Issue 3: Double Prefixes

**Symptom**: Messages show `[forge-lint] [forge lint] message`.

**Debug Steps**:
```bash
# Check source field vs message content
python3 -c "
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider
import asyncio
async def test():
    provider = ForgeDiagnosticsProvider()
    diags = await provider.get_diagnostics_for_file_async('examples/src/TestLint.sol')
    for d in diags:
        print(f'Source: {d.source}, Message: {d.message}')
asyncio.run(test())
"
```

**Solution**: Removed manual prefix addition since LSP client already displays source field.

## Performance Testing

### 1. Diagnostic Speed Test

```bash
# Time diagnostic generation
time python3 -c "
import asyncio
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def test():
    provider = ForgeDiagnosticsProvider()
    diags = await provider.get_diagnostics_for_file_async('examples/src/TestLint.sol', use_cache=False)
    print(f'Generated {len(diags)} diagnostics')

asyncio.run(test())
"
```

### 2. Cache Performance Test

```bash
python3 test_cache_functionality.py
```

### 3. Memory Usage Test

```bash
# Monitor memory usage during diagnostic generation
python3 -c "
import psutil
import asyncio
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def test():
    process = psutil.Process()
    print(f'Initial memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
    
    provider = ForgeDiagnosticsProvider()
    for i in range(10):
        diags = await provider.get_diagnostics_for_file_async('examples/src/TestLint.sol')
        print(f'Iteration {i+1}: {process.memory_info().rss / 1024 / 1024:.1f} MB')

asyncio.run(test())
"
```

## Test File Structure

```
tests/
├── test_message_cleanup.py          # Main lint message testing
├── test_lint_message_analysis.py    # Comprehensive message analysis
├── debug_lint_parsing.py            # Step-by-step parsing debug
├── test_forge_diagnostics.py        # General diagnostics testing
├── test_cache_functionality.py      # Cache behavior testing
├── test_error_diagnostics.py        # Error handling testing
└── examples/
    └── src/
        ├── TestLint.sol             # Lint issues test file
        ├── TestErrors.sol           # Compilation errors test file
        └── TestWarnings.sol         # Warning messages test file
```

## Debugging Workflow

When investigating lint message issues:

1. **Start with raw forge output**:
   ```bash
   forge lint src/TestLint.sol --json
   forge compile src/TestLint.sol --format-json
   ```

2. **Test manual parsing**:
   ```bash
   python3 debug_lint_parsing.py
   ```

3. **Check full pipeline**:
   ```bash
   python3 test_message_cleanup.py
   ```

4. **Analyze differences**:
   ```bash
   python3 test_lint_message_analysis.py
   ```

5. **Verify in LSP context**:
   ```bash
   python3 test_lsp_server.py
   ```

## Environment Variables

Useful environment variables for debugging:

```bash
# Disable forge nightly warnings
export FOUNDRY_DISABLE_NIGHTLY_WARNING=1

# Enable debug logging
export FORGE_LSP_LOG_LEVEL=DEBUG

# Force cache refresh
export FORGE_LSP_NO_CACHE=1
```

## Continuous Testing

For ongoing development, run the full test suite:

```bash
#!/bin/bash
# run_tests.sh

echo "🧪 Running Forge LSP Test Suite"
echo "================================"

echo "📋 Testing message cleanup..."
python3 test_message_cleanup.py || exit 1

echo "🔍 Testing lint message analysis..."
python3 test_lint_message_analysis.py || exit 1

echo "⚡ Testing cache functionality..."
python3 test_cache_functionality.py || exit 1

echo "🏗️  Testing forge diagnostics..."
python3 test_forge_diagnostics.py || exit 1

echo "✅ All tests passed!"
```

This comprehensive testing and debugging guide ensures reliable development and maintenance of the Forge LSP server's diagnostic capabilities.
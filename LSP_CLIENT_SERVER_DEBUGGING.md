# LSP Client-Server Debugging Guide

This guide covers comprehensive debugging techniques for the Forge LSP server and client interactions, including all the diagnostic message processing work.

## Table of Contents

- [LSP Protocol Debugging](#lsp-protocol-debugging)
- [Server-Side Debugging](#server-side-debugging)
- [Client-Side Debugging](#client-side-debugging)
- [Message Flow Analysis](#message-flow-analysis)
- [Diagnostic Processing Debug](#diagnostic-processing-debug)
- [Real-World Debugging Scenarios](#real-world-debugging-scenarios)

## LSP Protocol Debugging

### 1. Manual LSP Communication Testing

Test LSP protocol messages manually to understand the communication flow:

```bash
# Start LSP server in stdio mode
python3 -m src.forge_lsp

# Send initialization request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{"textDocument":{"publishDiagnostics":{"relatedInformation":true}}},"rootUri":"file:///path/to/project"}}' | python3 -m src.forge_lsp
```

### 2. LSP Message Logging

Enable comprehensive message logging:

```python
# In your LSP server code
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lsp_debug.log'),
        logging.StreamHandler()
    ]
)

# Log all incoming/outgoing messages
logger = logging.getLogger('lsp_messages')
logger.debug(f"Received: {message}")
logger.debug(f"Sending: {response}")
```

### 3. Protocol Compliance Testing

Test LSP protocol compliance:

```bash
# Test initialize sequence
cat << 'EOF' | python3 -m src.forge_lsp
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}
{"jsonrpc":"2.0","method":"initialized","params":{}}
{"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"file:///test.sol","languageId":"solidity","version":1,"text":"contract Test {}"}}}
EOF
```

## Server-Side Debugging

### 1. Diagnostic Generation Debug

Debug the diagnostic generation pipeline:

```python
# debug_diagnostics.py
import asyncio
import logging
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

logging.basicConfig(level=logging.DEBUG)

async def debug_diagnostics():
    provider = ForgeDiagnosticsProvider()
    
    # Test file path
    test_file = "examples/src/TestLint.sol"
    
    print("🔍 Debugging diagnostic generation...")
    
    # Step 1: Check project root detection
    project_root = provider.get_project_root(test_file)
    print(f"Project root: {project_root}")
    
    # Step 2: Test forge runner
    runner = provider.forge_runner
    print(f"Forge path: {runner.forge_path}")
    print(f"Supports linting: {runner._supports_linting()}")
    
    # Step 3: Generate diagnostics with debug info
    diagnostics = await provider.get_diagnostics_for_file_async(test_file, use_cache=False)
    
    print(f"\n📊 Generated {len(diagnostics)} diagnostics:")
    for i, diag in enumerate(diagnostics):
        print(f"  {i+1}. [{diag.source}] {diag.message}")
        print(f"      Severity: {diag.severity}, Code: {diag.code}")
        if hasattr(diag, 'data') and diag.data:
            print(f"      Data: {diag.data}")

if __name__ == "__main__":
    asyncio.run(debug_diagnostics())
```

### 2. Forge Command Debug

Debug forge command execution:

```python
# debug_forge_commands.py
import asyncio
import subprocess
import json

async def debug_forge_commands():
    print("🔨 Debugging forge commands...")
    
    # Test forge compile
    print("\n1. Testing forge compile:")
    result = await asyncio.create_subprocess_exec(
        "forge", "compile", "src/TestLint.sol", "--format-json",
        cwd="examples",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await result.communicate()
    
    print(f"Return code: {result.returncode}")
    print(f"Stdout length: {len(stdout.decode())}")
    print(f"Stderr length: {len(stderr.decode())}")
    
    # Parse and analyze JSONC output
    jsonc_lines = stderr.decode().strip().split('\n')
    print(f"JSONC lines: {len(jsonc_lines)}")
    
    for i, line in enumerate(jsonc_lines[:3]):  # Show first 3 lines
        if line.strip():
            try:
                data = json.loads(line)
                print(f"  Line {i+1}: {data.get('$message_type', 'unknown')} - {data.get('code', {}).get('code', 'no-code')}")
            except json.JSONDecodeError:
                print(f"  Line {i+1}: Invalid JSON")

if __name__ == "__main__":
    asyncio.run(debug_forge_commands())
```

### 3. Message Processing Debug

Debug the lint message processing pipeline:

```python
# debug_message_processing.py
import json
from src.forge_lsp.forge_diagnostics import ForgeOutputParser, clean_ansi_sequences

def debug_message_processing():
    print("🔧 Debugging message processing...")
    
    # Sample JSONC data from forge compile
    sample_jsonc = '''{"$message_type":"diag","message":"","code":{"code":"screaming-snake-case-const","explanation":null},"level":"note","spans":[{"file_name":"src/TestLint.sol","byte_start":194,"byte_end":207,"line_start":7,"line_end":7,"column_start":22,"column_end":35,"is_primary":true,"text":[{"text":"    uint256 constant constantValue = 100;","highlight_start":22,"highlight_end":35}],"label":null}],"children":[{"message":"\\u001b]8;;https://example.com\\u001b\\\\link\\u001b]8;;\\u001b\\\\","code":null,"level":"help","spans":[],"children":[],"rendered":null}],"rendered":"note[screaming-snake-case-const]: constants should use SCREAMING_SNAKE_CASE\\n --> src/TestLint.sol:7:22\\n"}'''
    
    parser = ForgeOutputParser()
    
    # Parse the JSONC line
    data = json.loads(sample_jsonc)
    
    print("📋 Raw data analysis:")
    print(f"  Message field: {repr(data.get('message', ''))}")
    print(f"  Code: {data.get('code', {}).get('code', 'N/A')}")
    print(f"  Level: {data.get('level', 'N/A')}")
    print(f"  Children: {len(data.get('children', []))}")
    print(f"  Rendered: {repr(data.get('rendered', '')[:100])}...")
    
    # Test ANSI cleaning
    if data.get('children'):
        child_message = data['children'][0].get('message', '')
        print(f"\n🧹 ANSI cleaning test:")
        print(f"  Original: {repr(child_message)}")
        print(f"  Cleaned:  {repr(clean_ansi_sequences(child_message))}")
    
    # Test diagnostic parsing
    diagnostic = parser._parse_lint_jsonc_diag(data, "/test/dir")
    if diagnostic:
        print(f"\n✅ Parsed diagnostic:")
        print(f"  Message: {repr(diagnostic.message)}")
        print(f"  Code: {diagnostic.code}")
        print(f"  Help URL: {diagnostic.help_url}")
    else:
        print("\n❌ Failed to parse diagnostic")

if __name__ == "__main__":
    debug_message_processing()
```

## Client-Side Debugging

### 1. VS Code Extension Debug

For VS Code extension debugging:

```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug LSP Client",
            "type": "extensionHost",
            "request": "launch",
            "args": ["--extensionDevelopmentPath=${workspaceFolder}"],
            "outFiles": ["${workspaceFolder}/out/**/*.js"],
            "preLaunchTask": "npm: compile"
        }
    ]
}
```

### 2. Client Message Tracing

Enable client-side message tracing:

```typescript
// In your LSP client code
import { LanguageClient, TransportKind } from 'vscode-languageclient/node';

const client = new LanguageClient(
    'forge-lsp',
    'Forge LSP',
    serverOptions,
    clientOptions
);

// Enable tracing
client.trace = Trace.Verbose;

// Log all messages
client.onRequest((method, params) => {
    console.log(`Request: ${method}`, params);
});

client.onNotification((method, params) => {
    console.log(`Notification: ${method}`, params);
});
```

### 3. Diagnostic Display Debug

Debug how diagnostics are displayed in the client:

```typescript
// Debug diagnostic processing
client.onNotification('textDocument/publishDiagnostics', (params) => {
    console.log('Received diagnostics:', {
        uri: params.uri,
        diagnostics: params.diagnostics.map(d => ({
            message: d.message,
            severity: d.severity,
            source: d.source,
            code: d.code,
            range: d.range
        }))
    });
});
```

## Message Flow Analysis

### 1. Complete Message Flow Trace

Trace the complete message flow from client to server:

```bash
# Create a trace script
cat << 'EOF' > trace_lsp_flow.py
import asyncio
import json
import sys
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def trace_flow():
    print("🔄 Tracing complete LSP message flow...")
    
    # Step 1: Client sends textDocument/didOpen
    print("\n1️⃣ Client: textDocument/didOpen")
    file_uri = "file:///path/to/test.sol"
    file_content = "contract Test { uint256 constant value = 1; }"
    
    # Step 2: Server processes file
    print("2️⃣ Server: Processing file...")
    provider = ForgeDiagnosticsProvider()
    
    # Extract file path from URI
    file_path = file_uri.replace("file://", "")
    
    # Step 3: Generate diagnostics
    print("3️⃣ Server: Generating diagnostics...")
    try:
        diagnostics = await provider.get_diagnostics_for_file_async(file_path)
        print(f"   Generated {len(diagnostics)} diagnostics")
    except Exception as e:
        print(f"   Error: {e}")
        diagnostics = []
    
    # Step 4: Convert to LSP format
    print("4️⃣ Server: Converting to LSP format...")
    lsp_diagnostics = []
    for diag in diagnostics:
        lsp_diag = {
            "range": {
                "start": {"line": diag.range.start.line, "character": diag.range.start.character},
                "end": {"line": diag.range.end.line, "character": diag.range.end.character}
            },
            "message": diag.message,
            "severity": diag.severity,
            "source": diag.source,
            "code": diag.code
        }
        lsp_diagnostics.append(lsp_diag)
    
    # Step 5: Send publishDiagnostics
    print("5️⃣ Server: Sending publishDiagnostics...")
    publish_message = {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": file_uri,
            "diagnostics": lsp_diagnostics
        }
    }
    
    print("6️⃣ Client: Receives diagnostics...")
    print(json.dumps(publish_message, indent=2))

if __name__ == "__main__":
    asyncio.run(trace_flow())
EOF

python3 trace_lsp_flow.py
```

### 2. Performance Analysis

Analyze performance bottlenecks:

```python
# performance_analysis.py
import asyncio
import time
import psutil
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def analyze_performance():
    print("⚡ Performance Analysis...")
    
    provider = ForgeDiagnosticsProvider()
    test_file = "examples/src/TestLint.sol"
    
    # Memory usage before
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024
    
    # Time diagnostic generation
    start_time = time.time()
    diagnostics = await provider.get_diagnostics_for_file_async(test_file, use_cache=False)
    end_time = time.time()
    
    # Memory usage after
    mem_after = process.memory_info().rss / 1024 / 1024
    
    print(f"📊 Results:")
    print(f"  Time taken: {end_time - start_time:.3f}s")
    print(f"  Memory before: {mem_before:.1f} MB")
    print(f"  Memory after: {mem_after:.1f} MB")
    print(f"  Memory delta: {mem_after - mem_before:.1f} MB")
    print(f"  Diagnostics generated: {len(diagnostics)}")
    
    # Test with cache
    start_time = time.time()
    cached_diagnostics = await provider.get_diagnostics_for_file_async(test_file, use_cache=True)
    end_time = time.time()
    
    print(f"  Cached time: {end_time - start_time:.3f}s")
    print(f"  Cache hit: {len(cached_diagnostics) == len(diagnostics)}")

if __name__ == "__main__":
    asyncio.run(analyze_performance())
```

## Diagnostic Processing Debug

### 1. Step-by-Step Diagnostic Debug

Debug each step of diagnostic processing:

```python
# step_by_step_debug.py
import asyncio
import json
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider, ForgeRunner

async def step_by_step_debug():
    print("🔍 Step-by-step diagnostic debugging...")
    
    # Step 1: Initialize components
    print("\n1️⃣ Initializing components...")
    provider = ForgeDiagnosticsProvider()
    runner = ForgeRunner()
    
    # Step 2: Check forge availability
    print("2️⃣ Checking forge availability...")
    version = runner._get_forge_version()
    supports_lint = runner._supports_linting()
    print(f"   Forge version: {version}")
    print(f"   Supports linting: {supports_lint}")
    
    # Step 3: Run forge compile
    print("3️⃣ Running forge compile...")
    working_dir = "examples"
    file_path = "src/TestLint.sol"
    
    try:
        diagnostics = await runner.run_forge_compile(working_dir, file_path, use_cache=False)
        print(f"   Generated {len(diagnostics)} raw diagnostics")
        
        # Analyze each diagnostic
        for i, diag in enumerate(diagnostics):
            print(f"   Diagnostic {i+1}:")
            print(f"     Source: {diag.source}")
            print(f"     Category: {diag.category}")
            print(f"     Message: {repr(diag.message[:50])}...")
            print(f"     Code: {diag.code}")
            
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(step_by_step_debug())
```

### 2. Message Comparison Debug

Compare raw forge output with processed messages:

```bash
# Create comparison script
cat << 'EOF' > compare_messages.py
import subprocess
import json
import asyncio
from src.forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def compare_messages():
    print("🔄 Comparing raw forge output with processed messages...")
    
    # Get raw forge lint output
    print("\n📥 Raw forge lint output:")
    result = subprocess.run(
        ["forge", "lint", "src/TestLint.sol", "--json"],
        cwd="examples",
        capture_output=True,
        text=True
    )
    
    raw_lines = result.stderr.strip().split('\n')
    for line in raw_lines:
        if line.strip():
            try:
                data = json.loads(line)
                print(f"  Raw message: {repr(data.get('message', ''))}")
                print(f"  Raw code: {data.get('code', {}).get('code', 'N/A')}")
            except json.JSONDecodeError:
                pass
    
    # Get processed output
    print("\n📤 Processed LSP output:")
    provider = ForgeDiagnosticsProvider()
    diagnostics = await provider.get_diagnostics_for_file_async("examples/src/TestLint.sol")
    
    lint_diags = [d for d in diagnostics if d.source == "forge-lint"]
    for diag in lint_diags:
        print(f"  Processed message: {repr(diag.message)}")
        print(f"  Processed code: {diag.code}")

if __name__ == "__main__":
    asyncio.run(compare_messages())
EOF

python3 compare_messages.py
```

## Real-World Debugging Scenarios

### Scenario 1: Missing Lint Messages

**Problem**: Lint messages not appearing in client

**Debug Steps**:

1. **Check forge version**:
   ```bash
   forge --version
   # Ensure it's nightly build for linting support
   ```

2. **Test forge lint directly**:
   ```bash
   cd examples
   forge lint src/TestLint.sol --json
   ```

3. **Check LSP server logs**:
   ```bash
   # Enable debug logging
   FORGE_LSP_LOG_LEVEL=DEBUG python3 -m src.forge_lsp
   ```

4. **Verify message processing**:
   ```python
   python3 debug_lint_parsing.py
   ```

### Scenario 2: Malformed Diagnostic Messages

**Problem**: Diagnostic messages contain ANSI sequences or weird characters

**Debug Steps**:

1. **Check raw forge output**:
   ```bash
   forge compile src/TestLint.sol --format-json 2>&1 | hexdump -C
   ```

2. **Test ANSI cleaning**:
   ```python
   from src.forge_lsp.forge_diagnostics import clean_ansi_sequences
   test_msg = "\u001b]8;;url\u001b\\text\u001b]8;;\u001b\\"
   print(repr(clean_ansi_sequences(test_msg)))
   ```

3. **Verify message processing**:
   ```python
   python3 test_message_cleanup.py
   ```

### Scenario 3: Performance Issues

**Problem**: LSP server is slow to respond

**Debug Steps**:

1. **Profile diagnostic generation**:
   ```python
   python3 performance_analysis.py
   ```

2. **Check cache effectiveness**:
   ```python
   python3 test_cache_functionality.py
   ```

3. **Monitor system resources**:
   ```bash
   # While running LSP server
   top -p $(pgrep -f "forge_lsp")
   ```

### Scenario 4: Client-Server Communication Issues

**Problem**: Client not receiving diagnostics

**Debug Steps**:

1. **Test LSP protocol manually**:
   ```bash
   echo '{"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"file:///test.sol","languageId":"solidity","version":1,"text":"contract Test {}"}}}' | python3 -m src.forge_lsp
   ```

2. **Enable message tracing**:
   ```typescript
   // In client code
   client.trace = Trace.Verbose;
   ```

3. **Check server response format**:
   ```python
   python3 trace_lsp_flow.py
   ```

## Debugging Checklist

When debugging LSP issues, follow this checklist:

- [ ] **Environment Setup**
  - [ ] Python 3.8+ installed
  - [ ] Forge nightly installed
  - [ ] Dependencies installed
  - [ ] PYTHONPATH set correctly

- [ ] **Server Functionality**
  - [ ] Server starts without errors
  - [ ] Forge commands execute successfully
  - [ ] Diagnostics generate correctly
  - [ ] Message processing works

- [ ] **Client Communication**
  - [ ] Initialize sequence completes
  - [ ] textDocument/didOpen works
  - [ ] publishDiagnostics received
  - [ ] Messages properly formatted

- [ ] **Message Quality**
  - [ ] Original messages preserved
  - [ ] ANSI sequences cleaned
  - [ ] URLs properly formatted
  - [ ] Prefixes added correctly

This comprehensive debugging guide ensures you can effectively troubleshoot and maintain the Forge LSP server's diagnostic capabilities.
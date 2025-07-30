# Foundry Remapping System for LSP

This document explains how the forge-lsp implements dynamic remapping resolution using Foundry's build output to enable proper import resolution, go-to-definition, and intelligent completions.

## Overview

The remapping system reads from Foundry's compiled output instead of hardcoding remappings, providing a natural way for the LSP to resolve all file imports correctly. This enables:

- **Go-to-definition**: Jump to external library functions and contracts
- **References**: Find all usages of symbols across the project
- **Smart completions**: Context-aware completions for library functions
- **Import resolution**: Proper resolution of complex import paths

## Architecture

### Key Components

1. **RemappingResolver** (`src/forge_lsp/remapping_resolver.py`)
   - Extracts remappings from `forge remappings` command
   - Reads file cache from `cache/solidity-files-cache.json`
   - Loads build info from `out/build-info/*.json`
   - Provides import resolution and symbol finding

2. **FoundryIntegration** (`src/forge_lsp/foundry_integration.py`)
   - Integrates RemappingResolver with LSP features
   - Provides high-level API for symbol resolution
   - Handles Foundry-specific completions

3. **Cache Structure**
   - `cache/solidity-files-cache.json`: Contains file metadata and imports
   - `out/build-info/*.json`: Contains source ID mappings
   - `out/`: Contains compiled artifacts and source maps

## How It Works

### 1. Remapping Extraction

```python
# Get remappings from forge command
result = subprocess.run(["forge", "remappings"], ...)
# Example output: "forge-std/=lib/forge-std/src/"
```

### 2. Cache Loading

```python
# Load file cache
with open("cache/solidity-files-cache.json") as f:
    cache_data = json.load(f)
    
# Example cache entry:
{
  "lib/forge-std/src/Test.sol": {
    "imports": ["lib/forge-std/src/Vm.sol", ...],
    "artifacts": {...}
  }
}
```

### 3. Import Resolution

```python
def resolve_import(self, import_path: str, from_file: str = None):
    # 1. Handle relative imports (./Counter.sol)
    # 2. Apply remapping rules (forge-std/Test.sol -> lib/forge-std/src/Test.sol)
    # 3. Try direct resolution from project root
    # 4. Search in common library directories
```

### 4. Symbol Finding

```python
def find_symbol_definition(self, symbol: str):
    # Search all project files for symbol definitions
    # Pattern match: contract Counter, function increment, etc.
    # Return list of (file_path, line_number) tuples
```

## Usage Examples

### Basic Import Resolution

```python
from forge_lsp.remapping_resolver import RemappingResolver

resolver = RemappingResolver(Path("./foundry-project"))

# Resolve forge-std import
resolved = resolver.resolve_import("forge-std/Test.sol")
# Returns: /path/to/project/lib/forge-std/src/Test.sol

# Resolve relative import
resolved = resolver.resolve_import("./Counter.sol", "src/ExampleContract.sol")
# Returns: /path/to/project/src/Counter.sol
```

### Symbol Definition Finding

```python
# Find all definitions of "Counter" contract
definitions = resolver.find_symbol_definition("Counter")
# Returns: [(Path("src/Counter.sol"), 4), (Path("test/Counter.t.sol"), 7)]

# Find "Test" contract from forge-std
definitions = resolver.find_symbol_definition("Test")
# Returns: [(Path("lib/forge-std/src/Test.sol"), 31)]
```

### Completion Candidates

```python
# Get completion candidates for imports
candidates = resolver.get_completion_candidates("forge-std/")
# Returns: ["forge-std/Test.sol", "forge-std/console.sol", "forge-std/Vm.sol", ...]

candidates = resolver.get_completion_candidates("src/")
# Returns: ["src/Counter.sol", "src/ExampleContract.sol", ...]
```

## LSP Integration

### Go-to-Definition

When a user requests go-to-definition on an import or symbol:

1. Extract the symbol/import at cursor position
2. Use `resolve_import()` for import statements
3. Use `find_symbol_definition()` for contract/function names
4. Return LSP Location objects pointing to the resolved files

### Completions

For import statement completions:

1. Extract the partial import path being typed
2. Use `get_completion_candidates()` to get matching files
3. Return LSP CompletionItem objects with proper insert text

### References

To find all references to a symbol:

1. Find the symbol definition using `find_symbol_definition()`
2. Search all project files for usages of the symbol
3. Return LSP Location objects for all found references

## File Structure

```
foundry-project/
├── cache/
│   └── solidity-files-cache.json    # File metadata and imports
├── out/
│   ├── build-info/
│   │   └── *.json                   # Source ID mappings
│   └── */                           # Compiled artifacts
├── lib/
│   └── forge-std/                   # External libraries
├── src/
│   └── *.sol                        # Source files
└── foundry.toml                     # Project configuration
```

## Benefits

1. **No Hardcoded Remappings**: Dynamically reads from forge output
2. **Accurate Resolution**: Uses the same resolution logic as forge
3. **Library Support**: Proper support for external libraries and dependencies
4. **Performance**: Caches file information for fast lookups
5. **Extensible**: Easy to add support for new import patterns

## Testing

Run the test script to verify functionality:

```bash
python tests/test_remapping.py
```

This will test:
- Remapping extraction
- Import resolution
- File cache loading
- Symbol finding
- Completion candidates

## Future Enhancements

1. **Incremental Updates**: Watch for file changes and update cache incrementally
2. **Better Symbol Parsing**: Use a proper Solidity AST parser for more accurate symbol detection
3. **Cross-Reference Analysis**: Build a complete symbol table with type information
4. **Workspace Support**: Handle multi-project workspaces with different foundry.toml files
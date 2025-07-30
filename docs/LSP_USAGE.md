# Forge LSP Server Usage Guide

## Overview

The Forge LSP Server provides real-time diagnostics for Solidity files using `forge compile --json` output. It integrates with any LSP-compatible editor to show compilation errors, warnings, and other diagnostics directly in your editor.

## Features

✅ **Real-time diagnostics** - Get compilation errors as you type  
✅ **Forge integration** - Uses `forge compile --json` for accurate diagnostics  
✅ **File-specific compilation** - Compiles individual files for faster feedback  
✅ **Debounced updates** - Avoids excessive compilation during rapid typing  
✅ **Project detection** - Automatically finds `foundry.toml` to determine project root  
✅ **LSP standard compliance** - Works with any LSP-compatible editor  

## Installation

1. Install the package:
```bash
pip install -e .
```

2. Make sure you have `forge` installed and available in your PATH:
```bash
forge --version
```

## Running the LSP Server

### Command Line
```bash
forge-lsp
```

### Programmatically
```python
from forge_lsp import main
main()
```

## Editor Integration

### VS Code
Add this to your VS Code settings.json:
```json
{
  "solidity.defaultCompiler": "localNodeModule",
  "solidity.compileUsingRemoteVersion": "",
  "solidity.enabledAsYouTypeCompilationErrorCheck": false,
  "solidity.validationDelay": 1500
}
```

Then install a generic LSP client extension and configure it to use `forge-lsp`.

### Neovim
Example configuration with nvim-lspconfig:
```lua
local lspconfig = require('lspconfig')

lspconfig.forge_lsp = {
  default_config = {
    cmd = { 'forge-lsp' },
    filetypes = { 'solidity' },
    root_dir = function(fname)
      return lspconfig.util.find_git_ancestor(fname) or 
             lspconfig.util.root_pattern('foundry.toml')(fname)
    end,
    settings = {},
  },
}

lspconfig.forge_lsp.setup{}
```

### Other Editors
Any editor that supports LSP can use this server. Configure your editor's LSP client to:
- **Command**: `forge-lsp`
- **File types**: `solidity`, `sol`
- **Root directory**: Directory containing `foundry.toml`

## How It Works

1. **File Detection**: When you open a `.sol` file, the server detects the project root by looking for `foundry.toml`

2. **File-Specific Compilation**: The server always compiles the specific file you're working on, not the entire project:
   - **On typing/changes**: `forge compile <filename> --format-json` (uses cache for speed)
   - **On save**: `forge compile <filename> --format-json --no-cache` (ensures all warnings are shown)

3. **Parsing**: The JSON output is parsed to extract:
   - Error messages
   - Line/column positions  
   - Severity levels
   - Error codes
   - Source information

4. **LSP Diagnostics**: Errors are converted to LSP diagnostic format and sent to your editor

### Key Benefits of File-Specific Compilation

- **Faster feedback**: Only compiles the current file, not the entire project
- **Current buffer focus**: Always shows diagnostics for the file you're editing
- **Optimal performance**: Uses caching during typing, full compilation on save
- **Warning visibility**: `--no-cache` on save ensures warnings appear even for simple/empty files

## Diagnostic Information

Each diagnostic includes:
- **Location**: Precise line and column numbers
- **Message**: Clear error description from Forge
- **Severity**: Error, Warning, Information, or Hint
- **Code**: Forge error code (e.g., "7576")
- **Source**: "forge-compile" to identify the source

## Example Output

For a file with an undeclared variable:
```solidity
contract Test {
    function bad() public {
        undefinedVar = 10; // Error on this line
    }
}
```

The LSP server will report:
- **Line 3, Column 9**: "Undeclared identifier."
- **Severity**: Error
- **Code**: 7576
- **Source**: forge-compile

## Performance Features

- **File-specific compilation**: Always compiles only the current file, not the entire project
- **Smart caching strategy**: 
  - Uses cache during typing for fast feedback
  - Uses `--no-cache` on save to ensure all warnings are visible
- **Debouncing**: 500ms delay on file changes to avoid excessive compilation
- **Async processing**: Non-blocking compilation using asyncio
- **Current buffer focus**: Diagnostics always target the file you're actively editing

### Compilation Strategy

| Event | Command | Purpose |
|-------|---------|---------|
| File open | `forge compile <file> --format-json` | Fast initial feedback |
| Typing/changes | `forge compile <file> --format-json` | Quick error detection |
| File save | `forge compile <file> --format-json --no-cache` | Complete analysis with all warnings |

## Troubleshooting

### No diagnostics appearing
1. Check that `forge` is installed: `forge --version`
2. Verify `foundry.toml` exists in your project root
3. Check LSP server logs for error messages

### Slow performance
- The server uses debouncing (500ms delay) to avoid excessive compilation
- Large projects may take longer to compile

### Incorrect error positions
- Make sure your file is saved - the server compiles the file on disk
- Check that the file path is correct relative to the project root

## Testing

Run the included test scripts to verify functionality:

```bash
# Test basic functionality
python3 tests/test_lsp_server.py

# Test error detection
python3 tests/test_error_diagnostics.py
```

## Architecture

The LSP server consists of:

- **`__init__.py`**: Main LSP server implementation with pygls
- **`forge_diagnostics.py`**: Forge integration and JSON parsing
- **Debouncing**: Prevents excessive compilation during rapid typing
- **Async processing**: Non-blocking compilation using asyncio

## Contributing

The server is designed to be extensible. Key areas for enhancement:
- Additional LSP features (hover, completion, go-to-definition)
- Better error message formatting
- Support for additional Forge commands
- Performance optimizations
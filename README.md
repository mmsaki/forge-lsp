# Forge LSP

A Language Server Protocol (LSP) implementation for Solidity development with Foundry integration. This LSP server provides real-time compilation and linting diagnostics for Foundry-based Solidity projects.

## Features

### Diagnostics
- **Compilation Diagnostics**: Real-time error detection using `forge compile --json`
- **Linting Diagnostics**: Code style and best practice warnings using `forge lint --json` (forge nightly only)
- **File-based Analysis**: Diagnostics triggered on file open and save
- **Forge Version Detection**: Automatically detects forge stable vs nightly and adjusts features accordingly

### Foundry Integration
- **Forge Build Integration**: Uses `forge compile` for compilation diagnostics
- **Forge Lint Integration**: Uses `forge lint` for linting diagnostics (nightly only)
- **Project Structure Awareness**: Understands Foundry project layout and `foundry.toml` configuration
- **Version Compatibility**: Works with both forge stable and nightly versions

## Installation

### Prerequisites
- Python 3.9 or higher
- [Foundry](https://getfoundry.sh/) installed and available in PATH
- A Neovim setup with LSP support

### Install the LSP Server

```bash
# Clone the repository
git clone <repository-url>
cd forge_lsp

# Install using uv (recommended)
uv pip install -e .

# Or install using pip
pip install -e .
```

### Verify Installation

```bash
forge-lsp --help
```

## Neovim Configuration

### Using lazy.nvim

Add this to your Neovim configuration:

```lua
{
  "neovim/nvim-lspconfig",
  config = function()
    -- Load the forge-lsp configuration
    local forge_lsp = require('path.to.forge-lsp')
    
    -- Setup the LSP server
    forge_lsp.setup({
      -- Custom configuration options
      settings = {
        forge = {
          foundry = {
            profile = "default",
            buildOnSave = true,
          },
        },
      },
    })
  end,
}
```

### Manual Configuration

Add this to your `init.lua`:

```lua
-- Copy the contents of nvim/forge-lsp.lua to your config
-- Then call:
require('forge-lsp').setup()
```

### Usage

The LSP server automatically provides diagnostics when you:
- Open a Solidity file (`.sol`)
- Save a Solidity file
- Make changes to a Solidity file (with debouncing)

No additional key bindings are required - diagnostics appear automatically in your editor's diagnostic interface.

## Project Structure

For optimal functionality, your Foundry project should follow this structure:

```
my-foundry-project/
├── foundry.toml          # Foundry configuration
├── src/                  # Contract source files
│   └── Contract.sol
├── test/                 # Test files
│   └── Contract.t.sol
├── lib/                  # Dependencies
│   ├── forge-std/
│   └── openzeppelin-contracts/
└── out/                  # Build artifacts
```

## Configuration

### Foundry Configuration

The LSP server reads your `foundry.toml` file for project configuration:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
test = "test"
cache_path = "cache"

# Compiler settings
solc_version = "0.8.19"
optimizer = true
optimizer_runs = 200
```

### LSP Settings

The LSP server currently focuses on diagnostics and requires minimal configuration. It automatically:
- Detects forge version (stable vs nightly)
- Enables compilation diagnostics for all versions
- Enables linting diagnostics for nightly versions only
- Triggers diagnostics on file open and save events

## Supported File Types

- `.sol` - Solidity source files
- `.t.sol` - Foundry test files (with additional test-specific features)

## Development

### Running from Source

```bash
# Install in development mode
uv pip install -e .

# Run the LSP server
forge-lsp

# Run with debug logging
PYTHONPATH=src python -m forge_lsp --log-level debug
```

### Testing

```bash
# Install test dependencies
uv pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

## Troubleshooting

### Common Issues

1. **LSP server not starting**
   - Ensure `forge-lsp` is in your PATH
   - Check that Python 3.9+ is installed
   - Verify Foundry is installed: `forge --version`

2. **No completions or diagnostics**
   - Ensure you're in a Foundry project (has `foundry.toml`)
   - Check that the file is recognized as Solidity (`.sol` extension)
   - Verify the LSP server is running: check your editor's LSP logs

3. **Compilation errors not showing**
   - Ensure `forge` is available in PATH
   - Check that your project compiles: `forge build`
   - Verify the LSP server has read access to your project directory

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
# Set environment variable
export FORGE_LSP_LOG_LEVEL=DEBUG

# Or run with debug flag
forge-lsp --debug
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Foundry](https://github.com/foundry-rs/foundry) - The blazing fast Ethereum development toolkit
- [pygls](https://github.com/openlawlibrary/pygls) - Python LSP server framework
- [Solidity](https://soliditylang.org/) - The Solidity programming language
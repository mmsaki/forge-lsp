# Forge LSP Usage Guide

## Default Behavior

By default, the Forge LSP server compiles only the specific file you're currently editing. This provides:

- **Fast compilation** (~100-200ms for single files)
- **Reduced resource usage** for large projects
- **Immediate feedback** on the file you're working on

## Diagnostics Source

**All diagnostics come exclusively from forge tooling**. The LSP server does not generate any custom warnings or errors. This ensures:

- **Consistency** with forge command-line behavior
- **Accuracy** of Solidity compiler diagnostics
- **No false positives** from custom parsing
- **Official error codes** and messages from the Solidity compiler

### Dual Diagnostics System

The LSP server combines diagnostics from two sources:

1. **`forge compile --json`** (Original format)
   - Compilation errors and warnings
   - Source: `"forge-compile"`
   - Message format: `**[forge compile]** Error message (Error 7576)`
   - Includes error type and code information

2. **`forge lint --json`** (Nightly feature - rustc-compatible format)
   - Additional linting rules and style checks
   - Source: `"forge-lint"`
   - Message format: `**[forge lint]** Lint message`
   - Includes helpful suggestions when available

### Message Formatting

All diagnostic messages use **clean, readable text formatting** optimized for Lua/Neovim:

- **Clear prefixes** identify the source: `[forge compile]` or `[forge lint]`
- **Error codes** in parentheses: `(Error 7576)` or `(Code: mixed-case-function)`
- **Additional context** with dashes: `- Type: DeclarationError`
- **Suggestions** for lint issues: `- Suggestion: add 'public' to the declaration`

#### Message Examples:

**Compile Error:**
```
[forge compile] Undeclared identifier. (Error 7576) - Type: DeclarationError
```

**Lint Warning:**
```
[forge lint] function names should use mixedCase (Code: mixed-case-function) - Suggestion: use camelCase naming
```

#### Clean Text Processing

The LSP automatically cleans up messy forge output by removing:
- ANSI escape sequences and color codes
- OSC hyperlink sequences (`]8;;...`)
- Table references (`[table: 0x...]`)
- Dictionary representations in messages
- Control characters and formatting artifacts

This ensures **clean, readable text** that works perfectly with Lua and doesn't require complex object destructuring.

### Backward Compatibility

- **Older forge versions**: Only compile diagnostics are used
- **Forge nightly**: Both compile and lint diagnostics are combined
- **Graceful degradation**: If lint fails, compile diagnostics still work

## Cache Behavior

The LSP uses intelligent caching to balance performance and accuracy:

- **Document Changes**: Uses cached compilation for fast feedback during typing
- **Document Save**: Uses `--no-cache` to ensure all warnings are shown, especially for empty/simple files

This is critical because forge's cache can hide warnings on subsequent runs of the same file.

## Single File Compilation

When you open, edit, or save a Solidity file, the LSP will run:
```bash
forge compile src/YourFile.sol --json
```

This gives you diagnostics (errors/warnings) for just that file.

## Full Project Compilation

For full project analysis, you can configure your editor to use the `get_project_diagnostics()` method. This is useful for:

- **Project-wide error checking**
- **Finding all files with errors**
- **Comprehensive analysis before deployment**

### Neovim Configuration Example

Add this to your Neovim configuration to enable full project compilation:

```lua
-- Add a command to run full project diagnostics
vim.api.nvim_create_user_command('ForgeCompileProject', function()
  -- This would call the LSP method to get project-wide diagnostics
  -- Implementation depends on your LSP client setup
  vim.lsp.buf.execute_command({
    command = 'forge.compileProject',
    arguments = {}
  })
end, {})

-- Optional: Bind to a key
vim.keymap.set('n', '<leader>fc', ':ForgeCompileProject<CR>', { desc = 'Forge: Compile entire project' })
```

## Performance Comparison

| Operation | Single File | Full Project |
|-----------|-------------|--------------|
| Compilation Time | ~100-200ms | ~500ms-2s |
| Resource Usage | Low | Medium-High |
| Scope | Current file only | All project files |
| Use Case | Real-time editing | Project analysis |

## Cache vs No-Cache Behavior

| Event | Cache Setting | Reason |
|-------|---------------|--------|
| Document Change | Cached | Fast feedback during typing |
| Document Save | No-cache (`--no-cache`) | Ensures all warnings are shown |
| Document Open | Cached | Fast initial load |

**Why this matters**: Forge's cache can hide warnings on empty or simple files. Using `--no-cache` on save ensures you see all diagnostics, including SPDX license and pragma warnings.

## Recommendations

- **Use single-file compilation** (default) for day-to-day development
- **Use full project compilation** before commits, deployments, or when debugging cross-file issues
- **Configure your editor** to run full compilation on demand (e.g., with a keybinding)

## Files Outside Workspace

Files outside the Foundry project workspace will not be compiled and will return empty diagnostics. This prevents errors when editing files that aren't part of the current project.
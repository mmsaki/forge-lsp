# Solidity LSP

A Language Server Protocol (LSP) implementation for Solidity development using Foundry's compilation and linting infrastructure.

This work is a continuation from [foundry-rs/foundry PR #11187](https://github.com/foundry-rs/foundry/pull/11187).

## Install

Install binary from crates.io

```sh
cargo install forge-lsp
```

## Usage

Start the LSP server using:

```bash
forge-lsp --stdio
```

### LSP Features

**General**

- [x] `initialize` - Server initialization
- [x] `initialized` - Server initialized notification
- [x] `shutdown` - Server shutdown

**Text Synchronization**

- [x] `textDocument/didOpen` - Handle file opening
- [x] `textDocument/didChange` - Handle file content changes
- [x] `textDocument/didSave` - Handle file saving with diagnostics refresh
- [x] `textDocument/didClose` - Handle file closing
- [ ] `textDocument/willSave` - File will save notification
- [ ] `textDocument/willSaveWaitUntil` - File will save wait until

**Diagnostics**

- [x] `textDocument/publishDiagnostics` - Publish compilation errors and warnings via `forge build`
- [x] `textDocument/publishDiagnostics` - Publish linting errors and warnings via `forge lint`

**Language Features**

- [x] `textDocument/definition` - Go to definition
- [x] `textDocument/declaration` - Go to declaration
- [x] `textDocument/references` - Find all references
- [x] `textDocument/documentSymbol` - Document symbol outline (contracts, functions, variables, events, structs, enums, etc.)
- [x] `textDocument/rename` - Rename symbols across files
- [ ] `textDocument/completion` - Code completion
- [ ] `textDocument/hover` - Hover information
- [ ] `textDocument/signatureHelp` - Function signature help
- [ ] `textDocument/typeDefinition` - Go to type definition
- [ ] `textDocument/implementation` - Go to implementation
- [ ] `textDocument/documentHighlight` - Document highlighting
- [ ] `textDocument/codeAction` - Code actions (quick fixes, refactoring)
- [ ] `textDocument/codeLens` - Code lens
- [ ] `textDocument/documentLink` - Document links
- [ ] `textDocument/documentColor` - Color information
- [ ] `textDocument/colorPresentation` - Color presentation
- [ ] `textDocument/formatting` - Document formatting
- [ ] `textDocument/rangeFormatting` - Range formatting
- [ ] `textDocument/onTypeFormatting` - On-type formatting
- [ ] `textDocument/prepareRename` - Prepare rename validation
- [ ] `textDocument/foldingRange` - Folding ranges
- [ ] `textDocument/selectionRange` - Selection ranges
- [ ] `textDocument/semanticTokens` - Semantic tokens
- [ ] `textDocument/semanticTokens/full` - Full semantic tokens
- [ ] `textDocument/semanticTokens/range` - Range semantic tokens
- [ ] `textDocument/semanticTokens/delta` - Delta semantic tokens

**Workspace Features**

- [x] `workspace/symbol` - Workspace-wide symbol search
- [x] `workspace/didChangeConfiguration` - Acknowledges configuration changes (logs only)
- [x] `workspace/didChangeWatchedFiles` - Acknowledges watched file changes (logs only)
- [x] `workspace/didChangeWorkspaceFolders` - Acknowledges workspace folder changes (logs only)
- [ ] `workspace/executeCommand` - Execute workspace commands (stub implementation)
- [ ] `workspace/applyEdit` - Apply workspace edits
- [ ] `workspace/willCreateFiles` - File creation preview
- [ ] `workspace/willRenameFiles` - File rename preview
- [ ] `workspace/willDeleteFiles` - File deletion preview

**Window Features**

- [ ] `window/showMessage` - Show message to user
- [ ] `window/showMessageRequest` - Show message request to user
- [ ] `window/workDoneProgress` - Work done progress

## Development

### Building

```bash
cargo build --release
```

### Testing

```bash
cargo test
```

### VSCode or Cursor

You can add the following to VSCode (or cursor) using a lsp-proxy extension see comment [here](https://github.com/foundry-rs/foundry/pull/11187#issuecomment-3148743488):

```json
[
  {
    "languageId": "solidity",
    "command": "forge-lsp",
    "fileExtensions": [
      ".sol"
    ],
  }
]
```

### Neovim

If you have neovim 0.11+ installed add these to your config

```lua
-- lsp/forge_lsp.lua
return {
  cmd = { "forge-lsp" },
  filetypes = { "solidity" },
  root_markers = { "foundry.toml", ".git" },
  root_dir = vim.fs.root(0, { "foundry.toml", ".git" }),
}
-- init.lua
vim.lsp.enable("forge_lsp")
```

### Debugging in neovim

Lsp logs are stored in `~/.local/state/nvim/lsp.log`

To clear lsp logs run:

```bash
> -f ~/.local/state/nvim/lsp.log
```

To monitor logs in real time run:

```bash
tail -f ~/.local/state/nvim/lsp.log
```

Enable traces in neovim to view full traces in logs:

```sh
:lua vim.lsp.set_log_level("trace")
```

## Contributing

Check out the [foundry contribution guide](https://github.com/foundry-rs/foundry/blob/master/CONTRIBUTING.md).

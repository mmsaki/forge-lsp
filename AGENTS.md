# Agent Instructions for forge-lsp

## Build/Test Commands
- Build: `cargo build --release`
- Test all: `cargo test`
- Test single: `cargo test <test_name>`
- Lint: `cargo clippy`
- Format: `cargo fmt`

## Code Style Guidelines
- **Rust Edition**: 2024
- **Error Handling**: Use `eyre::Result<()>` for main functions, `thiserror` for custom error types
- **Async**: Use `tokio` runtime with `#[tokio::main]`
- **Logging**: Use `tracing` crate for logging
- **CLI**: Use `clap` with derive macros for argument parsing
- **LSP**: Use `tower-lsp` for Language Server Protocol implementation

## Naming Conventions
- Functions: snake_case
- Types/Structs: PascalCase
- Modules: snake_case
- Constants: SCREAMING_SNAKE_CASE

## Import Organization
- Standard library imports first
- External crates (alphabetical)
- Local crate imports
- Use absolute paths for clarity

## Testing
- Unit tests in `#[cfg(test)]` modules within source files
- Integration tests in `tests/` directory (if any)
- Use descriptive test names with `test_` prefix
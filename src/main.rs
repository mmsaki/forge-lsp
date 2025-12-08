use clap::Parser;
use forge_lsp::cli::LspArgs;

#[tokio::main]
async fn main() -> eyre::Result<()> {
    let args = LspArgs::parse();
    args.run().await
}

use crate::{
    goto, references, rename,
    runner::{ForgeRunner, Runner},
};
use std::{collections::HashMap, sync::Arc};
use tokio::sync::RwLock;
use tower_lsp::{Client, LanguageServer, lsp_types::*};

pub type FileId = usize;

fn byte_offset(content: &str, position: Position) -> Result<usize, String> {
    let lines: Vec<&str> = content.lines().collect();
    if position.line as usize >= lines.len() {
        return Err("Line out of range".to_string());
    }
    let mut offset = 0;
    for i in 0..position.line as usize {
        offset += lines[i].len() + 1; // +1 for \n
    }
    offset += position.character as usize;
    if offset > content.len() {
        return Err("Character out of range".to_string());
    }
    Ok(offset)
}

pub struct ForgeLsp {
    client: Client,
    compiler: Arc<dyn Runner>,
    ast_cache: Arc<RwLock<HashMap<String, serde_json::Value>>>,
}

#[allow(dead_code)]
#[derive(Debug, Clone)]
struct TextDocumentItem<'a> {
    uri: Url,
    text: &'a str,
    version: Option<i32>,
}

impl ForgeLsp {
    pub fn new(client: Client) -> Self {
        let compiler = Arc::new(ForgeRunner) as Arc<dyn Runner>;
        let ast_cache = Arc::new(RwLock::new(HashMap::new()));
        Self { client, compiler, ast_cache }
    }

    async fn on_change<'a>(&self, params: TextDocumentItem<'a>) {
        let uri = params.uri.clone();
        let version = params.version;

        // Get file path for AST caching
        let file_path = match uri.to_file_path() {
            Ok(path) => path,
            Err(_) => {
                self.client
                    .log_message(MessageType::ERROR, "Invalid file URI for AST caching")
                    .await;
                return;
            }
        };

        let path_str = match file_path.to_str() {
            Some(s) => s,
            None => {
                self.client
                    .log_message(MessageType::ERROR, "Invalid file path for AST caching")
                    .await;
                return;
            }
        };

        let (lint_result, build_result, ast_result) = tokio::join!(
            self.compiler.get_lint_diagnostics(&uri),
            self.compiler.get_build_diagnostics(&uri),
            self.compiler.ast(path_str)
        );

        // Cache the AST data
        if let Ok(ast_data) = ast_result {
            let mut cache = self.ast_cache.write().await;
            cache.insert(uri.to_string(), ast_data);
            self.client.log_message(MessageType::INFO, "AST data cached successfully").await;
        } else if let Err(e) = ast_result {
            self.client
                .log_message(MessageType::WARNING, format!("Failed to cache AST data: {e}"))
                .await;
        }

        let mut all_diagnostics = vec![];

        match lint_result {
            Ok(mut lints) => {
                self.client
                    .log_message(
                        MessageType::INFO,
                        format!("Found {} linting diagnostics", lints.len()),
                    )
                    .await;
                all_diagnostics.append(&mut lints);
            }
            Err(e) => {
                self.client
                    .log_message(
                        MessageType::WARNING,
                        format!("Forge linting diagnostics failed: {e}"),
                    )
                    .await;
            }
        }

        match build_result {
            Ok(mut builds) => {
                self.client
                    .log_message(
                        MessageType::INFO,
                        format!("Found {} build diagnostics", builds.len()),
                    )
                    .await;
                all_diagnostics.append(&mut builds);
            }
            Err(e) => {
                self.client
                    .log_message(
                        MessageType::WARNING,
                        format!("Forge build diagnostics failed: {e}"),
                    )
                    .await;
            }
        }

        self.client.publish_diagnostics(uri, all_diagnostics, version).await;
    }

    async fn apply_workspace_edit(&self, workspace_edit: &WorkspaceEdit) -> Result<(), String> {
        if let Some(changes) = &workspace_edit.changes {
            for (uri, edits) in changes {
                let path = uri.to_file_path().map_err(|_| "Invalid URI".to_string())?;
                let mut content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;

                // Sort edits by start position descending to avoid offset issues
                let mut sorted_edits = edits.clone();
                sorted_edits.sort_by(|a, b| b.range.start.cmp(&a.range.start));

                for edit in sorted_edits {
                    let start_byte = byte_offset(&content, edit.range.start)?;
                    let end_byte = byte_offset(&content, edit.range.end)?;
                    content.replace_range(start_byte..end_byte, &edit.new_text);
                }

                std::fs::write(&path, &content).map_err(|e| e.to_string())?;
            }
        }
        Ok(())
    }
}

#[tower_lsp::async_trait]
impl LanguageServer for ForgeLsp {
    async fn initialize(
        &self,
        _: InitializeParams,
    ) -> tower_lsp::jsonrpc::Result<InitializeResult> {
        Ok(InitializeResult {
            server_info: Some(ServerInfo {
                name: "forge lsp".to_string(),
                version: Some("0.0.1".to_string()),
            }),
            capabilities: ServerCapabilities {
                definition_provider: Some(OneOf::Left(true)),
                declaration_provider: Some(DeclarationCapability::Simple(true)),
                references_provider: Some(OneOf::Left(true)),
                rename_provider: Some(OneOf::Left(true)),
                text_document_sync: Some(TextDocumentSyncCapability::Kind(
                    TextDocumentSyncKind::FULL,
                )),
                ..ServerCapabilities::default()
            },
        })
    }

    async fn initialized(&self, _: InitializedParams) {
        self.client.log_message(MessageType::INFO, "lsp server initialized!").await;
    }

    async fn shutdown(&self) -> tower_lsp::jsonrpc::Result<()> {
        self.client.log_message(MessageType::INFO, "lsp server shutting down").await;
        Ok(())
    }

    async fn did_open(&self, params: DidOpenTextDocumentParams) {
        self.client.log_message(MessageType::INFO, "file opened").await;

        self.on_change(TextDocumentItem {
            uri: params.text_document.uri,
            text: &params.text_document.text,
            version: Some(params.text_document.version),
        })
        .await
    }

    async fn did_change(&self, params: DidChangeTextDocumentParams) {
        self.client.log_message(MessageType::INFO, "file changed").await;

        // Invalidate cached AST data for the changed file
        let uri = params.text_document.uri;
        let mut cache = self.ast_cache.write().await;
        if cache.remove(&uri.to_string()).is_some() {
            self.client
                .log_message(MessageType::INFO, "Invalidated cached AST data for changed file")
                .await;
        }
    }

    async fn did_save(&self, params: DidSaveTextDocumentParams) {
        self.client.log_message(MessageType::INFO, "file saved - running diagnostics").await;

        // Run diagnostics on save, regardless of whether text is provided
        // If text is provided, use it; otherwise read from file system
        let text_content = if let Some(text) = params.text {
            text
        } else {
            // Read the file from disk since many LSP clients don't send text on save
            match std::fs::read_to_string(params.text_document.uri.path()) {
                Ok(content) => content,
                Err(e) => {
                    self.client
                        .log_message(
                            MessageType::ERROR,
                            format!("Failed to read file on save: {e}"),
                        )
                        .await;
                    return;
                }
            }
        };

        let item =
            TextDocumentItem { uri: params.text_document.uri, text: &text_content, version: None };

        // Always run diagnostics on save to reflect the current file state
        self.on_change(item).await;
        _ = self.client.semantic_tokens_refresh().await;
    }

    async fn did_close(&self, _: DidCloseTextDocumentParams) {
        self.client.log_message(MessageType::INFO, "file closed").await;
    }

    async fn did_change_configuration(&self, _: DidChangeConfigurationParams) {
        self.client.log_message(MessageType::INFO, "configuration changed!").await;
    }

    async fn did_change_workspace_folders(&self, _: DidChangeWorkspaceFoldersParams) {
        self.client.log_message(MessageType::INFO, "workspace folders changed!").await;
    }

    async fn did_change_watched_files(&self, _: DidChangeWatchedFilesParams) {
        self.client.log_message(MessageType::INFO, "watched files have changed!").await;
    }

    async fn goto_definition(
        &self,
        params: GotoDefinitionParams,
    ) -> tower_lsp::jsonrpc::Result<Option<GotoDefinitionResponse>> {
        self.client.log_message(MessageType::INFO, "Got a textDocument/definition request").await;

        let uri = params.text_document_position_params.text_document.uri;
        let position = params.text_document_position_params.position;

        // Get the file path from URI
        let file_path = match uri.to_file_path() {
            Ok(path) => path,
            Err(_) => {
                self.client.log_message(MessageType::ERROR, "Invalid file URI").await;
                return Ok(None);
            }
        };

        // Read the source file
        let source_bytes = match std::fs::read(&file_path) {
            Ok(bytes) => bytes,
            Err(e) => {
                self.client
                    .log_message(MessageType::ERROR, format!("Failed to read file: {e}"))
                    .await;
                return Ok(None);
            }
        };

        // Try to get AST data from cache first
        let ast_data = {
            let cache = self.ast_cache.read().await;
            if let Some(cached_ast) = cache.get(&uri.to_string()) {
                self.client.log_message(MessageType::INFO, "Using cached AST data").await;
                cached_ast.clone()
            } else {
                // Cache miss - get AST data and cache it
                drop(cache); // Release read lock

                let path_str = match file_path.to_str() {
                    Some(s) => s,
                    None => {
                        self.client.log_message(MessageType::ERROR, "Invalid file path").await;
                        return Ok(None);
                    }
                };

                match self.compiler.ast(path_str).await {
                    Ok(data) => {
                        self.client
                            .log_message(MessageType::INFO, "Fetched and caching new AST data")
                            .await;

                        // Cache the new AST data
                        let mut cache = self.ast_cache.write().await;
                        cache.insert(uri.to_string(), data.clone());
                        data
                    }
                    Err(e) => {
                        self.client
                            .log_message(MessageType::ERROR, format!("Failed to get AST: {e}"))
                            .await;
                        return Ok(None);
                    }
                }
            }
        };

        // Use goto_declaration function (same logic for both definition and declaration)
        if let Some(location) = goto::goto_declaration(&ast_data, &uri, position, &source_bytes) {
            self.client
                .log_message(
                    MessageType::INFO,
                    format!("Found definition at {}:{}", location.uri, location.range.start.line),
                )
                .await;
            Ok(Some(GotoDefinitionResponse::from(location)))
        } else {
            self.client.log_message(MessageType::INFO, "No definition found").await;
            // Fallback to current position
            let location = Location { uri, range: Range { start: position, end: position } };
            Ok(Some(GotoDefinitionResponse::from(location)))
        }
    }

    async fn goto_declaration(
        &self,
        params: request::GotoDeclarationParams,
    ) -> tower_lsp::jsonrpc::Result<Option<request::GotoDeclarationResponse>> {
        self.client.log_message(MessageType::INFO, "Got a textDocument/declaration request").await;

        let uri = params.text_document_position_params.text_document.uri;
        let position = params.text_document_position_params.position;

        // Get the file path from URI
        let file_path = match uri.to_file_path() {
            Ok(path) => path,
            Err(_) => {
                self.client.log_message(MessageType::ERROR, "Invalid file URI").await;
                return Ok(None);
            }
        };

        // Read the source file
        let source_bytes = match std::fs::read(&file_path) {
            Ok(bytes) => bytes,
            Err(e) => {
                self.client
                    .log_message(MessageType::ERROR, format!("Failed to read file: {e}"))
                    .await;
                return Ok(None);
            }
        };

        // Try to get AST data from cache first
        let ast_data = {
            let cache = self.ast_cache.read().await;
            if let Some(cached_ast) = cache.get(&uri.to_string()) {
                self.client.log_message(MessageType::INFO, "Using cached AST data").await;
                cached_ast.clone()
            } else {
                // Cache miss - get AST data and cache it
                drop(cache); // Release read lock

                let path_str = match file_path.to_str() {
                    Some(s) => s,
                    None => {
                        self.client.log_message(MessageType::ERROR, "Invalid file path").await;
                        return Ok(None);
                    }
                };

                match self.compiler.ast(path_str).await {
                    Ok(data) => {
                        self.client
                            .log_message(MessageType::INFO, "Fetched and caching new AST data")
                            .await;

                        // Cache the new AST data
                        let mut cache = self.ast_cache.write().await;
                        cache.insert(uri.to_string(), data.clone());
                        data
                    }
                    Err(e) => {
                        self.client
                            .log_message(MessageType::ERROR, format!("Failed to get AST: {e}"))
                            .await;
                        return Ok(None);
                    }
                }
            }
        };

        // Use goto_declaration function
        if let Some(location) = goto::goto_declaration(&ast_data, &uri, position, &source_bytes) {
            self.client
                .log_message(
                    MessageType::INFO,
                    format!("Found declaration at {}:{}", location.uri, location.range.start.line),
                )
                .await;
            Ok(Some(request::GotoDeclarationResponse::from(location)))
        } else {
            self.client.log_message(MessageType::INFO, "No declaration found").await;
            // Fallback to current position
            let location = Location { uri, range: Range { start: position, end: position } };
            Ok(Some(request::GotoDeclarationResponse::from(location)))
        }
    }

    async fn references(
        &self,
        params: ReferenceParams,
    ) -> tower_lsp::jsonrpc::Result<Option<Vec<Location>>> {
        self.client.log_message(MessageType::INFO, "Got a textDocument/references request").await;

        let uri = params.text_document_position.text_document.uri;
        let position = params.text_document_position.position;

        // Get the file path from URI
        let file_path = match uri.to_file_path() {
            Ok(path) => path,
            Err(_) => {
                self.client.log_message(MessageType::ERROR, "Invalid file URI").await;
                return Ok(None);
            }
        };

        // Read the source file
        let source_bytes = match std::fs::read(&file_path) {
            Ok(bytes) => bytes,
            Err(e) => {
                self.client
                    .log_message(MessageType::ERROR, format!("Failed to read file: {e}"))
                    .await;
                return Ok(None);
            }
        };

        // Try to get AST data from cache first
        let ast_data = {
            let cache = self.ast_cache.read().await;
            if let Some(cached_ast) = cache.get(&uri.to_string()) {
                self.client.log_message(MessageType::INFO, "Using cached AST data").await;
                cached_ast.clone()
            } else {
                // Cache miss - get AST data and cache it
                drop(cache); // Release read lock

                let path_str = match file_path.to_str() {
                    Some(s) => s,
                    None => {
                        self.client.log_message(MessageType::ERROR, "Invalid file path").await;
                        return Ok(None);
                    }
                };

                match self.compiler.ast(path_str).await {
                    Ok(data) => {
                        self.client
                            .log_message(MessageType::INFO, "Fetched and caching new AST data")
                            .await;

                        // Cache the new AST data
                        let mut cache = self.ast_cache.write().await;
                        cache.insert(uri.to_string(), data.clone());
                        data
                    }
                    Err(e) => {
                        self.client
                            .log_message(MessageType::ERROR, format!("Failed to get AST: {e}"))
                            .await;
                        return Ok(None);
                    }
                }
            }
        };

        // Use goto_references function to find all references
        let locations = references::goto_references(&ast_data, &uri, position, &source_bytes);

        if locations.is_empty() {
            self.client.log_message(MessageType::INFO, "No references found").await;
            Ok(None)
        } else {
            self.client
                .log_message(MessageType::INFO, format!("Found {} references", locations.len()))
                .await;
            Ok(Some(locations))
        }
    }

    async fn rename(
        &self,
        params: RenameParams,
    ) -> tower_lsp::jsonrpc::Result<Option<WorkspaceEdit>> {
        self.client.log_message(MessageType::INFO, "Got a textDocument/rename request").await;

        let uri = params.text_document_position.text_document.uri;
        let position = params.text_document_position.position;
        let new_name = params.new_name;

        // Get the file path from URI
        let file_path = match uri.to_file_path() {
            Ok(path) => path,
            Err(_) => {
                self.client.log_message(MessageType::ERROR, "Invalid file URI").await;
                return Ok(None);
            }
        };

        // Read the source file
        let source_bytes = match std::fs::read(&file_path) {
            Ok(bytes) => bytes,
            Err(e) => {
                self.client
                    .log_message(MessageType::ERROR, format!("Failed to read file: {e}"))
                    .await;
                return Ok(None);
            }
        };

        // Try to get AST data from cache first
        let ast_data = {
            let cache = self.ast_cache.read().await;
            if let Some(cached_ast) = cache.get(&uri.to_string()) {
                self.client.log_message(MessageType::INFO, "Using cached AST data").await;
                cached_ast.clone()
            } else {
                // Cache miss - get AST data and cache it
                drop(cache); // Release read lock

                let path_str = match file_path.to_str() {
                    Some(s) => s,
                    None => {
                        self.client.log_message(MessageType::ERROR, "Invalid file path").await;
                        return Ok(None);
                    }
                };

                match self.compiler.ast(path_str).await {
                    Ok(data) => {
                        self.client
                            .log_message(MessageType::INFO, "Fetched and caching new AST data")
                            .await;

                        // Cache the new AST data
                        let mut cache = self.ast_cache.write().await;
                        cache.insert(uri.to_string(), data.clone());
                        data
                    }
                    Err(e) => {
                        self.client
                            .log_message(MessageType::ERROR, format!("Failed to get AST: {e}"))
                            .await;
                        return Ok(None);
                    }
                }
            }
        };

        // Use the rename_symbol function to handle the rename logic
        match rename::rename_symbol(&ast_data, &uri, position, &source_bytes, new_name) {
            Some(workspace_edit) => {
                self.client
                    .log_message(
                        MessageType::INFO,
                        format!(
                            "Created rename edit with {} changes",
                            workspace_edit.changes.as_ref()
                                .map(|c| c.values().map(|v| v.len()).sum::<usize>())
                                .unwrap_or(0)
                        ),
                    )
                    .await;

                // Separate changes: apply server-side for other files, return client-side for current file
                let mut server_changes = HashMap::new();
                let mut client_changes = HashMap::new();

                if let Some(changes) = &workspace_edit.changes {
                    for (file_uri, edits) in changes {
                        if file_uri == &uri {
                            client_changes.insert(file_uri.clone(), edits.clone());
                        } else {
                            server_changes.insert(file_uri.clone(), edits.clone());
                        }
                    }
                }

                // Apply edits for other files server-side
                if !server_changes.is_empty() {
                    let server_edit = WorkspaceEdit {
                        changes: Some(server_changes),
                        ..Default::default()
                    };
                    if let Err(e) = self.apply_workspace_edit(&server_edit).await {
                        self.client
                            .log_message(MessageType::ERROR, format!("Failed to apply server-side rename edits: {}", e))
                            .await;
                        return Ok(None);
                    }
                    self.client
                        .log_message(MessageType::INFO, "Applied server-side rename edits and saved other files")
                        .await;
                }

                // Return edits for the current file to be applied client-side
                if client_changes.is_empty() {
                    Ok(None)
                } else {
                    let client_edit = WorkspaceEdit {
                        changes: Some(client_changes),
                        ..Default::default()
                    };
                    Ok(Some(client_edit))
                }
            }
            None => {
                self.client.log_message(MessageType::INFO, "No locations found for renaming").await;
                Ok(None)
            }
        }
    }

    async fn execute_command(
        &self,
        _: ExecuteCommandParams,
    ) -> tower_lsp::jsonrpc::Result<Option<serde_json::Value>> {
        self.client.log_message(MessageType::INFO, "command executed!").await;

        match self.client.apply_edit(WorkspaceEdit::default()).await {
            Ok(res) if res.applied => self.client.log_message(MessageType::INFO, "applied").await,
            Ok(_) => self.client.log_message(MessageType::INFO, "rejected").await,
            Err(err) => self.client.log_message(MessageType::ERROR, err).await,
        }
        Ok(None)
    }
}

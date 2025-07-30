import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from lsprotocol.types import (
    INITIALIZE,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    InitializeParams,
    TextDocumentSyncKind,
)
from pygls.server import LanguageServer

from .forge_diagnostics import ForgeDiagnosticsProvider


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ForgeLSPServer(LanguageServer):
    """Custom Language Server with Foundry integration."""

    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.diagnostics_provider = ForgeDiagnosticsProvider()
        self.workspace_root: Optional[str] = None


server = ForgeLSPServer("forge-lsp", "v0.1.0")

# Debouncing for document changes
_pending_diagnostics: Dict[str, asyncio.Task] = {}
DIAGNOSTICS_DEBOUNCE_DELAY = 0.5  # 500ms delay


def uri_to_path(uri: str) -> str:
    """Convert file URI to local file path."""
    parsed = urlparse(uri)
    return parsed.path


@server.feature(INITIALIZE)
def initialize(params: InitializeParams):
    """Initialize the LSP server."""
    logger.info("Initializing Forge LSP server")

    # Set workspace root
    if params.workspace_folders:
        server.workspace_root = uri_to_path(params.workspace_folders[0].uri)
    elif params.root_uri:
        server.workspace_root = uri_to_path(params.root_uri)

    logger.info(f"Workspace root: {server.workspace_root}")

    return {
        "capabilities": {
            "textDocumentSync": {
                "openClose": True,
                "change": TextDocumentSyncKind.Full,
                "save": {"includeText": True},
            },
            # Only diagnostics are supported - no completion, hover, definition, or references
        }
    }


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(params: DidOpenTextDocumentParams):
    """Handle document open event."""
    logger.info(f"Document opened: {params.text_document.uri}")
    # Use cache on open for faster initial feedback
    await _publish_diagnostics(params.text_document.uri, use_cache=True)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(params: DidChangeTextDocumentParams):
    """Handle document change event with debouncing."""
    # Use cache on changes for faster feedback during typing
    await _publish_diagnostics_debounced(params.text_document.uri, use_cache=True)


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(params: DidSaveTextDocumentParams):
    """Handle document save event."""
    logger.info(f"Document saved: {params.text_document.uri}")

    # Cancel any pending debounced diagnostics since we're doing immediate diagnostics on save
    global _pending_diagnostics
    if params.text_document.uri in _pending_diagnostics:
        _pending_diagnostics[params.text_document.uri].cancel()
        _pending_diagnostics.pop(params.text_document.uri, None)

    # Use --no-cache on save to ensure all warnings are shown, including for empty files
    await _publish_diagnostics(params.text_document.uri, use_cache=False)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: DidCloseTextDocumentParams):
    """Handle document close event."""
    logger.info(f"Document closed: {params.text_document.uri}")

    # Cancel any pending diagnostics for the closed document
    global _pending_diagnostics
    if params.text_document.uri in _pending_diagnostics:
        _pending_diagnostics[params.text_document.uri].cancel()
        _pending_diagnostics.pop(params.text_document.uri, None)


# LSP features like completion, hover, definition, and references have been removed
# This LSP server focuses only on diagnostics (compilation and linting errors)


async def _publish_diagnostics_debounced(document_uri: str, use_cache: bool = True):
    """Publish diagnostics with debouncing to avoid excessive compilation."""
    global _pending_diagnostics

    # Cancel any pending diagnostics for this document
    if document_uri in _pending_diagnostics:
        _pending_diagnostics[document_uri].cancel()

    # Create a new task with debouncing
    async def delayed_diagnostics():
        try:
            await asyncio.sleep(DIAGNOSTICS_DEBOUNCE_DELAY)
            await _publish_diagnostics(document_uri, use_cache)
        except asyncio.CancelledError:
            # Task was cancelled, ignore
            pass
        finally:
            # Clean up the task reference
            _pending_diagnostics.pop(document_uri, None)

    _pending_diagnostics[document_uri] = asyncio.create_task(delayed_diagnostics())


async def _publish_diagnostics(document_uri: str, use_cache: bool = True):
    """Publish diagnostics for a document using forge compile --json output."""
    try:
        cache_info = "cached" if use_cache else "no-cache"
        logger.info(f"Publishing diagnostics for {document_uri} ({cache_info})")
        
        # Convert URI to file path
        file_path = uri_to_path(document_uri)
        
        # Get diagnostics from forge compile for the specific file
        diagnostics = await server.diagnostics_provider.get_diagnostics_for_file_async(file_path, use_cache)
        
        # Publish diagnostics to the client
        server.publish_diagnostics(document_uri, diagnostics)
        logger.info(f"Published {len(diagnostics)} diagnostics for {document_uri}")
        
    except Exception as e:
        logger.error(f"Error publishing diagnostics for {document_uri}: {e}")
        # Publish empty diagnostics on error to clear any existing ones
        server.publish_diagnostics(document_uri, [])


def main() -> None:
    """Main entry point for the LSP server."""
    logger.info("Starting Forge LSP server")
    server.start_io()

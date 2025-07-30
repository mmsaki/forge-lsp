import logging
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream, ParseTreeWalker
from antlr4.error.ErrorListener import ErrorListener

from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    Diagnostic,
    DiagnosticSeverity,
    Location,
    Position,
    Range,
)

try:
    from .antlr_generated.grammar.SolidityLexer import SolidityLexer
    from .antlr_generated.grammar.SolidityParser import SolidityParser
    from .antlr_generated.grammar.SolidityParserListener import SolidityParserListener
except ImportError:
    # Fallback for development/testing
    import sys
    import os

    sys.path.append(
        os.path.join(os.path.dirname(__file__), "antlr_generated", "grammar")
    )
    from SolidityLexer import SolidityLexer
    from SolidityParser import SolidityParser
    from SolidityParserListener import SolidityParserListener

logger = logging.getLogger(__name__)


class SymbolDefinition:
    """Represents a symbol definition in Solidity code."""

    def __init__(
        self,
        name: str,
        symbol_type: str,
        location: Location,
        scope: str = "",
        additional_info: Optional[Dict] = None,
    ):
        self.name = name
        self.symbol_type = (
            symbol_type  # 'contract', 'function', 'variable', 'struct', 'import', etc.
        )
        self.location = location
        self.scope = scope  # contract name, function name, etc.
        self.additional_info = additional_info or {}


class SymbolReference:
    """Represents a reference to a symbol."""

    def __init__(self, name: str, location: Location, context: str = ""):
        self.name = name
        self.location = location
        self.context = context


class UsingDirective:
    """Represents a 'using Library for Type' directive."""

    def __init__(
        self,
        library_name: str,
        target_type: str,
        is_global: bool = False,
        functions: Optional[List[str]] = None,
    ):
        self.library_name = library_name
        self.target_type = target_type  # "*" for wildcard
        self.is_global = is_global
        self.functions = functions or []  # Specific functions if using aliases


class SoliditySymbolListener(SolidityParserListener):
    """ANTLR4 listener to extract symbols from Solidity code."""

    def __init__(self, document_uri: str, token_stream: CommonTokenStream):
        self.document_uri = document_uri
        self.token_stream = token_stream
        self.symbols: Dict[str, List[SymbolDefinition]] = {}
        self.using_directives: List[UsingDirective] = []
        self.current_contract = ""
        self.current_function = ""
        self.library_functions: Dict[
            str, List[str]
        ] = {}  # library_name -> [function_names]

    def _create_location(self, ctx) -> Location:
        """Create a Location from ANTLR4 context."""
        start_token = ctx.start
        stop_token = ctx.stop if ctx.stop else ctx.start

        return Location(
            uri=self.document_uri,
            range=Range(
                start=Position(line=start_token.line - 1, character=start_token.column),
                end=Position(
                    line=stop_token.line - 1,
                    character=stop_token.column + len(stop_token.text),
                ),
            ),
        )

    def _add_symbol(
        self,
        name: str,
        symbol_type: str,
        ctx,
        scope: str = "",
        additional_info: Optional[Dict] = None,
    ):
        """Add a symbol definition."""
        location = self._create_location(ctx)
        definition = SymbolDefinition(
            name, symbol_type, location, scope, additional_info
        )

        if name not in self.symbols:
            self.symbols[name] = []
        self.symbols[name].append(definition)

    def enterContractDefinition(self, ctx: SolidityParser.ContractDefinitionContext):
        """Handle contract definitions."""
        identifier_ctx = ctx.identifier()
        if identifier_ctx:
            contract_name = identifier_ctx.getText()
            self.current_contract = contract_name
            self._add_symbol(contract_name, "contract", identifier_ctx)

    def exitContractDefinition(self, ctx: SolidityParser.ContractDefinitionContext):
        """Exit contract scope."""
        self.current_contract = ""

    def enterInterfaceDefinition(self, ctx: SolidityParser.InterfaceDefinitionContext):
        """Handle interface definitions."""
        identifier_ctx = ctx.identifier()
        if identifier_ctx:
            interface_name = identifier_ctx.getText()
            self.current_contract = interface_name
            self._add_symbol(interface_name, "interface", identifier_ctx)

    def exitInterfaceDefinition(self, ctx: SolidityParser.InterfaceDefinitionContext):
        """Exit interface scope."""
        self.current_contract = ""

    def enterLibraryDefinition(self, ctx: SolidityParser.LibraryDefinitionContext):
        """Handle library definitions."""
        if ctx.name:
            library_name = ctx.name.text
            self.current_contract = library_name
            self._add_symbol(library_name, "library", ctx.name)
            # Initialize library functions list
            if library_name not in self.library_functions:
                self.library_functions[library_name] = []

    def exitLibraryDefinition(self, ctx: SolidityParser.LibraryDefinitionContext):
        """Exit library scope."""
        self.current_contract = ""

    def enterFunctionDefinition(self, ctx: SolidityParser.FunctionDefinitionContext):
        """Handle function definitions."""
        if ctx.name:
            function_name = ctx.name.text
            self.current_function = function_name
            self._add_symbol(
                function_name, "function", ctx.name, scope=self.current_contract
            )

            # If we're in a library, add this function to the library's function list
            if (
                self.current_contract
                and self.current_contract in self.library_functions
            ):
                self.library_functions[self.current_contract].append(function_name)

    def exitFunctionDefinition(self, ctx: SolidityParser.FunctionDefinitionContext):
        """Exit function scope."""
        self.current_function = ""

    def enterStructDefinition(self, ctx: SolidityParser.StructDefinitionContext):
        """Handle struct definitions."""
        if ctx.name:
            struct_name = ctx.name.text
            self._add_symbol(
                struct_name, "struct", ctx.name, scope=self.current_contract
            )

    def enterEnumDefinition(self, ctx: SolidityParser.EnumDefinitionContext):
        """Handle enum definitions."""
        if ctx.name:
            enum_name = ctx.name.text
            self._add_symbol(enum_name, "enum", ctx.name, scope=self.current_contract)

    def enterStateVariableDeclaration(
        self, ctx: SolidityParser.StateVariableDeclarationContext
    ):
        """Handle state variable declarations."""
        if ctx.name:
            var_name = ctx.name.text
            scope = (
                self.current_function
                if self.current_function
                else self.current_contract
            )
            self._add_symbol(var_name, "variable", ctx.name, scope=scope)

    def enterVariableDeclaration(self, ctx: SolidityParser.VariableDeclarationContext):
        """Handle variable declarations."""
        if ctx.name:
            var_name = ctx.name.text
            scope = (
                self.current_function
                if self.current_function
                else self.current_contract
            )
            self._add_symbol(var_name, "variable", ctx.name, scope=scope)

    def enterImportDirective(self, ctx: SolidityParser.ImportDirectiveContext):
        """Handle import directives."""
        # Handle different import patterns
        if ctx.path:
            import_path = ctx.path.text.strip("\"'")
            self._add_symbol(
                import_path,
                "import",
                ctx.path,
                additional_info={"import_path": import_path},
            )

        # Handle named imports: import {Symbol1, Symbol2} from "path"
        if ctx.symbols:
            for symbol_ctx in ctx.symbols:
                if hasattr(symbol_ctx, "name") and symbol_ctx.name:
                    symbol_name = symbol_ctx.name.text
                    import_path = ctx.path.text.strip("\"'") if ctx.path else ""
                    self._add_symbol(
                        symbol_name,
                        "imported_symbol",
                        symbol_ctx.name,
                        additional_info={"import_path": import_path},
                    )

    def enterUsingDirective(self, ctx: SolidityParser.UsingDirectiveContext):
        """Handle using directives - this is the key for library method resolution!"""
        library_name = ""
        target_type = "*"
        is_global = ctx.Global() is not None
        functions = []

        # Extract library name or function list
        if ctx.identifierPath():
            # Simple case: using LibraryName for Type
            library_name = ctx.identifierPath().getText()
        elif ctx.usingAliases():
            # Complex case: using {func1, func2} for Type
            for alias_ctx in ctx.usingAliases():
                if alias_ctx.identifierPath():
                    func_name = alias_ctx.identifierPath().getText()
                    functions.append(func_name)
                    # Extract library name from the function path if possible
                    if "." in func_name:
                        library_name = func_name.split(".")[0]

        # Extract target type
        if ctx.Mul():
            target_type = "*"
        elif ctx.typeName():
            target_type = ctx.typeName().getText()

        # Create using directive
        using_directive = UsingDirective(
            library_name, target_type, is_global, functions
        )
        self.using_directives.append(using_directive)

        # Add symbol for the using directive itself
        self._add_symbol(
            f"using_{library_name}_{target_type}",
            "using_directive",
            ctx,
            scope=self.current_contract,
            additional_info={
                "library_name": library_name,
                "target_type": target_type,
                "is_global": is_global,
                "functions": functions,
            },
        )


class SolidityErrorListener(ErrorListener):
    """Custom error listener for ANTLR4 parsing errors with enhanced recovery."""

    def __init__(self):
        super().__init__()
        self.errors = []
        self.warnings = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        """Handle syntax errors with enhanced reporting."""
        error_info = {
            "line": line - 1,  # Convert to 0-based
            "column": column,
            "message": self._enhance_error_message(msg, offendingSymbol),
            "symbol": offendingSymbol.text if offendingSymbol else None,
            "severity": "error",
            "suggestions": self._get_error_suggestions(msg, offendingSymbol)
        }
        self.errors.append(error_info)

    def _enhance_error_message(self, msg: str, offending_symbol) -> str:
        """Enhance error messages with more context."""
        if "missing" in msg.lower():
            if "';'" in msg:
                return "Missing semicolon ';' - statements must end with a semicolon"
            elif "'{'" in msg:
                return "Missing opening brace '{' - code blocks must be enclosed in braces"
            elif "'}'" in msg:
                return "Missing closing brace '}' - check for unmatched opening braces"
            elif "'('" in msg:
                return "Missing opening parenthesis '(' - function calls and conditions need parentheses"
            elif "')'" in msg:
                return "Missing closing parenthesis ')' - check for unmatched opening parentheses"
        
        if "extraneous input" in msg.lower():
            return f"Unexpected token '{offending_symbol.text if offending_symbol else 'unknown'}' - check syntax"
        
        if "no viable alternative" in msg.lower():
            return "Invalid syntax - check for typos or missing keywords"
        
        return msg

    def _get_error_suggestions(self, msg: str, offending_symbol) -> List[str]:
        """Get suggestions for fixing common errors."""
        suggestions = []
        
        if "missing" in msg.lower():
            if "';'" in msg:
                suggestions.append("Add a semicolon ';' at the end of the statement")
            elif "'{'" in msg:
                suggestions.append("Add an opening brace '{' to start the code block")
            elif "'}'" in msg:
                suggestions.append("Add a closing brace '}' to end the code block")
            elif "'('" in msg:
                suggestions.append("Add an opening parenthesis '(' before the parameters")
            elif "')'" in msg:
                suggestions.append("Add a closing parenthesis ')' after the parameters")
        
        if "extraneous input" in msg.lower() and offending_symbol:
            token = offending_symbol.text
            if token in ["{", "}", "(", ")", "[", "]"]:
                suggestions.append(f"Remove the extra '{token}' or check for missing matching bracket")
            else:
                suggestions.append(f"Remove '{token}' or check if it's in the correct position")
        
        if "no viable alternative" in msg.lower():
            suggestions.extend([
                "Check for typos in keywords or identifiers",
                "Ensure proper syntax for the current context",
                "Verify that all required elements are present"
            ])
        
        return suggestions

    def reportAmbiguity(self, recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs):
        """Handle ambiguity warnings."""
        warning = {
            "line": startIndex,
            "column": 0,
            "message": "Ambiguous grammar detected - this may cause parsing issues",
            "severity": "warning"
        }
        self.warnings.append(warning)

    def reportAttemptingFullContext(self, recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs):
        """Handle full context attempts."""
        pass  # Usually not critical for LSP

    def reportContextSensitivity(self, recognizer, dfa, startIndex, stopIndex, prediction, configs):
        """Handle context sensitivity."""
        pass  # Usually not critical for LSP


class ANTLRSolidityParser:
    """ANTLR4-based Solidity parser with same API as the regex-based parser."""

    def __init__(self, remapping_resolver=None):
        self.remapping_resolver = remapping_resolver
        self.symbol_definitions: Dict[str, List[SymbolDefinition]] = {}
        self.symbol_references: Dict[str, List[SymbolReference]] = {}
        self.file_symbols: Dict[str, Dict[str, List[SymbolDefinition]]] = {}
        self.using_directives: Dict[
            str, List[UsingDirective]
        ] = {}  # file_uri -> directives
        self.library_functions: Dict[
            str, Dict[str, List[str]]
        ] = {}  # file_uri -> {library -> functions}
        
        # Initialize the advanced navigation provider
        try:
            from .navigation_provider import NavigationProvider
            self.navigation_provider = NavigationProvider(remapping_resolver)
        except ImportError:
            logger.warning("Navigation provider not available")
            self.navigation_provider = None
        
        # Initialize forge diagnostics provider
        try:
            from .forge_diagnostics import ForgeDiagnosticsProvider
            self.forge_diagnostics = ForgeDiagnosticsProvider()
        except ImportError:
            logger.warning("Forge diagnostics not available")
            self.forge_diagnostics = None

        # Solidity keywords and types (same as original parser)
        self.keywords = {
            "contract",
            "interface",
            "library",
            "abstract",
            "function",
            "modifier",
            "event",
            "struct",
            "enum",
            "mapping",
            "array",
            "string",
            "bytes",
            "bool",
            "address",
            "uint",
            "int",
            "fixed",
            "ufixed",
            "public",
            "private",
            "internal",
            "external",
            "pure",
            "view",
            "payable",
            "constant",
            "immutable",
            "override",
            "virtual",
            "returns",
            "return",
            "if",
            "else",
            "for",
            "while",
            "do",
            "break",
            "continue",
            "try",
            "catch",
            "throw",
            "revert",
            "require",
            "assert",
            "import",
            "pragma",
            "using",
            "is",
            "as",
            "memory",
            "storage",
            "calldata",
            "stack",
            "wei",
            "gwei",
            "ether",
            "seconds",
            "minutes",
            "hours",
            "days",
            "weeks",
        }

        self.types = {
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "uint128",
            "uint256",
            "int8",
            "int16",
            "int32",
            "int64",
            "int128",
            "int256",
            "bytes1",
            "bytes2",
            "bytes4",
            "bytes8",
            "bytes16",
            "bytes32",
            "address",
            "bool",
            "string",
            "bytes",
        }

        # Add uint and int variants
        for i in range(8, 257, 8):
            self.types.add(f"uint{i}")
            self.types.add(f"int{i}")

        # Add bytes variants
        for i in range(1, 33):
            self.types.add(f"bytes{i}")

    def _parse_solidity_code(
        self, text: str, document_uri: str
    ) -> Tuple[SoliditySymbolListener, List[Dict]]:
        """Parse Solidity code using ANTLR4 and return symbol listener and errors."""
        input_stream = InputStream(text)
        lexer = SolidityLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        parser = SolidityParser(token_stream)

        # Add error listener
        error_listener = SolidityErrorListener()
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)

        # Parse the source unit
        tree = parser.sourceUnit()

        # Walk the parse tree with our listener
        listener = SoliditySymbolListener(document_uri, token_stream)
        walker = ParseTreeWalker()
        walker.walk(listener, tree)

        return listener, error_listener.errors

    def get_completions(self, text: str, position: Position) -> List[CompletionItem]:
        """Get completion suggestions for Solidity code."""
        completions = []
        
        # Parse the file to get context
        self._index_file_symbols(text, "temp://completions")
        
        lines = text.split("\n")
        if position.line >= len(lines):
            return completions
        
        current_line = lines[position.line]
        line_prefix = current_line[:position.character]
        
        # Get the current word being typed
        word_start = position.character
        while word_start > 0 and (current_line[word_start - 1].isalnum() or current_line[word_start - 1] == "_"):
            word_start -= 1
        
        current_word = current_line[word_start:position.character]
        
        # Determine completion context
        context = self._get_completion_context(lines, position)
        
        # Add context-specific completions
        if context == "contract_body":
            completions.extend(self._get_contract_body_completions(current_word))
        elif context == "function_body":
            completions.extend(self._get_function_body_completions(current_word, text))
        elif context == "type":
            completions.extend(self._get_type_completions(current_word))
        elif context == "import":
            completions.extend(self._get_import_completions(current_word))
        else:
            # General completions
            completions.extend(self._get_general_completions(current_word))
        
        # Add symbols from current file
        completions.extend(self._get_symbol_completions(current_word, "temp://completions"))
        
        # Filter and sort completions
        if current_word:
            completions = [c for c in completions if c.label.lower().startswith(current_word.lower())]
        
        return completions[:50]  # Limit to 50 completions
    
    def _get_completion_context(self, lines: List[str], position: Position) -> str:
        """Determine the completion context based on surrounding code."""
        current_line = lines[position.line]
        
        # Check if we're in an import statement
        if "import" in current_line and not current_line.strip().endswith(";"):
            return "import"
        
        # Look backwards to find context
        for i in range(position.line, -1, -1):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("//"):
                continue
            
            # Check for contract/interface/library context
            if any(keyword in line for keyword in ["contract", "interface", "library"]) and "{" in line:
                # Check if we're inside the contract body
                brace_count = 0
                for j in range(i, position.line + 1):
                    brace_count += lines[j].count("{") - lines[j].count("}")
                
                if brace_count > 0:
                    # Check if we're in a function
                    for k in range(position.line, i, -1):
                        func_line = lines[k].strip()
                        if "function" in func_line and "{" in func_line:
                            return "function_body"
                    return "contract_body"
            
            # Check for type context
            if any(keyword in line for keyword in ["mapping", "uint", "int", "bytes", "string", "address"]):
                return "type"
        
        return "general"
    
    def _get_contract_body_completions(self, prefix: str) -> List[CompletionItem]:
        """Get completions for contract body context."""
        completions = []
        
        # Function-related completions
        completions.extend([
            CompletionItem(label="function", kind=CompletionItemKind.Keyword, 
                         detail="Function declaration"),
            CompletionItem(label="constructor", kind=CompletionItemKind.Keyword,
                         detail="Constructor function"),
            CompletionItem(label="modifier", kind=CompletionItemKind.Keyword,
                         detail="Function modifier"),
            CompletionItem(label="event", kind=CompletionItemKind.Event,
                         detail="Event declaration"),
        ])
        
        # Visibility modifiers
        completions.extend([
            CompletionItem(label="public", kind=CompletionItemKind.Keyword),
            CompletionItem(label="private", kind=CompletionItemKind.Keyword),
            CompletionItem(label="internal", kind=CompletionItemKind.Keyword),
            CompletionItem(label="external", kind=CompletionItemKind.Keyword),
        ])
        
        # State mutability
        completions.extend([
            CompletionItem(label="pure", kind=CompletionItemKind.Keyword),
            CompletionItem(label="view", kind=CompletionItemKind.Keyword),
            CompletionItem(label="payable", kind=CompletionItemKind.Keyword),
        ])
        
        # Data structures
        completions.extend([
            CompletionItem(label="struct", kind=CompletionItemKind.Struct,
                         detail="Struct declaration"),
            CompletionItem(label="enum", kind=CompletionItemKind.Enum,
                         detail="Enum declaration"),
            CompletionItem(label="mapping", kind=CompletionItemKind.TypeParameter,
                         detail="Mapping type"),
        ])
        
        return completions
    
    def _get_function_body_completions(self, prefix: str, text: str) -> List[CompletionItem]:
        """Get completions for function body context."""
        completions = []
        
        # Control flow
        completions.extend([
            CompletionItem(label="if", kind=CompletionItemKind.Keyword),
            CompletionItem(label="else", kind=CompletionItemKind.Keyword),
            CompletionItem(label="for", kind=CompletionItemKind.Keyword),
            CompletionItem(label="while", kind=CompletionItemKind.Keyword),
            CompletionItem(label="return", kind=CompletionItemKind.Keyword),
            CompletionItem(label="break", kind=CompletionItemKind.Keyword),
            CompletionItem(label="continue", kind=CompletionItemKind.Keyword),
        ])
        
        # Error handling
        completions.extend([
            CompletionItem(label="require", kind=CompletionItemKind.Function,
                         detail="Require condition"),
            CompletionItem(label="assert", kind=CompletionItemKind.Function,
                         detail="Assert condition"),
            CompletionItem(label="revert", kind=CompletionItemKind.Function,
                         detail="Revert transaction"),
        ])
        
        # Common patterns
        completions.extend([
            CompletionItem(label="msg.sender", kind=CompletionItemKind.Property,
                         detail="Transaction sender"),
            CompletionItem(label="msg.value", kind=CompletionItemKind.Property,
                         detail="Transaction value"),
            CompletionItem(label="block.timestamp", kind=CompletionItemKind.Property,
                         detail="Current block timestamp"),
            CompletionItem(label="address(this)", kind=CompletionItemKind.Function,
                         detail="Contract address"),
        ])
        
        return completions
    
    def _get_type_completions(self, prefix: str) -> List[CompletionItem]:
        """Get type-related completions."""
        completions = []
        
        # Basic types
        for type_name in self.types:
            completions.append(
                CompletionItem(label=type_name, kind=CompletionItemKind.TypeParameter,
                             detail=self._get_type_documentation(type_name))
            )
        
        return completions
    
    def _get_import_completions(self, prefix: str) -> List[CompletionItem]:
        """Get import-related completions."""
        completions = []
        
        # Common import patterns
        completions.extend([
            CompletionItem(label="@openzeppelin/contracts/", kind=CompletionItemKind.Module,
                         detail="OpenZeppelin contracts"),
            CompletionItem(label="./", kind=CompletionItemKind.Folder,
                         detail="Current directory"),
            CompletionItem(label="../", kind=CompletionItemKind.Folder,
                         detail="Parent directory"),
        ])
        
        return completions
    
    def _get_general_completions(self, prefix: str) -> List[CompletionItem]:
        """Get general Solidity completions."""
        completions = []
        
        # Keywords
        for keyword in self.keywords:
            completions.append(
                CompletionItem(label=keyword, kind=CompletionItemKind.Keyword,
                             detail=self._get_keyword_documentation(keyword))
            )
        
        return completions
    
    def _get_symbol_completions(self, prefix: str, document_uri: str) -> List[CompletionItem]:
        """Get completions from symbols in the current file."""
        completions = []
        
        if document_uri not in self.file_symbols:
            return completions
        
        for symbol_name, definitions in self.file_symbols[document_uri].items():
            for definition in definitions:
                kind = CompletionItemKind.Variable
                
                if definition.symbol_type == "contract":
                    kind = CompletionItemKind.Class
                elif definition.symbol_type == "function":
                    kind = CompletionItemKind.Function
                elif definition.symbol_type == "struct":
                    kind = CompletionItemKind.Struct
                elif definition.symbol_type == "enum":
                    kind = CompletionItemKind.Enum
                elif definition.symbol_type == "event":
                    kind = CompletionItemKind.Event
                
                completions.append(
                    CompletionItem(
                        label=symbol_name,
                        kind=kind,
                        detail=f"{definition.symbol_type} in {definition.scope}" if definition.scope else definition.symbol_type
                    )
                )
        
        return completions

    def get_hover_info(self, text: str, position: Position) -> Optional[str]:
        """Get hover information for a symbol."""
        lines = text.split("\n")
        if position.line >= len(lines):
            return None

        current_line = lines[position.line]
        word = self._get_word_at_position(current_line, position.character)
        if not word:
            return None

        # Check if it's a keyword
        if word in self.keywords:
            return self._get_keyword_documentation(word)

        # Check if it's a type
        if word in self.types:
            return self._get_type_documentation(word)

        # TODO: Implement symbol definition lookup using ANTLR4 parse tree
        return None

    def get_definitions(
        self, text: str, position: Position, document_uri: str
    ) -> List[Location]:
        """Get definition locations for a symbol with comprehensive resolution."""
        # Use the advanced navigation provider if available
        if self.navigation_provider:
            try:
                # Parse file for library info first
                file_path = document_uri.replace('file://', '')
                self.navigation_provider.library_resolver.parse_file_for_library_info(file_path, text)
                
                # Use advanced resolution
                definitions = self.navigation_provider.get_definitions(text, position, document_uri)
                if definitions:
                    return definitions
            except Exception as e:
                logger.debug(f"Advanced navigation failed, falling back: {e}")
        
        # Fallback to original implementation
        lines = text.split("\n")
        if position.line >= len(lines):
            return []

        current_line = lines[position.line]
        word = self._get_word_at_position(current_line, position.character)

        if not word:
            return []

        logger.info(
            f"Looking for definitions of '{word}' at {position.line}:{position.character}"
        )

        # Parse the file and index symbols
        self._index_file_symbols(text, document_uri)

        # Check if this is an import path
        import_location = self._check_import_path(text, position, document_uri)
        if import_location:
            return [import_location]

        # Find definitions in current file
        definitions = self._find_symbol_definitions(word, text, document_uri)

        # If not found locally and we have remapping resolver, search across project
        if not definitions and self.remapping_resolver:
            definitions.extend(self._find_cross_file_definitions(word, document_uri))

        # Handle library method resolution for 'using' directives
        if not definitions:
            definitions.extend(
                self._find_library_method_definitions(word, text, document_uri)
            )

        return definitions

    def get_references(
        self, text: str, position: Position, document_uri: str
    ) -> List[Location]:
        """Find all references to a symbol across the project."""
        lines = text.split("\n")
        if position.line >= len(lines):
            return []

        current_line = lines[position.line]
        word = self._get_word_at_position(current_line, position.character)

        if not word:
            return []

        logger.info(
            f"Looking for references to '{word}' at {position.line}:{position.character}"
        )

        # Index symbols in current file
        self._index_file_symbols(text, document_uri)

        references = []

        # Find references in current file
        references.extend(self._find_symbol_references(word, text, document_uri))

        # Find references across project if remapping resolver is available
        if self.remapping_resolver:
            references.extend(self._find_cross_file_references(word, document_uri))

        return references

    def _index_file_symbols(self, text: str, document_uri: str) -> None:
        """Index all symbols in a file using ANTLR4 parser."""
        try:
            listener, errors = self._parse_solidity_code(text, document_uri)

            # Store symbols
            self.file_symbols[document_uri] = listener.symbols

            # Store using directives for library method resolution
            self.using_directives[document_uri] = listener.using_directives

            # Store library functions
            self.library_functions[document_uri] = listener.library_functions

        except Exception as e:
            logger.error(f"Error parsing file {document_uri}: {e}")
            # Fallback to empty symbols
            self.file_symbols[document_uri] = {}
            self.using_directives[document_uri] = []
            self.library_functions[document_uri] = {}

    def _find_library_method_definitions(
        self, symbol: str, text: str, document_uri: str
    ) -> List[Location]:
        """Find library method definitions based on 'using' directives."""
        definitions = []

        if document_uri not in self.using_directives:
            return definitions

        # Check all using directives in the current file
        for using_directive in self.using_directives[document_uri]:
            # If this is a wildcard using directive (using Library for *)
            if using_directive.target_type == "*":
                # Look for the symbol in the specified library
                library_definitions = self._find_symbol_in_library(
                    symbol, using_directive.library_name, document_uri
                )
                definitions.extend(library_definitions)

            # If specific functions are listed
            elif using_directive.functions and symbol in using_directive.functions:
                library_definitions = self._find_symbol_in_library(
                    symbol, using_directive.library_name, document_uri
                )
                definitions.extend(library_definitions)

        return definitions

    def _find_symbol_in_library(
        self, symbol: str, library_name: str, current_uri: str
    ) -> List[Location]:
        """Find a symbol within a specific library."""
        definitions = []

        # First check if the library is defined in the current file
        if (
            current_uri in self.file_symbols
            and library_name in self.file_symbols[current_uri]
        ):
            for definition in self.file_symbols[current_uri][library_name]:
                if definition.symbol_type == "library":
                    # Look for the symbol within this library's scope
                    for symbol_name, symbol_defs in self.file_symbols[
                        current_uri
                    ].items():
                        for symbol_def in symbol_defs:
                            if (
                                symbol_def.name == symbol
                                and symbol_def.scope == library_name
                            ):
                                definitions.append(symbol_def.location)

        # If not found locally and we have remapping resolver, search across project
        if not definitions and self.remapping_resolver:
            try:
                # Use the remapping resolver to find the library and then the symbol within it
                symbol_locations = self.remapping_resolver.find_symbol_definition(
                    symbol
                )

                for file_path, line_num in symbol_locations:
                    file_uri = f"file://{file_path}"
                    if file_uri != current_uri:
                        # Check if this symbol is in the correct library context
                        # This would require parsing the target file, but for now we'll include it
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                lines = f.readlines()
                                if line_num <= len(lines):
                                    line = lines[line_num - 1]
                                    # Simple check if we're in a library context
                                    if (
                                        library_name.lower() in line.lower()
                                        or "library" in line.lower()
                                    ):
                                        definitions.append(
                                            Location(
                                                uri=file_uri,
                                                range=Range(
                                                    start=Position(
                                                        line=line_num - 1, character=0
                                                    ),
                                                    end=Position(
                                                        line=line_num - 1,
                                                        character=len(symbol),
                                                    ),
                                                ),
                                            )
                                        )
                        except Exception as e:
                            logger.debug(f"Error reading file {file_path}: {e}")
            except Exception as e:
                logger.debug(f"Error finding library symbol: {e}")

        return definitions

    def _find_symbol_definitions(
        self, symbol: str, text: str, document_uri: str
    ) -> List[Location]:
        """Find symbol definitions in the current file."""
        definitions = []

        if (
            document_uri in self.file_symbols
            and symbol in self.file_symbols[document_uri]
        ):
            for definition in self.file_symbols[document_uri][symbol]:
                definitions.append(definition.location)

        return definitions

    def _find_symbol_references(
        self, symbol: str, text: str, document_uri: str
    ) -> List[Location]:
        """Find all references to a symbol in the current file."""
        references = []
        lines = text.split("\n")

        for line_num, line in enumerate(lines):
            # Find all occurrences of the symbol
            import re

            for match in re.finditer(rf"\b{re.escape(symbol)}\b", line):
                # Skip if this is the definition itself
                is_definition = False
                if (
                    document_uri in self.file_symbols
                    and symbol in self.file_symbols[document_uri]
                ):
                    for definition in self.file_symbols[document_uri][symbol]:
                        if (
                            definition.location.range.start.line == line_num
                            and definition.location.range.start.character
                            <= match.start()
                            <= definition.location.range.end.character
                        ):
                            is_definition = True
                            break

                if not is_definition:
                    references.append(
                        Location(
                            uri=document_uri,
                            range=Range(
                                start=Position(line=line_num, character=match.start()),
                                end=Position(line=line_num, character=match.end()),
                            ),
                        )
                    )

        return references

    def _find_cross_file_definitions(
        self, symbol: str, current_uri: str
    ) -> List[Location]:
        """Find symbol definitions across the project using remapping resolver."""
        definitions = []

        if not self.remapping_resolver:
            return definitions

        try:
            # Use the remapping resolver to find symbol definitions
            symbol_locations = self.remapping_resolver.find_symbol_definition(symbol)

            for file_path, line_num in symbol_locations:
                file_uri = f"file://{file_path}"
                if file_uri != current_uri:  # Don't include current file
                    # Try to get more precise position by reading the file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            if line_num <= len(lines):
                                line = lines[line_num - 1]  # line_num is 1-based
                                import re

                                match = re.search(rf"\b{re.escape(symbol)}\b", line)
                                if match:
                                    definitions.append(
                                        Location(
                                            uri=file_uri,
                                            range=Range(
                                                start=Position(
                                                    line=line_num - 1,
                                                    character=match.start(),
                                                ),
                                                end=Position(
                                                    line=line_num - 1,
                                                    character=match.end(),
                                                ),
                                            ),
                                        )
                                    )
                    except Exception as e:
                        logger.debug(f"Error reading file {file_path}: {e}")
                        # Fallback to line start
                        definitions.append(
                            Location(
                                uri=file_uri,
                                range=Range(
                                    start=Position(line=line_num - 1, character=0),
                                    end=Position(
                                        line=line_num - 1, character=len(symbol)
                                    ),
                                ),
                            )
                        )
        except Exception as e:
            logger.debug(f"Error finding cross-file definitions: {e}")

        return definitions

    def _find_cross_file_references(
        self, symbol: str, current_uri: str
    ) -> List[Location]:
        """Find symbol references across the project, filtering out cache and library files."""
        references = []

        if not self.remapping_resolver:
        return references

    def get_declarations(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get declaration locations (includes interface declarations)."""
        if self.navigation_provider:
            try:
                file_path = document_uri.replace('file://', '')
                self.navigation_provider.library_resolver.parse_file_for_library_info(file_path, text)
                return self.navigation_provider.get_declarations(text, position, document_uri)
            except Exception as e:
                logger.debug(f"Advanced declarations failed, falling back: {e}")
        
        # Fallback to definitions
        return self.get_definitions(text, position, document_uri)

    def get_type_definitions(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get type definition locations for variables and expressions."""
        if self.navigation_provider:
            try:
                file_path = document_uri.replace('file://', '')
                self.navigation_provider.library_resolver.parse_file_for_library_info(file_path, text)
                return self.navigation_provider.get_type_definitions(text, position, document_uri)
            except Exception as e:
                logger.debug(f"Advanced type definitions failed, falling back: {e}")
        
        # Fallback implementation
        lines = text.split('\n')
        if position.line >= len(lines):
            return []
        
        current_line = lines[position.line]
        word = self._get_word_at_position(current_line, position.character)
        
        if not word:
            return []
        
        # Try to find type definitions
        return self._find_type_definitions(word, text, document_uri)

    def get_implementations(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get implementation locations for interfaces and abstract functions."""
        if self.navigation_provider:
            try:
                file_path = document_uri.replace('file://', '')
                self.navigation_provider.library_resolver.parse_file_for_library_info(file_path, text)
                return self.navigation_provider.get_implementations(text, position, document_uri)
            except Exception as e:
                logger.debug(f"Advanced implementations failed, falling back: {e}")
        
        # Fallback implementation
        return []

    def find_references_advanced(self, text: str, position: Position, document_uri: str, 
                                include_declaration: bool = True) -> List[Location]:
        """
        Advanced find references with library method support.
        This is the method that handles the complex 'using Library for Type' resolution.
        """
        if self.navigation_provider:
            try:
                file_path = document_uri.replace('file://', '')
                self.navigation_provider.library_resolver.parse_file_for_library_info(file_path, text)
                return self.navigation_provider.find_references(text, position, document_uri, include_declaration)
            except Exception as e:
                logger.debug(f"Advanced find references failed, falling back: {e}")
        
        # Fallback to existing implementation
        return self.get_references(text, position, document_uri)

    def _find_type_definitions(self, type_name: str, text: str, document_uri: str) -> List[Location]:
        """Find type definitions (structs, contracts, enums)."""
        definitions = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            # Look for struct definitions
            if f'struct {type_name}' in line:
                start_pos = line.find(type_name)
                definitions.append(
                    Location(
                        uri=document_uri,
                        range=Range(
                            start=Position(line=line_num, character=start_pos),
                            end=Position(line=line_num, character=start_pos + len(type_name))
                        )
                    )
                )
            
            # Look for contract definitions
            if f'contract {type_name}' in line or f'interface {type_name}' in line or f'library {type_name}' in line:
                start_pos = line.find(type_name)
                definitions.append(
                    Location(
                        uri=document_uri,
                        range=Range(
                            start=Position(line=line_num, character=start_pos),
                            end=Position(line=line_num, character=start_pos + len(type_name))
                        )
                    )
                )
            
            # Look for enum definitions
            if f'enum {type_name}' in line:
                start_pos = line.find(type_name)
                definitions.append(
                    Location(
                        uri=document_uri,
                        range=Range(
                            start=Position(line=line_num, character=start_pos),
                            end=Position(line=line_num, character=start_pos + len(type_name))
                        )
                    )
                )
        
        return definitions
        try:
            # Get all Solidity files in the project
            all_files = self.remapping_resolver.get_all_solidity_files()

            for file_path in all_files:
                file_uri = f"file://{file_path}"
                if file_uri == current_uri:
                    continue  # Skip current file, already processed

                # Filter out cache files, node_modules, and lib directories
                file_str = str(file_path)
                if any(
                    exclude in file_str
                    for exclude in ["/cache/", "/node_modules/", "/lib/", "/.git/"]
                ):
                    continue

                # Only include src/, test/, script/ directories and root level files
                if (
                    not any(
                        include in file_str
                        for include in ["/src/", "/test/", "/script/"]
                    )
                    and "/" in file_str
                ):
                    # Check if it's a root level file
                    if (
                        file_str.count("/") > file_str.rfind("/src/") + 1
                        if "/src/" in file_str
                        else True
                    ):
                        continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        file_references = self._find_symbol_references(
                            symbol, content, file_uri
                        )
                        # Limit references per file to avoid overwhelming results
                        if len(file_references) > 10:
                            file_references = file_references[:10]
                        references.extend(file_references)
                except Exception as e:
                    logger.debug(f"Error reading file {file_path}: {e}")

        except Exception as e:
            logger.debug(f"Error finding cross-file references: {e}")

        return references

    def _check_import_path(
        self, text: str, position: Position, document_uri: str
    ) -> Optional[Location]:
        """Check if the position is on an import path and resolve it."""
        lines = text.split("\n")
        if position.line >= len(lines):
            return None

        line = lines[position.line]

        # Check if we're in an import statement
        import re

        import_match = re.search(r'import\s+["\']([^"\']+)["\']', line)
        if import_match:
            import_path = import_match.group(1)
            start_pos = import_match.start(1)
            end_pos = import_match.end(1)

            # Check if cursor is within the import path
            if start_pos <= position.character <= end_pos:
                if self.remapping_resolver:
                    try:
                        current_file = document_uri.replace("file://", "")
                        resolved_path = self.remapping_resolver.resolve_import(
                            import_path, current_file
                        )
                        if resolved_path and resolved_path.exists():
                            return Location(
                                uri=f"file://{resolved_path}",
                                range=Range(
                                    start=Position(line=0, character=0),
                                    end=Position(line=0, character=0),
                                ),
                            )
                    except Exception as e:
                        logger.debug(f"Error resolving import path: {e}")

        return None

    def get_diagnostics(self, text: str) -> List[Diagnostic]:
        """Get comprehensive diagnostics for Solidity code using ANTLR4."""
        diagnostics = []

        try:
            listener, error_listener_errors = self._parse_solidity_code(text, "temp://diagnostics")

            # Add syntax errors
            for error in error_listener_errors:
                severity = DiagnosticSeverity.Error
                if error.get("severity") == "warning":
                    severity = DiagnosticSeverity.Warning
                
                # Calculate end position based on symbol length
                end_char = error["column"] + 1
                if error.get("symbol"):
                    end_char = error["column"] + len(error["symbol"])
                
                diagnostic = Diagnostic(
                    range=Range(
                        start=Position(line=error["line"], character=error["column"]),
                        end=Position(line=error["line"], character=end_char),
                    ),
                    message=error["message"],
                    severity=severity,
                    source="solidity-parser",
                )
                
                # Add code actions/suggestions if available
                if error.get("suggestions"):
                    diagnostic.data = {"suggestions": error["suggestions"]}
                
                diagnostics.append(diagnostic)

            # Add semantic diagnostics if we have a semantic analyzer
            try:
                from .semantic_analyzer import SemanticAnalyzer
                from .ast_builder import ASTBuilderVisitor
                
                # Build AST and run semantic analysis
                input_stream = InputStream(text)
                lexer = SolidityLexer(input_stream)
                token_stream = CommonTokenStream(lexer)
                parser = SolidityParser(token_stream)
                
                # Remove default error listeners to avoid duplicate errors
                parser.removeErrorListeners()
                
                tree = parser.sourceUnit()
                
                # Build AST
                ast_builder = ASTBuilderVisitor("temp://diagnostics", token_stream)
                ast = tree.accept(ast_builder)
                
                if ast:
                    # Run semantic analysis
                    analyzer = SemanticAnalyzer("temp://diagnostics")
                    semantic_diagnostics = analyzer.analyze(ast)
                    diagnostics.extend(semantic_diagnostics)
                    
            except ImportError:
                logger.debug("Semantic analyzer not available, skipping semantic diagnostics")
            except Exception as e:
                logger.debug(f"Error in semantic analysis: {e}")

            # Add additional Solidity-specific checks
            diagnostics.extend(self._get_solidity_specific_diagnostics(text))

        except Exception as e:
            logger.error(f"Error getting diagnostics: {e}")
            # Fallback diagnostic
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=1),
                    ),
                    message=f"Parser error: {str(e)}",
                    severity=DiagnosticSeverity.Error,
                    source="solidity-parser",
                )
            )

        # Add forge diagnostics if available
        if self.forge_diagnostics:
            try:
                forge_diags = self.forge_diagnostics.get_diagnostics_for_file(
                    "temp://diagnostics" if not hasattr(self, '_current_file_path') else self._current_file_path
                )
                diagnostics.extend(forge_diags)
            except Exception as e:
                logger.debug(f"Error getting forge diagnostics: {e}")

        return diagnostics

    def _get_solidity_specific_diagnostics(self, text: str) -> List[Diagnostic]:
        """Get Solidity-specific diagnostics beyond syntax errors."""
        diagnostics = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check for common Solidity issues
            
            # 1. Missing SPDX license identifier
            if line_num == 0 and not line_stripped.startswith('// SPDX-License-Identifier:'):
                diagnostics.append(
                    Diagnostic(
                        range=Range(
                            start=Position(line=0, character=0),
                            end=Position(line=0, character=len(line)),
                        ),
                        message="Missing SPDX license identifier. Consider adding '// SPDX-License-Identifier: MIT' at the top of the file",
                        severity=DiagnosticSeverity.Warning,
                        source="solidity-linter",
                    )
                )
            
            # 2. Check for pragma version
            if 'pragma solidity' in line_stripped:
                if '^' not in line_stripped and '~' not in line_stripped and '>=' not in line_stripped:
                    diagnostics.append(
                        Diagnostic(
                            range=Range(
                                start=Position(line=line_num, character=0),
                                end=Position(line=line_num, character=len(line)),
                            ),
                            message="Consider using a version range (e.g., ^0.8.0) instead of a fixed version",
                            severity=DiagnosticSeverity.Information,
                            source="solidity-linter",
                        )
                    )
            
            # 3. Check for functions without visibility
            if 'function ' in line_stripped and not any(vis in line_stripped for vis in ['public', 'private', 'internal', 'external']):
                if 'constructor' not in line_stripped:
                    func_start = line.find('function')
                    diagnostics.append(
                        Diagnostic(
                            range=Range(
                                start=Position(line=line_num, character=func_start),
                                end=Position(line=line_num, character=func_start + 8),
                            ),
                            message="Function visibility must be specified (public, private, internal, or external)",
                            severity=DiagnosticSeverity.Warning,
                            source="solidity-linter",
                        )
                    )
            
            # 4. Check for state variables without visibility
            if any(type_keyword in line_stripped for type_keyword in ['uint', 'int', 'bool', 'address', 'string', 'bytes']) and '=' in line_stripped:
                if not any(vis in line_stripped for vis in ['public', 'private', 'internal']) and 'function' not in line_stripped:
                    diagnostics.append(
                        Diagnostic(
                            range=Range(
                                start=Position(line=line_num, character=0),
                                end=Position(line=line_num, character=len(line)),
                            ),
                            message="State variable visibility should be specified",
                            severity=DiagnosticSeverity.Information,
                            source="solidity-linter",
                        )
                    )
            
            # 5. Check for potential reentrancy patterns
            if 'call{' in line_stripped or '.call(' in line_stripped:
                diagnostics.append(
                    Diagnostic(
                        range=Range(
                            start=Position(line=line_num, character=line.find('call')),
                            end=Position(line=line_num, character=line.find('call') + 4),
                        ),
                        message="Low-level call detected. Consider using reentrancy guards and checks-effects-interactions pattern",
                        severity=DiagnosticSeverity.Warning,
                        source="solidity-security",
                    )
                )
        
        return diagnostics

    def _get_word_at_position(self, line: str, character: int) -> Optional[str]:
        """Get the word at a specific character position in a line."""
        if character >= len(line):
            return None

        # Find word boundaries
        start = character
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
            start -= 1

        end = character
        while end < len(line) and (line[end].isalnum() or line[end] == "_"):
            end += 1

        if start == end:
            return None

        return line[start:end]

    def _get_keyword_documentation(self, keyword: str) -> str:
        """Get documentation for a Solidity keyword."""
        docs = {
            "contract": "Defines a contract - the fundamental building block of Ethereum applications.",
            "function": "Defines a function that can be called to execute code.",
            "modifier": "Defines a modifier that can change the behavior of functions.",
            "event": "Defines an event that can be emitted to log information.",
            "struct": "Defines a custom data type that groups related data.",
            "mapping": "Defines a hash table data structure.",
            "require": "Validates conditions and reverts if they are not met.",
            "assert": "Validates invariants and reverts if they are not met.",
            "revert": "Reverts the transaction with an optional error message.",
            "payable": "Allows a function to receive Ether.",
            "view": "Indicates that a function does not modify state.",
            "pure": "Indicates that a function does not read or modify state.",
            "using": "Attaches library functions to types for convenient method-like syntax.",
        }

        return docs.get(keyword, f"Solidity keyword: {keyword}")

    def _get_type_documentation(self, type_name: str) -> str:
        """Get documentation for a Solidity type."""
        if type_name == "address":
            return "Ethereum address (20 bytes)"
        elif type_name == "bool":
            return "Boolean value (true or false)"
        elif type_name == "string":
            return "Dynamic string of UTF-8 characters"
        elif type_name == "bytes":
            return "Dynamic byte array"
        elif type_name.startswith("uint"):
            return f"Unsigned integer ({type_name})"
        elif type_name.startswith("int"):
            return f"Signed integer ({type_name})"
        elif type_name.startswith("bytes"):
            return f"Fixed-size byte array ({type_name})"
        else:
            return f"Solidity type: {type_name}"

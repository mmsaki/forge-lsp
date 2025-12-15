#![allow(deprecated)]

use serde_json::Value;
use tower_lsp::lsp_types::{Location, Range, SymbolInformation, SymbolKind, Url, Position};

pub fn extract_symbols(ast_data: &Value) -> Vec<SymbolInformation> {
    let mut symbols = Vec::new();
    let mut seen = std::collections::HashSet::new();

    if let Some(sources) = ast_data.get("sources") {
        if let Some(sources_obj) = sources.as_object() {
            for (path, contents) in sources_obj {
                if let Some(contents_array) = contents.as_array() {
                    if let Some(first_content) = contents_array.first() {
                        if let Some(source_file) = first_content.get("source_file") {
                            if let Some(ast) = source_file.get("ast") {
                                let file_symbols = extract_symbols_from_ast(ast, path);
                                for symbol in file_symbols {
                                    // Deduplicate based on location (URI + range)
                                    let key = format!("{}:{:?}:{:?}",
                                        symbol.location.uri,
                                        symbol.location.range.start,
                                        symbol.location.range.end
                                    );
                                    if seen.insert(key) {
                                        symbols.push(symbol);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    symbols
}

fn extract_symbols_from_ast(ast: &Value, file_path: &str) -> Vec<SymbolInformation> {
    let mut symbols = Vec::new();
    let mut stack = vec![ast];

    while let Some(node) = stack.pop() {
        if let Some(node_type) = node.get("nodeType").and_then(|v| v.as_str()) {
            match node_type {
                "ContractDefinition" => {
                    if let Some(symbol) = create_contract_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "FunctionDefinition" => {
                    if let Some(symbol) = create_function_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "VariableDeclaration" => {
                    if let Some(symbol) = create_variable_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "EventDefinition" => {
                    if let Some(symbol) = create_event_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "ModifierDefinition" => {
                    if let Some(symbol) = create_modifier_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "StructDefinition" => {
                    if let Some(symbol) = create_struct_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                "EnumDefinition" => {
                    if let Some(symbol) = create_enum_symbol(node, file_path) {
                        symbols.push(symbol);
                    }
                }
                _ => {}
            }
        }

        // Add child nodes to stack
        push_child_nodes(node, &mut stack);
    }

    symbols
}

fn create_contract_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    Some(SymbolInformation {
        name: name.to_string(),
        kind: SymbolKind::CLASS, // Contracts are represented as classes in LSP
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn create_function_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    // Skip constructors (they have empty name in some AST versions)
    if name.is_empty() {
        return None;
    }

    let kind = if node.get("kind").and_then(|v| v.as_str()) == Some("constructor") {
        SymbolKind::CONSTRUCTOR
    } else {
        SymbolKind::FUNCTION
    };

    Some(SymbolInformation {
        name: name.to_string(),
        kind,
        location: Location { uri, range },
        container_name: None, // Could be set to contract name if we track hierarchy
        tags: None,
        deprecated: None,
    })
}

fn create_variable_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    // Determine if this is a state variable or local variable
    let kind = if is_state_variable(node) {
        SymbolKind::FIELD
    } else {
        SymbolKind::VARIABLE
    };

    Some(SymbolInformation {
        name: name.to_string(),
        kind,
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn create_event_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    Some(SymbolInformation {
        name: name.to_string(),
        kind: SymbolKind::EVENT,
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn create_modifier_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    Some(SymbolInformation {
        name: name.to_string(),
        kind: SymbolKind::METHOD, // Modifiers are represented as methods
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn create_struct_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    Some(SymbolInformation {
        name: name.to_string(),
        kind: SymbolKind::STRUCT,
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn create_enum_symbol(node: &Value, file_path: &str) -> Option<SymbolInformation> {
    let name = node.get("name").and_then(|v| v.as_str())?;
    let range = get_node_range(node, file_path)?;
    let uri = Url::from_file_path(file_path).ok()?;

    Some(SymbolInformation {
        name: name.to_string(),
        kind: SymbolKind::ENUM,
        location: Location { uri, range },
        container_name: None,
        tags: None,
        deprecated: None,
    })
}

fn get_node_range(node: &Value, file_path: &str) -> Option<Range> {
    let src = node.get("src").and_then(|v| v.as_str())?;
    let parts: Vec<&str> = src.split(':').collect();
    if parts.len() >= 3 {
        let start_offset: usize = parts[0].parse().ok()?;
        let length: usize = parts[1].parse().ok()?;

        // Read the file to convert byte offsets to line/column positions
        if let Ok(content) = std::fs::read_to_string(file_path) {
            let start_pos = byte_offset_to_position(&content, start_offset)?;
            let end_pos = byte_offset_to_position(&content, start_offset + length)?;

            Some(Range {
                start: start_pos,
                end: end_pos,
            })
        } else {
            None
        }
    } else {
        None
    }
}

fn byte_offset_to_position(content: &str, byte_offset: usize) -> Option<Position> {
    let mut line = 0;
    let mut character = 0;

    for (i, ch) in content.char_indices() {
        if i >= byte_offset {
            break;
        }

        if ch == '\n' {
            line += 1;
            character = 0;
        } else {
            character += 1;
        }
    }

    Some(Position {
        line: line as u32,
        character: character as u32,
    })
}

fn is_state_variable(node: &Value) -> bool {
    // State variables are VariableDeclarations that are direct children of ContractDefinition
    // This is a simplified check - in practice, we'd need to check the parent context
    node.get("stateVariable").and_then(|v| v.as_bool()).unwrap_or(false)
}

fn push_child_nodes<'a>(node: &'a Value, stack: &mut Vec<&'a Value>) {
    // Common child node fields to traverse
    let child_fields = [
        "nodes", "body", "statements", "parameters", "returnParameters",
        "members", "modifiers", "baseContracts", "arguments",
        "expression", "leftExpression", "rightExpression", "condition",
        "trueBody", "falseBody", "initialValue", "typeName",
    ];

    for field in &child_fields {
        if let Some(value) = node.get(field) {
            match value {
                Value::Array(arr) => {
                    stack.extend(arr);
                }
                Value::Object(_) => {
                    stack.push(value);
                }
                _ => {}
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    fn get_test_ast_data() -> Option<serde_json::Value> {
        let output = Command::new("forge")
            .args(["build", "--ast", "--silent", "--build-info"])
            .current_dir("testdata")
            .output()
            .ok()?;

        let stdout_str = String::from_utf8(output.stdout).ok()?;
        serde_json::from_str(&stdout_str).ok()
    }

    #[test]
    fn test_extract_symbols_basic() {
        let ast_data = match get_test_ast_data() {
            Some(data) => data,
            None => return,
        };

        let symbols = extract_symbols(&ast_data);

        // Should find some symbols
        assert!(!symbols.is_empty());

        // Check that we have contracts
        let contract_symbols: Vec<_> = symbols.iter()
            .filter(|s| s.kind == SymbolKind::CLASS)
            .collect();
        assert!(!contract_symbols.is_empty(), "Should find at least one contract");

        // Check that we have functions
        let function_symbols: Vec<_> = symbols.iter()
            .filter(|s| s.kind == SymbolKind::FUNCTION)
            .collect();
        assert!(!function_symbols.is_empty(), "Should find at least one function");
    }

    #[test]
    fn test_symbol_kinds() {
        let ast_data = match get_test_ast_data() {
            Some(data) => data,
            None => return,
        };

        let symbols = extract_symbols(&ast_data);

        // Check that we have various symbol kinds
        let has_class = symbols.iter().any(|s| s.kind == SymbolKind::CLASS);
        let has_function = symbols.iter().any(|s| s.kind == SymbolKind::FUNCTION);

        // Should have at least contracts and functions
        assert!(has_class, "Should have contract symbols");
        assert!(has_function, "Should have function symbols");
    }
}
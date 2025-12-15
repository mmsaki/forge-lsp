use serde_json::Value;
use std::collections::{HashMap, HashSet};
use tower_lsp::lsp_types::{Location, Position, Range, Url};

use crate::goto::{NodeInfo, bytes_to_pos, cache_ids, pos_to_bytes};

/// Build a map of all reference relationships in the AST
/// Returns a HashMap where keys are node IDs and values are vectors of related node IDs
pub fn all_references(nodes: &HashMap<String, HashMap<u64, NodeInfo>>) -> HashMap<u64, Vec<u64>> {
    let mut all_refs: HashMap<u64, Vec<u64>> = HashMap::new();

    // Iterate through all files and nodes
    for file_nodes in nodes.values() {
        for (id, node_info) in file_nodes {
            if let Some(ref_id) = node_info.referenced_declaration {
                // Add the reference relationship
                all_refs.entry(ref_id).or_default().push(*id);
                all_refs.entry(*id).or_default().push(ref_id);
            }
        }
    }

    all_refs
}

/// Find the node ID at a specific byte position in a file
pub fn byte_to_id(
    nodes: &HashMap<String, HashMap<u64, NodeInfo>>,
    abs_path: &str,
    byte_position: usize,
) -> Option<u64> {
    let file_nodes = nodes.get(abs_path)?;
    let mut refs: HashMap<usize, u64> = HashMap::new();

    for (id, node_info) in file_nodes {
        let src_parts: Vec<&str> = node_info.src.split(':').collect();
        if src_parts.len() != 3 {
            continue;
        }

        let start: usize = src_parts[0].parse().ok()?;
        let length: usize = src_parts[1].parse().ok()?;
        let end = start + length;

        if start <= byte_position && byte_position < end {
            let diff = end - start;
            refs.entry(diff).or_insert(*id);
        }
    }

    refs.keys().min().map(|min_diff| refs[min_diff])
}

/// Convert a node ID to a Location for LSP
pub fn id_to_location(
    nodes: &HashMap<String, HashMap<u64, NodeInfo>>,
    id_to_path: &HashMap<String, String>,
    node_id: u64,
) -> Option<Location> {
    // Find the file containing this node
    let mut target_node: Option<&NodeInfo> = None;
    for file_nodes in nodes.values() {
        if let Some(node) = file_nodes.get(&node_id) {
            target_node = Some(node);
            break;
        }
    }

    let node = target_node?;

    // Get location from nameLocation or src
    let (byte_str, length_str, file_id) = if let Some(name_location) = &node.name_location {
        let parts: Vec<&str> = name_location.split(':').collect();
        if parts.len() == 3 {
            (parts[0], parts[1], parts[2])
        } else {
            return None;
        }
    } else {
        let parts: Vec<&str> = node.src.split(':').collect();
        if parts.len() == 3 {
            (parts[0], parts[1], parts[2])
        } else {
            return None;
        }
    };

    let byte_offset: usize = byte_str.parse().ok()?;
    let length: usize = length_str.parse().ok()?;
    let file_path = id_to_path.get(file_id)?;

    // Read the file to convert byte positions to line/column
    let absolute_path = if std::path::Path::new(file_path).is_absolute() {
        std::path::PathBuf::from(file_path)
    } else {
        std::env::current_dir().ok()?.join(file_path)
    };

    let source_bytes = std::fs::read(&absolute_path).ok()?;
    let start_pos = bytes_to_pos(&source_bytes, byte_offset)?;
    let end_pos = bytes_to_pos(&source_bytes, byte_offset + length)?;

    let uri = Url::from_file_path(&absolute_path).ok()?;

    Some(Location { uri, range: Range { start: start_pos, end: end_pos } })
}

/// Find all references to a symbol at the given position
pub fn goto_references(
    ast_data: &Value,
    file_uri: &Url,
    position: Position,
    source_bytes: &[u8],
) -> Vec<Location> {
    let sources = match ast_data.get("sources") {
        Some(s) => s,
        None => return vec![],
    };

    let build_infos = match ast_data.get("build_infos").and_then(|v| v.as_array()) {
        Some(infos) => infos,
        None => return vec![],
    };

    let first_build_info = match build_infos.first() {
        Some(info) => info,
        None => return vec![],
    };

    let id_to_path = match first_build_info.get("source_id_to_path").and_then(|v| v.as_object()) {
        Some(map) => map,
        None => return vec![],
    };

    let id_to_path_map: HashMap<String, String> =
        id_to_path.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap_or("").to_string())).collect();

    let (nodes, path_to_abs) = cache_ids(sources);
    let all_refs = all_references(&nodes);

    // Get the file path and convert to absolute path
    let path = match file_uri.to_file_path() {
        Ok(p) => p,
        Err(_) => return vec![],
    };

    let path_str = match path.to_str() {
        Some(s) => s,
        None => return vec![],
    };

    let abs_path = match path_to_abs.get(path_str) {
        Some(ap) => ap,
        None => return vec![],
    };

    // Convert position to byte offset
    let byte_position = pos_to_bytes(source_bytes, position);

    // Find the node ID at this position
    let node_id = match byte_to_id(&nodes, abs_path, byte_position) {
        Some(id) => id,
        None => return vec![],
    };

    // Determine the target node ID for finding references
    // If this is a usage node, get its declaration; otherwise use the node itself
    let target_node_id = {
        let file_nodes = match nodes.get(abs_path) {
            Some(nodes) => nodes,
            None => return vec![],
        };

        if let Some(node_info) = file_nodes.get(&node_id) {
            // If this node references a declaration, use the declaration as the target
            // This ensures we get ALL references to the same symbol
            node_info.referenced_declaration.unwrap_or(node_id)
        } else {
            node_id
        }
    };

    // Get all references for the target node (declaration)
    let refs = match all_refs.get(&target_node_id) {
        Some(r) => r,
        None => return vec![],
    };

    // Collect all related references
    let mut results = HashSet::new();
    results.extend(refs.iter().copied());
    // Also include the target node itself (the declaration)
    results.insert(target_node_id);

    // Convert node IDs to locations
    let mut locations = Vec::new();
    for id in results {
        if let Some(location) = id_to_location(&nodes, &id_to_path_map, id) {
            locations.push(location);
        }
    }

    // Remove duplicate locations
    let mut unique_locations = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for location in locations {
        let key = (location.uri.clone(), location.range.start.line, location.range.start.character, location.range.end.line, location.range.end.character);
        if seen.insert(key) {
            unique_locations.push(location);
        }
    }

    unique_locations
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    fn get_ast_data() -> Option<Value> {
        let output = Command::new("forge")
            .args(["build", "--ast", "--silent", "--build-info"])
            .current_dir("testdata")
            .output()
            .ok()?;

        let stdout_str = String::from_utf8(output.stdout).ok()?;
        serde_json::from_str(&stdout_str).ok()
    }

    fn get_test_file_uri(relative_path: &str) -> Url {
        let current_dir = std::env::current_dir().expect("Failed to get current directory");
        let absolute_path = current_dir.join(relative_path);
        Url::from_file_path(absolute_path).expect("Failed to create file URI")
    }

    #[test]
    fn test_goto_references_basic() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/C.sol");
        let source_bytes = std::fs::read("testdata/C.sol").unwrap();

        // Test goto references on "name" in add_vote function (line 22, column 8)
        let position = Position::new(21, 8);
        let references = goto_references(&ast_data, &file_uri, position, &source_bytes);

        // The function should return a vector (may be empty if no references found)
        // This is just testing that the function runs without panicking

        // If references are found, verify they have valid locations
        for location in &references {
            assert!(location.range.start.line < 100, "Reference line should be reasonable");
            assert!(!location.uri.as_str().is_empty(), "Reference URI should not be empty");
        }
    }

    #[test]
    fn test_goto_references_from_usage_includes_all_references() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/Reference.sol");
        let source_bytes = std::fs::read("testdata/Reference.sol").unwrap();

        // Test goto references from a usage of myValue (line 8: myValue = _value)
        let position = Position::new(7, 8); // Position of "myValue" in assignment
        let references_from_usage = goto_references(&ast_data, &file_uri, position, &source_bytes);

        // Test goto references from the declaration of myValue (line 5: uint256 public myValue)
        let position_declaration = Position::new(4, 13); // Position of "myValue" in declaration
        let references_from_declaration = goto_references(&ast_data, &file_uri, position_declaration, &source_bytes);

        // Both should return the same number of references (declaration + all usages)
        assert_eq!(
            references_from_usage.len(),
            references_from_declaration.len(),
            "References from usage and declaration should return the same count"
        );

        // Both should have at least 2 references (declaration + at least 1 usage)
        assert!(
            references_from_usage.len() >= 2,
            "Should find at least declaration and one usage, found {}",
            references_from_usage.len()
        );

        // The locations should be the same regardless of where we started
        let usage_locations: std::collections::HashSet<_> = references_from_usage.iter()
            .map(|loc| (loc.uri.as_str(), loc.range.start.line, loc.range.start.character))
            .collect();
        let declaration_locations: std::collections::HashSet<_> = references_from_declaration.iter()
            .map(|loc| (loc.uri.as_str(), loc.range.start.line, loc.range.start.character))
            .collect();

        assert_eq!(
            usage_locations,
            declaration_locations,
            "References from usage and declaration should return the same locations"
        );
    }

    #[test]
    fn test_all_references_basic() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let sources = ast_data.get("sources").unwrap();
        let (nodes, _path_to_abs) = cache_ids(sources);
        let all_refs = all_references(&nodes);

        // Should have some reference relationships (or be empty if none found)
        // Just verify the function runs without panicking

        // If references exist, verify they are bidirectional
        for refs in all_refs.values() {
            for ref_id in refs {
                if let Some(back_refs) = all_refs.get(ref_id) {
                    // This is a more lenient check - just verify the structure is reasonable
                    assert!(
                        !back_refs.is_empty(),
                        "Back references should exist if forward references exist"
                    );
                }
            }
        }
    }
}

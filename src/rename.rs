use serde_json::Value;
use std::collections::HashMap;
use tower_lsp::lsp_types::{Position, Range, TextEdit, Url, WorkspaceEdit};

use crate::references;

/// Extract the identifier (word) at the given position in the source bytes
fn get_identifier_at_position(source_bytes: &[u8], position: Position) -> Option<String> {
    let text = String::from_utf8_lossy(source_bytes);
    let lines: Vec<&str> = text.lines().collect();

    if position.line as usize >= lines.len() {
        return None;
    }

    let line = lines[position.line as usize];
    if position.character as usize > line.len() {
        return None;
    }

    // Find the word boundaries around the character position
    let mut start = position.character as usize;
    let mut end = position.character as usize;

    // Move start backwards to find word start
    while start > 0 && (line.as_bytes()[start - 1].is_ascii_alphanumeric() || line.as_bytes()[start - 1] == b'_') {
        start -= 1;
    }

    // Move end forwards to find word end
    while end < line.len() && (line.as_bytes()[end].is_ascii_alphanumeric() || line.as_bytes()[end] == b'_') {
        end += 1;
    }

    if start == end {
        return None; // No word found
    }

    // Check if it starts with a digit (not a valid identifier)
    if line.as_bytes()[start].is_ascii_digit() {
        return None;
    }

    Some(line[start..end].to_string())
}



/// Adjust the range to cover only the specific identifier within the range text
fn adjust_range_for_identifier(range: &Range, source_bytes: &[u8], identifier: &str) -> Option<Range> {
    let text = String::from_utf8_lossy(source_bytes);
    let start_line = range.start.line as usize;
    let end_line = range.end.line as usize;
    let start_char = range.start.character as usize;
    let end_char = range.end.character as usize;

    if start_line != end_line {
        // Multi-line ranges not supported for now
        return None;
    }

    let lines: Vec<&str> = text.lines().collect();
    if start_line >= lines.len() {
        return None;
    }

    let line = lines[start_line];
    if start_char > end_char || end_char > line.len() {
        return None;
    }

    let range_text = &line[start_char..end_char];

    // Find the identifier in the range text
    if let Some(pos) = range_text.find(identifier) {
        let new_start_char = start_char + pos;
        let new_end_char = new_start_char + identifier.len();

        // Make sure it doesn't go beyond the original range
        if new_end_char <= end_char {
            return Some(Range {
                start: Position {
                    line: start_line as u32,
                    character: new_start_char as u32,
                },
                end: Position {
                    line: end_line as u32,
                    character: new_end_char as u32,
                },
            });
        }
    }

    None
}

/// Handle a rename request by finding all references to the symbol at the given position
/// and creating a WorkspaceEdit with the new name
pub fn rename_symbol(
    ast_data: &Value,
    file_uri: &Url,
    position: Position,
    source_bytes: &[u8],
    new_name: String,
) -> Option<WorkspaceEdit> {
    // Extract the identifier at the cursor position
    let identifier = get_identifier_at_position(source_bytes, position)?;

    // Get all locations for renaming (declaration + references)
    // This should already include the cursor position since we fixed goto_references
    let locations = references::goto_references(ast_data, file_uri, position, source_bytes);

    if locations.is_empty() {
        return None;
    }

    // Group locations by URI
    let mut changes: HashMap<Url, Vec<TextEdit>> = HashMap::new();

    for location in locations {
        // Read the source file for this location to adjust the range
        let location_source_bytes = match std::fs::read(location.uri.to_file_path().ok()?) {
            Ok(bytes) => bytes,
            Err(_) => continue, // Skip if can't read
        };

        // Adjust the range to cover only the identifier
        let adjusted_range = adjust_range_for_identifier(&location.range, &location_source_bytes, &identifier)
            .unwrap_or(location.range);

        let text_edit = TextEdit {
            range: adjusted_range,
            new_text: new_name.clone(),
        };
        changes.entry(location.uri).or_default().push(text_edit);
    }

    Some(WorkspaceEdit {
        changes: Some(changes),
        document_changes: None,
        change_annotations: None,
    })
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
    fn test_rename_symbol_basic() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/C.sol");
        let source_bytes = std::fs::read("testdata/C.sol").unwrap();

        // Test rename on "name" parameter in add_vote function (line 22, column 8)
        let position = Position::new(21, 8);
        let new_name = "new_name".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return a workspace edit
        assert!(result.is_some());
        let workspace_edit = result.unwrap();

        // Should have changes
        assert!(workspace_edit.changes.is_some());
        let changes = workspace_edit.changes.unwrap();

        // Should have at least one file with changes
        assert!(!changes.is_empty());

        // Each change should have the new name
        for file_changes in changes.values() {
            for text_edit in file_changes {
                assert_eq!(text_edit.new_text, "new_name");
            }
        }
    }

    #[test]
    fn test_rename_symbol_no_references() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/C.sol");
        let source_bytes = std::fs::read("testdata/C.sol").unwrap();

        // Test rename on a position with no references (whitespace)
        let position = Position::new(0, 0); // Start of file (comment)
        let new_name = "new_name".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return None for positions with no references
        assert!(result.is_none());
    }

    #[test]
    fn test_rename_symbol_dotted_expression() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/rename.sol");
        let source_bytes = std::fs::read("testdata/rename.sol").unwrap();

        // Test rename on "Name" in "IC.Name" (line 12, column around 10-11 for "Name")
        // IC.Name starts at column 12, "Name" is at 14-17
        let position = Position::new(11, 14); // Position of "N" in "Name"
        let new_name = "NewName".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return a workspace edit
        assert!(result.is_some());
        let workspace_edit = result.unwrap();

        // Should have changes
        assert!(workspace_edit.changes.is_some());
        let changes = workspace_edit.changes.unwrap();

        // Should have at least one file with changes
        assert!(!changes.is_empty());

        // Check that the changes replace "Name" with "NewName"
        for file_changes in changes.values() {
            for text_edit in file_changes {
                assert_eq!(text_edit.new_text, "NewName");
                // The range should cover "Name" (4 characters)
                let range_len = text_edit.range.end.character - text_edit.range.start.character;
                assert_eq!(range_len, 4);
            }
        }
    }

    #[test]
    fn test_rename_symbol_member_access() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/rename.sol");
        let source_bytes = std::fs::read("testdata/rename.sol").unwrap();

        // Test rename on "id" in "name.id" (line 13, "name.id" starts around column 8, "id" at 13-14)
        let position = Position::new(12, 13); // Position of "i" in "id"
        let new_name = "new_id".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return a workspace edit
        assert!(result.is_some());
        let workspace_edit = result.unwrap();

        // Should have changes
        assert!(workspace_edit.changes.is_some());
        let changes = workspace_edit.changes.unwrap();

        // Should have at least one file with changes
        assert!(!changes.is_empty());

        // Check that the changes replace "id" with "new_id"
        for file_changes in changes.values() {
            for text_edit in file_changes {
                assert_eq!(text_edit.new_text, "new_id");
                // The range should cover "id" (2 characters)
                let range_len = text_edit.range.end.character - text_edit.range.start.character;
                assert_eq!(range_len, 2);
            }
        }
    }

    #[test]
    fn test_rename_symbol_struct_in_interface() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/rename.sol");
        let source_bytes = std::fs::read("testdata/rename.sol").unwrap();

        // Test rename on "Name" in "IC.Name" (line 12, "IC.Name" at column 12-18, "Name" at 15-18)
        let position = Position::new(11, 15); // Position of "N" in "Name"
        let new_name = "NewStruct".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return a workspace edit
        assert!(result.is_some());
        let workspace_edit = result.unwrap();

        // Should have changes
        assert!(workspace_edit.changes.is_some());
        let changes = workspace_edit.changes.unwrap();

        // Should have changes in the file
        assert!(changes.contains_key(&file_uri));

        let file_changes = &changes[&file_uri];
        assert!(!file_changes.is_empty());

        // Check that "Name" is replaced with "NewStruct" in struct declaration and type reference
        // But "IC" should not be changed
        let mut found_struct_decl = false;
        let mut found_type_ref = false;
        for text_edit in file_changes {
            assert_eq!(text_edit.new_text, "NewStruct");
            let range_len = text_edit.range.end.character - text_edit.range.start.character;
            assert_eq!(range_len, 4); // "Name" is 4 characters

            // Check the line to see if it's the struct or the reference
            let line = text_edit.range.start.line as usize;
            if line == 4 { // struct Name
                found_struct_decl = true;
            } else if line == 11 { // IC.Name
                found_type_ref = true;
            }
        }

        assert!(found_struct_decl, "Should rename the struct declaration");
        assert!(found_type_ref, "Should rename the type reference");
    }

    #[test]
    fn test_rename_symbol_cursor_position_handling() {
        let ast_data = match get_ast_data() {
            Some(data) => data,
            None => {
                return;
            }
        };

        let file_uri = get_test_file_uri("testdata/Reference.sol");
        let source_bytes = std::fs::read("testdata/Reference.sol").unwrap();

        // Test rename on "myValue" in the declaration (line 5: uint256 public myValue)
        let position = Position::new(4, 13); // Position of "m" in "myValue"
        let new_name = "newValue".to_string();
        let result = rename_symbol(&ast_data, &file_uri, position, &source_bytes, new_name);

        // Should return a workspace edit
        assert!(result.is_some());
        let workspace_edit = result.unwrap();

        // Should have changes
        assert!(workspace_edit.changes.is_some());
        let changes = workspace_edit.changes.unwrap();

        // Should have changes in the file
        assert!(changes.contains_key(&file_uri));

        let file_changes = &changes[&file_uri];
        assert!(!file_changes.is_empty());

        // Should have exactly 3 changes: declaration and 2 usages
        assert_eq!(file_changes.len(), 3, "Should have 3 changes: declaration and 2 usages");

        // All changes should have the new name
        for text_edit in file_changes {
            assert_eq!(text_edit.new_text, "newValue");
            // Each range should cover "myValue" (7 characters)
            let range_len = text_edit.range.end.character - text_edit.range.start.character;
            assert_eq!(range_len, 7);
        }

        // Check that we have changes on the expected lines
        let mut lines_with_changes: Vec<u32> = file_changes.iter()
            .map(|edit| edit.range.start.line)
            .collect();
        lines_with_changes.sort();
        lines_with_changes.dedup();

        // Should have changes on lines 5 (declaration), 8 (setMyValue), and 12 (getMyValue)
        assert_eq!(lines_with_changes, vec![4, 7, 11]);
    }
}

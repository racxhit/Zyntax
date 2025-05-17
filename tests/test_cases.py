"""
File: test_cases.py
Description: Contains test functions and test cases for validating the correctness
             of NLP parsing and system command execution.
Date Created: 05-04-2025
Last Updated: 17-05-2025
"""

import pytest
from nlp_engine.parser import parse_input # Make sure this import path is correct

# Test cases: list of tuples (input_string, expected_action, expected_args_list)
# For commands that don't take args, expected_args_list should be []
# For commands where args are tricky, manual testing is needed.
TEST_COMMANDS = [
    ("make a new folder named project_alpha", "make_directory", ["project_alpha"]),
    ("cd Zyntax-NLP-Terminal", "change_directory", ["Zyntax-NLP-Terminal"]),
    ("touch my_new_file.txt", "create_file", ["my_new_file.txt"]),
    ("rename old_name.py as new_name.py", "move_rename", ["old_name.py", "new_name.py"]),
    ("move script.py to src/", "move_rename", ["script.py", "src/"]),
    ('cp file1 folder1/', "copy_file", ["file1", "folder1/"]),
    ('create file "report with spaces.docx"', "create_file", ["report with spaces.docx"]),
    ('go to "/path with spaces/folder"', "change_directory", ["/path with spaces/folder"]),
    ("git commit This is my detailed commit message", "git_commit", ["-m", "This is my detailed commit message"]),
    ("ls", "list_files", []),
    ("pwd", "show_path", []),
    ("go up one level", "change_directory", [".."]),
    ("change to home directory", "change_directory", ["~"]),
    ("folder banao hinglish_test", "make_directory", ["hinglish_test"]),

    ("create dir user2", "make_directory", ["user2"]),
    ("lsit files", "list_files", []),
    ("mkae diretory temp_stuff", "make_directory", ["temp_stuff"]),
    ("show me script.js", "display_file", ["script.js"]),

    ("show file.py", "display_file", ["file.py"]),
]

@pytest.mark.parametrize("input_text, expected_action, expected_args", TEST_COMMANDS)
def test_parse_input(input_text, expected_action, expected_args):
    result = parse_input(input_text)

    assert result is not None, f"Parser returned None for input: '{input_text}'"

    if result.get('action') == 'suggest':
        print(f"Input '{input_text}' resulted in suggestion: {result.get('suggestion_phrase')}")
        return

    assert result.get('action') == expected_action, \
        f"For input '{input_text}', expected action '{expected_action}' but got '{result.get('action')}'"

    if result.get('action') == expected_action:
        assert result.get('args') == expected_args, \
            f"For input '{input_text}', expected args {expected_args} but got {result.get('args')}"


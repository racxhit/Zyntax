"""
File: parser.py
Description: Contains functions to parse natural language inputs and convert them
             into structured command representations (intents and targets).
             Includes entity extraction, filtering, and argument refinement.
Date Created: 05-04-2025
Last Updated: 13-04-2025
"""

import re
import spacy
from rapidfuzz import process, fuzz
from spacy.lang.en.stop_words import STOP_WORDS
import traceback
import os

# --- Configuration ---
FUZZY_MATCH_THRESHOLD_EXECUTE = 90
FUZZY_MATCH_THRESHOLD_SUGGEST = 65
ENTITY_FILTER_FUZZY_THRESHOLD = 85

# --- Load spaCy Model ---
try:
    nlp = spacy.load("en_core_web_sm", disable=['ner'])
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm", disable=['ner'])

# --- Define Known Actions and Mappings ---
ACTION_KEYWORDS = {
    # File/Directory Listing & Navigation
    "list files": "list_files", "show files": "list_files", "ls": "list_files",
    "display files": "list_files", "contents of": "list_files",
    "what files are": "list_files", "list all": "list_files",
    "show directory contents": "list_files",

    "show current directory": "show_path", "current directory": "show_path",
    "where am i": "show_path", "print working directory": "show_path", "pwd": "show_path",
    "what's the path": "show_path", "tell me the current folder": "show_path",

    "change directory": "change_directory", "move to directory": "change_directory",
    "go to directory": "change_directory", "cd": "change_directory",
    "change dir to": "change_directory", "change directory to": "change_directory",
    "go into": "change_directory", "enter the directory": "change_directory",
    "change my location to": "change_directory", "move to": "change_directory",
    "go up one level": "change_directory", "go back": "change_directory",

    # Directory Creation/Deletion
    "make folder": "make_directory", "create folder": "make_directory",
    "make directory": "make_directory", "create directory": "make_directory",
    "mkdir": "make_directory", "make dir": "make_directory", "create dir": "make_directory",
    "generate directory": "make_directory", "new folder": "make_directory",

    "delete folder": "delete_directory", "remove folder": "delete_directory",
    "delete directory": "delete_directory", "remove directory": "delete_directory",
    "delete dir": "delete_directory", "remove dir": "delete_directory", "rmdir": "delete_directory",
    "get rid of folder": "delete_directory", "get rid of directory": "delete_directory",

    # File Creation/Deletion
    "create file": "create_file", "make file": "create_file",
    "touch file": "create_file", "new file": "create_file",
    "touch": "create_file", "generate empty file": "create_file",

    "delete file": "delete_file", "remove file": "delete_file", "rm": "delete_file",
    "get rid of file": "delete_file", "get rid of": "delete_file",

    # File Operations
    "display file": "display_file", "display file content": "display_file",
    "show file content": "display_file", "cat file": "display_file", "view file": "display_file",
    "cat": "display_file", "view": "display_file",
    "show me": "display_file", "print file": "display_file",

    "rename file": "move_rename", "move file": "move_rename", "mv": "move_rename",
    "rename": "move_rename", "move": "move_rename",
    "change name of": "move_rename",

    "copy file": "copy_file", "cp": "copy_file",
    "duplicate file": "copy_file", "make copy": "copy_file",
    "copy": "copy_file",

    # System Info
    "who am i": "whoami", "whoami": "whoami",
    "who is the current user": "whoami",

    # Git Commands
    "git status": "git_status", "check git status": "git_status",
    "initialize git": "git_init", "git init": "git_init",
    "commit changes": "git_commit", "git commit": "git_commit",

    # System Monitoring
    "show processes": "show_processes", "list processes": "show_processes", "ps": "show_processes",
    "list running processes": "show_processes",

    "disk usage": "disk_usage", "show disk space": "disk_usage", "df": "disk_usage",
    "how much disk space": "disk_usage",

    "memory usage": "memory_usage", "show memory": "memory_usage", "free": "memory_usage",
    "check system memory": "memory_usage",
}


def extract_relevant_entities(doc, text):
    """
    Extracts potential arguments (filenames, paths, etc.) using primarily
    Regex for paths/quotes and spaCy POS tagging for nouns/proper nouns,
    followed by filtering. (Simplified strategy).
    """
    potential_entities = []
    processed_indices = set()

    # --- Strategy 1: Regex for Paths and Quoted Strings (High Priority) ---
    path_pattern = r"([\"'])(.+?)\1|((?:~|\.\.|\.)?/(?:[a-zA-Z0-9_./ -]|\\ )+/?)|([a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+)|(\.\.)|([a-zA-Z0-9_-]+[/\\].*)"
    for match in re.finditer(path_pattern, text):
         entity = match.group(2) or match.group(3) or match.group(4) or match.group(5) or match.group(6)
         if entity:
             entity = entity.strip()
             start, end = match.span()
             # Avoid adding duplicates or simple substrings of already found entities
             is_substring = any(entity in p_entity or p_entity in entity for p_entity in potential_entities if len(p_entity) > len(entity))
             if not any(entity == p_entity for p_entity in potential_entities) and not is_substring:
                  potential_entities.append(entity)
                  processed_indices.update(range(start, end)) # Mark indices as covered


    # --- Strategy 2: spaCy POS Tagging Fallback ---
    # Looks for Nouns, Proper Nouns, Numerals, or 'X' (often paths/symbols)
    likely_entity_tags = {"NOUN", "PROPN", "X", "NUM"}
    # Defined words to generally ignore even if they have the right POS tag
    common_verbs_etc = {'ls', 'cd', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'ps', 'df', 'free', 'git', 'cat', 'touch', 'view', 'rmdir', 'go', 'enter', 'navigate', 'display', 'check', 'initialize', 'commit', 'generate', 'remove', 'get', 'rid', 'tell', 'print', 'duplicate', 'copy', 'make', 'show', 'list', 'change', 'move', 'rename', 'delete', 'file', 'folder', 'directory', 'dir', 'named', 'called', 'with', 'name', 'to', 'from', 'a', 'the', 'in', 'on', 'at', 'me', 'my', 'please', 'using', 'via', 'of', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up', 'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is', 'are', 'system', 'location', 'arguments'} | STOP_WORDS

    for token in doc:
        # Skip if processed by regex, punctuation, or a common non-entity word
        if token.i in processed_indices or token.is_punct or token.lower_ in common_verbs_etc:
            continue

        if token.pos_ in likely_entity_tags:
            # Basic compound handling: checks if previous token modifies this one
            entity_text = token.text
            if token.i > 0 and doc[token.i - 1].dep_ == "compound" and doc[token.i - 1].head == token:
                 # Checks if previous token should also be ignored
                 if doc[token.i - 1].lower_ not in common_verbs_etc and (token.i - 1) not in processed_indices:
                      entity_text = doc[token.i - 1].text + " " + token.text
                      processed_indices.add(token.i - 1) # Mark compound prefix as used

            # Avoid duplicates or words already matched by regex
            if not any(entity_text in p_entity for p_entity in potential_entities):
                 potential_entities.append(entity_text)
            processed_indices.add(token.i) # Marks current token as used


    # --- Strategy 3: Filtering (Mainly for fuzzy check now) ---
    # Final filtering step using fuzzy match with keyword list
    filtered_entities = []
    fuzzy_check_list = ['folder', 'directory', 'file', 'delete', 'create', 'rename', 'move', 'process', 'memory', 'disk', 'status', 'commit', 'list', 'show', 'change', 'copy', 'git'] # Shorter list of core concepts

    for entity in potential_entities:
        entity_lower = entity.lower()
        is_fuzzy_keyword = False
        for keyword in fuzzy_check_list:
            if fuzz.ratio(entity_lower, keyword) > ENTITY_FILTER_FUZZY_THRESHOLD:
                 # Adds exceptions: allow things that look like filenames/paths even if similar
                 is_path_like = '/' in entity or '\\' in entity or entity in ['.', '..']
                 has_extension = '.' in entity and not entity.startswith('.')
                 # Allows if it looks like a path or filename, unless it's an exact match to a short keyword
                 allow_anyway = (is_path_like or has_extension) and entity_lower not in ['ls','cd','rm','cp','mv','ps','df']

                 if not allow_anyway:
                      is_fuzzy_keyword = True
                      print(f"Debug: Filtered entity '{entity}' as it's too similar to keyword/verb '{keyword}' (Score > {ENTITY_FILTER_FUZZY_THRESHOLD})")
                      break
        if is_fuzzy_keyword:
            continue

        filtered_entities.append(entity)

    # Removes duplicates
    seen = set()
    unique_entities = [x for x in filtered_entities if not (x in seen or seen.add(x))]
    print(f"Debug: Extracted entities (final): {unique_entities}")
    return unique_entities


def parse_input(text):
    """
    Parses natural language input into a structured command dictionary
    containing 'action' and 'args'. Handles direct commands, fuzzy matching,
    suggestions, heuristics, and argument refinement.
    """
    try:
        original_text = text
        text_lower = text.lower().strip()
        if not text_lower:
            return None

        action_id = None
        args = [] # Arguments extracted initially
        parsed_args = [] # Final arguments after refinement
        suggestion_action_id = None
        suggestion_phrase = None
        match_result = None
        score = 0
        matched_direct = False

        # --- 0. Direct Command Check ---
        # Check for common commands at the start of the input
        direct_commands = {
            'cd ': 'change_directory', 'ls': 'list_files', 'pwd': 'show_path',
            'rm ': 'delete_file', 'rmdir ': 'delete_directory', 'mkdir ': 'make_directory',
            'mv ': 'move_rename', 'cp ': 'copy_file', 'cat ': 'display_file',
            'touch ': 'create_file', 'whoami': 'whoami', 'df': 'disk_usage',
            'free': 'memory_usage', 'ps': 'show_processes', 'git status': 'git_status',
            'git init': 'git_init', 'git commit': 'git_commit' # Needs arg check later
        }
        for cmd_prefix, mapped_action in direct_commands.items():
            if text_lower.startswith(cmd_prefix):
                # Exact match for commands without trailing space
                if not cmd_prefix.endswith(' ') and text_lower != cmd_prefix:
                    continue
                print(f"Debug: Direct command prefix match for '{cmd_prefix}'")
                action_id = mapped_action
                # Crude extraction of remainder - will be refined by extract_relevant_entities
                arg_string = original_text[len(cmd_prefix):].strip()
                # Store crude args temporarily if needed, but rely on full extraction
                matched_direct = True
                break

        # --- 1. Intent Recognition (Fuzzy Match - Only if no direct match) ---
        if not matched_direct:
            match_result = process.extractOne(
                text_lower, ACTION_KEYWORDS.keys(),
                scorer=fuzz.WRatio, score_cutoff=FUZZY_MATCH_THRESHOLD_SUGGEST
            )
            if match_result:
                matched_phrase, score, _ = match_result
                print(f"Debug: Fuzzy match: phrase='{matched_phrase}', score={score}")
                if score >= FUZZY_MATCH_THRESHOLD_EXECUTE:
                    action_id = ACTION_KEYWORDS[matched_phrase]
                    print(f"Debug: Matched action '{action_id}' via fuzzy.")
                elif score >= FUZZY_MATCH_THRESHOLD_SUGGEST:
                    suggestion_action_id = ACTION_KEYWORDS[matched_phrase]
                    suggestion_phrase = matched_phrase
                    print(f"Debug: Potential suggestion: action='{suggestion_action_id}' (phrase='{suggestion_phrase}')")

        # --- Preliminary Action Check & Entity Extraction ---
        # Determine the best guess for action ID before applying heuristics
        best_guess_action_id = action_id if action_id else suggestion_action_id

        if best_guess_action_id is None:
            print(f"Debug: No good match found for '{text_lower}'")
            return {'action': 'unrecognized'}

        # Runs entity extraction always now
        doc = nlp(original_text)
        args = extract_relevant_entities(doc, original_text)
        print(f"Debug: Args before refinement: {args}")

        # --- 3. Heuristics & Action Overrides ---
        # Heuristic for 'show file.py' vs 'show files'
        if best_guess_action_id in ['list_files', 'show_path'] and len(args) == 1:
            filename_pattern = r"\.[a-zA-Z0-9]+$"
            arg_check = args[0]
            if (re.search(filename_pattern, arg_check) or '.' in arg_check) and arg_check not in ['.', '..']:
                print(f"Debug: Heuristic override! Best guess '{best_guess_action_id}' changed to 'display_file' due to filename arg '{arg_check}'.")
                action_id = 'display_file' # Force direct execution
                suggestion_action_id = None # Cancel any suggestion

        # --- Handle Suggestion (if no direct action_id after heuristics) ---
        if action_id is None and suggestion_action_id is not None:
             return {'action': 'suggest',
                    'suggestion_action_id': suggestion_action_id,
                    'suggestion_phrase': suggestion_phrase}
        elif action_id is None: # No match or suggestion left after heuristic
             print(f"Debug: No action identified for '{text_lower}' after all checks.")
             return {'action': 'unrecognized'}

        # --- If we have a definite final action_id ---

        # --- Apply other heuristics based on final action_id ---
        if action_id == 'change_directory':
            if "up one level" in text_lower or "go back" in text_lower:
                 print("Debug: Heuristic: Interpreted 'go up/back' as 'cd ..'")
                 args = ['..'] # Override args

        # --- 4. Argument Refinement based on Final Action ---
        parsed_args = []
        if action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file']:
            if args: parsed_args = [args[0]]
            else: print(f"Warning: Action '{action_id}' requires an argument."); parsed_args = []

        elif action_id == 'change_directory':
             if args:
                  if args[0].lower() == 'home' or args[0] == '~': parsed_args = ['~']
                  elif args[0] == '..': parsed_args = ['..'] # Handle heuristic override
                  else: parsed_args = [args[0]]
             else: parsed_args = [] # 'cd' with no args

        elif action_id == 'move_rename' or action_id == 'copy_file':
            # Reset source/dest determination
            source, destination = None, None
            if len(args) >= 2:
                keywords = ['to', 'as', 'into']
                split_found = False
                # Find the last keyword BETWEEN potential args
                for i in range(len(args) - 2, 0, -1):
                    if args[i].lower() in keywords:
                         source = " ".join(args[:i]); destination = " ".join(args[i+1:]); split_found = True
                         print(f"Debug: Split mv/cp args by keyword '{args[i]}': S='{source}', D='{destination}'"); break
                if not split_found: # Assume order if no keyword
                    source = args[0]; destination = " ".join(args[1:]) # Handle spaces in dest
                    print(f"Debug: Split mv/cp args by position: S='{source}', D='{destination}'")
                if source and destination: parsed_args = [source, destination]
                else: # Fallback if something went wrong
                     print(f"Warning: Could not determine source/destination for '{action_id}'. Using first two args: {args}"); parsed_args = args[:2]
            elif len(args) == 1: print(f"Warning: '{action_id}' requires source and destination. Only one provided: {args}"); return {'action': 'error', 'message': f"Missing destination argument for {action_id}"}
            else: print(f"Warning: '{action_id}' requires source and destination. None provided."); return {'action': 'error', 'message': f"Missing arguments for {action_id}"}

        elif action_id == 'git_commit':
            msg_match = re.search(r"(?:-m|message)\s+([\"'])(.+?)\1", original_text, re.IGNORECASE)
            if msg_match:
                parsed_args = ["-m", msg_match.group(2)]
            else: # Fallback logic
                fallback_msg = ""
                # Use text after the identified action phrase (either direct or fuzzy)
                phrase_to_find = cmd_prefix if matched_direct else (matched_phrase if match_result else None)
                if phrase_to_find:
                     try:
                         phrase_lower = phrase_to_find.lower()
                         indices = [m.start() for m in re.finditer(re.escape(phrase_lower), text_lower)]
                         if indices: start_index = indices[-1] + len(phrase_to_find); fallback_msg = original_text[start_index:].strip().strip("'\"")
                     except Exception as e: print(f"Debug: Error finding fallback commit msg: {e}")

                if fallback_msg:
                     print(f"Warning: Commit message flag not found. Using text after command: '{fallback_msg}'")
                     parsed_args = ["-m", fallback_msg]
                else:
                     print("Error: Commit message required via -m '...' or after command.")
                     return {'action': 'error', 'message': 'Commit message required'}

        # Commands that take no arguments
        elif action_id in ['list_files', 'show_path', 'whoami', 'git_status', 'git_init', 'show_processes', 'disk_usage', 'memory_usage']:
             if args: print(f"Debug: Action '{action_id}' doesn't take arguments, ignoring extracted: {args}")
             parsed_args = []
        else: # Default passthrough if action not handled above
             parsed_args = args
             if args: print(f"Debug: Passing arguments {args} to unhandled action '{action_id}'")

        # --- 5. Return Structured Command ---
        return {
            'action': action_id,
            'args': parsed_args
        }

    except Exception as e:
         print(f"❌❌❌ PARSER FUNCTION CRASHED! ❌❌❌")
         print(f"Input Text: '{text}'")
         print(f"Error Type: {type(e).__name__}")
         print(f"Error Details: {e}")
         print("Traceback:")
         traceback.print_exc()
         return {'action': 'error', 'message': f'Internal parser error: {type(e).__name__}'}
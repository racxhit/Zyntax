"""
File: parser.py
Description: Contains functions to parse natural language inputs and convert them
             into structured command representations (intents and targets).
             Includes entity extraction, filtering, and argument refinement.
Date Created: 05-04-2025
Last Updated: 17-05-2025
"""

import re
import spacy
from rapidfuzz import process, fuzz
from spacy.lang.en.stop_words import STOP_WORDS
import traceback
import shlex
import os

# Configuration
FUZZY_MATCH_THRESHOLD_EXECUTE = 90
FUZZY_MATCH_THRESHOLD_SUGGEST = 65
ENTITY_FILTER_FUZZY_THRESHOLD = 87

# Load spaCy Model
try:
    nlp = spacy.load("en_core_web_sm", disable=['ner'])
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm", disable=['ner'])

# Known Actions and Mappings
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

ENTITY_IGNORE_WORDS = (
    STOP_WORDS |
    # Common command verbs/keywords that are unlikely to be arguments themselves
    # crucial for filtering noun chunks and final entities
    {'ls', 'cd', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'ps', 'df', 'free', 'git',
     'cat', 'touch', 'view', 'rmdir', 'dir', 'md', 'del', 'rd', 'copy', 'move', 'ren',
     'go', 'enter', 'navigate', 'display', 'check', 'initialize', 'commit',
     'generate', 'remove', 'get', 'rid', 'tell', 'print', 'duplicate',
     'make', 'show', 'list', 'change', 'delete',
     'file', 'folder', 'directory', 'named', 'called', 'with', 'name', # 'name' can be tricky
     'to', 'from', 'a', 'the', 'in', 'on', 'at', 'me', 'my', 'please', 'using',
     'via', 'of', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up',
     'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is',
     'are', 'system', 'location', 'arguments', 'mein', 'karo', 'dikhao', 'batao',

     # Hinglish stopwords
     "ko", "mein", "se", "ka", "ki", "ke", "hai", "hoon", "ho", "kya", "mera", "meri", "mere",
     "batao", "dikhao", "karo", "dekho", "banao", "hatao", "badlo", "kaun", "kitna", "kitni",
     "jao", "aao", "sabhi", "sab", "ek", "agar", "toh", "phir", "yeh", "woh", "aur", "bhi",
     "abhi", "wala", "wali", "naya", "nayi", "naye", "kuch", "thoda", "pura", "sirf", "bas"}
)

def extract_relevant_entities(doc, text):
    """
    Extracts potential arguments using a layered approach:
    1. Regex for explicit paths and quoted strings.
    2. spaCy noun chunks for remaining parts of the text, with stricter filtering.
    3. Final filtering.
    """
    entities_with_spans = []
    processed_char_indices = [False] * len(text)

    def mark_processed(start, end):
        for i in range(start, end):
            if 0 <= i < len(processed_char_indices): processed_char_indices[i] = True

    # Strategy 1: Regex for Paths and Quoted Strings
    path_pattern = r"([\"'])(.+?)\1|((?:~|\.\.|\.)?/(?:[a-zA-Z0-9_./\- ]|\\ )+/?)|([a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+)|(\.\.)|([a-zA-Z0-9_-]+(?:[/\\].*)?)"
    for match in re.finditer(path_pattern, text):
        entity_text = match.group(2) or match.group(3) or match.group(4) or match.group(5) or match.group(6)
        if entity_text:
            entity_text = entity_text.strip()
            start, end = match.span()
            is_overlapping = any(max(start, ps_start) < min(end, ps_end) for _, (ps_start, ps_end) in entities_with_spans)
            if not is_overlapping:
                entities_with_spans.append((entity_text, (start, end)))
                mark_processed(start, end)

    # Strategy 2: spaCy Noun Chunks for Remaining Text
    for chunk in doc.noun_chunks:
        chunk_start, chunk_end = chunk.start_char, chunk.end_char
        covered_chars = sum(1 for i in range(chunk_start, chunk_end) if processed_char_indices[i])
        if covered_chars > len(chunk.text) * 0.75: # If > 75% covered, likely already handled
            continue

        chunk_text = chunk.text.strip()
        # Stricter filtering for noun chunks:
        words_in_chunk = chunk_text.lower().split()
        # Ignore if empty, all words are ignore words, or if it's a single word that's an ignore word
        if not chunk_text or \
           all(word in ENTITY_IGNORE_WORDS for word in words_in_chunk) or \
           (len(words_in_chunk) == 1 and words_in_chunk[0] in ENTITY_IGNORE_WORDS):
            print(f"Debug EntityExtract: Ignoring noun chunk '{chunk_text}' (all ignore words).")
            continue

        # Further filter: if the chunk contains critical command verbs, it's likely not an entity
        # unless it also looks like a path or filename.
        critical_verbs = {'make', 'create', 'delete', 'remove', 'show', 'list', 'change', 'move', 'rename', 'copy', 'display', 'cat', 'view', 'touch', 'cd', 'mkdir', 'rm', 'cp', 'mv'}
        contains_critical_verb = any(verb in words_in_chunk for verb in critical_verbs)
        looks_like_path_or_file = any(char in chunk_text for char in './\\') or any(chunk_text.endswith(ext) for ext in ['.txt', '.py', '.js', '.md', '.csv', '.json', '.docx'])

        if contains_critical_verb and not looks_like_path_or_file:
            print(f"Debug EntityExtract: Ignoring noun chunk '{chunk_text}' (contains critical verb, not path/file).")
            continue

        # Refined check to avoid adding if it's a substring of an existing regex-found entity
        is_substring_of_regex_entity = any(
            (chunk_text.lower() in regex_entity_text.lower() or regex_entity_text.lower() in chunk_text.lower()) and \
            (len(regex_entity_text) > len(chunk_text) or len(chunk_text) > len(regex_entity_text)) # Ensure not identical
            for regex_entity_text, _ in entities_with_spans
        )
        if is_substring_of_regex_entity:
            print(f"Debug EntityExtract: Ignoring noun chunk '{chunk_text}' as substring of regex entity.")
            continue

        if any(chunk_text == regex_entity_text for regex_entity_text, _ in entities_with_spans):
            continue # Already added by regex

        entities_with_spans.append((chunk_text, (chunk_start, chunk_end)))
        mark_processed(chunk_start, chunk_end)

    entities_with_spans.sort(key=lambda x: x[1][0])
    current_entities_text = [entity_tuple[0] for entity_tuple in entities_with_spans]

    # Strategy 3: Final Filtering
    final_filtered_entities = []
    fuzzy_check_list = ['folder', 'directory', 'file', 'delete', 'create', 'rename', 'move', 'list', 'show', 'change', 'copy', 'git', 'status', 'commit', 'process', 'memory', 'disk']

    for entity in current_entities_text:
        entity_lower = entity.lower()
        # Exact match short command verbs (if they slipped through)
        if entity_lower in {'ls', 'cd', 'rm', 'cp', 'mv', 'ps', 'df', 'cat', 'pwd', 'touch', 'mkdir', 'git'}:
             if not ('.' in entity or '/' in entity or '\\' in entity or entity in ['..','~']):
                  print(f"Debug EntityExtract: Final filter for exact short command: '{entity}'")
                  continue

        is_fuzzy_keyword = False
        for keyword in fuzzy_check_list:
            if fuzz.ratio(entity_lower, keyword) > ENTITY_FILTER_FUZZY_THRESHOLD:
                 looks_like_arg = (any(char.isdigit() for char in entity) or
                                  '/' in entity or '\\' in entity or
                                  '.' in entity or entity in ['..', '~'])

                 if looks_like_arg and len(entity) > 1 :
                      if len(entity) <= 3 and fuzz.ratio(entity_lower, keyword) > 92 and not (looks_like_arg and '.' in entity):
                           is_fuzzy_keyword = True; print(f"Debug EntityExtract: Filtered (fuzzy) very short entity '{entity}' similar to '{keyword}'"); break
                 elif not looks_like_arg:
                      is_fuzzy_keyword = True; print(f"Debug EntityExtract: Filtered (fuzzy) entity '{entity}' similar to '{keyword}' (Score > {ENTITY_FILTER_FUZZY_THRESHOLD})"); break
        if is_fuzzy_keyword: continue
        final_filtered_entities.append(entity)

    seen = set()
    unique_entities = [x for x in final_filtered_entities if not (x in seen or seen.add(x))]
    print(f"Debug: Extracted entities (final): {unique_entities}")
    return unique_entities


def select_primary_argument(args_list):
    """
    From a list of extracted entities, select the most likely primary argument.
    Prefers longer entities, those not in ignore list, or the last one.
    """
    if not args_list:
        return None

    # Filter out any remaining common command verbs/stopwords explicitly
    # This is a stricter version of ENTITY_IGNORE_WORDS for final selection
    strict_ignore = {'make', 'create', 'delete', 'remove', 'show', 'list', 'change', 'move', 'rename', 'copy', 'display', 'cat', 'view', 'touch', 'cd', 'mkdir', 'rm', 'cp', 'mv', 'git', 'go', 'enter', 'navigate', 'get', 'rid', 'tell', 'print', 'duplicate', 'file', 'folder', 'directory', 'dir', 'named', 'called', 'with', 'name', 'to', 'from', 'a', 'the', 'in', 'on', 'at', 'me', 'my', 'please', 'using', 'via', 'of', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up', 'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is', 'are', 'system', 'location', 'arguments'} | STOP_WORDS

    # Prefer entities that look like paths/filenames or are longer
    best_arg = None
    max_score = -1

    for arg in reversed(args_list): # Iterate from the end
        if arg.lower() in strict_ignore and not ('.' in arg or '/' in arg or '\\' in arg or arg in ['..', '~']):
            continue # Skip if it's a stopword unless it looks like a path/file

        score = len(arg) # Simple score: length
        if '.' in arg or '/' in arg or '\\' in arg or any(char.isdigit() for char in arg):
            score += 10 # Boost score for path/file-like features

        if score > max_score:
            max_score = score
            best_arg = arg

    if best_arg:
        return best_arg

    # Fallback if all were filtered (rare)
    return args_list[-1] if args_list else None


def parse_input(text):
    """
    Parses natural language input (Eng/Hinglish) into a structured command dictionary.
    """
    try:
        original_text = text
        text_lower = text.lower().strip()
        if not text_lower: return None

        action_id, initial_args, parsed_args = None, [], []
        suggestion_action_id, suggestion_phrase = None, None
        match_result, score, matched_direct = None, 0, False
        cmd_prefix_for_fallback_msg = ""

        # 0. Direct Command Check
        direct_commands = {
            'cd ': 'change_directory', 'ls': 'list_files', 'pwd': 'show_path',
            'rm ': 'delete_file', 'rmdir ': 'delete_directory', 'mkdir ': 'make_directory',
            'mv ': 'move_rename', 'cp ': 'copy_file', 'cat ': 'display_file',
            'touch ': 'create_file', 'whoami': 'whoami', 'df': 'disk_usage',
            'free': 'memory_usage', 'ps': 'show_processes', 'git status': 'git_status',
            'git init': 'git_init', 'git commit ': 'git_commit'
        }
        for cmd_prefix, mapped_action in direct_commands.items():
            if text_lower.startswith(cmd_prefix):
                if not cmd_prefix.endswith(' ') and text_lower != cmd_prefix: continue
                print(f"Debug: Direct command prefix match for '{cmd_prefix}'")
                action_id = mapped_action
                arg_string_direct = original_text[len(cmd_prefix):].strip()
                # For direct commands, pass the whole arg string as a single item for now
                # extract_relevant_entities will try to split it more intelligently if needed for mv/cp
                initial_args = [arg_string_direct] if arg_string_direct else []
                matched_direct = True
                if action_id == 'git_commit': cmd_prefix_for_fallback_msg = cmd_prefix.strip()
                break

        # 1. Intent Recognition (Fuzzy Match - Only if no direct match)
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

        # Determine Best Guess Action & Extract Entities
        current_action_guess = action_id if action_id else suggestion_action_id
        if current_action_guess is None:
            print(f"Debug: No good match found for '{text_lower}'")
            return {'action': 'unrecognized'}

        doc = nlp(original_text)
        # If direct match had initial_args, use them as primary input for entity extraction
        # Otherwise, use the full original text.
        text_to_extract_from = initial_args[0] if matched_direct and initial_args else original_text
        doc_for_extraction = nlp(text_to_extract_from) # Process relevant part

        args = extract_relevant_entities(doc_for_extraction, text_to_extract_from)
        # If direct match and args are empty after extraction, but arg_string_direct was not,
        # it means extraction filtered everything. Fallback to shlex for direct.
        if matched_direct and arg_string_direct and not args:
            try:
                args = shlex.split(arg_string_direct)
                print(f"Debug: Using shlex-split args for direct match as fallback: {args}")
            except ValueError: # Handle empty string or other shlex errors
                args = [arg_string_direct] if arg_string_direct else []


        print(f"Debug: Args after extraction, before refinement: {args}")

        # 3. Heuristics & Action Overrides (Applied to current_action_guess)
        if current_action_guess in ['list_files', 'show_path'] and len(args) == 1:
            filename_pattern = r"\.[a-zA-Z0-9]+$"
            arg_check = args[0]
            if (re.search(filename_pattern, arg_check) or '.' in arg_check) and arg_check not in ['.', '..']:
                print(f"Debug: Heuristic override! Action '{current_action_guess}' changed to 'display_file' due to filename arg '{arg_check}'.")
                action_id = 'display_file'; suggestion_action_id = None; suggestion_phrase = None

        if action_id is None:
            if suggestion_action_id is not None:
                return {'action': 'suggest', 'suggestion_action_id': suggestion_action_id, 'suggestion_phrase': suggestion_phrase}
            else:
                 print(f"Debug: No action identified for '{text_lower}' after all checks.")
                 return {'action': 'unrecognized'}

        # If we have a definite final action_id
        if action_id == 'change_directory':
            if any(phrase in text_lower for phrase in ["up one level", "go back", "ek level peeche jao", "wapas jao"]):
                 print("Debug: Heuristic: Interpreted 'go up/back' as 'cd ..'"); args = ['..']

        # 4. Argument Refinement based on Final Action
        parsed_args = []
        if action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file']:
            selected_arg = select_primary_argument(args)
            if selected_arg: parsed_args = [selected_arg]
            else: print(f"Warning: Action '{action_id}' requires an argument, none suitable in {args}."); parsed_args = []

        elif action_id == 'change_directory':
             if args:
                  chosen_arg = None
                  home_path_variants = {'home', '~', 'ghar'}
                  actual_home = os.path.expanduser("~")
                  for arg_val in args: # Search all extracted args
                      if arg_val.lower() in home_path_variants or arg_val == actual_home:
                          chosen_arg = '~'; break
                      if arg_val == '..':
                          chosen_arg = '..'; break
                  if chosen_arg: parsed_args = [chosen_arg]
                  else: parsed_args = [args[0]] # Default to first if no special case
             else: parsed_args = []

        elif action_id == 'move_rename' or action_id == 'copy_file':
            source, destination = None, None
            # Try to use shlex if it's a direct command and args were not split well by extract_entities
            if matched_direct and arg_string_direct and len(args) < 2:
                try: args = shlex.split(arg_string_direct)
                except: pass # Keep original args if shlex fails

            if len(args) >= 2:
                keywords = ['to', 'as', 'into', 'se', 'ko', 'mein']
                split_found = False
                for i in range(len(args) - 2, 0, -1):
                    if args[i].lower() in keywords:
                         source = " ".join(args[:i]); destination = " ".join(args[i+1:])
                         split_found = True; print(f"Debug: Split mv/cp args by keyword '{args[i]}': S='{source}', D='{destination}'"); break
                if not split_found:
                    source = args[0]; destination = " ".join(args[1:])
                    print(f"Debug: Split mv/cp args by position: S='{source}', D='{destination}'")
                if source and destination: parsed_args = [source, destination]
                else: print(f"Warning: Could not determine S/D for '{action_id}'. Args: {args}"); parsed_args = args[:2] if len(args) >=2 else args
            elif len(args) == 1: print(f"Warning: '{action_id}' requires S/D. Only one arg: {args}"); return {'action': 'error', 'message': f"Missing destination for {action_id}"}
            else: print(f"Warning: '{action_id}' requires S/D. None provided."); return {'action': 'error', 'message': f"Missing args for {action_id}"}

        elif action_id == 'git_commit':
            msg_match = re.search(r"(?:-m|message)\s+([\"'])(.+?)\1", original_text, re.IGNORECASE)
            if msg_match:
                parsed_args = ["-m", msg_match.group(2)]
            else:
                fallback_msg = ""
                phrase_that_matched = cmd_prefix_for_fallback_msg if matched_direct and cmd_prefix_for_fallback_msg else (matched_phrase if match_result else None)
                if phrase_that_matched:
                     try:
                         phrase_lower = phrase_that_matched.lower()
                         indices = [m.start() for m in re.finditer(re.escape(phrase_lower), text_lower)]
                         if indices: start_index = indices[-1] + len(phrase_that_matched); fallback_msg = original_text[start_index:].strip().strip("'\"")
                     except Exception as e: print(f"Debug: Error finding fallback commit msg: {e}")

                if fallback_msg:
                     print(f"Warning: Commit message flag not found. Using text after command: '{fallback_msg}'")
                     parsed_args = ["-m", fallback_msg]
                elif args and not (matched_direct and arg_string_direct): # If fuzzy matched and args remain (not from direct)
                    fallback_msg = " ".join(args)
                    print(f"Warning: Commit message flag not found. Using remaining extracted args: '{fallback_msg}'")
                    parsed_args = ["-m", fallback_msg]
                else:
                     print("Error: Commit message required via -m '...' or after command."); return {'action': 'error', 'message': 'Commit message required'}

        elif action_id in ['list_files', 'show_path', 'whoami', 'git_status', 'git_init', 'show_processes', 'disk_usage', 'memory_usage']:
             if args: print(f"Debug: Action '{action_id}' doesn't take arguments, ignoring extracted: {args}")
             parsed_args = []
        else:
             parsed_args = args
             if args: print(f"Debug: Passing arguments {args} to unhandled action '{action_id}'")

        # 5. Return Structured Command
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

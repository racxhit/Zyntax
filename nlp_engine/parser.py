"""
File: parser.py
Description: Contains functions to parse natural language inputs and convert them
             into structured command representations (intents and targets).
             Includes entity extraction, filtering, argument refinement, and pipelining.
Date Created: 05-04-2025
Last Updated: 19-05-2025 # Refactor 27: NL Pipe Entity Fix
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
ENTITY_FILTER_FUZZY_THRESHOLD = 88

# Load spaCy Model
try:
    nlp = spacy.load("en_core_web_sm", disable=['ner'])
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm", disable=['ner'])

# Define Known Actions and Mappings
ACTION_KEYWORDS = {
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

    "make folder": "make_directory", "create folder": "make_directory",
    "make directory": "make_directory", "create directory": "make_directory",
    "mkdir": "make_directory", "make dir": "make_directory", "create dir": "make_directory",
    "generate directory": "make_directory", "new folder": "make_directory",

    "delete folder": "delete_directory", "remove folder": "delete_directory",
    "delete directory": "delete_directory", "remove directory": "delete_directory",
    "delete dir": "delete_directory", "remove dir": "delete_directory", "rmdir": "delete_directory",
    "get rid of folder": "delete_directory", "get rid of directory": "delete_directory",

    "create file": "create_file", "make file": "create_file",
    "touch file": "create_file", "new file": "create_file",
    "touch": "create_file", "generate empty file": "create_file",

    "delete file": "delete_file", "remove file": "delete_file", "rm": "delete_file",
    "get rid of file": "delete_file", "get rid of": "delete_file",

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

    "who am i": "whoami", "whoami": "whoami",
    "who is the current user": "whoami",

    "git status": "git_status", "check git status": "git_status",
    "initialize git": "git_init", "git init": "git_init",
    "commit changes": "git_commit", "git commit": "git_commit",

    "show processes": "show_processes", "list processes": "show_processes", "ps": "show_processes",
    "list running processes": "show_processes",

    "disk usage": "disk_usage", "show disk space": "disk_usage", "df": "disk_usage",
    "how much disk space": "disk_usage",

    "memory usage": "memory_usage", "show memory": "memory_usage", "free": "memory_usage",
    "check system memory": "memory_usage",
    "grep": "grep", "find text": "grep", "search for text": "grep", "filter for": "grep",
}

ARG_SPLIT_KEYWORDS = {'to', 'as', 'into', 'se', 'ko', 'mein'}

COMMAND_VERBS = {'ls', 'cd', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'ps', 'df', 'free', 'git', 'cat', 'touch', 'view', 'rmdir', 'dir', 'md', 'del', 'rd', 'copy', 'move', 'ren', 'rename', 'go', 'enter', 'navigate', 'display', 'check', 'initialize', 'commit', 'generate', 'remove', 'get', 'rid', 'tell', 'print', 'duplicate', 'make', 'show', 'list', 'change', 'delete', 'banao', 'dikhao', 'karo', 'hatao', 'badlo', 'jao', 'grep', 'find', 'filter'}

ENTITY_IGNORE_WORDS = (
    STOP_WORDS | COMMAND_VERBS |
    {'file', 'folder', 'directory', 'named', 'called', 'with', 'name',
     'from', 'a', 'the', 'in', 'on', 'at', 'me', 'my', 'please', 'using',
     'via', 'of', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up',
     'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is',
     'are', 'system', 'location', 'arguments', 'mein', 'text'} |
    {"ka", "ki", "ke", "hai", "hoon", "ho", "kya", "mera", "meri", "mere",
     "sabhi", "sab", "ek", "agar", "toh", "phir", "yeh", "woh", "aur", "bhi",
     "abhi", "wala", "wali", "naya", "nayi", "naye", "kuch", "thoda", "pura", "sirf", "bas"}
)
ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING = ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS

NL_PIPE_INDICATORS = [
    r'\s+and then\s+', r'\s+then pipe to\s+', r'\s+pipe to\s+',
    r'\s+piped to\s+', r'\s+and pass to\s+', r'\s+and send output to\s+',
]
NL_PIPE_PATTERN = re.compile("|".join(NL_PIPE_INDICATORS), re.IGNORECASE)


def _is_token_covered(token, processed_char_indices):
    start_idx, end_idx = token.idx, token.idx + len(token.text)
    covered_count = 0
    for i in range(start_idx, end_idx):
        if i < len(processed_char_indices) and processed_char_indices[i]:
            covered_count += 1
    return covered_count > (len(token.text) * 0.5)

def _is_valid_start_of_entity_phrase(token_lower, token_text):
    is_command_verb_strict = token_lower in COMMAND_VERBS and \
                           not (any(c in token_text for c in './\\0123456789') or token_text in ['..', '~'])
    return not is_command_verb_strict and \
           (token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
            any(c in token_text for c in './\\0123456789') or \
            token_text in ['..', '~'] or token_lower in ARG_SPLIT_KEYWORDS)

def _is_valid_continuation_of_entity_phrase(token_lower, token_text):
    if token_lower in ARG_SPLIT_KEYWORDS: return True
    return token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
           any(c in token_text for c in './\\0123456789') or \
           token_text in ['..', '~']

def extract_relevant_entities(doc, text_for_extraction):
    entities_with_spans = []
    processed_char_indices = [False] * len(text_for_extraction)
    doc_tokens = list(doc) # doc is now created from text_for_extraction only

    def mark_processed(start, end):
        for i in range(start, end):
            if 0 <= i < len(processed_char_indices): processed_char_indices[i] = True

    path_pattern = r"([\"'])(.+?)\1|((?:~|\.\.|\.)?/(?:[a-zA-Z0-9_./\- ]|\\ )+/?)|([a-zA-Z0-9_.-]+\.[a-zA-Z0-9_.-]+)|(\.\.)|([a-zA-Z0-9_-]+(?:[/\\].*)?)"
    for match in re.finditer(path_pattern, text_for_extraction):
        entity_text = match.group(2) or match.group(3) or match.group(4) or match.group(5) or match.group(6)
        if entity_text:
            entity_text = entity_text.strip()
            start, end = match.span()
            already_covered_chars = sum(1 for i in range(start,end) if processed_char_indices[i])
            if already_covered_chars < (end - start) * 0.5 and entity_text:
                is_path = '/' in entity_text or '\\' in entity_text or entity_text in ['..', '~']
                already_exists = any((entity_text == et) or (not is_path and entity_text.lower() == et.lower()) for et, _ in entities_with_spans)
                if not already_exists:
                    entities_with_spans.append((entity_text, (start, end)))
                    mark_processed(start, end)

    current_phrase_tokens_text = []
    current_phrase_start_char = -1
    for token in doc_tokens: # doc_tokens are from the specific segment's doc
        is_covered_by_regex = _is_token_covered(token, processed_char_indices)
        if not is_covered_by_regex and not token.is_punct:
            token_lower = token.lower_
            token_text = token.text
            if not current_phrase_tokens_text:
                if _is_valid_start_of_entity_phrase(token_lower, token_text):
                    current_phrase_start_char = token.idx
                    current_phrase_tokens_text.append(token_text)
                else:
                    if token_lower in ENTITY_IGNORE_WORDS: mark_processed(token.idx, token.idx + len(token_text))
            elif _is_valid_continuation_of_entity_phrase(token_lower, token_text):
                current_phrase_tokens_text.append(token_text)
            else:
                if current_phrase_tokens_text:
                    entity_text = " ".join(current_phrase_tokens_text).strip()
                    if entity_text:
                        phrase_end_char = token.idx
                        if not any(entity_text == et for et, _ in entities_with_spans):
                            entities_with_spans.append((entity_text, (current_phrase_start_char, phrase_end_char)))
                            mark_processed(current_phrase_start_char, phrase_end_char)
                    current_phrase_tokens_text = []
                    current_phrase_start_char = -1
                if token_lower in ENTITY_IGNORE_WORDS: mark_processed(token.idx, token.idx + len(token.text))
                elif _is_valid_start_of_entity_phrase(token_lower, token_text):
                    current_phrase_start_char = token.idx
                    current_phrase_tokens_text.append(token_text)
        elif current_phrase_tokens_text:
            entity_text = " ".join(current_phrase_tokens_text).strip()
            if entity_text:
                phrase_end_char = token.idx
                if not any(entity_text == et for et, _ in entities_with_spans):
                    entities_with_spans.append((entity_text, (current_phrase_start_char, phrase_end_char)))
                    mark_processed(current_phrase_start_char, phrase_end_char)
            current_phrase_tokens_text = []
            current_phrase_start_char = -1
            if is_covered_by_regex: mark_processed(token.idx, token.idx + len(token.text))
    if current_phrase_tokens_text:
        entity_text = " ".join(current_phrase_tokens_text).strip()
        if entity_text:
            phrase_end_char = len(text_for_extraction)
            if not any(entity_text == et for et, _ in entities_with_spans):
                 if current_phrase_start_char != -1 :
                    entities_with_spans.append((entity_text, (current_phrase_start_char, phrase_end_char)))
                    mark_processed(current_phrase_start_char, phrase_end_char)

    entities_with_spans.sort(key=lambda x: x[1][0])
    current_entities_text = [entity_tuple[0] for entity_tuple in entities_with_spans if entity_tuple[0]]
    final_filtered_entities = []
    fuzzy_check_list_args = ['folder', 'directory', 'file']
    for entity in current_entities_text:
        entity_lower = entity.lower()
        is_path_like_or_num_or_long = ('.' in entity or '/' in entity or '\\' in entity or entity in ['..','~'] or any(char.isdigit() for char in entity) or len(entity)>3)
        if entity_lower in COMMAND_VERBS and not is_path_like_or_num_or_long and entity_lower not in ARG_SPLIT_KEYWORDS:
            print(f"Debug EntityExtract: Final filter (exact verb): '{entity}'")
            continue
        if entity_lower in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING and not is_path_like_or_num_or_long:
            if not entity.isdigit():
                print(f"Debug EntityExtract: Final filter (exact ignore word): '{entity}'")
                continue
        is_fuzzy_keyword = False
        for keyword in fuzzy_check_list_args:
            if fuzz.ratio(entity_lower, keyword) > ENTITY_FILTER_FUZZY_THRESHOLD + 2:
                 looks_like_arg_f = (any(char.isdigit() for char in entity) or '/' in entity or '\\' in entity or '.' in entity or entity in ['..', '~'])
                 if not looks_like_arg_f:
                      is_fuzzy_keyword = True
                      print(f"Debug EntityExtract: Filtered (fuzzy) non-arg entity '{entity}' similar to '{keyword}'")
                      break
        if is_fuzzy_keyword: continue
        if entity: final_filtered_entities.append(entity)
    seen = set()
    unique_entities = [x for x in final_filtered_entities if not (x in seen or seen.add(x))]
    print(f"Debug: Extracted entities (final): {unique_entities}")
    return unique_entities

def select_primary_argument(args_list, action_id=None):
    if not args_list: return None
    selection_ignore_words = ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS
    candidate_args = [arg for arg in args_list if arg.lower() not in ARG_SPLIT_KEYWORDS]
    if not candidate_args:
        if args_list : print(f"Debug select_primary_argument: Only split keywords found in {args_list}, returning None for primary.")
        return None
    for arg_candidate in reversed(candidate_args):
        arg_cand_lower = arg_candidate.lower()
        is_path_like = '/' in arg_candidate or '\\' in arg_candidate or arg_candidate in ['..', '~']
        has_extension = '.' in arg_candidate and not arg_candidate.startswith('.')
        has_digits = any(c.isdigit() for c in arg_candidate)
        if arg_cand_lower not in selection_ignore_words:
            print(f"Debug select_primary_argument: Selected '{arg_candidate}' (not in strict_ignore_selection)")
            return arg_candidate
        elif is_path_like or has_extension or has_digits:
            print(f"Debug select_primary_argument: Selected '{arg_candidate}' (is ignore_word but path/file/digit-like)")
            return arg_candidate
    if candidate_args:
        last_candidate_arg = candidate_args[-1].strip()
        if last_candidate_arg:
            print(f"Debug select_primary_argument: Fallback, selected last candidate arg '{last_candidate_arg}'")
            return last_candidate_arg
    print(f"Debug select_primary_argument: No suitable primary argument found in {args_list}")
    return None


def _parse_single_command_segment(text_segment, is_part_of_pipe=False): # Added flag
    """
    Parses a single command segment.
    Returns a dictionary like {'action': '...', 'args': [...]} or error/suggest structures.
    """
    text_lower_segment = text_segment.lower().strip()
    if not text_lower_segment: return None

    action_id, initial_args_str_segment, parsed_args = None, "", []
    suggestion_action_id, suggestion_phrase = None, None
    match_result, score, matched_direct = None, 0, False
    cmd_prefix_for_fallback_msg = ""

    # 0. Direct Command Check for this segment
    direct_commands = {
        'cd ': 'change_directory', 'ls': 'list_files', 'pwd': 'show_path',
        'rm ': 'delete_file', 'rmdir ': 'delete_directory', 'mkdir ': 'make_directory',
        'mv ': 'move_rename', 'cp ': 'copy_file', 'cat ': 'display_file',
        'touch ': 'create_file', 'whoami': 'whoami', 'df': 'disk_usage',
        'free': 'memory_usage', 'ps': 'show_processes', 'git status': 'git_status',
        'git init': 'git_init', 'git commit ': 'git_commit', 'grep ': 'grep',
    }
    for cmd_prefix, mapped_action in direct_commands.items():
        if text_lower_segment.startswith(cmd_prefix):
            if not cmd_prefix.endswith(' ') and text_lower_segment != cmd_prefix: continue
            print(f"Debug (Segment): Direct command prefix match for '{cmd_prefix}'")
            action_id = mapped_action
            initial_args_str_segment = text_segment[len(cmd_prefix):].strip()
            matched_direct = True
            if action_id == 'git_commit': cmd_prefix_for_fallback_msg = cmd_prefix.strip()
            break

    # 1. Intent Recognition (Fuzzy Match - Only if no direct match)
    if not matched_direct:
        match_result = process.extractOne(
            text_lower_segment, ACTION_KEYWORDS.keys(),
            scorer=fuzz.WRatio, score_cutoff=FUZZY_MATCH_THRESHOLD_SUGGEST
        )
        if match_result:
            matched_phrase, score, _ = match_result
            print(f"Debug (Segment): Fuzzy match: phrase='{matched_phrase}', score={score}")
            if score >= FUZZY_MATCH_THRESHOLD_EXECUTE:
                action_id = ACTION_KEYWORDS[matched_phrase]
                print(f"Debug (Segment): Matched action '{action_id}' via fuzzy.")
            elif score >= FUZZY_MATCH_THRESHOLD_SUGGEST:
                suggestion_action_id = ACTION_KEYWORDS[matched_phrase]
                suggestion_phrase = matched_phrase
                print(f"Debug (Segment): Potential suggestion: action='{suggestion_action_id}' (phrase='{suggestion_phrase}')")

    # Determine Best Guess Action & Extract Entities
    current_action_guess = action_id if action_id else suggestion_action_id
    if current_action_guess is None:
        print(f"Debug (Segment): No good match found for '{text_lower_segment}'")
        return {'action': 'unrecognized_segment', 'segment_text': text_segment}

    # Create spaCy doc only for the current segment text
    doc_for_extraction = nlp(text_segment) # Use text_segment for both doc and text_for_extraction
    args = extract_relevant_entities(doc_for_extraction, text_segment)
    print(f"Debug (Segment): Args after extraction, before refinement: {args}")

    # 3. Heuristics & Action Overrides
    if current_action_guess in ['list_files', 'show_path'] and len(args) == 1:
        filename_pattern = r"\.[a-zA-Z0-9]+$"
        arg_check = args[0]
        if (re.search(filename_pattern, arg_check) or '.' in arg_check) and arg_check not in ['.', '..']:
            print(f"Debug (Segment): Heuristic override! Action '{current_action_guess}' changed to 'display_file'.")
            action_id = 'display_file'; suggestion_action_id = None; suggestion_phrase = None

    # If after heuristic, action_id is set, it's a direct match for this segment.
    # If action_id is still None, but suggestion_action_id exists, return suggestion for this segment.
    if action_id is None:
        if suggestion_action_id is not None:
            return {'action': 'suggest_segment',
                    'suggestion_action_id': suggestion_action_id,
                    'suggestion_phrase': suggestion_phrase,
                    'args': args} # Pass current args
        else:
             print(f"Debug (Segment): No action identified for '{text_lower_segment}'.")
             return {'action': 'unrecognized_segment', 'segment_text': text_segment}

    # If we have a definite final action_id for this segment
    if action_id == 'change_directory':
        if any(phrase in text_segment.lower() for phrase in ["up one level", "go back", "ek level peeche jao", "wapas jao"]):
             print("Debug (Segment): Heuristic: Interpreted 'go up/back' as 'cd ..'"); args = ['..']

    # 4. Argument Refinement based on Final Action
    parsed_args = []
    if action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file', 'grep']:
        selected_arg = select_primary_argument(args, action_id)
        if selected_arg: parsed_args = [selected_arg]
        if action_id == 'grep':
             if len(args) > 1: # If there were more entities extracted
                 non_ignore_args = [arg for arg in args if arg.lower() not in ENTITY_IGNORE_WORDS or any(c in arg for c in './\\0123456789') or arg in ['..', '~']]
                 if non_ignore_args: parsed_args = non_ignore_args
                 elif args: parsed_args = args # fallback to all extracted args
                 if not parsed_args: print(f"Warning: Grep might need more arguments. Found in segment: {args}")
             elif not selected_arg and not is_part_of_pipe : # If not part of pipe, grep needs a pattern
                 print(f"Warning: Action '{action_id}' requires an argument, none suitable in {args}.")
                 parsed_args = []
            # If it is part of a pipe, grep might not have explicit file args, using stdin.

        elif not selected_arg and action_id != 'grep':
            print(f"Warning: Action '{action_id}' requires an argument, none suitable in {args}."); parsed_args = []

    elif action_id == 'change_directory':
         selected_arg = select_primary_argument(args, action_id)
         if selected_arg:
              home_path_variants = {'home', '~', 'ghar'}; actual_home_for_comp = os.path.expanduser("~")
              if selected_arg.lower() in home_path_variants or selected_arg == actual_home_for_comp or selected_arg == '~': parsed_args = ['~']
              elif selected_arg == '..': parsed_args = ['..']
              else: parsed_args = [selected_arg]
         else: parsed_args = []

    elif action_id == 'move_rename' or action_id == 'copy_file':
        source, destination = None, None; candidate_args = list(args)
        if matched_direct and initial_args_str_segment and (' ' in initial_args_str_segment or '\t' in initial_args_str_segment):
            if len(candidate_args) < 2 or not all(s.strip() for s in candidate_args):
                try:
                    shlex_args = [s for s in shlex.split(initial_args_str_segment) if s]
                    if len(shlex_args) >= 2 : candidate_args = shlex_args; print(f"Debug (Segment): Using shlex-split args for mv/cp: {candidate_args}")
                except: pass

        clean_cand_args = [arg for arg in candidate_args if arg.lower() not in (ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS) or any(c in arg for c in './\\0123456789') or arg in ['..', '~']]
        if not clean_cand_args and candidate_args: clean_cand_args = candidate_args

        if len(clean_cand_args) >= 2:
            split_found = False
            for i in range(len(clean_cand_args) - 2, 0, -1):
                if clean_cand_args[i].lower() in ARG_SPLIT_KEYWORDS:
                     source_list = clean_cand_args[:i]; dest_list = clean_cand_args[i+1:]
                     source = select_primary_argument(source_list, action_id); destination = select_primary_argument(dest_list, action_id)
                     if source and destination: split_found = True; print(f"Debug (Segment): Split mv/cp args by keyword '{clean_cand_args[i]}': S='{source}', D='{destination}'"); break
            if not split_found:
                arg1 = select_primary_argument(clean_cand_args); temp_remaining = list(clean_cand_args)
                if arg1 in temp_remaining: temp_remaining.remove(arg1)
                arg2 = select_primary_argument(temp_remaining)
                if arg1 and arg2:
                    try:
                        idx1 = clean_cand_args.index(arg1); idx2 = clean_cand_args.index(arg2)
                        if idx1 < idx2: source, destination = arg1, arg2
                        else: source, destination = arg2, arg1
                    except ValueError: source, destination = arg1, arg2
                elif arg1: source = arg1
                print(f"Debug (Segment): Split mv/cp args by position: S='{source}', D='{destination}'")
            if source and destination: parsed_args = [source, destination]
            elif source: print(f"Warning: '{action_id}' requires S/D. Only source '{source}' found. Cand Args: {clean_cand_args}"); return {'action': 'error', 'message': f"Missing destination for {action_id}"}
            else: print(f"Warning: Could not determine S/D for '{action_id}'. Cand Args: {clean_cand_args}"); parsed_args = clean_cand_args[:2] if len(clean_cand_args) >=2 else clean_cand_args
        elif len(clean_cand_args) == 1: print(f"Warning: '{action_id}' requires S/D. Only one candidate: {clean_cand_args}"); return {'action': 'error', 'message': f"Missing destination for {action_id}"}
        else: print(f"Warning: '{action_id}' requires S/D. No candidate args from {args}."); return {'action': 'error', 'message': f"Missing args for {action_id}"}

    elif action_id == 'git_commit':
        msg_match = re.search(r"(?:-m|message)\s+([\"'])(.+?)\1", text_segment, re.IGNORECASE) # Use text_segment
        if msg_match:
            parsed_args = ["-m", msg_match.group(2)]
        else:
            fallback_msg = ""
            # Fallback using text after the matched phrase from this segment's text
            phrase_that_matched_segment = cmd_prefix_for_fallback_msg if matched_direct and cmd_prefix_for_fallback_msg else (matched_phrase if match_result else None)
            if phrase_that_matched_segment:
                 try:
                     phrase_lower = phrase_that_matched_segment.lower()
                     indices = [m.start() for m in re.finditer(re.escape(phrase_lower), text_lower_segment)]
                     if indices: start_index = indices[-1] + len(phrase_that_matched_segment); fallback_msg = text_segment[start_index:].strip().strip("'\"")
                 except Exception as e: print(f"Debug (Segment): Error finding fallback commit msg: {e}")

            if fallback_msg:
                 print(f"Warning: Commit message flag not found. Using text after command: '{fallback_msg}'")
                 parsed_args = ["-m", fallback_msg]
            elif args : # If no -m, and args were extracted from this segment
                commit_msg_parts = [arg for arg in args if arg.lower() not in (ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS) or len(arg)>1 or any(c in arg for c in './\\0123456789')]
                if not commit_msg_parts and args: commit_msg_parts = args
                if commit_msg_parts:
                    fallback_msg = " ".join(commit_msg_parts)
                    print(f"Warning: Commit message flag not found. Using remaining extracted args: '{fallback_msg}'")
                    parsed_args = ["-m", fallback_msg]
                else: print("Error: Commit message required."); return {'action': 'error', 'message': 'Commit message required'}
            else: print("Error: Commit message required."); return {'action': 'error', 'message': 'Commit message required'}

    elif action_id in ['list_files', 'show_path', 'whoami', 'git_status', 'git_init', 'show_processes', 'disk_usage', 'memory_usage']:
         if args: print(f"Debug (Segment): Action '{action_id}' doesn't take arguments, ignoring extracted: {args}")
         parsed_args = []
    else:
         parsed_args = args

    return {'action': action_id, 'args': parsed_args}


def parse_input(text):
    """
    Main parser function. Detects pipes and calls segment parser.
    """
    try:
        original_text = text
        pipe_segments_raw = []

        # splitting by NL pipe phrases first (more complex)
        nl_pipe_match = NL_PIPE_PATTERN.search(original_text)
        if nl_pipe_match:
            print(f"Debug: NL Pipe detected with '{nl_pipe_match.group(0).strip()}'")
            # Split only on the first found NL pipe phrase to handle A and then B and then C
            first_segment = original_text[:nl_pipe_match.start()].strip()
            remaining_after_nl_pipe = original_text[nl_pipe_match.end():].strip()
            pipe_segments_raw.append(first_segment)
            # Check if remaining part also contains pipes (literal or NL)
            # This makes it recursive for the part after the first NL pipe
            if NL_PIPE_PATTERN.search(remaining_after_nl_pipe) or '|' in remaining_after_nl_pipe:
                 pipe_segments_raw.append(remaining_after_nl_pipe) # Simplification for now
            else:
                 pipe_segments_raw.append(remaining_after_nl_pipe)

        elif '|' in original_text: # Fallback to literal pipe
            print(f"Debug: Literal Pipe '|' detected.")
            pipe_segments_raw = original_text.split('|')
        else: # No pipe
            pipe_segments_raw = [original_text]

        pipe_segments = [s.strip() for s in pipe_segments_raw if s.strip()]

        if len(pipe_segments) > 1:
            parsed_commands_list = []
            for i, segment_text in enumerate(pipe_segments):
                # Each segment is parsed as if it's a standalone command for entity extraction purposes
                segment_result = _parse_single_command_segment(segment_text, segment_text) # Pass segment as its own context

                if segment_result and segment_result.get('action') == 'suggest_segment':
                    print(f"Debug: Suggestion within pipe segment ('{segment_result.get('suggestion_phrase')}'). Pipelining suggestions not yet supported.")
                    return {'action': 'error', 'message': f"Ambiguous command '{segment_result.get('suggestion_phrase')}' within a pipe. Please clarify."}

                if not segment_result or segment_result.get('action') in ['unrecognized_segment', 'error']:
                    error_msg = segment_result.get('message', "Unknown error") if segment_result else "Unknown error"
                    segment_err_text = segment_result.get('segment_text', segment_text) if segment_result else segment_text
                    print(f"Error parsing pipe segment '{segment_err_text}': {error_msg}")
                    return {'action': 'error', 'message': f"Error in piped command segment: '{segment_err_text}' - {error_msg}"}

                # For grep as second command in pipe, if it has no args, assume it takes stdin
                if i > 0 and segment_result['action'] == 'grep' and not segment_result['args']:
                    print("Debug: Grep in pipe with no args, assuming stdin.")
                    # No change needed for args, executor handles empty args for grep with pipe

                parsed_commands_list.append({'action': segment_result['action'], 'args': segment_result['args']})

            if parsed_commands_list:
                return {'type': 'piped_commands', 'commands': parsed_commands_list}
            else:
                return {'action': 'error', 'message': 'Failed to parse piped command'}

        else: # No pipe detected or only one segment after split
            # For single commands, original_text is the full context
            single_result = _parse_single_command_segment(original_text, original_text)
            if single_result and single_result.get('action') == 'suggest_segment':
                return {'action': 'suggest',
                        'suggestion_action_id': single_result.get('suggestion_action_id'),
                        'suggestion_phrase': single_result.get('suggestion_phrase')}
            elif single_result and single_result.get('action') == 'unrecognized_segment':
                 return {'action': 'unrecognized'}
            return single_result

    except Exception as e:
         print(f"❌❌❌ TOP LEVEL PARSER FUNCTION CRASHED! ❌❌❌")
         print(f"Input Text: '{text}'")
         print(f"Error Type: {type(e).__name__}")
         print(f"Error Details: {e}")
         print("Traceback:")
         traceback.print_exc()
         return {'action': 'error', 'message': f'Internal parser error: {type(e).__name__}'}


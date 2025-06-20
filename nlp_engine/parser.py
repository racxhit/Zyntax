"""
File: parser.py
Description: Contains functions to parse natural language inputs and convert them
             into structured command representations (intents and targets).
             Includes entity extraction, filtering, argument refinement, and pipelining.
Date Created: 05-04-2025
Last Updated: 27-05-2025
"""

import re
import spacy
from rapidfuzz import process, fuzz
from spacy.lang.en.stop_words import STOP_WORDS
import traceback
import shlex
import os

# Configuration
FUZZY_MATCH_THRESHOLD_EXECUTE = 88 # Slightly lowered to catch more direct intents if well-phrased
FUZZY_MATCH_THRESHOLD_SUGGEST = 60 # Lowered for more suggestions
ENTITY_FILTER_FUZZY_THRESHOLD = 88

# Load spaCy Model
try:
    nlp = spacy.load("en_core_web_sm", disable=['ner'])
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm", disable=['ner'])

# --- Enhanced Lexicons ---
HINGLISH_STOP_WORDS = {
    "ek", "oye", "kya", "kaise", "hai", "hain", "toh", "na", "bhai", "zara", "plz", "pleej", "krdo", "krna", "krne",
    "hua", "hui", "kiye", "diya", "gaya", "tha", "thi", "abhi", "main", "kis", "andar", "hoon", "batao", "saari",
    "wala", "wali", "liye", "mera", "meri", "mere", "mujhe", "humko", "iss", "uss", "yeh", "woh", "aur", "bhi",
    "abhi", "kuch", "thoda", "pura", "sirf", "bas", "kar", "de", "do", "mein", "se", "ko", "ka", "ki", "ke",
    "is", "this", "that", "are", "am", "was", "were", "a", "an", "the", "of", "to", "in", "on", "at", "from",
    "with", "by", "for", "as", "about", "up", "down", "out", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
    "just", "don", "should", "now", "he", "she", "it", "me", "my", "you", "your", "yours", "please", "using", "via",
    "contents", "empty", "new", "working", "one", "level", "current", "everything", "location", "arguments", "text",
    "hey", "yo", "yaar", "abe",
}


HINGLISH_COMMAND_VERBS = {
    "banao", "bana", "kardo", "dikhao", "batao", "karo", "khol", "band", "likho", "padho", "chalao", "badlo", "jao", "hatao",
    "dekh", "sun", "bol", "kar", "chal", "rakh", "le", "de", "maar", "nikal", "ghus", "uth", "baith", "soch", "samajh",
    "pakad", "chhod", "daal", "pheko", "la", "leja", "istemaal", "istemal", "prayoga", "executable" # Added executable
}

# Define Known Actions and Mappings
ACTION_KEYWORDS = {
    # List Files
    "list files": "list_files", "show files": "list_files", "ls": "list_files", "dir": "list_files",
    "display files": "list_files", "contents of": "list_files", "show directory contents": "list_files",
    "what files are": "list_files", "list all": "list_files", "files dikhao": "list_files",
    "kya kya hai dikhao": "list_files", "andar kya hai": "list_files", "saari files dikhao": "list_files",

    # Show Path
    "show current directory": "show_path", "current directory": "show_path", "pwd": "show_path",
    "where am i": "show_path", "print working directory": "show_path", "what's the path": "show_path",
    "tell me the current folder": "show_path", "current folder batao": "show_path", "abhi kahan hoon": "show_path",
    "konsa folder hai batao": "show_path", "current path kya hai": "show_path",

    # Change Directory
    "change directory to": "change_directory", "change dir to": "change_directory", # More specific first
    "change directory": "change_directory", "move to directory": "change_directory", "cd": "change_directory",
    "go to directory": "change_directory",
    "go into": "change_directory", "enter the directory": "change_directory", "folder badlo": "change_directory",
    "change my location to": "change_directory", "move to": "change_directory", "directory mein jao": "change_directory",
    "go up one level": "change_directory", "go back": "change_directory", "cd ..": "change_directory",
    "change to home directory": "change_directory", "cd ~": "change_directory", "ghar jao": "change_directory",
    "peeche jao": "change_directory", "ek level upar": "change_directory", "ek level peeche": "change_directory",


    # Make Directory
    "make new folder": "make_directory", "create new folder": "make_directory", # More specific
    "make folder": "make_directory", "create folder": "make_directory", "mkdir": "make_directory",
    "make directory": "make_directory", "create directory": "make_directory", "md": "make_directory",
    "make dir": "make_directory", "create dir": "make_directory", "new folder": "make_directory",
    "folder banao": "make_directory", "directory banao": "make_directory", "naya folder banao": "make_directory",

    # Delete Directory
    "delete folder": "delete_directory", "remove folder": "delete_directory", "rmdir": "delete_directory",
    "delete directory": "delete_directory", "remove directory": "delete_directory",
    "delete dir": "delete_directory", "remove dir": "delete_directory", "get rid of folder": "delete_directory",
    "folder hatao": "delete_directory", "directory delete kardo": "delete_directory",

    # Create File
    "create empty file": "create_file", "make empty file": "create_file", # More specific
    "create file": "create_file", "make file": "create_file", "touch": "create_file",
    "touch file": "create_file", "new file": "create_file", "generate empty file": "create_file",
    "file banao": "create_file", "khali file banao": "create_file", "nai file": "create_file",

    # Delete File
    "delete file": "delete_file", "remove file": "delete_file", "rm": "delete_file",
    "get rid of file": "delete_file", "get rid of": "delete_file", "del": "delete_file",
    "file hatao": "delete_file", "file delete kardo": "delete_file",

    # Display File
    "display file content": "display_file", "show file content": "display_file", # More specific
    "display file": "display_file", "cat": "display_file",
    "cat file": "display_file", "view file": "display_file",
    "show me": "display_file", "print file": "display_file", "view": "display_file",
    "file dikhao": "display_file", "content dikhao": "display_file",

    # Move/Rename
    "rename file": "move_rename", "move file": "move_rename", "mv": "move_rename",
    "rename": "move_rename", "move": "move_rename", "change name of": "move_rename",
    "naam badlo": "move_rename", "file ka naam badlo": "move_rename",

    # Copy File
    "copy file": "copy_file", "cp": "copy_file", "copy": "copy_file",
    "duplicate file": "copy_file", "make copy": "copy_file", "file copy karo": "copy_file",

    # System Info
    "who am i": "whoami", "whoami": "whoami", "who is the current user": "whoami", "main kaun hoon": "whoami",
    "show processes": "show_processes", "list processes": "show_processes", "ps": "show_processes", "ps aux": "show_processes",
    "list running processes": "show_processes", "processes check karo": "show_processes",
    "disk usage": "disk_usage", "show disk space": "disk_usage", "df": "disk_usage", "df -h": "disk_usage",
    "how much disk space": "disk_usage", "disk space batao": "disk_usage",
    "memory usage": "memory_usage", "show memory": "memory_usage", "free": "memory_usage", "free -m": "memory_usage",
    "check system memory": "memory_usage", "memory kitni hai": "memory_usage",

    # Git
    "git status": "git_status", "check git status": "git_status",
    "initialize git": "git_init", "git init": "git_init",
    "commit changes": "git_commit", "git commit": "git_commit",

    # Search/Filter
    "grep": "grep", "find text": "grep", "search for text": "grep", "filter for": "grep", "text dhoondo": "grep",

    # Permissions
    "make executable": "make_executable", "make file executable": "make_executable", # New action
    "chmod": "chmod", "change permissions": "chmod", "permissions badlo": "chmod",
}

ARG_SPLIT_KEYWORDS = {'to', 'as', 'into', 'se', 'ko', 'mein', 'aur', 'and'}

COMMAND_VERBS = (
    {'ls', 'cd', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'ps', 'df', 'free', 'git', 'cat', 'touch', 'view', 'rmdir', 'dir', 'md', 'del', 'rd', 'copy', 'move', 'ren', 'rename', 'go', 'enter', 'navigate', 'display', 'check', 'initialize', 'commit', 'generate', 'remove', 'get', 'rid', 'tell', 'print', 'duplicate', 'make', 'show', 'list', 'change', 'delete', 'grep', 'find', 'filter', 'chmod', 'ping'} |
    HINGLISH_COMMAND_VERBS
)

ENTITY_IGNORE_WORDS = (
    STOP_WORDS | HINGLISH_STOP_WORDS | COMMAND_VERBS |
    {'file', 'folder', 'directory', 'named', 'called', 'with', 'name',
     'from', 'a', 'the', 'in', 'on', 'at', 'me', 'my', 'please', 'using',
     'via', 'of', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up',
     'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is',
     'are', 'system', 'location', 'arguments', 'text', 'hey', 'naam'}
)
ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING = ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS


NL_PIPE_INDICATORS = [
    r'\s+and then\s+', r'\s+then pipe to\s+', r'\s+pipe to\s+',
    r'\s+piped to\s+', r'\s+and pass to\s+', r'\s+and send output to\s+',
    r'\s+aur phir\s+', r'\s+phir\s+',
]
NL_PIPE_PATTERN = re.compile("|".join(NL_PIPE_INDICATORS), re.IGNORECASE)

COMMON_SHELL_CMDS = {
    'wc', 'awk', 'sed', 'tr', 'sort', 'uniq', 'head', 'tail', 'cut', 'xargs', 'tee', 'du', 'find', 'ping',
}
REDIRECTION_CHARS = ['>', '<', '>>']


def _is_token_covered(token, processed_char_indices):
    start_idx, end_idx = token.idx, token.idx + len(token.text)
    covered_count = 0
    for i in range(start_idx, end_idx):
        if i < len(processed_char_indices) and processed_char_indices[i]:
            covered_count += 1
    return covered_count > (len(token.text) * 0.5)


def _is_valid_start_of_entity_phrase(token_lower, token_text, doc, token_idx):
    if any(c in token_text for c in './\\0123456789"') or token_text in ['..', '~'] or token_text.startswith('"') or token_text.startswith("'"):
        if token_text == '.' and token_idx + 1 < len(doc):
            next_token_text = doc[token_idx + 1].text
            if re.match(r"^[a-zA-Z0-9_]+$", next_token_text):
                return True
        else:
            return True
    is_command_verb_strict = token_lower in COMMAND_VERBS
    if is_command_verb_strict:
        return False
    return token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
        token_lower in ARG_SPLIT_KEYWORDS

def _is_valid_continuation_of_entity_phrase(token_lower, token_text):
    if token_lower in ARG_SPLIT_KEYWORDS: return True
    return token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
           any(c in token_text for c in './\\0123456789"') or \
           token_text in ['..', '~'] or token_text.endswith('"') or token_text.endswith("'")


def extract_relevant_entities(doc, text_for_extraction):
    entities_with_spans = []
    processed_char_indices = [False] * len(text_for_extraction)
    doc_tokens = list(doc)

    def mark_processed(start, end):
        for i in range(start, end):
            if 0 <= i < len(processed_char_indices): processed_char_indices[i] = True

    path_pattern = r"([\"'])(.+?)\1|((?:~|\.\.|\.)?/(?:[a-zA-Z0-9_./\- ]|\\ )+/?)|([a-zA-Z0-9_.-]+\.[a-zA-Z0-9_*-]+)|(\.\.)|([a-zA-Z0-9_*'-]+(?:[/\\].*)?)"

    for match in re.finditer(path_pattern, text_for_extraction):
        entity_text = match.group(2) or match.group(3) or match.group(4) or match.group(5) or match.group(6)
        if entity_text:
            entity_text = entity_text.strip()
            start, end = match.span()
            already_covered_chars = sum(1 for i in range(start,end) if processed_char_indices[i])
            if already_covered_chars < (end - start) * 0.5 and entity_text:
                is_path = '/' in entity_text or '\\' in entity_text or entity_text in ['..', '~'] or '*' in entity_text
                already_exists = any((entity_text == et) or (not is_path and entity_text.lower() == et.lower()) for et, _ in entities_with_spans)
                if not already_exists:
                    entities_with_spans.append((entity_text, (start, end)))
                    mark_processed(start, end)

    current_phrase_tokens_text = []
    current_phrase_start_char = -1
    for token_idx, token in enumerate(doc_tokens):
        is_covered_by_regex = _is_token_covered(token, processed_char_indices)
        if not is_covered_by_regex and not token.is_punct:
            token_lower = token.lower_
            token_text = token.text
            if not current_phrase_tokens_text:
                if _is_valid_start_of_entity_phrase(token_lower, token_text, doc_tokens, token_idx):
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
                elif _is_valid_start_of_entity_phrase(token_lower, token_text, doc_tokens, token_idx):
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
            if is_covered_by_regex or token.is_punct : mark_processed(token.idx, token.idx + len(token.text))
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
        is_path_like_or_num_or_long_or_quoted_or_wild = (
            '.' in entity or '/' in entity or '\\' in entity or entity in ['..','~'] or
            any(char.isdigit() for char in entity) or len(entity)>3 or
            (entity.startswith('"') and entity.endswith('"')) or
            (entity.startswith("'") and entity.endswith("'")) or
            '*' in entity
        )

        if entity_lower in COMMAND_VERBS and not is_path_like_or_num_or_long_or_quoted_or_wild and entity_lower not in ARG_SPLIT_KEYWORDS:
            # print(f"Debug EntityExtract: Final filter (exact verb): '{entity}'") # Too verbose
            continue
        if entity_lower in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING and not is_path_like_or_num_or_long_or_quoted_or_wild:
            if not entity.isdigit():
                # print(f"Debug EntityExtract: Final filter (exact ignore word): '{entity}'") # Too verbose
                continue

        is_fuzzy_keyword = False
        for keyword in fuzzy_check_list_args:
            if fuzz.ratio(entity_lower, keyword) > ENTITY_FILTER_FUZZY_THRESHOLD + 5:
                 looks_like_arg_f = (any(char.isdigit() for char in entity) or '/' in entity or '\\' in entity or '.' in entity or entity in ['..', '~'] or '*' in entity or (entity.startswith('"') and entity.endswith('"')))
                 if not looks_like_arg_f:
                      is_fuzzy_keyword = True
                      # print(f"Debug EntityExtract: Filtered (fuzzy) non-arg entity '{entity}' similar to '{keyword}'") # Too verbose
                      break
        if is_fuzzy_keyword: continue

        if entity: final_filtered_entities.append(entity)

    seen = set()
    unique_entities = [x for x in final_filtered_entities if not (x.lower() in seen or seen.add(x.lower()))]
    print(f"Debug: Extracted entities (final): {unique_entities}")
    return unique_entities


def select_primary_argument(args_list, action_id=None):
    if not args_list: return None
    for arg_candidate in args_list:
        if (arg_candidate.startswith('"') and arg_candidate.endswith('"')) or \
           (arg_candidate.startswith("'") and arg_candidate.endswith("'")):
            return arg_candidate.strip("\"'")
        if '/' in arg_candidate or '\\' in arg_candidate or '.' in arg_candidate or arg_candidate in ['..', '~'] or '*' in arg_candidate:
            return arg_candidate

    selection_ignore_words = ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS
    candidate_args = [arg for arg in args_list if arg.lower() not in ARG_SPLIT_KEYWORDS]
    if not candidate_args:
        if args_list : print(f"Debug select_primary_argument: Only split keywords found in {args_list}, returning None for primary.")
        return None

    for arg_candidate in reversed(candidate_args):
        arg_cand_lower = arg_candidate.lower()
        is_path_like = '/' in arg_candidate or '\\' in arg_candidate or arg_candidate in ['..', '~'] or '*' in arg_candidate
        has_extension = '.' in arg_candidate and not arg_candidate.startswith('.')
        has_digits = any(c.isdigit() for c in arg_candidate)

        if arg_cand_lower not in selection_ignore_words:
            # print(f"Debug select_primary_argument: Selected '{arg_candidate}' (not in strict_ignore_selection)")
            return arg_candidate
        elif is_path_like or has_extension or has_digits:
            # print(f"Debug select_primary_argument: Selected '{arg_candidate}' (is ignore_word but path/file/digit-like)")
            return arg_candidate

    if candidate_args:
        last_candidate_arg = candidate_args[-1].strip()
        if last_candidate_arg:
            # print(f"Debug select_primary_argument: Fallback, selected last candidate arg '{last_candidate_arg}'")
            return last_candidate_arg
    # print(f"Debug select_primary_argument: No suitable primary argument found in {args_list}")
    return None


def _parse_single_command_segment(text_segment, is_part_of_pipe=False):
    text_lower_segment = text_segment.lower().strip()
    if not text_lower_segment: return None

    action_id, initial_args_str_segment, parsed_args = None, "", []
    suggestion_action_id, suggestion_phrase, matched_phrase_for_intent = None, None, None
    match_result, score, matched_direct = None, 0, False
    cmd_prefix_for_fallback_msg = ""

    direct_commands = {
        'cd ': 'change_directory', 'ls': 'list_files', 'pwd': 'show_path',
        'rm ': 'delete_file', 'rmdir ': 'delete_directory', 'mkdir ': 'make_directory',
        'mv ': 'move_rename', 'cp ': 'copy_file', 'cat ': 'display_file',
        'touch ': 'create_file', 'whoami': 'whoami', 'df ': 'disk_usage', 'df': 'disk_usage',
        'free ': 'memory_usage', 'free': 'memory_usage',
        'ps ': 'show_processes', 'ps': 'show_processes',
        'git status': 'git_status', 'git init': 'git_init', 'git commit ': 'git_commit',
        'grep ': 'grep', 'chmod ': 'chmod', 'ping ': 'ping',
    }
    for cmd_prefix, mapped_action in direct_commands.items():
        if text_lower_segment.startswith(cmd_prefix.lower()): # Ensure prefix check is case-insensitive
            if not cmd_prefix.endswith(' ') and text_lower_segment != cmd_prefix.lower():
                continue
            print(f"Debug (Segment): Direct command prefix match for '{cmd_prefix}' -> '{mapped_action}'")
            action_id = mapped_action
            initial_args_str_segment = text_segment[len(cmd_prefix):].strip()
            matched_direct = True
            matched_phrase_for_intent = cmd_prefix.strip() # Store the matched prefix
            if action_id == 'git_commit': cmd_prefix_for_fallback_msg = cmd_prefix.strip()
            break

    if not action_id and is_part_of_pipe:
        try:
            shlex_parts_check = shlex.split(text_segment)
            if shlex_parts_check and shlex_parts_check[0].lower() in COMMON_SHELL_CMDS:
                print(f"Debug (Segment): Recognized common shell command '{shlex_parts_check[0]}' in pipe. Treating as raw.")
                return {'type': 'raw_command', 'command': shlex_parts_check[0], 'args': shlex_parts_check[1:], 'segment_text': text_segment}
        except ValueError:
            pass

    if not matched_direct:
        sorted_action_keywords = sorted(ACTION_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True)
        sorted_action_phrases = [item[0] for item in sorted_action_keywords]

        match_result = process.extractOne(
            text_lower_segment, sorted_action_phrases,
            scorer=fuzz.WRatio, score_cutoff=FUZZY_MATCH_THRESHOLD_SUGGEST
        )
        if match_result:
            current_matched_phrase, current_score, _ = match_result
            print(f"Debug (Segment): Fuzzy match: phrase='{current_matched_phrase}', score={current_score}")
            if current_score >= FUZZY_MATCH_THRESHOLD_EXECUTE:
                action_id = ACTION_KEYWORDS[current_matched_phrase]
                matched_phrase_for_intent = current_matched_phrase
                print(f"Debug (Segment): Matched action '{action_id}' via fuzzy ('{current_matched_phrase}').")
            elif current_score >= FUZZY_MATCH_THRESHOLD_SUGGEST:
                suggestion_action_id = ACTION_KEYWORDS[current_matched_phrase]
                suggestion_phrase = current_matched_phrase
                print(f"Debug (Segment): Potential suggestion: action='{suggestion_action_id}' (phrase='{suggestion_phrase}')")

    # Heuristic for "create dir user2" vs "dir"
    if (action_id == 'list_files' and matched_phrase_for_intent == 'dir') or \
       (suggestion_action_id == 'list_files' and suggestion_phrase == 'dir'):
        if 'create' in text_lower_segment or 'make' in text_lower_segment:
            # Check if a more specific "make_directory" keyword is a better fit
            potential_make_dir_phrase = None
            best_make_dir_score = 0
            for phrase_key, act_val in ACTION_KEYWORDS.items():
                if act_val == 'make_directory' and phrase_key in text_lower_segment:
                    # Score this phrase against the segment
                    phrase_score = fuzz.partial_ratio(phrase_key, text_lower_segment)
                    if phrase_score > best_make_dir_score:
                        best_make_dir_score = phrase_score
                        potential_make_dir_phrase = phrase_key

            # If a make_directory phrase is a significantly better match than "dir"
            if potential_make_dir_phrase and best_make_dir_score > (score if match_result else 0) + 10 : # Require a notable score increase
                print(f"Debug (Segment): Heuristic override! Context suggests 'make_directory' (matched '{potential_make_dir_phrase}') over 'list_files' for input '{text_segment}'.")
                action_id = 'make_directory'
                matched_phrase_for_intent = potential_make_dir_phrase
                suggestion_action_id = None
                suggestion_phrase = None
                matched_direct = False # It's a heuristic match

    # Argument Extraction
    args_text_to_parse = text_segment # Default to full segment for suggestions or if no phrase stripped
    if action_id: # If an action is confirmed (direct, fuzzy, or heuristic)
        if matched_direct:
            args_text_to_parse = initial_args_str_segment
        elif matched_phrase_for_intent: # Fuzzy or heuristic match
            # Attempt to strip the matched phrase, case-insensitively
            # This needs to be careful if the matched phrase is not at the very beginning
            # or if it's a substring of a potential argument.
            # A simple startswith check is often sufficient if keywords are well-defined.
            if text_lower_segment.startswith(matched_phrase_for_intent.lower()):
                args_text_to_parse = text_segment[len(matched_phrase_for_intent):].strip()
                print(f"Debug (Segment): Args text after stripping '{matched_phrase_for_intent}': '{args_text_to_parse}'")
            else:
                # If matched phrase not at start, could be complex. Fallback to full segment for args,
                # but this might re-introduce the command phrase as an arg.
                # A better approach might be to use the span of the fuzzy match if available,
                # or to rely on entity extraction to filter out command verbs later.
                # For now, let's be cautious and use the full segment if stripping isn't clean.
                print(f"Debug (Segment): Matched phrase '{matched_phrase_for_intent}' not at start. Using full segment for arg extraction for action '{action_id}'.")
                args_text_to_parse = text_segment # Revert to full segment, rely on entity filtering

    doc_for_args_extraction = nlp(args_text_to_parse)
    args = extract_relevant_entities(doc_for_args_extraction, args_text_to_parse)
    print(f"Debug (Segment): Args after extraction (from '{args_text_to_parse}'), before refinement: {args}")


    if action_id is None: # No firm action yet
        if suggestion_action_id is not None:
            # For suggestions, args should be from the *full original segment* because the user confirms based on that.
            full_segment_doc = nlp(text_segment)
            suggestion_args = extract_relevant_entities(full_segment_doc, text_segment)
            print(f"Debug (Segment): Args for suggestion (from full segment '{text_segment}'): {suggestion_args}")
            return {'action': 'suggest_segment',
                    'suggestion_action_id': suggestion_action_id,
                    'suggestion_phrase': suggestion_phrase,
                    'args': suggestion_args}
        else: # Unrecognized
            if is_part_of_pipe:
                try:
                    shlex_parts = shlex.split(text_segment)
                    if shlex_parts:
                        print(f"Debug (Segment): No NLP match in pipe, treating '{text_segment}' as raw.")
                        return {'type': 'raw_command', 'command': shlex_parts[0], 'args': shlex_parts[1:], 'segment_text': text_segment}
                except ValueError: pass # Fall through
            print(f"Debug (Segment): No action identified for '{text_lower_segment}'.")
            return {'action': 'unrecognized_segment', 'segment_text': text_segment}

    # --- Argument Refinement based on Final Action ---
    parsed_args = []
    NO_ARG_ACTIONS = {'show_path', 'whoami', 'git_status', 'git_init'} # list_files can take args (path)
    OPT_ARG_ACTIONS = {'show_processes', 'disk_usage', 'memory_usage', 'list_files'} # ps, df, free, ls can take flags/paths

    if action_id in NO_ARG_ACTIONS:
        if args: print(f"Debug (Segment): Action '{action_id}' strictly takes no arguments. Clearing extracted: {args}")
        parsed_args = []
    elif action_id in OPT_ARG_ACTIONS:
        if matched_direct and initial_args_str_segment:
            try:
                parsed_args = shlex.split(initial_args_str_segment)
                print(f"Debug (Segment): Action '{action_id}' (direct) using shlexed args: {parsed_args}")
            except ValueError: parsed_args = args; print(f"Warning: shlex failed for '{action_id}' direct args, using NLP args: {args}")
        else: # Fuzzy match, or direct match but initial_args_str_segment was empty, or NLP args are preferred
            parsed_args = args # Keep NLP extracted args as potential flags/paths
            print(f"Debug (Segment): Action '{action_id}' (non-direct or no direct args string) using NLP extracted args: {args}")

    elif action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file', 'make_executable']:
        selected_arg = select_primary_argument(args, action_id)
        if selected_arg: parsed_args = [selected_arg]
        else:
            if matched_direct and not initial_args_str_segment and action_id not in ['make_executable']: # make_executable might not need arg if context implies current dir
                 return {'action': 'error', 'message': f"Missing argument for {action_id}"}
            elif not args and action_id not in ['make_executable']: # No args extracted by NLP
                 return {'action': 'error', 'message': f"Missing argument for {action_id}"}
            print(f"Warning: Action '{action_id}' requires an argument, none suitable in {args}."); parsed_args = []


    elif action_id == 'grep':
        if matched_direct and cmd_prefix_for_fallback_msg == 'grep':
            try: parsed_args = shlex.split(initial_args_str_segment)
            except ValueError: parsed_args = args
        elif args:
            pattern_cand, file_cand, remaining_args = None, None, list(args)
            for i, arg_val in enumerate(args):
                if (arg_val.startswith('"') and arg_val.endswith('"')) or (arg_val.startswith("'") and arg_val.endswith("'")):
                    pattern_cand = arg_val;
                    if arg_val in remaining_args: remaining_args.remove(arg_val)
                    break
            if not pattern_cand and remaining_args:
                for arg_val in list(remaining_args): # Iterate over a copy for safe removal
                    if not ('.' in arg_val or '/' in arg_val or '\\' in arg_val or arg_val in ['..','~']):
                        pattern_cand = arg_val
                        if arg_val in remaining_args: remaining_args.remove(arg_val)
                        break
            if not pattern_cand and args: pattern_cand = args[0]
            if args and args[0] in remaining_args: remaining_args.remove(args[0]) # if first arg was taken as pattern
            if remaining_args: file_cand = select_primary_argument(remaining_args, action_id)

            if pattern_cand and file_cand: parsed_args = [pattern_cand, file_cand]
            elif pattern_cand: parsed_args = [pattern_cand]
            elif file_cand and not is_part_of_pipe: return {'action': 'error', 'message': f"Grep pattern missing for file '{file_cand}'"}
            elif not pattern_cand and not is_part_of_pipe and not (matched_direct and not initial_args_str_segment):
                return {'action': 'error', 'message': 'Grep pattern required'}
        elif matched_direct and not initial_args_str_segment and not is_part_of_pipe:
            return {'action': 'error', 'message': 'Grep pattern required'}

    elif action_id == 'change_directory':
         selected_arg = select_primary_argument(args, action_id)
         if selected_arg:
              home_path_variants = {'home', '~', 'ghar'}; actual_home_for_comp = os.path.expanduser("~")
              if selected_arg.lower() in home_path_variants or selected_arg == actual_home_for_comp or selected_arg == '~': parsed_args = ['~']
              elif selected_arg == '..': parsed_args = ['..']
              else: parsed_args = [selected_arg]
         else:
            if not args and not (matched_direct and not initial_args_str_segment):
                 parsed_args = ['~']
            else: parsed_args = []


    elif action_id == 'move_rename' or action_id == 'copy_file' or action_id == 'chmod':
        candidate_args = list(args)
        if matched_direct and initial_args_str_segment:
            try:
                shlex_args = [s for s in shlex.split(initial_args_str_segment) if s]
                if len(shlex_args) >= (1 if action_id == 'chmod' else 2):
                    candidate_args = shlex_args
            except ValueError: pass

        clean_cand_args = [
            arg for arg in candidate_args
            if arg.lower() not in (ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS - {"."}) or
               any(c in arg for c in './\\0123456789*') or arg in ['..', '~'] or
               (action_id == 'chmod' and re.match(r"^[0-7]{3,4}$|^[ugoa]*[-+=][rwxXstugo]*$", arg))
        ]
        if not clean_cand_args and candidate_args: clean_cand_args = candidate_args

        if action_id == 'chmod':
            if len(clean_cand_args) >= 2:
                perm_arg, target_arg = None, None
                temp_perms = [arg_c for arg_c in clean_cand_args if re.match(r"^[0-7]{3,4}$|^[ugoa]*[-+=][rwxXstugo]*$", arg_c)]
                temp_targets = [arg_c for arg_c in clean_cand_args if arg_c not in temp_perms]
                if temp_perms: perm_arg = temp_perms[0]
                if temp_targets: target_arg = select_primary_argument(temp_targets, action_id) or temp_targets[0]
                if perm_arg and target_arg: parsed_args = [perm_arg, target_arg]
                elif len(clean_cand_args) >=2 : parsed_args = clean_cand_args[:2]
                else: return {'action': 'error', 'message': f"Missing arguments for {action_id}"}
            else: return {'action': 'error', 'message': f"Missing arguments for {action_id}"}

        elif action_id in ['move_rename', 'copy_file']:
            source, destination = None, None
            if len(clean_cand_args) >= 2:
                split_found_keyword = False
                for i in range(len(clean_cand_args) - 2, -1, -1):
                    if clean_cand_args[i].lower() in ARG_SPLIT_KEYWORDS:
                        source_parts = clean_cand_args[:i]; dest_parts = clean_cand_args[i+1:]
                        if source_parts and dest_parts:
                            source = select_primary_argument(source_parts, action_id) or " ".join(source_parts)
                            destination = select_primary_argument(dest_parts, action_id) or " ".join(dest_parts)
                            if source and destination: split_found_keyword = True; break
                if not split_found_keyword:
                    if len(clean_cand_args) > 2 and not any(k in clean_cand_args[-2].lower() for k in ARG_SPLIT_KEYWORDS):
                        destination = clean_cand_args[-1]; source = " ".join(clean_cand_args[:-1])
                    else: source = clean_cand_args[0]; destination = clean_cand_args[1]
                if source and destination: parsed_args = [source, destination]
                elif source: return {'action': 'error', 'message': f"Missing destination for {action_id}"}
                else: return {'action': 'error', 'message': f"Missing source/destination for {action_id}"}
            elif len(clean_cand_args) == 1: return {'action': 'error', 'message': f"Missing destination for {action_id}"}
            else: return {'action': 'error', 'message': f"Missing arguments for {action_id}"}


    elif action_id == 'git_commit':
        msg_match = re.search(r"(?:-m|message)\s+([\"'])(.+?)\1", text_segment, re.IGNORECASE)
        if msg_match: parsed_args = ["-m", msg_match.group(2)]
        else:
            fallback_msg = ""
            if matched_direct and initial_args_str_segment:
                fallback_msg = initial_args_str_segment.strip().strip("'\"")
            elif args:
                commit_msg_parts = [arg for arg in args if arg.lower() not in (ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS - COMMAND_VERBS) or len(arg)>1 or any(c in arg for c in './\\0123456789')]
                if not commit_msg_parts and args: commit_msg_parts = args
                if commit_msg_parts: fallback_msg = " ".join(commit_msg_parts)
            if fallback_msg: parsed_args = ["-m", fallback_msg]
            else: return {'action': 'error', 'message': 'Commit message required'}
    else: # Default for other actions
         parsed_args = args

    return {'action': action_id, 'args': parsed_args}


def parse_input(text):
    try:
        original_text = text.strip()
        if any(char in original_text for char in REDIRECTION_CHARS):
            is_grep_quoted_redir = False
            if "grep" in original_text.lower():
                grep_match = re.search(r"grep\s+.*?([\"'])(.+?[><].*?)\1", original_text, re.IGNORECASE)
                if grep_match: is_grep_quoted_redir = True
            if not is_grep_quoted_redir:
                print(f"Debug: Redirection character detected. Treating as single raw command.")
                return {'type': 'raw_shell_string', 'command_string': original_text}

        pipe_segments_raw = []
        # Prioritize splitting by NL pipe indicators first
        # This is a simplified greedy approach. For "A then B | C then D", it will split at "then" first.
        # A more robust parser might use a grammar or more complex precedence rules.

        current_text_to_split = original_text
        while True:
            nl_pipe_match = NL_PIPE_PATTERN.search(current_text_to_split)
            if nl_pipe_match:
                first_segment = current_text_to_split[:nl_pipe_match.start()].strip()
                if first_segment: # Add segment before the NL pipe
                    # If this segment itself contains literal pipes, split it
                    if '|' in first_segment:
                        pipe_segments_raw.extend(s.strip() for s in first_segment.split('|') if s.strip())
                    else:
                        pipe_segments_raw.append(first_segment)

                current_text_to_split = current_text_to_split[nl_pipe_match.end():].strip() # Continue with text after NL pipe
                if not current_text_to_split: break # No more text
            else: # No more NL pipes in the remaining text
                if current_text_to_split:
                    # Split the rest by literal pipes if any
                    if '|' in current_text_to_split:
                         pipe_segments_raw.extend(s.strip() for s in current_text_to_split.split('|') if s.strip())
                    else: # Single command or last segment
                        pipe_segments_raw.append(current_text_to_split)
                break # Done splitting

        if not pipe_segments_raw and original_text: # Should not happen if original_text was not empty
            pipe_segments_raw = [original_text]


        pipe_segments = [s.strip() for s in pipe_segments_raw if s.strip()]

        if len(pipe_segments) > 1:
            parsed_commands_list = []
            for i, segment_text in enumerate(pipe_segments):
                segment_result = _parse_single_command_segment(segment_text, is_part_of_pipe=True)

                if segment_result and segment_result.get('action') == 'suggest_segment':
                    return {'action': 'error', 'message': f"Ambiguous command '{segment_result.get('suggestion_phrase')}' within a pipe. Please clarify: '{segment_text}'"}

                if not segment_result or segment_result.get('action') in ['unrecognized_segment', 'error']:
                    if segment_result and segment_result.get('action') == 'unrecognized_segment':
                        try:
                            shlex_parts = shlex.split(segment_text)
                            if shlex_parts:
                                segment_result = {'type': 'raw_command', 'command': shlex_parts[0], 'args': shlex_parts[1:], 'segment_text': segment_text}
                            else: return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - Unrecognized & could not split"}
                        except ValueError: return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - Unrecognized & shlex failed"}
                    else:
                        error_msg = segment_result.get('message', "Unknown error") if segment_result else "Unknown error"
                        return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - {error_msg}"}

                if segment_result.get('type') == 'raw_command':
                    parsed_commands_list.append(segment_result)
                else:
                    parsed_commands_list.append({'action': segment_result['action'], 'args': segment_result.get('args', [])})

            if parsed_commands_list: return {'type': 'piped_commands', 'commands': parsed_commands_list}
            else: return {'action': 'error', 'message': 'Failed to parse piped command'}
        else:
            single_result = _parse_single_command_segment(original_text, is_part_of_pipe=False)
            if single_result and single_result.get('action') == 'suggest_segment':
                return {'action': 'suggest',
                        'suggestion_action_id': single_result.get('suggestion_action_id'),
                        'suggestion_phrase': single_result.get('suggestion_phrase'),
                        'args': single_result.get('args', [])}
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

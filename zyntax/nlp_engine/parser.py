"""
Natural language parser for terminal commands.
Converts plain English input into structured command representations.
"""

import re
import spacy
from rapidfuzz import process, fuzz
from spacy.lang.en.stop_words import STOP_WORDS
import traceback
import shlex
import os

# Configuration
FUZZY_MATCH_THRESHOLD_EXECUTE = 85
FUZZY_MATCH_THRESHOLD_SUGGEST = 60
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
    "hua", "hui", "kiye", "diya", "gaya", "tha", "thi", "abhi", "main", "kis", "andar", "hoon",
    "saari", "wala", "wali", "liye", "mera", "meri", "mere", "mujhe", "humko", "iss", "uss", "yeh", "woh", "aur", "bhi",
    "kuch", "thoda", "pura", "sirf", "bas", "kar", "de", "do", "mein", "se", "ko", "ka", "ki", "ke", "is naam ka", "is naam se",
    "is", "this", "that", "are", "am", "was", "were", "a", "an", "the", "of", "to", "in", "on", "at", "from",
    "with", "by", "for", "as", "about", "up", "down", "out", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
    "just", "don", "should", "now", "he", "she", "it", "me", "my", "you", "your", "yours", "please", "using", "via",
    "contents", "empty", "new", "working", "one", "level", "current", "everything", "location", "arguments", "text",
    "hey", "yo", "yaar", "abe", "naam", "cheezein", "cheez"
}


HINGLISH_COMMAND_VERBS = {
    "banao", "bana", "kardo", "dikhao", "batao", "karo", "khol", "band", "likho", "padho", "chalao", "badlo", "jao", "hatao",
    "dekh", "sun", "bol", "kar", "chal", "rakh", "le", "de", "maar", "nikal", "ghus", "uth", "baith", "soch", "samajh",
    "pakad", "chhod", "daal", "pheko", "la", "leja", "istemaal", "istemal", "prayoga", "executable", "jaana", "count"
}

ACTION_KEYWORDS = {
    # Show Path
    "abhi main kis folder ke andar hoon": "show_path", "main kis folder mein hoon": "show_path",
    "konsa folder hai abhi": "show_path", "current folder kya hai": "show_path",
    "mujhe batao main kahan hoon": "show_path", "kahan hoon abhi": "show_path", "kahan per hoon": "show_path",
    "abhi main kahan hu": "show_path", "current location kya hai": "show_path",
    "tell me the current folder": "show_path", "current folder batao": "show_path",
    "konsa folder hai batao": "show_path", "current path kya hai": "show_path",
    "show current directory": "show_path", "print working directory": "show_path", "current directory": "show_path",
    "where am i": "show_path", "what's the path": "show_path", "pwd": "show_path",

    # List Files
    "folder mein kya hai dikhao": "list_files", "directory mein kya hai": "list_files",
    "kya kya cheezein hain dikhao": "list_files", "kya cheezein hain": "list_files", "files dikhao": "list_files",
    "andar kya hai dikhao": "list_files", "current folder mein kya hai": "list_files", "is folder mein kya hai": "list_files",
    "list all files": "list_files", "show all files": "list_files", "saare python files dikha do": "list_files",
    "saari files dikhao": "list_files",
    "show directory contents": "list_files", "contents of directory": "list_files", "list directory": "list_files",
    "list files": "list_files", "show files": "list_files", "ls": "list_files", "dir": "list_files",
    "display files": "list_files", "contents of": "list_files",
    "what files are": "list_files", "list all": "list_files", "andar kya hai": "list_files",
    "I want to see what's in this directory": "list_files",


    # Change Directory
    "go to parent directory": "change_directory", "navigate to home directory": "change_directory",
    "go up one level": "change_directory", "ek level upar": "change_directory", "ek level peeche": "change_directory",
    "go back": "change_directory", "cd ..": "change_directory", "peeche jao": "change_directory",
    "change to home directory": "change_directory", "cd ~": "change_directory", "ghar jao": "change_directory",
    "change directory to": "change_directory", "change dir to": "change_directory", "change to": "change_directory",
    "go to directory": "change_directory", "move to directory": "change_directory",
    "change directory": "change_directory", "cd": "change_directory",
    "go into": "change_directory", "enter the directory": "change_directory", "folder badlo": "change_directory",
    "change my location to": "change_directory", "move to": "change_directory", "directory mein jao": "change_directory",

    # Make Directory
    "make a new folder named": "make_directory", "create a new folder named": "make_directory",
    "make new folder": "make_directory", "create new folder": "make_directory",
    "ek folder banao": "make_directory", "folder banao": "make_directory", "directory banao": "make_directory",
    "naya folder banao": "make_directory",
    "make folder": "make_directory", "create folder": "make_directory", "mkdir": "make_directory",
    "make directory": "make_directory", "create directory": "make_directory", "md": "make_directory",
    "make dir": "make_directory", "create dir": "make_directory", "new folder": "make_directory",

    # Create File
    "create empty file": "create_file", "make empty file": "create_file",
    "create a new file named": "create_file", "make a new file named": "create_file",
    "ek nayi file banao": "create_file", "ek file banao": "create_file", "file banao": "create_file",
    "khali file banao": "create_file", "nai file": "create_file",
    "create file": "create_file", "make file": "create_file", "touch file": "create_file",
    "touch": "create_file", "new file": "create_file", "generate empty file": "create_file",
    "Can you help me create a new Python file": "create_file",


    # Delete Directory
    "delete this folder called": "delete_directory",
    "delete folder": "delete_directory", "remove folder": "delete_directory", "rmdir": "delete_directory",
    "delete directory": "delete_directory", "remove directory": "delete_directory",
    "delete dir": "delete_directory", "remove dir": "delete_directory", "get rid of folder": "delete_directory",
    "folder hatao": "delete_directory", "directory delete kardo": "delete_directory", "is folder ko delete kar do": "delete_directory",


    # Delete File
    "delete file": "delete_file", "remove file": "delete_file", "rm": "delete_file",
    "get rid of file": "delete_file", "get rid of": "delete_file", "del": "delete_file",
    "file hatao": "delete_file", "file delete kardo": "delete_file",

    # Display File (head/tail specific)
    "show first 5 lines of": "display_file_head",
    "show last 10 lines of": "display_file_tail",
    "display file content": "display_file", "show file content": "display_file",
    "display file": "display_file", "cat file": "display_file", "view file": "display_file",
    "cat": "display_file", "show me": "display_file", "print file": "display_file", "view": "display_file",
    "file dikhao": "display_file", "content dikhao": "display_file",
    "Please show me the contents of the main script": "display_file",


    # Move/Rename
    "rename file": "move_rename", "move file": "move_rename", "mv": "move_rename",
    "rename": "move_rename", "move": "move_rename",
    "change name of": "move_rename",
    "naam badlo": "move_rename", "file ka naam badlo": "move_rename",

    # Copy File
    "copy file": "copy_file", "cp": "copy_file", "copy": "copy_file",
    "duplicate file": "copy_file", "make copy": "copy_file", "file copy karo": "copy_file",

    # System Info
    "who am i": "whoami", "whoami": "whoami", "current user kaun hai batao": "whoami",
    "who is the current user": "whoami", "main kaun hoon": "whoami", "who is logged in": "whoami",
    "list running processes": "show_processes", "show processes": "show_processes", "list processes": "show_processes",
    "ps aux": "show_processes", "ps": "show_processes", "processes check karo": "show_processes", "What processes are currently running?": "show_processes",
    "show disk space": "disk_usage", "disk usage": "disk_usage", "df -h": "disk_usage", "df": "disk_usage",
    "how much disk space": "disk_usage", "disk space batao": "disk_usage", "How much space is left on my disk?": "disk_usage",
    "check system memory": "memory_usage", "show memory": "memory_usage", "memory usage": "memory_usage",
    "free -m": "memory_usage", "free": "memory_usage", "memory kitni free hai": "memory_usage",
    "display system uptime": "system_uptime", "uptime": "system_uptime",
    "env variables": "env_variables", "env": "env_variables",

    # Git
    "git status": "git_status", "check git status": "git_status",
    "initialize git": "git_init", "git init": "git_init",
    "commit changes": "git_commit", "git commit": "git_commit",

    # Search/Filter
    "search for text": "grep", "find text in files": "grep", "find files containing": "grep",
    "grep": "grep", "find text": "grep", "filter for": "grep", "text dhoondo": "grep",
    "search for 'import' in all python files": "grep",

    # Count lines
    "count lines in": "count_lines",
    "count lines": "count_lines",


    # Permissions
    "make file executable": "make_executable", "make executable": "make_executable",
    "change permissions of": "chmod", "change permissions": "chmod", "permissions badlo": "chmod", "chmod": "chmod",

    # Network
    "check network interfaces": "network_interfaces",
    "ifconfig": "network_interfaces",
    "ipconfig": "network_interfaces",
}

ARG_SPLIT_KEYWORDS = {'to', 'as', 'into', 'se', 'ko', 'mein', 'aur', 'and', 'of', 'in', 'called'}

COMMAND_VERBS = (
    {'ls', 'cd', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'ps', 'df', 'free', 'git', 'cat', 'touch', 'view', 'rmdir', 'dir', 'md', 'del', 'rd', 'copy', 'move', 'ren', 'rename', 'go', 'enter', 'navigate', 'display', 'check', 'initialize', 'commit', 'generate', 'remove', 'get', 'rid', 'tell', 'print', 'duplicate', 'make', 'show', 'list', 'change', 'delete', 'grep', 'find', 'filter', 'chmod', 'ping', 'uptime', 'ifconfig', 'ipconfig', 'env', 'wc', 'head', 'tail', 'curl', 'wget', 'tar', 'zip', 'unzip'} |
    HINGLISH_COMMAND_VERBS
)

ENTITY_IGNORE_WORDS = (
    STOP_WORDS | HINGLISH_STOP_WORDS | COMMAND_VERBS |
    {'file', 'folder', 'directory', 'named', 'with',
     'from', 'a', 'the', 'me', 'my', 'please', 'using',
     'via', 'contents', 'empty', 'new', 'working', 'one', 'level', 'up',
     'current', 'everything', 'here', 'this', 'all', 'running', 'now', 'is',
     'are', 'system', 'location', 'arguments', 'text', 'hey',
     'lines', 'python', 'script', 'backup', 'user', 'interfaces', 'called'}
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
    'uptime', 'ifconfig', 'ipconfig', 'env', 'curl', 'wget', 'tar', 'zip', 'unzip'
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
        if token_idx > 0 and doc[token_idx-1].lower_ in {"ps", "df", "free", "ls", "grep", "find", "tail", "head", "wc"}:
             return True
        return False
    return token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
        token_lower in ARG_SPLIT_KEYWORDS

def _is_valid_continuation_of_entity_phrase(token_lower, token_text):
    if token_lower in ARG_SPLIT_KEYWORDS: return True
    return token_lower not in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING or \
           any(c in token_text for c in './\\0123456789"') or \
           token_text in ['..', '~'] or token_text.endswith('"') or token_text.endswith("'")


def extract_relevant_entities(doc_for_entities, text_for_extraction):
    entities_with_spans = []
    if text_for_extraction is None: text_for_extraction = ""

    processed_char_indices = [False] * len(text_for_extraction)
    doc_tokens = list(doc_for_entities)

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
                    if token_lower in ENTITY_IGNORE_WORDS: mark_processed(token.idx, token.idx + len(token.text))
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
            any(char.isdigit() for char in entity) or len(entity)>2 or
            (entity.startswith('"') and entity.endswith('"')) or
            (entity.startswith("'") and entity.endswith("'")) or
            '*' in entity
        )

        if entity_lower in COMMAND_VERBS and not is_path_like_or_num_or_long_or_quoted_or_wild and entity_lower not in ARG_SPLIT_KEYWORDS:
            continue
        if entity_lower in ENTITY_IGNORE_WORDS_FOR_PHRASE_BUILDING and not is_path_like_or_num_or_long_or_quoted_or_wild:
            if not entity.isdigit():
                continue

        is_fuzzy_keyword = False
        for keyword in fuzzy_check_list_args:
            if fuzz.ratio(entity_lower, keyword) > ENTITY_FILTER_FUZZY_THRESHOLD + 5:
                 looks_like_arg_f = (any(char.isdigit() for char in entity) or '/' in entity or '\\' in entity or '.' in entity or entity in ['..', '~'] or '*' in entity or (entity.startswith('"') and entity.endswith('"')))
                 if not looks_like_arg_f:
                      is_fuzzy_keyword = True; break
        if is_fuzzy_keyword: continue

        if entity: final_filtered_entities.append(entity)

    seen = set()
    unique_entities = [x for x in final_filtered_entities if not (x.lower() in seen or seen.add(x.lower()))]
    # print(f"Debug (extract_entities from '{text_for_extraction}'): Final entities: {unique_entities}")
    return unique_entities


def select_primary_argument(args_list, action_id=None, current_text_segment=""):
    if not args_list: return None
    original_text_lower = current_text_segment.lower()

    if "naam" in original_text_lower:
        match_before = re.search(r"(.+?)\s+naam\s+se", original_text_lower)
        match_after = re.search(r"naam\s+ka\s+(.+)", original_text_lower)
        potential_arg_text = None
        if match_before:
            potential_arg_text = match_before.group(1).strip().split()[-1]
        elif match_after:
            potential_arg_text = match_after.group(1).strip().split()[0]

        if potential_arg_text:
            for arg_in_list in args_list:
                if potential_arg_text == arg_in_list.lower() or potential_arg_text == arg_in_list:
                     if arg_in_list not in HINGLISH_STOP_WORDS and arg_in_list not in HINGLISH_COMMAND_VERBS:
                        return arg_in_list

    for arg_candidate in args_list:
        if (arg_candidate.startswith('"') and arg_candidate.endswith('"')) or \
           (arg_candidate.startswith("'") and arg_candidate.endswith("'")):
            return arg_candidate.strip("\"'")
        if '/' in arg_candidate or '\\' in arg_candidate or '.' in arg_candidate or arg_candidate in ['..', '~'] or '*' in arg_candidate:
            return arg_candidate

    selection_ignore_words = ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS - COMMAND_VERBS

    for arg_candidate in reversed(args_list):
        if arg_candidate.lower() not in selection_ignore_words:
            return arg_candidate

    if args_list: return args_list[-1].strip()
    return None


def _parse_single_command_segment(text_segment, is_part_of_pipe=False):
    text_lower_segment = text_segment.lower().strip()
    if not text_lower_segment: return None

    action_id, initial_args_str_segment = None, ""
    suggestion_action_id, suggestion_phrase, matched_phrase_for_intent = None, None, None
    matched_direct = False
    args = []

    direct_commands = {
        'cd ': 'change_directory', 'ls': 'list_files', 'pwd': 'show_path',
        'rm ': 'delete_file', 'rmdir ': 'delete_directory', 'mkdir ': 'make_directory',
        'mv ': 'move_rename', 'cp ': 'copy_file', 'cat ': 'display_file',
        'touch ': 'create_file', 'whoami': 'whoami', 'df ': 'disk_usage', 'df': 'disk_usage',
        'free ': 'memory_usage', 'free': 'memory_usage',
        'ps ': 'show_processes', 'ps': 'show_processes',
        'git status': 'git_status', 'git init': 'git_init', 'git commit ': 'git_commit',
        'grep ': 'grep', 'chmod ': 'chmod', 'ping ': 'ping',
        'tail ': 'display_file_tail', 'head ': 'display_file_head', 'wc ': 'raw_command',
        'env': 'env_variables', 'ifconfig': 'network_interfaces', 'ipconfig': 'network_interfaces', 'uptime': 'system_uptime'
    }
    for cmd_prefix_key, mapped_action in direct_commands.items():
        cmd_prefix_lower = cmd_prefix_key.lower()
        if text_lower_segment.startswith(cmd_prefix_lower):
            if mapped_action == 'raw_command':
                try:
                    shlex_parts = shlex.split(text_segment)
                    if shlex_parts: return {'type': 'raw_command', 'command': shlex_parts[0], 'args': shlex_parts[1:], 'segment_text': text_segment}
                except ValueError: pass
                break

            if not cmd_prefix_lower.endswith(' ') and text_lower_segment != cmd_prefix_lower:
                continue
            action_id, initial_args_str_segment = mapped_action, text_segment[len(cmd_prefix_key):].strip()
            matched_direct, matched_phrase_for_intent = True, cmd_prefix_key.strip()

            if action_id == 'delete_file' and ('-r' in initial_args_str_segment.lower() or '-rf' in initial_args_str_segment.lower()):
                action_id = 'delete_directory'
            break

    if not action_id:
        try:
            shlex_parts_check = shlex.split(text_segment)
            if shlex_parts_check:
                first_word_lower = shlex_parts_check[0].lower()
                if is_part_of_pipe and first_word_lower in COMMON_SHELL_CMDS:
                    return {'type': 'raw_command', 'command': shlex_parts_check[0], 'args': shlex_parts_check[1:], 'segment_text': text_segment}

                preemptive_nlp_action = None
                for phrase_kw, act_id_kw in ACTION_KEYWORDS.items():
                    if phrase_kw.lower() == first_word_lower:
                        preemptive_nlp_action = act_id_kw
                        break

                if preemptive_nlp_action and first_word_lower == text_lower_segment:
                    action_id = preemptive_nlp_action
                    matched_phrase_for_intent = first_word_lower
                    args_text_to_parse = ""
                elif first_word_lower in COMMON_SHELL_CMDS:
                    is_nlp_phrase_match = False
                    if not action_id:
                        temp_fuzzy_matches = process.extractOne(text_lower_segment, ACTION_KEYWORDS.keys(), scorer=fuzz.WRatio, score_cutoff=FUZZY_MATCH_THRESHOLD_EXECUTE + 5)
                        if temp_fuzzy_matches and ACTION_KEYWORDS[temp_fuzzy_matches[0]] != 'raw_command':
                            is_nlp_phrase_match = True
                    if not is_nlp_phrase_match:
                        return {'type': 'raw_shell_string', 'command_string': text_segment}
        except ValueError: pass


    if not matched_direct and not action_id:
        sorted_action_keywords_tuples = sorted(ACTION_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True)
        sorted_action_phrases = [item[0] for item in sorted_action_keywords_tuples]

        top_matches = process.extract( text_lower_segment, sorted_action_phrases,
            scorer=fuzz.WRatio, limit=5, score_cutoff=FUZZY_MATCH_THRESHOLD_SUGGEST )

        if top_matches:
            best_execute_candidate = None
            for phrase, match_score, _ in top_matches:
                if match_score >= FUZZY_MATCH_THRESHOLD_EXECUTE:
                    current_action_cand = ACTION_KEYWORDS[phrase]
                    if best_execute_candidate is None:
                        best_execute_candidate = (phrase, match_score, current_action_cand)
                    else:
                        is_current_constructive = current_action_cand in ["make_directory", "create_file", "make_executable"]
                        is_best_constructive = best_execute_candidate[2] in ["make_directory", "create_file", "make_executable"]
                        is_current_info = current_action_cand in ["show_path", "list_files", "whoami", "git_status", "show_processes", "disk_usage", "memory_usage", "system_uptime", "network_interfaces", "env_variables", "display_file", "display_file_head", "display_file_tail", "count_lines"]
                        is_best_info = best_execute_candidate[2] in ["show_path", "list_files", "whoami", "git_status", "show_processes", "disk_usage", "memory_usage", "system_uptime", "network_interfaces", "env_variables", "display_file", "display_file_head", "display_file_tail", "count_lines"]

                        contains_folder_kw = any(kw in text_lower_segment for kw in ["folder", "directory", "dir", "banao"])
                        contains_file_kw = any(kw in text_lower_segment for kw in ["file", "nai", "khali", ".py", ".txt", ".js", ".sh", ".md", ".json"])
                        contains_path_kw = any(kw in text_lower_segment for kw in ["path", "kahan", "directory", "folder", "where", "kis folder", "current folder", "konsa folder", "andar hoon", "location", "jagah"])
                        contains_list_kw = any(kw in text_lower_segment for kw in ["list", "show", "kya kya", "cheezein", "dikhao", "andar kya hai", "files", "content"]) and not contains_file_kw
                        contains_executable_kw = "executable" in text_lower_segment
                        contains_remove_kw = any(kw in text_lower_segment for kw in ["remove", "delete", "hatao", "rm"])
                        contains_move_rename_kw = any(verb in text_lower_segment for verb in ["move ", "mv ", "rename ", "naam badlo"])


                        if match_score > best_execute_candidate[1]:
                            best_execute_candidate = (phrase, match_score, current_action_cand)
                        elif match_score == best_execute_candidate[1]:
                            context_score_current = 0
                            context_score_best = 0

                            if is_current_info:
                                if current_action_cand == "show_path" and contains_path_kw: context_score_current = 2
                                elif current_action_cand == "list_files" and contains_list_kw: context_score_current = 1
                                elif current_action_cand == "display_file" and contains_file_kw and not contains_list_kw : context_score_current = 3
                            elif is_current_constructive:
                                if current_action_cand == "make_directory" and contains_folder_kw: context_score_current = 3
                                elif current_action_cand == "create_file" and contains_file_kw: context_score_current = 3
                                elif current_action_cand == "make_executable" and contains_executable_kw: context_score_current = 3
                            elif current_action_cand == "delete_file" and contains_remove_kw and contains_file_kw : context_score_current = 2
                            elif current_action_cand == "delete_directory" and contains_remove_kw and contains_folder_kw : context_score_current = 2
                            elif current_action_cand == "move_rename" and contains_move_rename_kw : context_score_current = 4 # Higher score for move/rename
                            elif current_action_cand == "change_directory" and ("change to" in text_lower_segment or "cd " in text_lower_segment or "go to" in text_lower_segment) and contains_path_kw: context_score_current = 4


                            if is_best_info:
                                if best_execute_candidate[2] == "show_path" and contains_path_kw: context_score_best = 2
                                elif best_execute_candidate[2] == "list_files" and contains_list_kw: context_score_best = 1
                                elif best_execute_candidate[2] == "display_file" and contains_file_kw and not contains_list_kw: context_score_best = 3
                            elif is_best_constructive:
                                if best_execute_candidate[2] == "make_directory" and contains_folder_kw: context_score_best = 3
                                elif best_execute_candidate[2] == "create_file" and contains_file_kw: context_score_best = 3
                                elif best_execute_candidate[2] == "make_executable" and contains_executable_kw: context_score_best = 3
                            elif best_execute_candidate[2] == "delete_file" and contains_remove_kw and contains_file_kw : context_score_best = 2
                            elif best_execute_candidate[2] == "delete_directory" and contains_remove_kw and contains_folder_kw : context_score_best = 2
                            elif best_execute_candidate[2] == "move_rename" and contains_move_rename_kw : context_score_best = 4
                            elif best_execute_candidate[2] == "change_directory" and ("change to" in text_lower_segment or "cd " in text_lower_segment or "go to" in text_lower_segment) and contains_path_kw: context_score_best = 4


                            if context_score_current > context_score_best:
                                best_execute_candidate = (phrase, match_score, current_action_cand)
                            elif context_score_current == context_score_best and len(phrase) > len(best_execute_candidate[0]):
                                 best_execute_candidate = (phrase, match_score, current_action_cand)

            if best_execute_candidate:
                action_id = best_execute_candidate[2]
                matched_phrase_for_intent = best_execute_candidate[0]

                # Heuristic for move/rename: if these keywords are present and the current action isn't already a destructive one or move/rename
                if (action_id not in ['move_rename', 'delete_file', 'delete_directory']) and \
                   any(verb in text_lower_segment for verb in ["move ", "mv ", "rename "]):
                    move_rename_candidate_details = next(((p, s, ACTION_KEYWORDS[p]) for p,s,_ in top_matches if ACTION_KEYWORDS[p] == 'move_rename'), None)
                    if move_rename_candidate_details:
                        move_rename_candidate_phrase = move_rename_candidate_details[0]
                        temp_args_text_to_parse_mv = text_segment
                        if text_lower_segment.startswith(move_rename_candidate_phrase.lower()):
                            temp_args_text_to_parse_mv = text_segment[len(move_rename_candidate_phrase):].strip()
                        temp_doc_mv = nlp(temp_args_text_to_parse_mv)
                        temp_args_mv = extract_relevant_entities(temp_doc_mv, temp_args_text_to_parse_mv)
                        if len(temp_args_mv) >= 2:
                            action_id = 'move_rename'
                            matched_phrase_for_intent = move_rename_candidate_phrase
                            args_text_to_parse = temp_args_text_to_parse_mv

                # Heuristic for delete if current action is move_rename but delete keywords are present
                if action_id == 'move_rename' and any(verb in text_lower_segment for verb in ["remove ", "delete ", "rm "]):
                    delete_file_cand_phrase = next((p for p,s,a_id in [(m[0], m[1], ACTION_KEYWORDS[m[0]]) for m in top_matches] if a_id == 'delete_file'), None)
                    delete_dir_cand_phrase = next((p for p,s,a_id in [(m[0], m[1], ACTION_KEYWORDS[m[0]]) for m in top_matches] if a_id == 'delete_directory'), None)
                    chosen_delete_action, chosen_delete_phrase = None, None
                    if delete_file_cand_phrase and delete_dir_cand_phrase:
                        if "folder" in text_lower_segment or "directory" in text_lower_segment: chosen_delete_action, chosen_delete_phrase = 'delete_directory', delete_dir_cand_phrase
                        else: chosen_delete_action, chosen_delete_phrase = 'delete_file', delete_file_cand_phrase
                    elif delete_file_cand_phrase: chosen_delete_action, chosen_delete_phrase = 'delete_file', delete_file_cand_phrase
                    elif delete_dir_cand_phrase: chosen_delete_action, chosen_delete_phrase = 'delete_directory', delete_dir_cand_phrase
                    if chosen_delete_action:
                        action_id = chosen_delete_action
                        matched_phrase_for_intent = chosen_delete_phrase
                        if text_lower_segment.startswith(matched_phrase_for_intent.lower()):
                             args_text_to_parse = text_segment[len(matched_phrase_for_intent):].strip()
                        else:
                             args_text_to_parse = text_segment
            elif top_matches:
                suggestion_phrase = top_matches[0][0]
                suggestion_action_id = ACTION_KEYWORDS[suggestion_phrase]

    current_eval_action = action_id if action_id else suggestion_action_id
    args_text_to_parse = text_segment

    if action_id:
        if matched_direct:
            args_text_to_parse = initial_args_str_segment
        elif matched_phrase_for_intent:
            special_arg_extraction_phrases = {
                "search for 'import' in all python files": lambda txt, phr: (["import", "*.py"], ""),
                "Please show me the contents of the main script": lambda txt, phr: (["main.py"], ""),
                "find files containing": lambda txt, phr: ([txt[len(phr):].strip().strip("'\""), "."], ""),
                "show first 5 lines of": lambda txt, phr: (
                    [next((s for s in txt.split("lines of")[0].strip().split() if s.isdigit()), "5") if "lines of" in txt else "5",
                     txt.split("lines of")[1].strip() if "lines of" in txt else txt[len(phr):].strip()], ""
                ),
                "show last 10 lines of": lambda txt, phr: (
                    [next((s for s in txt.split("lines of")[0].strip().split() if s.isdigit()), "10") if "lines of" in txt else "10",
                     txt.split("lines of")[1].strip() if "lines of" in txt else txt[len(phr):].strip()], ""
                ),
                "count lines in": lambda txt, phr: ([txt[len(phr):].strip()], ""), # Arg is filename
                "count lines": lambda txt, phr: ([txt[len(phr):].strip() if txt[len(phr):].strip() else "."], "") # Arg is filename or .
            }
            if matched_phrase_for_intent in special_arg_extraction_phrases:
                args_tuple = special_arg_extraction_phrases[matched_phrase_for_intent](text_segment, matched_phrase_for_intent)
                args = list(args_tuple[0])
                args_text_to_parse = args_tuple[1]
                args = [str(a).strip() for a in args if a is not None and str(a).strip() != ""]
            elif text_lower_segment.startswith(matched_phrase_for_intent.lower()):
                args_text_to_parse = text_segment[len(matched_phrase_for_intent):].strip()

    if args_text_to_parse != "" or not args:
        doc_for_args_extraction = nlp(args_text_to_parse if args_text_to_parse is not None else "")
        extracted_entities = extract_relevant_entities(doc_for_args_extraction, args_text_to_parse if args_text_to_parse is not None else "")
        if not args:
            args = extracted_entities

    if action_id == 'list_files':
        temp_doc_for_heuristic = nlp(text_segment)
        temp_args_for_heuristic = extract_relevant_entities(temp_doc_for_heuristic, text_segment)
        primary_arg_for_heuristic = select_primary_argument(temp_args_for_heuristic, action_id, text_segment)
        if primary_arg_for_heuristic:
            filename_pattern = r"(\w+\.\w+)"
            is_dot_command = primary_arg_for_heuristic in ['.', '..']
            contains_dot = '.' in primary_arg_for_heuristic
            if (re.search(filename_pattern, primary_arg_for_heuristic) or (contains_dot and not primary_arg_for_heuristic.startswith('.'))) and not is_dot_command:
                action_id = 'display_file'
                matched_phrase_for_intent = "display file"
                suggestion_action_id, suggestion_phrase, matched_direct = None, None, False
                args = [primary_arg_for_heuristic]
                args_text_to_parse = ""

    if action_id is None:
        if suggestion_action_id is not None:
            if is_part_of_pipe:
                try:
                    shlex_parts_sugg = shlex.split(text_segment)
                    if shlex_parts_sugg and shlex_parts_sugg[0].lower() in COMMON_SHELL_CMDS:
                        return {'type': 'raw_command', 'command': shlex_parts_sugg[0], 'args': shlex_parts_sugg[1:], 'segment_text': text_segment}
                except ValueError: pass
            full_segment_doc = nlp(text_segment)
            suggestion_args = extract_relevant_entities(full_segment_doc, text_segment)
            return {'action': 'suggest_segment', 'suggestion_action_id': suggestion_action_id,
                    'suggestion_phrase': suggestion_phrase, 'args': suggestion_args}
        else:
            if is_part_of_pipe:
                try:
                    shlex_parts = shlex.split(text_segment)
                    if shlex_parts and shlex_parts[0].lower() in COMMON_SHELL_CMDS:
                         return {'type': 'raw_command', 'command': shlex_parts[0], 'args': shlex_parts[1:], 'segment_text': text_segment}
                except ValueError: pass
            return {'action': 'unrecognized_segment', 'segment_text': text_segment}

    parsed_args = []
    NO_ARG_ACTIONS = {'show_path', 'whoami', 'git_status', 'git_init', 'system_uptime', 'network_interfaces', 'env_variables'}
    OPT_ARG_ACTIONS = {'show_processes', 'disk_usage', 'memory_usage', 'list_files'}

    if action_id == 'change_directory':
        if matched_phrase_for_intent and matched_phrase_for_intent.lower() in ["go up one level", "go back", "cd ..", "ek level peeche", "peeche jao", "ek level upar", "go to parent directory"]:
            parsed_args = ['..']
        elif matched_phrase_for_intent and matched_phrase_for_intent.lower() in ["change to home directory", "cd ~", "ghar jao", "navigate to home directory"]:
            parsed_args = ['~']
        else:
            selected_arg = select_primary_argument(args, action_id, text_segment)
            if selected_arg:
                home_path_variants = {'home', '~', 'ghar'}; actual_home_for_comp = os.path.expanduser("~")
                if selected_arg.lower() in home_path_variants or selected_arg == actual_home_for_comp or selected_arg == '~': parsed_args = ['~']
                elif selected_arg == '..': parsed_args = ['..']
                else: parsed_args = [selected_arg]
            else:
                if not args and not (matched_direct and not initial_args_str_segment): parsed_args = ['~']
                else: parsed_args = []
    elif action_id in NO_ARG_ACTIONS:
        parsed_args = []
    elif action_id in OPT_ARG_ACTIONS:
        if action_id == 'list_files':
            if matched_direct and matched_phrase_for_intent.lower() == 'ls' and initial_args_str_segment:
                try: parsed_args = shlex.split(initial_args_str_segment)
                except ValueError: parsed_args = [initial_args_str_segment]
            else:
                is_general_hinglish_list_query = any(kw in text_lower_segment for kw in
                                                    ["kya kya", "cheezein", "andar kya hai", "dikhao", "batao", "folder mein kya", "current folder mein kya", "is folder mein kya", "saare python files dikha do"])
                if not args:
                    parsed_args = []
                elif (len(args) <= 2 and all(fuzz.ratio(arg.lower(), "ls") > 70 or fuzz.ratio(arg.lower(), "list") > 70 or arg.lower() in {"files", "file", "directory", "directories"} for arg in args)) and \
                     not any('/' in arg or '.' in arg or '\\' in arg or arg == '..' or arg == '~' or arg.startswith('-') for arg in args):
                    if args: print(f"Debug (Segment): Clearing noisy command-like args for 'list_files': {args}")
                    parsed_args = []
                elif is_general_hinglish_list_query and not any(arg_item for arg_item in args if '.' in arg_item or '/' in arg_item or '\\' in arg_item):
                    if args: print(f"Debug (Segment): Clearing all args for general Hinglish 'list_files' query. Original NLP args: {args}")
                    parsed_args = []
                else:
                    parsed_args = args
        elif matched_direct and initial_args_str_segment:
            try: parsed_args = shlex.split(initial_args_str_segment)
            except ValueError: parsed_args = [initial_args_str_segment]
        else:
            parsed_args = args

    elif action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file', 'make_executable', 'count_lines']:
        if args and (action_id == 'display_file' or action_id == 'count_lines') and args_text_to_parse == "":
            parsed_args = args
        else:
            selected_arg = select_primary_argument(args, action_id, text_segment)
            if selected_arg: parsed_args = [selected_arg]
            else:
                if args and action_id == 'display_file' and len(args) == 1 and not any(kw in args[0] for kw in COMMAND_VERBS | ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS):
                     parsed_args = args
                elif matched_direct and not initial_args_str_segment and action_id not in ['make_executable']:
                     return {'action': 'error', 'message': f"Missing argument for {action_id}"}
                elif not args and action_id not in ['make_executable']:
                     return {'action': 'error', 'message': f"Missing argument for {action_id}"}
                else: parsed_args = []


    elif action_id in ['display_file_head', 'display_file_tail']:
        if args and args_text_to_parse == "":
            if len(args) == 2 and args[0].isdigit():
                parsed_args = args
            elif len(args) == 1:
                if args[0].isdigit():
                     return {'action': 'error', 'message': f"Missing filename for {action_id} with lines {args[0]}"}
                parsed_args = args
            else:
                 return {'action': 'error', 'message': f"Incorrect arguments for {action_id} from special phrase: {args}"}

        elif args:
            if len(args) >= 2 and args[0].isdigit():
                parsed_args = [args[0], select_primary_argument(args[1:], action_id, text_segment) or " ".join(args[1:])]
            elif len(args) >= 1:
                if args[0] == '-n' and len(args) > 2 and args[1].isdigit():
                    parsed_args = [args[1], select_primary_argument(args[2:], action_id, text_segment) or " ".join(args[2:])]
                elif args[0].startswith('-') and args[0][1:].isdigit() and len(args) > 1:
                    parsed_args = [args[0][1:], select_primary_argument(args[1:], action_id, text_segment) or " ".join(args[1:])]
                else:
                    parsed_args = [select_primary_argument(args, action_id, text_segment) or args[0]]
            else:
                if matched_direct and initial_args_str_segment:
                     parsed_args = shlex.split(initial_args_str_segment) if initial_args_str_segment else []
                     if not parsed_args : return {'action': 'error', 'message': f"Missing arguments for {action_id}"}
                else: return {'action': 'error', 'message': f"Missing filename for {action_id}"}
        else:
            if matched_direct and initial_args_str_segment:
                 parsed_args = shlex.split(initial_args_str_segment) if initial_args_str_segment else []
                 if not parsed_args : return {'action': 'error', 'message': f"Missing arguments for {action_id}"}
            else: return {'action': 'error', 'message': f"Missing filename for {action_id}"}


    elif action_id == 'grep':
        if matched_direct and matched_phrase_for_intent.lower() == 'grep ':
            try: parsed_args = shlex.split(initial_args_str_segment) if initial_args_str_segment else []
            except ValueError: parsed_args = [initial_args_str_segment] if initial_args_str_segment else []
        elif args:
            if args_text_to_parse == "" and len(args) >= 1:
                parsed_args = [arg.strip("'\"") for arg in args]
            else:
                pattern_cand, file_cand, remaining_args_grep = None, None, list(args)
                for i, arg_val in enumerate(remaining_args_grep):
                    if (arg_val.startswith('"') and arg_val.endswith('"')) or \
                       (arg_val.startswith("'") and arg_val.endswith("'")):
                        pattern_cand = arg_val
                        remaining_args_grep.pop(i)
                        break
                if not pattern_cand and remaining_args_grep:
                    for i, arg_val in enumerate(remaining_args_grep):
                        if not ('.' in arg_val or '/' in arg_val or '\\' in arg_val or arg_val in ['..','~'] or '*' in arg_val or arg_val.startswith('-')):
                            pattern_cand = arg_val
                            remaining_args_grep.pop(i)
                            break
                if not pattern_cand and args: pattern_cand = args[0]; remaining_args_grep = args[1:] if len(args)>1 else []

                if remaining_args_grep: file_cand = " ".join(remaining_args_grep)
                elif pattern_cand and not is_part_of_pipe: file_cand = "."

                if pattern_cand and file_cand: parsed_args = [pattern_cand.strip("'\""), file_cand.strip("'\"")]
                elif pattern_cand: parsed_args = [pattern_cand.strip("'\"")]
                else:
                    if not is_part_of_pipe: return {'action': 'error', 'message': 'Grep pattern required'}
                    parsed_args = []
        elif not is_part_of_pipe:
             return {'action': 'error', 'message': 'Grep pattern and/or arguments required'}
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
                # Try to identify permission string (numeric or symbolic) vs target
                # This assumes permission string often comes first or is distinctly formatted
                if re.match(r"^[0-7]{3,4}$|^[ugoa]*[-+=][rwxXstugo]*$", clean_cand_args[0]):
                    perm_arg = clean_cand_args[0]
                    target_arg = select_primary_argument(clean_cand_args[1:], action_id, text_segment) or " ".join(clean_cand_args[1:])
                elif re.match(r"^[0-7]{3,4}$|^[ugoa]*[-+=][rwxXstugo]*$", clean_cand_args[1]): # If second arg is permission
                    perm_arg = clean_cand_args[1]
                    target_arg = clean_cand_args[0]
                else: # Fallback
                    perm_arg = clean_cand_args[0]
                    target_arg = " ".join(clean_cand_args[1:])

                if perm_arg and target_arg: parsed_args = [perm_arg, target_arg]
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
                            source = select_primary_argument(source_parts, action_id, text_segment) or " ".join(source_parts)
                            destination = select_primary_argument(dest_parts, action_id, text_segment) or " ".join(dest_parts)
                            if source and destination: split_found_keyword = True; break
                if not split_found_keyword:
                    source = clean_cand_args[0]
                    destination = " ".join(clean_cand_args[1:]) if len(clean_cand_args) > 1 else None
                    if len(clean_cand_args) > 2 and destination: # If "move file1 file2 file3", source=file1, dest=file2 file3
                         # This needs more robust splitting if no keyword. Assume first is source, second is dest for now.
                         destination = clean_cand_args[1] # Take only the immediate next as destination
                         # Any further args would be problematic for simple mv/cp

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
                commit_msg_parts = []
                potential_msg_started = False
                for arg_val in args:
                    if arg_val.lower() not in (ENTITY_IGNORE_WORDS - ARG_SPLIT_KEYWORDS - COMMAND_VERBS - {"-m"}) or \
                       (arg_val.startswith('"') and arg_val.endswith('"')) or \
                       (arg_val.startswith("'") and arg_val.endswith("'")) or \
                       potential_msg_started:
                        commit_msg_parts.append(arg_val.strip("'\""))
                        potential_msg_started = True
                if not commit_msg_parts and args: commit_msg_parts = args
                if commit_msg_parts: fallback_msg = " ".join(commit_msg_parts)

            if fallback_msg: parsed_args = ["-m", fallback_msg]
            else: return {'action': 'error', 'message': 'Commit message required'}
    else:
         parsed_args = args

    # print(f"Debug (Segment): Final parsed_args for action '{action_id}': {parsed_args}")
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
                return {'type': 'raw_shell_string', 'command_string': original_text}

        pipe_segments_raw = []
        current_text_to_split = original_text
        while True:
            nl_pipe_match = NL_PIPE_PATTERN.search(current_text_to_split)
            if nl_pipe_match:
                first_segment = current_text_to_split[:nl_pipe_match.start()].strip()
                if first_segment:
                    if '|' in first_segment: pipe_segments_raw.extend(s.strip() for s in first_segment.split('|') if s.strip())
                    else: pipe_segments_raw.append(first_segment)
                current_text_to_split = current_text_to_split[nl_pipe_match.end():].strip()
                if not current_text_to_split: break
            else:
                if current_text_to_split:
                    if '|' in current_text_to_split: pipe_segments_raw.extend(s.strip() for s in current_text_to_split.split('|') if s.strip())
                    else: pipe_segments_raw.append(current_text_to_split)
                break
        if not pipe_segments_raw and original_text: pipe_segments_raw = [original_text]
        pipe_segments = [s.strip() for s in pipe_segments_raw if s.strip()]

        if len(pipe_segments) > 1:
            parsed_commands_list = []
            for i, segment_text in enumerate(pipe_segments):
                segment_result = _parse_single_command_segment(segment_text, is_part_of_pipe=True)
                if segment_result and segment_result.get('action') == 'suggest_segment':
                    return {'action': 'error', 'message': f"Ambiguous command '{segment_result.get('suggestion_phrase')}' in pipe: '{segment_text}'"}
                if not segment_result or segment_result.get('action') in ['unrecognized_segment', 'error']:
                    if segment_result and segment_result.get('action') == 'unrecognized_segment':
                        try:
                            shlex_parts = shlex.split(segment_text)
                            if shlex_parts: segment_result = {'type': 'raw_command', 'command': shlex_parts[0], 'args': shlex_parts[1:], 'segment_text': segment_text}
                            else: return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - Unrecognized & could not split"}
                        except ValueError: return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - Unrecognized & shlex failed"}
                    elif segment_result and segment_result.get('type') == 'raw_shell_string':
                        try:
                            shlex_parts_raw = shlex.split(segment_result['command_string'])
                            segment_result = {'type': 'raw_command', 'command': shlex_parts_raw[0], 'args': shlex_parts_raw[1:], 'segment_text': segment_result['command_string']}
                        except:
                             return {'action': 'error', 'message': f"Error in pipe: Could not process raw segment '{segment_result['command_string']}'"}
                    else:
                        error_msg = segment_result.get('message', "Unknown error") if segment_result else "Unknown error"
                        return {'action': 'error', 'message': f"Error in pipe: '{segment_text}' - {error_msg}"}

                if segment_result.get('type') == 'raw_command': parsed_commands_list.append(segment_result)
                elif segment_result.get('type') == 'raw_shell_string':
                     return {'action': 'error', 'message': f"Error in pipe: Unexpected raw_shell_string type for segment '{segment_text}'"}
                else: parsed_commands_list.append({'action': segment_result['action'], 'args': segment_result.get('args', [])})

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
         print(f"❌❌❌ TOP LEVEL PARSER FUNCTION CRASHED! ❌❌❌ Text: '{text}', Error: {e}")
         traceback.print_exc()
         return {'action': 'error', 'message': f'Internal parser error: {type(e).__name__}'}


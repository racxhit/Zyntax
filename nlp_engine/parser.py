"""
File: parser.py
Description: Contains functions to parse natural language inputs and convert them
             into structured command representations (intents and targets).
Date Created: 05-04-2025
Last Updated: 06-04-2025
"""

import re
import spacy
from rapidfuzz import process, fuzz
from spacy.lang.en.stop_words import STOP_WORDS

# 1. Configuration
# Min score to execute directly
FUZZY_MATCH_THRESHOLD_EXECUTE = 90
# Min score to suggest a command if execution threshold is not met
FUZZY_MATCH_THRESHOLD_SUGGEST = 65

# 2. Loads spaCy Model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# 3. Define Known Actions and Mappings
ACTION_KEYWORDS = {
    # File/Directory Listing & Navigation
    "list files": "list_files", "show files": "list_files", "ls": "list_files", "display files": "list_files",
    "show current directory": "show_path", "current directory": "show_path", "where am i": "show_path", "print working directory": "show_path", "pwd": "show_path",
    "change directory": "change_directory", "move to directory": "change_directory", "go to directory": "change_directory", "cd": "change_directory",
    "change dir to": "change_directory",
    "change directory to": "change_directory",

    # Directory Creation/Deletion
    "make folder": "make_directory", "create folder": "make_directory", "make directory": "make_directory", "create directory": "make_directory", "mkdir": "make_directory", "make dir": "make_directory", "create dir": "make_directory",
    "delete folder": "delete_directory", "remove folder": "delete_directory", "delete directory": "delete_directory", "remove directory": "delete_directory", "delete dir": "delete_directory", "remove dir": "delete_directory", "rmdir": "delete_directory",

    # File Creation/Deletion
    "create file": "create_file", "make file": "create_file", "touch file": "create_file", "new file": "create_file",
    "delete file": "delete_file", "remove file": "delete_file", "rm": "delete_file",

    # File Operations
    "display file": "display_file", "display file content": "display_file", # Specific phrases
    "show file content": "display_file", "cat file": "display_file", "view file": "display_file",
    "rename file": "move_rename", "move file": "move_rename", "mv": "move_rename",
    "copy file": "copy_file", "cp": "copy_file",

    # System Info
    "who am i": "whoami", "whoami": "whoami",

    # Git Commands
    "git status": "git_status", "check git status": "git_status",
    "initialize git": "git_init", "git init": "git_init",
    "commit changes": "git_commit", "git commit": "git_commit",

    # System Monitoring
    "show processes": "show_processes", "list processes": "show_processes", "ps": "show_processes",
    "disk usage": "disk_usage", "show disk space": "disk_usage", "df": "disk_usage",
    "memory usage": "memory_usage", "show memory": "memory_usage", "free": "memory_usage",
}


def extract_relevant_entities(doc, text):
    """
    Extracts file/folder names, paths and other arguments using
    spaCy dependency parsing and regex fallbacks, then filters them.
    """
    potential_entities = []

    # Strategy 1: spaCy Dependency Parsing (Prioritized)
    # Look for nouns/proper nouns that are objects of relevant verbs or prepositions
    possible_targets_spacy = []
    action_verb_lemmas = ["make", "create", "delete", "remove", "list", "show", "display", "cat", "touch", "change", "go", "move", "rename", "copy", "cd", "mkdir", "rm", "cp", "mv", "open", "edit"]
    preposition_lemmas = ["to", "from", "in", "into", "directory", "folder", "file"]
    name_markers = ["named", "called"]

    for token in doc:
        # Direct object of an action verb? (e.g., "make [folder]")
        if token.dep_ == "dobj" and token.head.lemma_ in action_verb_lemmas:
            possible_targets_spacy.append(token)
        # Object of a preposition connected to an action verb? (e.g., "change directory to [target]")
        elif token.dep_ == "pobj" and token.head.lemma_ in preposition_lemmas and token.head.head.lemma_ in action_verb_lemmas:
            possible_targets_spacy.append(token)
        # Object following a name marker? (e.g. "folder named [target]")
        elif token.head.lemma_ in name_markers and token.dep_ in ["oprd", "pobj", "appos"]:
            possible_targets_spacy.append(token)
        elif token.head.lemma_ in name_markers and token.i + 1 < len(doc) and doc[token.i + 1].pos_ in ["NOUN", "PROPN"]:
            possible_targets_spacy.append(doc[token.i + 1])
        # Handle simple structure like "cd [target]"
        elif token.head.lemma_ == "cd" and token.dep_ in ["dobj", "advmod", "pobj", "appos"]:
            possible_targets_spacy.append(token)

    # Consolidate spaCy targets - Combine compound nouns/names (basic attempt)
    spacy_entities_text = []
    processed_indices = set()
    for i, token in enumerate(possible_targets_spacy):
        if i in processed_indices:
            continue
        current_entity = token.text
        next_token_index = token.i + 1
        # Combine if next token seems part of the name (e.g., compound relation)
        while next_token_index < len(doc) and doc[next_token_index].dep_ == "compound" and doc[next_token_index] in possible_targets_spacy:
            current_entity += " " + doc[next_token_index].text
            # Mark the combined token index as processed if it was in our target list
            try:
                 processed_indices.add(possible_targets_spacy.index(doc[next_token_index]))
            except ValueError:
                 pass 
            next_token_index += 1
        spacy_entities_text.append(current_entity)
        processed_indices.add(i)

    potential_entities.extend(spacy_entities_text)

    # Strategy 2: Simpler Regex fallback
    # Matches quoted strings OR standalone words (potential filenames/paths)
    regex_entities = []
    # Standalone words: Alphanumeric, dots, underscores, hyphens, forward slashes
    for match in re.finditer(r"([a-zA-Z0-9_.\-/]+)|(?:[\"'](.+?)[\"'])", text):
        name = match.group(1) or match.group(2)
        if name and name.strip():
            regex_entities.append(name.strip())

    # Add regex entities only if they weren't found by spaCy (basic check)
    for rentity in regex_entities:
        if not any(rentity.lower() == sentity.lower() for sentity in potential_entities):
            potential_entities.append(rentity)

    # Filtering
    # Removes stopwords, command keywords, and words fuzzy-similar to keywords/verbs
    filtered_entities = []
    custom_stops = {'file', 'folder', 'directory', 'dir', 'named', 'called', 'with', 'name', 'to', 'from', 'a', 'the', 'in', 'on', 'at', 'make', 'create', 'delete'}
    stopwords = STOP_WORDS.union(custom_stops)
    action_verbs = set(phrase.split()[0] for phrase in ACTION_KEYWORDS.keys())
    stopwords.update(action_verbs)

    # List of critical keywords/verbs to check with fuzzy matching
    keywords_to_check_fuzzy = ['folder', 'directory', 'delete', 'create', 'file', 'rename', 'move']
    keywords_to_check_fuzzy.extend(list(action_verbs))

    fuzzy_check_threshold = 85 # Threshold for filtering based on similarity

    for entity in potential_entities:
        # Checks exact stopwords/keywords (case-insensitive)
        is_exact_stopword = entity.lower() in stopwords
        # Checks if multi-word entity consists only of stopwords
        is_multiword_stopword = all(word.lower() in stopwords for word in entity.split())

        # Checks if entity is fuzzy-similar to critical keywords/verbs
        is_fuzzy_keyword = False
        for keyword in keywords_to_check_fuzzy:
            if fuzz.ratio(entity.lower(), keyword) > fuzzy_check_threshold:
                is_fuzzy_keyword = True
                print(f"Debug: Filtered entity '{entity}' as it's too similar to keyword/verb '{keyword}' (Score > {fuzzy_check_threshold})")
                break

        # Keep the entity if it passes all checks
        if entity and not is_exact_stopword and not is_multiword_stopword and not is_fuzzy_keyword:
            filtered_entities.append(entity)

    # Remove duplicates while preserving order
    seen = set()
    unique_entities = [x for x in filtered_entities if not (x in seen or seen.add(x))]

    print(f"Debug: Extracted entities: {unique_entities}")
    return unique_entities


def parse_input(text):
    """
    Parses natural language input into a structured command dictionary
    containing 'action' and 'args'. Handles fuzzy matching and suggestions.
    """
    original_text = text
    text_lower = text.lower().strip()
    if not text_lower:
        return None

    # 1. Intent Recognition using Fuzzy Matching
    match_result = process.extractOne(
        text_lower,
        ACTION_KEYWORDS.keys(),
        scorer=fuzz.WRatio, # Using WRatio
        score_cutoff=FUZZY_MATCH_THRESHOLD_SUGGEST
    )

    action_id = None
    suggestion_action_id = None 
    suggestion_phrase = None   

    if match_result:
        matched_phrase, score, _ = match_result
        print(f"Debug: Fuzzy match: phrase='{matched_phrase}', score={score}")
        if score >= FUZZY_MATCH_THRESHOLD_EXECUTE:
            action_id = ACTION_KEYWORDS[matched_phrase]
            print(f"Debug: Matched action '{action_id}' directly.")
        elif score >= FUZZY_MATCH_THRESHOLD_SUGGEST:
            # Suggests if score is high enough, but not enough to execute
            suggestion_action_id = ACTION_KEYWORDS[matched_phrase]
            suggestion_phrase = matched_phrase
            print(f"Debug: Potential suggestion: action='{suggestion_action_id}' (phrase='{suggestion_phrase}')")

    # If no action is identified or suggested, treat as unrecognized
    if action_id is None and suggestion_action_id is None:
        print(f"Debug: No good match found for '{text_lower}'")
        return {'action': 'unrecognized'}

    # If only a suggestion was found, return suggestion structure
    if action_id is None and suggestion_action_id:
        return {'action': 'suggest', 'suggestion_action_id': suggestion_action_id, 'suggestion_phrase': suggestion_phrase}

    # 2. Entity Extraction (Only if action is identified directly)
    doc = nlp(original_text) # Process with spaCy
    args = extract_relevant_entities(doc, original_text)

    # Heuristic Override for 'show file.py' case
    # If action is list/path, but a single filename like arg exists, switch to display_file
    if action_id in ['list_files', 'show_path'] and len(args) == 1:
        filename_pattern = r"\.[a-zA-Z0-9]+$"
        if re.search(filename_pattern, args[0]) or '.' in args[0]:
            print(f"Debug: Heuristic override! Action '{action_id}' changed to 'display_file' due to filename arg '{args[0]}'.")
            action_id = 'display_file'

    # 3. Argument Refinement based on Final Action 
    parsed_args = []
    if action_id in ['make_directory', 'create_file', 'delete_file', 'delete_directory', 'display_file', 'change_directory'] and args:
        parsed_args = [args[0]] # Assumes first extracted entity is the main target
    elif action_id == 'move_rename' or action_id == 'copy_file':
        if len(args) >= 2:
            # Assumes first is source, second is destination
            parsed_args = [args[0], args[1]]
        else:
            print(f"Warning: '{action_id}' requires source and destination. Found: {args}")
            return {'action': 'error', 'message': f"Missing arguments for {action_id}"}
    elif action_id == 'git_commit':
        # Extract commit message using regex
        msg_match = re.search(r"(?:message|-m)\s+([\"'])(.+?)\1", original_text, re.IGNORECASE)
        if msg_match:
            parsed_args = ["-m", msg_match.group(2)]
        else:
            # Fallback or error for missing commit message
            print("Warning: Commit message pattern not found. Using generic message or require -m flag.")
            # Depending on desired strictness:
            # return {'action': 'error', 'message': 'Commit message required via -m "..."'}
            parsed_args = ["-m", "Generic commit via Zyntax"] # Example fallback

    # Will add more specific argument extraction/validation logic here for other commands...

    # 4. Return Structured Command
    return {
        'action': action_id,
        'args': parsed_args
    }
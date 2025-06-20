"""
File: main.py
Description: Entry point for Zyntax. Takes user input, passes it to the NLP parser,
             and executes appropriate system commands based on the parsed output.
Date Created: 05-04-2025
Last Updated: 27-05-2025
"""

import sys
import spacy
from nlp_engine.parser import parse_input
from command_executor.executor import execute_command

# Load/Download spaCy Model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    sys.stdout.flush() # Flush after print
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

print("🧠 Welcome to Zyntax - Your NLP-powered Terminal!")
print("Type 'exit' or 'quit' to leave.")
sys.stdout.flush() # Explicitly flush initial prints

while True:
    try:
        user_input = input("Zyntax> ") # This prompt is handled by input()
        if user_input.lower() in ['exit', 'quit']:
            break
        if not user_input:
            continue

        # Parse the raw user input
        structured_command = parse_input(user_input)
        sys.stdout.flush() # Flush after parsing, before printing Zyntax response

        # Basic validation of parser output
        if not structured_command:
            print("❓ Parser returned an unexpected result.")
            sys.stdout.flush()
            continue

        action = structured_command.get('action')
        command_type = structured_command.get('type')


        if action == 'unrecognized':
            print("❓ Command not recognized.")
            sys.stdout.flush()

        elif action == 'suggest':
            suggestion_phrase = structured_command.get('suggestion_phrase', 'that command')
            suggestion_action_id = structured_command.get('suggestion_action_id')
            suggested_args = structured_command.get('args', [])


            if not suggestion_action_id:
                print("❓ Suggestion error: No action ID provided.")
                sys.stdout.flush()
                continue

            try:
                # sys.stdout.write is used here for the prompt to avoid extra newline from print()
                sys.stdout.write(f"Did you mean: '{suggestion_phrase}' with args {suggested_args}? (y/n): ")
                sys.stdout.flush() # Crucial before readline
                confirmation = sys.stdin.readline().strip().lower()

                if confirmation == 'y' or confirmation == 'yes':
                    print(f"Okay, trying action '{suggestion_action_id}' with args {suggested_args}...")
                    sys.stdout.flush()
                    confirmed_command = {
                        'action': suggestion_action_id,
                        'args': suggested_args
                    }
                    execute_command(confirmed_command)
                else:
                    print("Okay, command cancelled.")
                    sys.stdout.flush()

            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                sys.stdout.flush()
                break
            except Exception as e:
                print(f"Error processing suggestion: {e}")
                sys.stdout.flush()

        elif action == 'error':
            print(f"❗ Error: {structured_command.get('message', 'Parser error')}")
            sys.stdout.flush()

        elif command_type == 'raw_shell_string':
            print(f"Info: Executing as raw shell string due to redirection or complexity.")
            sys.stdout.flush()
            execute_command(structured_command)

        else:
            execute_command(structured_command)

        sys.stdout.flush() # Ensure all output for a command is sent

    except EOFError:
        print()
        sys.stdout.flush()
        break
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.stdout.flush()
        break

print("\nGoodbye!")
sys.stdout.flush()

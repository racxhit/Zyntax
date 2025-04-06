"""
File: main.py
Description: Entry point for Zyntax. Takes user input, passes it to the NLP parser,
             and executes appropriate system commands based on the parsed output.
Date Created: 05-04-2025
Last Updated: 06-04-2025  
"""

import sys
import spacy
from nlp_engine.parser import parse_input, extract_relevant_entities
from command_executor.executor import execute_command

# Load/Download spaCy Model 
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

print("🧠 Welcome to Zyntax - Your NLP-powered Terminal!")
print("Type 'exit' or 'quit' to leave.")

while True:
    try:
        user_input = input("Zyntax> ")
        if user_input.lower() in ['exit', 'quit']:
            break
        if not user_input:
            continue

        # Parse the raw user input
        structured_command = parse_input(user_input)

        # Basic validation of parser output
        if not structured_command:
            print("❓ Parser returned an unexpected result.")
            continue

        action = structured_command.get('action')

        # Handle different actions from the parser
        if action == 'unrecognized':
            print("❓ Command not recognized.")

        elif action == 'suggest':
            # Handle cases where the parser suggests a command
            suggestion_phrase = structured_command.get('suggestion_phrase', 'that command')
            suggestion_action_id = structured_command.get('suggestion_action_id')

            if not suggestion_action_id:
                print("❓ Suggestion error: No action ID provided.")
                continue

            try:
                # Ask user for confirmation
                sys.stdout.write(f"Did you mean: '{suggestion_phrase}'? (y/n): ")
                sys.stdout.flush()
                confirmation = sys.stdin.readline().strip().lower()

                if confirmation == 'y' or confirmation == 'yes':
                    # Executes the suggested action
                    print(f"Okay, trying action '{suggestion_action_id}'...")

                    # Re-extract entities from the original input for the suggested action
                    doc = nlp(user_input)
                    # Ensures extract_relevant_entities is imported correctly above
                    args = extract_relevant_entities(doc, user_input)

                    # Create the command structure with the *suggested* action
                    confirmed_command = {
                        'action': suggestion_action_id,
                        'args': args
                    }
                    # Executes the confirmed command
                    execute_command(confirmed_command)

                else:
                    print("Okay, command cancelled.")

            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break # Exit main loop on Ctrl+D/Ctrl+C during prompt
            except NameError:
                # Fallback if nlp object or extract function wasn't available
                print("Error: Could not re-process input for suggestion. Please re-type command.")
            except Exception as e:
                print(f"Error processing suggestion: {e}")

        elif action == 'error':
            # Handle specific errors reported by the parser
            print(f"❗ Error: {structured_command.get('message', 'Parser error')}")

        else:
            # Execute a directly recognized command
            execute_command(structured_command)
        # End of action handling

    except EOFError: # Handles Ctrl+D with Goodbye!
        print()
        break
    except KeyboardInterrupt: # Handles Ctrl+C with Goodbye!
        print("\nExiting...")
        break

print("\nGoodbye!")
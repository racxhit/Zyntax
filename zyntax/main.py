"""
Zyntax - A smart NLP-powered terminal for natural language command execution.
"""

import sys
import os
import traceback
import spacy
from .nlp_engine.parser import parse_input
from .command_executor.executor import execute_command

IS_UNDER_TEST_RUNNER = os.environ.get("ZYNTAX_TEST_MODE") == "1"

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model en_core_web_sm...")
    sys.stdout.flush()
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def main():
    """Main entry point for Zyntax CLI."""
    print("🚀 Zyntax - Natural Language Terminal")
    print("💬 Type commands in natural language (English/Hinglish). Type 'exit' to quit.")
    print()
    
    while True:
        try:
            if IS_UNDER_TEST_RUNNER:
                sys.stdout.write("Zyntax> \n")
                sys.stdout.flush()
                user_input_line = sys.stdin.readline()

                if not user_input_line:
                    sys.stdout.flush()
                    break
                user_input = user_input_line.strip()
            else:
                user_input = input("Zyntax> ")

            if user_input.lower() in ['exit', 'quit']:
                break

            if not user_input:
                if IS_UNDER_TEST_RUNNER:
                     sys.stdout.flush()
                continue


            structured_command = parse_input(user_input)
            sys.stdout.flush()

            if not structured_command:
                print("❓ Parser returned an unexpected result (None or empty).")
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
                    prompt_message = f"Did you mean: '{suggestion_phrase}' with args {suggested_args}? (y/n): "
                    if IS_UNDER_TEST_RUNNER:
                        sys.stdout.write(prompt_message + "\n")
                    else:
                        sys.stdout.write(prompt_message)
                    sys.stdout.flush()

                    confirmation_line = sys.stdin.readline()
                    if not confirmation_line and IS_UNDER_TEST_RUNNER:
                        sys.stdout.flush()
                        break
                    confirmation = confirmation_line.strip().lower()

                    if confirmation == 'y' or confirmation == 'yes':
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
                    print("\nExiting during suggestion...")
                    sys.stdout.flush()
                    break
                except Exception as e:
                    print(f"Error processing suggestion: {e}")
                    sys.stdout.flush()

            elif action == 'error':
                print(f"❗ Error: {structured_command.get('message', 'Parser error')}")
                sys.stdout.flush()

            elif command_type == 'raw_shell_string' or \
                 command_type == 'piped_commands' or \
                 (command_type == 'raw_command' and 'commands' not in structured_command):
                execute_command(structured_command)

            elif action:
                 execute_command(structured_command)

            else:
                 print(f"❓ Unhandled command structure in main: {structured_command}")
                 sys.stdout.flush()


            sys.stdout.flush()

        except EOFError:
            print("\nEOF received on input(), exiting Zyntax main loop.")
            sys.stdout.flush()
            break
        except KeyboardInterrupt:
            print("\nExiting Zyntax (KeyboardInterrupt)...")
            sys.stdout.flush()
            break
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR IN MAIN LOOP: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            break


    print("\nGoodbye!")
    sys.stdout.flush()

if __name__ == "__main__":
    main()

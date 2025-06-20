"""
File: run_interactive_tests.py
Description: A script to automate running a series of interactive commands
             through the Zyntax main.py and capturing their output.
Date Created: 27-05-2025
Last Updated: 27-05-2025
"""
import subprocess
import time
import os
import platform
import sys
import traceback

# --- Configuration ---
ZYNTAX_MAIN_SCRIPT = "main.py"
PYTHON_EXECUTABLE = "python"

PROMPT_TIMEOUT = 15
COMMAND_TIMEOUT = 30

INTERACTIVE_TEST_CASES = [
    # --- Hinglish Basic Commands ---
    {
        "description": "Hinglish: Create folder 'kelly' (accept suggestion)",
        "input": "ek folder bnao kelly",
        "suggestion_response": "y",
        "cleanup_commands": ["rm -rf kelly"] if platform.system() != "Windows" else ["rd /s /q kelly"]
    },
    {
        "description": "Hinglish: Create folder 'kell' with 'naam se' (accept suggestion)",
        "input": "oye ek folder bana kell naam se",
        "suggestion_response": "y",
        "cleanup_commands": ["rm -rf kell"] if platform.system() != "Windows" else ["rd /s /q kell"]
    },
    {
        "description": "Hinglish: Show current path (accept suggestion)",
        "input": "Abhi main kis folder ke andar hoon, batao.",
        "suggestion_response": "y"
    },
    {
        "description": "Hinglish: Create folder 'rach' with 'is naam ka' (accept suggestion)",
        "input": "Naya folder banana hai is naam ka rach",
        "suggestion_response": "y",
        "cleanup_commands": ["rm -rf rach"] if platform.system() != "Windows" else ["rd /s /q rach"]
    },
    {
        "description": "Hinglish: Create file 'rach.py' (accept suggestion)",
        "input": "Ek nayi khaali file bana do is naam se rach.py",
        "suggestion_response": "y",
        "cleanup_commands": ["rm -f rach.py"] if platform.system() != "Windows" else ["del /Q rach.py"]
    },
    {
        "description": "Hinglish: Display file (direct match for 'cat')",
        "input_modified_for_setup": "cat test_display.txt ka content dikha do",
        "input": "cat test_display.txt ka content dikha do",
        "suggestion_response": None,
        "setup_commands": [f"echo test content > test_display.txt" if platform.system() != "Windows" else f"echo test content > test_display.txt"],
        "cleanup_commands": ["rm -f test_display.txt"] if platform.system() != "Windows" else ["del /Q test_display.txt"]
    },
     {
        "description": "Hinglish: List files (accept suggestion)",
        "input": "Bhai, yeh current folder ke andar kya-kya cheezein hain, yeh dikha do.",
        "suggestion_response": "y"
    },
    {
        "description": "Hinglish: Go up one level (accept suggestion for 'cd ..')",
        "input": "Ek level peeche jaana hai",
        "suggestion_response": "y"
    },

    # --- Piped Commands (will test raw passthrough) ---
    {
        "description": "Pipe: cat | grep | wc (complex, relies on passthrough)",
        "input": 'cat log.txt | grep "error" | wc -l',
        "suggestion_response": None,
        "setup_commands": [f"echo error line 1 > log.txt", f"echo normal line >> log.txt", f"echo error line 2 >> log.txt"] if platform.system() != "Windows" else [f"cmd /c \"echo error line 1 > log.txt & echo normal line >> log.txt & echo error line 2 >> log.txt\""],
        "cleanup_commands": ["rm -f log.txt"] if platform.system() != "Windows" else ["del /Q log.txt"]
    },
    {
        "description": "Pipe: du | sort | head (complex, relies on passthrough)",
        "input": "du -ah . | sort -rh | head -n 5",
        "suggestion_response": None
    },
    {
        "description": "Pipe: cat | awk | sort | uniq (complex, relies on passthrough)",
        "input": "cat access.log | awk \"{print $1}\" | sort | uniq -c",
        "suggestion_response": None,
        "setup_commands": [f"echo 1.2.3.4 foo > access.log", f"echo 5.6.7.8 bar >> access.log", f"echo 1.2.3.4 baz >> access.log"] if platform.system() != "Windows" else [f"cmd /c \"echo 1.2.3.4 foo > access.log & echo 5.6.7.8 bar >> access.log & echo 1.2.3.4 baz >> access.log\""],
        "cleanup_commands": ["rm -f access.log"] if platform.system() != "Windows" else ["del /Q access.log"]
    },
    {
        "description": "Pipe: find | xargs ls (complex, 'find' might be NLP, 'xargs' raw)",
        "input": 'find . -name "*.py" | xargs ls -lh', # Note: "*.py" needs careful shell escaping if run directly, but Popen should handle it.
        "suggestion_response": None
    },
    {
        "description": "Pipe: ps | grep | awk (ps is NLP, grep is NLP, awk raw)",
        "input": "ps aux | grep python | awk \"{print $2}\"",
        "suggestion_response": None
    },
     {
        "description": "Redirection Test: cat | sed > newfile.txt (handled by raw_shell_string)",
        "input": "cat file.txt | sed \"s/foo/bar/g\" > newfile.txt", # Double quotes for sed script for consistency
        "suggestion_response": None,
        "setup_commands": [f"echo foo line > file.txt" if platform.system() != "Windows" else f"echo foo line > file.txt"],
        "cleanup_commands": [
            "rm -f file.txt" if platform.system() != "Windows" else "del /Q file.txt",
            "rm -f newfile.txt" if platform.system() != "Windows" else "del /Q newfile.txt"
        ]
    },
    # --- Simpler English Commands ---
    {
        "description": "English: create a new folder called test_data_interactive",
        "input": "create a new folder called test_data_interactive",
        "suggestion_response": None,
        "cleanup_commands": ["rm -rf test_data_interactive"] if platform.system() != "Windows" else ["rd /s /q test_data_interactive"]
    },
    {
        "description": "English: make file executable hello_exec.py (chmod test)",
        "input": "make file executable hello_exec.py",
        "suggestion_response": "y",
        "setup_commands": ["touch hello_exec.py"],
        "cleanup_commands": ["rm -f hello_exec.py"] if platform.system() != "Windows" else ["del /Q hello_exec.py"]
    },
    {
        "description": "English: ping google.com (short)",
        "input": "ping google.com -c 1" if platform.system() != "Windows" else "ping google.com -n 1",
        "suggestion_response": None
    },
]

def run_os_command(command_str):
    print(f"  OS CMD: {command_str}")
    try:
        # For Windows, some commands might need 'cmd /c' prefix if they are internal
        # and involve multiple operations with '&' or redirection that Popen's shell=True might not handle as expected directly.
        # Simpler commands like single echo, del, rd are often fine.
        if platform.system() == "Windows" and ("&" in command_str or ">" in command_str or "<" in command_str):
            # Using cmd /c for complex windows commands in setup/cleanup
            # This is a heuristic; direct shell=True might work for many cases.
            # subprocess.run(f"cmd /c \"{command_str}\"", shell=False, check=True, timeout=15, capture_output=True, text=True)
            # Sticking to shell=True for simplicity, but be mindful of complex quoting.
            pass # shell=True below should handle most cases.
        subprocess.run(command_str, shell=True, check=True, timeout=15, capture_output=True, text=True)
        print(f"  OS CMD OK")
    except subprocess.CalledProcessError as e:
        print(f"  OS CMD FAIL: {e}. Output: {e.stdout} {e.stderr}")
    except subprocess.TimeoutExpired:
        print(f"  OS CMD TIMEOUT.")

def run_zyntax_test(test_case):
    print(f"\n--- Test: {test_case['description']} ---")

    input_command = test_case.get("input_modified_for_setup", test_case["input"])
    print(f"Zyntax Input: {input_command}")

    if "setup_commands" in test_case:
        print("  Setting up...")
        for cmd_str in test_case["setup_commands"]:
            run_os_command(cmd_str)

    process = None
    try:
        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, ZYNTAX_MAIN_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1, # Line-buffered
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        full_output_log = []

        # Phase 1: Read initial banner
        banner_read_timeout = PROMPT_TIMEOUT
        lines_read = 0
        start_banner_wait = time.time()

        # Read initial lines (banner) until timeout or expected number of lines
        # Or until we see the first "Zyntax>" prompt if it appears quickly
        initial_prompt_seen = False
        for _i in range(int(banner_read_timeout * 10)): # Check 10 times a second
            if process.poll() is not None:
                full_output_log.append("Zyntax process terminated during banner.\n")
                break
            try:
                line = process.stdout.readline()
                if line:
                    full_output_log.append(line)
                    sys.stdout.write(f"DEBUG_BANNER_READ: {line.strip()}\n")
                    sys.stdout.flush()
                    lines_read +=1
                    if line.strip().startswith("Zyntax>"): # First prompt
                        initial_prompt_seen = True
                        break
                    if lines_read >= 2 and "Type 'exit' or 'quit' to leave." in line : # Heuristic for banner end
                        # Try to read one more line which might be the prompt
                        next_line_candidate = process.stdout.readline()
                        if next_line_candidate:
                            full_output_log.append(next_line_candidate)
                            sys.stdout.write(f"DEBUG_BANNER_READ (bonus): {next_line_candidate.strip()}\n")
                            sys.stdout.flush()
                            if next_line_candidate.strip().startswith("Zyntax>"):
                                initial_prompt_seen = True
                        break # Assume banner is done
                else: # readline returned empty
                    if process.poll() is not None: break
                    time.sleep(0.1)
            except BlockingIOError: # Should not happen with text=True, bufsize=1 but as fallback
                time.sleep(0.1)
            except Exception as e:
                full_output_log.append(f"Exception reading banner: {e}\n"); break
            if time.time() - start_banner_wait > banner_read_timeout: break

        if not initial_prompt_seen and process.poll() is None:
            full_output_log.append("Warning: Initial 'Zyntax>' prompt not explicitly detected after banner.\n")

        # Phase 2: Send the command
        if process.stdin and process.poll() is None:
            full_output_log.append(f"SENT_CMD: Zyntax> {input_command}\n")
            process.stdin.write(input_command + "\n")
            process.stdin.flush()
        elif process.poll() is not None:
            full_output_log.append("Process ended before command could be sent.\n")

        # Phase 3: Read command output and handle suggestion
        suggestion_responded = False
        command_start_time = time.time()

        while process.poll() is None and (time.time() - command_start_time) < COMMAND_TIMEOUT:
            line = ""
            try:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None: break
                    time.sleep(0.1)
                    continue

                full_output_log.append(line)
                sys.stdout.write(f"DEBUG_CMD_READ: {line.strip()}\n")
                sys.stdout.flush()

                # More specific check for suggestion prompt
                is_suggestion_prompt = "Did you mean:" in line and "(y/n):" in line.strip() # Ensure (y/n) is at the end

                if is_suggestion_prompt and test_case["suggestion_response"] and not suggestion_responded:
                    response = test_case["suggestion_response"] + "\n"
                    full_output_log.append(f"(Auto-responding: {response.strip()})\n")
                    sys.stdout.write(f"SENDING_SUGGESTION_RESP: {response.strip()}\n")
                    sys.stdout.flush()
                    if process.stdin and process.poll() is None:
                        process.stdin.write(response)
                        process.stdin.flush()
                    suggestion_responded = True
                    # After responding to suggestion, continue reading output for this command
                    # Do not break here, wait for the next actual "Zyntax>" prompt

                # Check for the *next* Zyntax prompt
                # It must be "Zyntax> " and not part of a debug line from Zyntax itself
                # and not the echo of the command we just sent (unless suggestion was handled)
                is_next_prompt = line.strip() == "Zyntax>" or (line.strip().startswith("Zyntax>") and "Debug" not in line and "Info" not in line and "Error" not in line and "Warning" not in line)

                if is_next_prompt:
                    if input_command in line and not suggestion_responded and not is_suggestion_prompt: # Echo of our input
                        pass # Continue reading for actual output or suggestion
                    else: # This is the prompt after command execution or after suggestion handling
                        break
            except Exception as e:
                full_output_log.append(f"Exception reading command output: {e}\n"); break

        if process.poll() is None and (time.time() - command_start_time) >= COMMAND_TIMEOUT:
            full_output_log.append(f"Timeout waiting for command '{input_command}' to complete or for next prompt.\n")

        # Phase 4: Send exit command
        if process.stdin and process.poll() is None:
            full_output_log.append("SENT_CMD: Zyntax> exit\n")
            process.stdin.write("exit\n")
            process.stdin.flush()

        # Phase 5: Capture remaining output
        try:
            stdout_rem, _ = process.communicate(timeout=PROMPT_TIMEOUT) # stderr is merged
            if stdout_rem:
                full_output_log.append(stdout_rem)
                sys.stdout.write(f"DEBUG_EXIT_READ:\n{stdout_rem.strip()}\n")
                sys.stdout.flush()
        except subprocess.TimeoutExpired:
            full_output_log.append("Timeout waiting for Zyntax to exit gracefully.\n")
            if process: process.kill(); process.communicate()
        except Exception as e:
             full_output_log.append(f"Error during Zyntax exit communication: {e}\n")

        print("\n--- Captured Zyntax Output ---")
        print("".join(full_output_log).strip())
        print("------------------------------")

    except FileNotFoundError:
        print(f"Error: '{PYTHON_EXECUTABLE}' or '{ZYNTAX_MAIN_SCRIPT}' not found.")
    except Exception as e:
        print(f"An error occurred running test '{test_case['description']}': {e}")
        traceback.print_exc()
    finally:
        if process and process.poll() is None:
            process.kill()
            process.communicate()

        if "cleanup_commands" in test_case:
            print("  Cleaning up...")
            for cmd_str in test_case["cleanup_commands"]:
                run_os_command(cmd_str)

if __name__ == "__main__":
    if not os.path.exists(ZYNTAX_MAIN_SCRIPT):
        print(f"Error: {ZYNTAX_MAIN_SCRIPT} not found in current directory ({os.getcwd()}).")
    else:
        total_tests = len(INTERACTIVE_TEST_CASES)
        print(f"Starting Zyntax interactive test run for {total_tests} cases...")
        print(f"Using Python: {PYTHON_EXECUTABLE}, Zyntax script: {ZYNTAX_MAIN_SCRIPT}")
        print("=" * 70)

        for i, test_case in enumerate(INTERACTIVE_TEST_CASES):
            run_zyntax_test(test_case)
            print("-" * 70)
            if i < total_tests - 1:
                print(f"Completed test {i+1}/{total_tests}. Next test in 1 second...")
                time.sleep(1)
        print("=" * 70)
        print("Zyntax interactive test run finished.")

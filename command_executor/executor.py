"""
File: executor.py
Description: Takes parsed structured commands and executes the corresponding OS-level
             terminal commands based on the current platform (Windows/Linux/macOS),
             using Linux mappings as a fallback for macOS (Darwin) when applicable.
             Uses psutil for memory usage action.
Date Created: 05-04-2025
Last Updated: 27-05-2025
"""

import subprocess
import platform
import os
import psutil # For fetching system stats like memory
import shlex # For joining command parts safely for shell=True

COMMAND_MAP = {
    'list_files': {'Linux': ['ls', '-la'], 'Windows': ['dir']},
    'show_path': {'Linux': ['pwd'], 'Windows': ['cd']},
    'change_directory': {'Linux': ['cd'], 'Windows': ['cd']},
    'make_directory': {'Linux': ['mkdir'], 'Windows': ['md']},
    'create_file': {'Linux': ['touch'], 'Windows': ['type', 'NUL', '>']},
    'delete_file': {'Linux': ['rm'], 'Windows': ['del']},
    'delete_directory': {'Linux': ['rm', '-r'], 'Windows': ['rd', '/s', '/q']},
    'display_file': {'Linux': ['cat'], 'Windows': ['type']},
    'move_rename': {'Linux': ['mv'], 'Windows': ['move']},
    'copy_file': {'Linux': ['cp'], 'Windows': ['copy']},
    'whoami': {'Linux': ['whoami'], 'Windows': ['whoami']},
    'git_status': {'default': ['git', 'status']},
    'git_init': {'default': ['git', 'init']},
    'git_commit': {'default': ['git', 'commit']},
    'show_processes': {'Linux': ['ps'], 'Windows': ['tasklist']}, # Base command, args like 'aux' come from parser
    'disk_usage': {'Linux': ['df'], 'Windows': ['wmic', 'logicaldisk', 'get', 'size,freespace,caption']}, # Base command, args like '-h' come from parser
    'memory_usage': {'Linux': ['free'], 'Darwin': ["#PYTHON_PSUTIL_MEM#"], 'Windows': ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize', '/Value']}, # Base command
    'grep': {'default': ['grep']},
    'chmod': {'default': ['chmod']},
    'make_executable': {'default': ['chmod', '+x']}, # New action mapping
    'ping': {'default': ['ping']},
}

def get_platform_command(action, args):
    os_name = platform.system()
    if action == 'memory_usage' and (os_name == 'Darwin' or not COMMAND_MAP['memory_usage'].get(os_name)):
        return "PYTHON_PSUTIL_MEM"
    elif action == 'change_directory':
        if args:
            target_dir = args[0]
            # print(f"Info: Change directory requested to '{target_dir}'.") # Already printed by parser potentially
            try:
                expanded_target_dir = os.path.expanduser(target_dir)
                os.chdir(expanded_target_dir)
                return "PYTHON_HANDLED_CHDIR_SUCCESS"
            except FileNotFoundError:
                error_path = expanded_target_dir if 'expanded_target_dir' in locals() else target_dir
                print(f"❌ Error: Directory not found: {error_path}")
                return "PYTHON_HANDLED_CHDIR_FAIL"
            except Exception as e:
                error_path = expanded_target_dir if 'expanded_target_dir' in locals() else target_dir
                print(f"❌ Error changing directory to {error_path}: {e}")
                return "PYTHON_HANDLED_CHDIR_FAIL"
        else:
            try:
                os.chdir(os.path.expanduser("~"))
                print(f"Info: Changed directory to HOME.")
                return "PYTHON_HANDLED_CHDIR_SUCCESS"
            except Exception as e:
                print(f"❌ Error changing to home directory: {e}")
                return "PYTHON_HANDLED_CHDIR_FAIL"

    mapping = COMMAND_MAP.get(action)
    base_cmd_list = None
    if mapping:
        base_cmd_list = mapping.get(os_name)
        if base_cmd_list is None and os_name == 'Darwin':
            base_cmd_list = mapping.get('Linux')
        if base_cmd_list is None:
            base_cmd_list = mapping.get('default')

    if base_cmd_list is None:
        print(f"Warning: Action '{action}' not directly mapped for {os_name}. Check COMMAND_MAP.")
        return None

    if action == 'create_file' and os_name == 'Windows':
         if args:
             filepath = args[0]
             try:
                 print(f"Creating file using Python (Windows): {filepath}")
                 with open(filepath, 'x') as f: pass
                 return "PYTHON_HANDLED_CREATE_FILE_SUCCESS"
             except FileExistsError:
                 print(f"Info: File '{filepath}' already exists.")
                 return "PYTHON_HANDLED_CREATE_FILE_EXISTS"
             except Exception as e:
                 print(f"Error creating file '{filepath}' with Python: {e}")
                 return None
         else:
              print("Error: Filename needed for create_file on Windows")
              return None

    # For make_executable, args should be the filename(s)
    # The '+x' is part of base_cmd_list
    full_cmd = list(base_cmd_list) + args
    return full_cmd


def execute_command(parsed_command):
    if not parsed_command:
        print("❓ Parser returned an unexpected result.")
        return

    command_type = parsed_command.get('type')

    if command_type == 'raw_shell_string':
        full_raw_command = parsed_command.get('command_string')
        if not full_raw_command:
            print("❌ Error: Raw shell string command is empty.")
            return
        print(f"🛠️ Executing Raw Shell String: {full_raw_command}")
        try:
            result = subprocess.run(full_raw_command, shell=True, capture_output=True, text=True, check=False)
            if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------")
            if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------")
            if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}")
        except Exception as e:
            print(f"❌ An unexpected error occurred during raw shell string execution: {e}")
        return


    if command_type == 'piped_commands':
        command_segments_for_shell = []
        for cmd_struct in parsed_command.get('commands', []):
            segment_type = cmd_struct.get('type')
            cmd_parts_for_segment = []

            if segment_type == 'raw_command':
                cmd_parts_for_segment.append(cmd_struct['command'])
                cmd_parts_for_segment.extend(cmd_struct.get('args', []))
            else:
                action = cmd_struct.get('action')
                args = cmd_struct.get('args', [])

                if action == 'change_directory':
                     print(f"Warning: 'cd' action found in a pipe segment ('{action} {' '.join(args)}'). This will not affect subsequent piped commands in the same shell execution string.")

                platform_cmd_list_or_action_str = get_platform_command(action, args)

                if platform_cmd_list_or_action_str is None:
                    print(f"❌ Error: Piped command segment '{action}' could not be mapped.")
                    return
                if isinstance(platform_cmd_list_or_action_str, str) and platform_cmd_list_or_action_str.startswith("PYTHON_"):
                    print(f"❌ Error: Python-internal action '{action}' cannot be part of a shell pipe string.")
                    return
                cmd_parts_for_segment = platform_cmd_list_or_action_str

            if cmd_parts_for_segment:
                try: command_segments_for_shell.append(shlex.join(cmd_parts_for_segment))
                except AttributeError: command_segments_for_shell.append(" ".join(cmd_parts_for_segment))
            else:
                print(f"❌ Error: Could not form command parts for pipe segment: {cmd_struct}")
                return

        if command_segments_for_shell:
            full_pipe_command = " | ".join(command_segments_for_shell)
            print(f"🛠️ Executing Piped Command: {full_pipe_command}")
            try:
                result = subprocess.run(full_pipe_command, shell=True, capture_output=True, text=True, check=False)
                if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------")
                if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------")
                if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}")
            except Exception as e:
                print(f"❌ An unexpected error occurred during piped execution: {e}")
        return

    action = parsed_command.get('action')
    args = parsed_command.get('args', [])
    command_list_or_action_str = get_platform_command(action, args)

    if command_list_or_action_str is None:
        print(f"❓ Command action '{action}' could not be executed.")
        return

    if isinstance(command_list_or_action_str, str):
        if command_list_or_action_str == "PYTHON_HANDLED_CHDIR_SUCCESS": pass # Message printed in get_platform_command
        elif command_list_or_action_str == "PYTHON_HANDLED_CHDIR_FAIL": pass
        elif command_list_or_action_str == "PYTHON_PSUTIL_MEM":
            try:
                mem = psutil.virtual_memory(); gb_divisor = 1024**3
                print(f"--- Memory Usage (psutil) ---\n  Total: {mem.total/gb_divisor:.2f} GB\n  Available: {mem.available/gb_divisor:.2f} GB\n  Used: {mem.used/gb_divisor:.2f} GB ({mem.percent}%)\n-----------------------------")
            except ImportError: print("❌ Error: psutil library not found. Please install it: pip install psutil")
            except Exception as e: print(f"❌ Error getting memory info via psutil: {e}")
        elif command_list_or_action_str == "PYTHON_HANDLED_CREATE_FILE_SUCCESS": print(f"✅ File created successfully by Python.")
        elif command_list_or_action_str == "PYTHON_HANDLED_CREATE_FILE_EXISTS": pass
        else: print(f"❌ Internal Error: Unrecognized Python-handled action string '{command_list_or_action_str}'")
        return

    if not isinstance(command_list_or_action_str, list):
        print(f"❌ Internal Error: Expected command_list to be a list, got {type(command_list_or_action_str)}")
        return

    command_list_str = [str(part) for part in command_list_or_action_str]
    print(f"🛠️ Executing: {shlex.join(command_list_str)}")
    try:
        result = subprocess.run(command_list_str, capture_output=True, text=True, check=False, shell=False)
        if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------")
        if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------")
        if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}")
    except FileNotFoundError: print(f"❌ Error: Command '{command_list_str[0]}' not found.")
    except Exception as e: print(f"❌ An unexpected error occurred: {e}")


"""
File: executor.py
Description: Takes parsed structured commands and executes the corresponding OS-level
             terminal commands based on the current platform (Windows/Linux/macOS),
             using Linux mappings as a fallback for macOS (Darwin) when applicable.
             Uses psutil for memory usage action.
Date Created: 05-04-2025
Last Updated: 19-05-2025 # Corrected pipe string construction with shlex.join
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
    'show_processes': {'Linux': ['ps', 'aux'], 'Windows': ['tasklist']},
    'disk_usage': {'Linux': ['df', '-h'], 'Windows': ['wmic', 'logicaldisk', 'get', 'size,freespace,caption']},
    'memory_usage': {'Linux': ['free', '-m'], 'Darwin': ["#"], 'Windows': ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize', '/Value']},
    'grep': {'default': ['grep']}
}

def get_platform_command(action, args):
    os_name = platform.system()
    if action == 'memory_usage': return "PYTHON_PSUTIL_MEM"
    elif action == 'change_directory':
        if args:
            target_dir = args[0]
            print(f"Info: Change directory requested to '{target_dir}'.")
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
             print("Info: 'cd' command needs a target directory.")
             return None

    mapping = COMMAND_MAP.get(action)
    base_cmd = None
    if mapping:
        base_cmd = mapping.get(os_name)
        if base_cmd is None and os_name == 'Darwin': base_cmd = mapping.get('Linux')
        if base_cmd is None: base_cmd = mapping.get('default')
    if base_cmd is None and 'default' in COMMAND_MAP.get(action, {}):
         base_cmd = COMMAND_MAP[action]['default']

    if not base_cmd:
        print(f"Warning: Action '{action}' not mapped or supported for {os_name}. Check COMMAND_MAP.")
        return None

    if action == 'create_file' and os_name == 'Windows':
         if args:
             filepath = args[0]
             try:
                 print(f"Creating file using Python: {filepath}")
                 with open(filepath, 'x') as f: pass
                 return "PYTHON_HANDLED"
             except FileExistsError:
                 print(f"Info: File '{filepath}' already exists.")
                 return "PYTHON_HANDLED"
             except Exception as e:
                 print(f"Error creating file with Python: {e}")
                 return None
         else:
              print("Error: Filename needed for create_file")
              return None

    full_cmd = base_cmd + args
    return full_cmd


def execute_command(parsed_command):
    if not parsed_command:
        print("❓ Parser returned an unexpected result.")
        return

    if parsed_command.get('type') == 'piped_commands':
        command_segments_for_shell = []
        for cmd_struct in parsed_command.get('commands', []):
            action = cmd_struct.get('action')
            args = cmd_struct.get('args', [])

            os_name = platform.system() # Determine OS for each segment
            mapping = COMMAND_MAP.get(action)
            base_cmd_list = None
            if mapping:
                base_cmd_list = mapping.get(os_name)
                if base_cmd_list is None and os_name == 'Darwin': base_cmd_list = mapping.get('Linux')
                if base_cmd_list is None: base_cmd_list = mapping.get('default')
            if base_cmd_list is None and 'default' in COMMAND_MAP.get(action, {}):
                 base_cmd_list = COMMAND_MAP[action]['default']

            if not base_cmd_list:
                print(f"❌ Error: Piped command segment '{action}' not supported on {os_name}.")
                return

            cmd_parts = base_cmd_list + args
            try:
                # Use shlex.join to correctly form each command segment string
                command_segments_for_shell.append(shlex.join(cmd_parts))
            except AttributeError:
                print("Warning: shlex.join not available (Python < 3.8?). Using simple space join for pipe segment.")
                command_segments_for_shell.append(" ".join(cmd_parts)) # Fallback

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

    # Single command logic
    action = parsed_command.get('action')
    args = parsed_command.get('args', [])
    command_list_or_action = get_platform_command(action, args)

    if command_list_or_action is None: return

    if isinstance(command_list_or_action, str):
        # (Python handled actions: cd, psutil, windows create_file)
        if command_list_or_action.startswith("PYTHON_HANDLED_CHDIR"):
            status = command_list_or_action.split("_")[-1]
            if status == "SUCCESS": print(f"✅ Directory changed successfully by Python.")
            return
        elif command_list_or_action == "PYTHON_PSUTIL_MEM":
            try:
                mem = psutil.virtual_memory(); gb_divisor = 1024**3
                print(f"--- Memory Usage (psutil) ---\n  Total: {mem.total/gb_divisor:.2f} GB\n  Available: {mem.available/gb_divisor:.2f} GB\n  Used: {mem.used/gb_divisor:.2f} GB ({mem.percent}%)\n-----------------------------")
            except ImportError: print("❌ Error: psutil library not found")
            except Exception as e: print(f"❌ Error getting memory info via psutil: {e}")
            return
        elif command_list_or_action == "PYTHON_HANDLED":
             print(f"✅ Action '{action}' completed successfully by Python.")
             return
        else:
            print(f"❌ Internal Error: Unrecognized string command '{command_list_or_action}'")
            return

    if not isinstance(command_list_or_action, list):
        print(f"❌ Internal Error: Expected command_list to be a list, got {type(command_list_or_action)}")
        return

    command_list = command_list_or_action
    print(f"🛠️ Executing: {' '.join(command_list)}")
    try:
        result = subprocess.run(command_list, capture_output=True, text=True, check=False, shell=False)
        if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------")
        if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------")
        if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}")
    except FileNotFoundError: print(f"❌ Error: Command '{command_list[0]}' not found.")
    except Exception as e: print(f"❌ An unexpected error occurred: {e}")

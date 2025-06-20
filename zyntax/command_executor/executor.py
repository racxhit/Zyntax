"""
Command executor for translating structured commands to OS-specific terminal commands.
Handles cross-platform compatibility for Linux, macOS, and Windows.
"""

import subprocess
import platform
import os
import psutil
import shlex
import sys

COMMAND_MAP = {
    'list_files': {'Linux': ['ls'], 'Windows': ['dir']},
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
    'show_processes': {'Linux': ['ps'], 'Windows': ['tasklist']},
    'disk_usage': {'Linux': ['df'], 'Windows': ['wmic', 'logicaldisk', 'get', 'size,freespace,caption']},
    'memory_usage': {'Linux': ['free'], 'Darwin': ["#PYTHON_PSUTIL_MEM#"], 'Windows': ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize', '/Value']},
    'grep': {'default': ['grep']},
    'chmod': {'default': ['chmod']},
    'make_executable': {'default': ['chmod', '+x']},
    'ping': {'default': ['ping']},
    'count_lines': {'Linux': ['wc'], 'Darwin': ['wc'], 'Windows': None}, # Base is 'wc', parser adds '-l'

    'display_file_head': {'Linux': ['head'], 'Darwin': ['head'], 'Windows': None},
    'display_file_tail': {'Linux': ['tail'], 'Darwin': ['tail'], 'Windows': None},
    'system_uptime': {'Linux': ['uptime'], 'Darwin': ['uptime'], 'Windows': ['net', 'statistics', 'workstation']},
    'network_interfaces': {'Linux': ['ip', 'addr'], 'Darwin': ['ifconfig'], 'Windows': ['ipconfig']},
    'env_variables': {'Linux': ['env'], 'Darwin': ['env'], 'Windows': ['set']},
}

def get_platform_command(action, args):
    os_name = platform.system()
    if action == 'memory_usage' and (os_name == 'Darwin' or not COMMAND_MAP['memory_usage'].get(os_name)):
        return "PYTHON_PSUTIL_MEM"
    elif action == 'change_directory':
        if args:
            target_dir = args[0]
            try:
                expanded_target_dir = os.path.expanduser(target_dir)
                os.chdir(expanded_target_dir)
                return "PYTHON_HANDLED_CHDIR_SUCCESS"
            except FileNotFoundError:
                error_path = expanded_target_dir if 'expanded_target_dir' in locals() else target_dir
                print(f"❌ Error: Directory not found: {error_path}"); sys.stdout.flush()
                return "PYTHON_HANDLED_CHDIR_FAIL"
            except Exception as e:
                error_path = expanded_target_dir if 'expanded_target_dir' in locals() else target_dir
                print(f"❌ Error changing directory to {error_path}: {e}"); sys.stdout.flush()
                return "PYTHON_HANDLED_CHDIR_FAIL"
        else:
            try:
                os.chdir(os.path.expanduser("~"))
                return "PYTHON_HANDLED_CHDIR_SUCCESS"
            except Exception as e:
                print(f"❌ Error changing to home directory: {e}"); sys.stdout.flush()
                return "PYTHON_HANDLED_CHDIR_FAIL"

    mapping = COMMAND_MAP.get(action)
    base_cmd_list_orig = None
    if mapping:
        base_cmd_list_orig = mapping.get(os_name)
        if base_cmd_list_orig is None and os_name == 'Darwin':
            if action == 'network_interfaces':
                 base_cmd_list_orig = mapping.get('Darwin')
            elif action not in ['memory_usage']:
                 base_cmd_list_orig = mapping.get('Linux')
        if base_cmd_list_orig is None:
            base_cmd_list_orig = mapping.get('default')

    if base_cmd_list_orig is None:
        if action in ['display_file_head', 'display_file_tail', 'count_lines'] and os_name == 'Windows':
            return f"ACTION_UNSUPPORTED_ON_CMD:{action}"
        return None

    base_cmd_list = list(base_cmd_list_orig)
    final_args = list(args)

    if action == 'create_file' and os_name == 'Windows':
         if args:
             filepath = args[0]
             try:
                 with open(filepath, 'x') as f: pass
                 return "PYTHON_HANDLED_CREATE_FILE_SUCCESS"
             except FileExistsError:
                 print(f"Info: File '{filepath}' already exists."); sys.stdout.flush()
                 return "PYTHON_HANDLED_CREATE_FILE_EXISTS"
             except Exception as e:
                 print(f"Error creating file '{filepath}' with Python: {e}"); sys.stdout.flush()
                 return None
         else:
              print("Error: Filename needed for create_file on Windows"); sys.stdout.flush()
              return None

    if action in ['display_file_head', 'display_file_tail']:
        processed_args_for_head_tail = []
        filename_parts = []
        num_lines_option_val = None

        temp_final_args = list(final_args) # Operate on a copy for parsing

        # Check for number and filename, or flags
        if temp_final_args:
            # Case 1: NLP passed ['<num>', '<filename>']
            if len(temp_final_args) >= 1 and temp_final_args[0].isdigit():
                num_lines_option_val = temp_final_args.pop(0)
                filename_parts = temp_final_args # Remaining is filename
            # Case 2: Direct command like 'head -n 5 file' or 'head -5 file'
            elif temp_final_args[0] == '-n' and len(temp_final_args) > 1 and temp_final_args[1].isdigit():
                num_lines_option_val = temp_final_args[1]
                filename_parts = temp_final_args[2:]
            elif temp_final_args[0].startswith('-') and temp_final_args[0][1:].isdigit():
                num_lines_option_val = temp_final_args[0][1:]
                filename_parts = temp_final_args[1:]
            # Case 3: Only filename passed
            else:
                filename_parts = temp_final_args

        # Construct command
        if num_lines_option_val:
            # Ensure -n is not duplicated if already in base_cmd_list
            if '-n' not in base_cmd_list:
                 base_cmd_list.extend(['-n', num_lines_option_val])
            else: # if -n is there, make sure the number is correct
                try:
                    n_idx = base_cmd_list.index('-n')
                    if n_idx + 1 < len(base_cmd_list):
                        base_cmd_list[n_idx+1] = num_lines_option_val
                    else:
                        base_cmd_list.append(num_lines_option_val)
                except ValueError: # Should not happen
                    pass

        if filename_parts:
            processed_args_for_head_tail.append(" ".join(filename_parts))

        final_args = processed_args_for_head_tail


    if action == 'delete_directory' and base_cmd_list and base_cmd_list[0] == 'rm':
        has_recursive_flag = any(flag in base_cmd_list for flag in ['-r', '-rf']) or \
                             any(flag in final_args for flag in ['-r', '-rf'])
        if not has_recursive_flag:
            base_cmd_list.append('-r')

    if action == 'grep': # For direct grep, parser provides args in order
        pass # final_args should be correct from parser's shlex.split

    if action == 'count_lines': # For wc -l
        # Base command is ['wc']. We need to insert '-l' before the filename args.
        # Args from parser should be just the filename(s).
        if '-l' not in base_cmd_list: # Ensure -l is not duplicated
            # Find first filename arg and insert -l before it, or at the end if no filename
            # However, for wc, '-l' usually comes before filenames.
            # A simpler approach: COMMAND_MAP gives ['wc'], parser gives ['filename.txt']
            # We want ['wc', '-l', 'filename.txt']
             base_cmd_list.append('-l') # Add -l to wc

    full_cmd = base_cmd_list + final_args
    return full_cmd


def execute_command(parsed_command):
    if not parsed_command:
        print("❓ Parser returned an unexpected result (None or empty)."); sys.stdout.flush()
        return

    command_type = parsed_command.get('type')

    if command_type == 'raw_shell_string':
        full_raw_command = parsed_command.get('command_string')
        if not full_raw_command: print("❌ Error: Raw shell string command is empty."); sys.stdout.flush(); return
        print(f"🛠️ Executing Raw Shell String: {full_raw_command}"); sys.stdout.flush()
        try:
            result = subprocess.run(full_raw_command, shell=True, capture_output=True, text=True, check=False, errors='ignore')
            if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------"); sys.stdout.flush()
            if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------"); sys.stdout.flush()
            if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}"); sys.stdout.flush()
        except Exception as e: print(f"❌ An unexpected error occurred during raw shell string execution: {e}"); sys.stdout.flush()
        return

    if command_type == 'raw_command' and 'commands' not in parsed_command:
        command_parts = [parsed_command.get('command')] + parsed_command.get('args', [])
        raw_cmd_string = " ".join(str(p) for p in command_parts) # Allow shell glob expansion

        print(f"🛠️ Executing Single Raw Command (shell=True): {raw_cmd_string}"); sys.stdout.flush()
        try:
            result = subprocess.run(raw_cmd_string, shell=True, capture_output=True, text=True, check=False, errors='ignore')
            if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------"); sys.stdout.flush()
            if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------"); sys.stdout.flush()
            if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}"); sys.stdout.flush()
        except Exception as e: print(f"❌ An unexpected error occurred during single raw_command execution: {e}"); sys.stdout.flush()
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
                action = cmd_struct.get('action'); args = cmd_struct.get('args', [])
                if action == 'change_directory':
                     print(f"Warning: 'cd' action in pipe segment ('{action} {' '.join(args)}'). This won't affect subsequent piped commands in this execution string."); sys.stdout.flush()
                platform_cmd_list_or_action_str = get_platform_command(action, args)
                if platform_cmd_list_or_action_str is None: print(f"❌ Error: Piped segment '{action}' unmappable."); sys.stdout.flush(); return
                if isinstance(platform_cmd_list_or_action_str, str) and platform_cmd_list_or_action_str.startswith("PYTHON_"):
                    print(f"❌ Error: Python-internal action '{action}' cannot be part of a shell pipe string."); sys.stdout.flush(); return
                if isinstance(platform_cmd_list_or_action_str, str) and platform_cmd_list_or_action_str.startswith("ACTION_UNSUPPORTED"):
                    print(f"❌ Error: {platform_cmd_list_or_action_str.split(':')[1]} is not supported directly on this OS's command line."); sys.stdout.flush(); return
                cmd_parts_for_segment = platform_cmd_list_or_action_str

            if cmd_parts_for_segment:
                cmd_parts_for_segment = [str(p) for p in cmd_parts_for_segment]
                try: command_segments_for_shell.append(shlex.join(cmd_parts_for_segment))
                except AttributeError: command_segments_for_shell.append(" ".join(shlex.quote(str(p)) for p in cmd_parts_for_segment))
            else: print(f"❌ Error: Could not form command parts for pipe segment: {cmd_struct}"); sys.stdout.flush(); return

        if command_segments_for_shell:
            full_pipe_command = " | ".join(command_segments_for_shell)
            print(f"🛠️ Executing Piped Command: {full_pipe_command}"); sys.stdout.flush()
            try:
                result = subprocess.run(full_pipe_command, shell=True, capture_output=True, text=True, check=False, errors='ignore')
                if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------"); sys.stdout.flush()
                if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------"); sys.stdout.flush()
                if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}"); sys.stdout.flush()
            except Exception as e: print(f"❌ An unexpected error during piped execution: {e}"); sys.stdout.flush()
        return

    action = parsed_command.get('action')
    args = parsed_command.get('args', [])
    if action is None:
        print(f"❓ Error: No action specified in parsed command: {parsed_command}"); sys.stdout.flush()
        return

    command_list_or_action_str = get_platform_command(action, args)

    if command_list_or_action_str is None: print(f"❓ Command action '{action}' could not be executed (get_platform_command returned None)."); sys.stdout.flush(); return

    if isinstance(command_list_or_action_str, str):
        if command_list_or_action_str == "PYTHON_HANDLED_CHDIR_SUCCESS": print(f"✅ Directory changed successfully."); sys.stdout.flush()
        elif command_list_or_action_str == "PYTHON_HANDLED_CHDIR_FAIL": pass
        elif command_list_or_action_str == "PYTHON_PSUTIL_MEM":
            try:
                mem = psutil.virtual_memory(); gb_divisor = 1024**3
                print(f"--- Memory Usage (psutil) ---\n  Total: {mem.total/gb_divisor:.2f} GB\n  Available: {mem.available/gb_divisor:.2f} GB\n  Used: {mem.used/gb_divisor:.2f} GB ({mem.percent}%)\n-----------------------------"); sys.stdout.flush()
            except ImportError: print("❌ Error: psutil library not found. Please install it: pip install psutil"); sys.stdout.flush()
            except Exception as e: print(f"❌ Error getting memory info via psutil: {e}"); sys.stdout.flush()
        elif command_list_or_action_str == "PYTHON_HANDLED_CREATE_FILE_SUCCESS": print(f"✅ File created successfully by Python."); sys.stdout.flush()
        elif command_list_or_action_str == "PYTHON_HANDLED_CREATE_FILE_EXISTS": pass
        elif command_list_or_action_str.startswith("ACTION_UNSUPPORTED_ON_CMD:"):
            print(f"❌ Error: Action '{command_list_or_action_str.split(':')[1]}' is not directly supported on this OS's command line via Zyntax yet."); sys.stdout.flush()
        else: print(f"❌ Internal Error: Unrecognized Python-handled action string '{command_list_or_action_str}'"); sys.stdout.flush()
        return

    if not isinstance(command_list_or_action_str, list):
        print(f"❌ Internal Error: Expected command_list to be a list, got {type(command_list_or_action_str)} for action '{action}'"); sys.stdout.flush(); return

    command_list_str = [str(part) for part in command_list_or_action_str]

    final_command_to_print = ""
    try:
        final_command_to_print = shlex.join(command_list_str)
    except AttributeError:
        final_command_to_print = " ".join(shlex.quote(str(p)) for p in command_list_str)

    print(f"🛠️ Executing: {final_command_to_print}"); sys.stdout.flush()
    try:
        result = subprocess.run(command_list_str, capture_output=True, text=True, check=False, shell=False, errors='ignore')
        if result.stdout: print(f"--- Output ---\n{result.stdout.strip()}\n--------------"); sys.stdout.flush()
        if result.stderr: print(f"--- Errors ---\n{result.stderr.strip()}\n--------------"); sys.stdout.flush()
        if result.returncode != 0: print(f"⚠️ Command finished with exit code: {result.returncode}"); sys.stdout.flush()
    except FileNotFoundError: print(f"❌ Error: Command '{command_list_str[0]}' not found."); sys.stdout.flush()
    except Exception as e: print(f"❌ An unexpected error occurred: {e}"); sys.stdout.flush()

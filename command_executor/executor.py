"""
File: executor.py
Description: Takes parsed structured commands and executes the corresponding OS-level
             terminal commands based on the current platform (Windows/Linux/macOS),
             using Linux mappings as a fallback for macOS (Darwin) when applicable.
             Uses psutil for memory usage action.
Date Created: 05-04-2025
Last Updated: 13-04-2025
"""

import subprocess
import platform
import os
import psutil # For fetching system stats like memory

# Platform Specific Command Mapping
# Only include 'Darwin' if it differs from 'Linux'.
COMMAND_MAP = {
    'list_files': {
        'Linux': ['ls', '-la'],  
        'Windows': ['dir']
    },
    'show_path': {
        'Linux': ['pwd'],  
        'Windows': ['cd']
    },
    'change_directory': {
        # 'cd' action handled internally via os.chdir
        'Linux': ['cd'], 'Windows': ['cd'] 
    },
    'make_directory': {
        'Linux': ['mkdir'],  
        'Windows': ['md']
    },
    'create_file': {
        'Linux': ['touch'],  
        'Windows': ['type', 'NUL', '>'] # Special handling
    },
    'delete_file': {
        'Linux': ['rm'],  
        'Windows': ['del']
    },
    'delete_directory': {
        'Linux': ['rm', '-r'],  
        'Windows': ['rd', '/s', '/q']
    },
    'display_file': {
        'Linux': ['cat'],  
        'Windows': ['type']
    },
    'move_rename': {
        'Linux': ['mv'],  
        'Windows': ['move']
    },
    'copy_file': {
        'Linux': ['cp'],  
        'Windows': ['copy']
     },
    'whoami': {
        'Linux': ['whoami'],
        'Windows': ['whoami']
    },
    # Commands same for all platforms use 'default'
    'git_status': {'default': ['git', 'status']},
    'git_init': {'default': ['git', 'init']},
    'git_commit': {'default': ['git', 'commit']},

    'show_processes': {
        'Linux': ['ps', 'aux'], 
        'Windows': ['tasklist']
    },
    'disk_usage': {
        'Linux': ['df', '-h'],  
        'Windows': ['wmic', 'logicaldisk', 'get', 'size,freespace,caption']
    },
    'memory_usage': {

        'Linux': ['free', '-m'],
        # Original macOS command fails with shell=False due to pipe. psutil is used instead.
        'Darwin': ["#", "top", "-l", "1", "-s", "0", "|", "grep", "PhysMem"],
        'Windows': ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize', '/Value']
    },
    # Plan to add other commands...
}

def get_platform_command(action, args):
    """
    Determines the correct command list or internal action string.
    Intercepts actions handled internally (like cd, memory_usage via psutil).
    Uses Linux mapping as fallback for Darwin (macOS).
    Returns a list of command parts, a special 'PYTHON_...' string, or None.
    """
    os_name = platform.system() # e.g., 'Linux', 'Darwin', 'Windows'

    # Intercept actions handled by Python directly
    if action == 'memory_usage':
        # Indicate that this should be handled by psutil in execute_command
        return "PYTHON_PSUTIL_MEM"
    elif action == 'change_directory':
        if args:
            target_dir = args[0]
            print(f"Info: Change directory requested to '{target_dir}'.")
            try:
                # Expand ~ to the actual home directory path
                expanded_target_dir = os.path.expanduser(target_dir)
                # The debug print for expanded_target_dir was already there, which is good.
                os.chdir(expanded_target_dir)  # Use the expanded path
                return "PYTHON_HANDLED_CHDIR_SUCCESS"
            except FileNotFoundError:
                # Use expanded_target_dir in the error message if it was defined
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

    # If not handled internally, determines platform command
    mapping = COMMAND_MAP.get(action)
    base_cmd = None

    if mapping:
        # 1. Try specific OS (e.g., 'Darwin', 'Windows', 'Linux')
        base_cmd = mapping.get(os_name)

        # 2. If OS is Darwin and no specific 'Darwin' command found, try 'Linux'
        if base_cmd is None and os_name == 'Darwin':
            base_cmd = mapping.get('Linux')

        # 3. If still not found, try 'default' within the action's mapping
        if base_cmd is None:
            base_cmd = mapping.get('default')

    # 4. If action wasn't in mapping OR steps above yielded None, try a global 'default'
    if base_cmd is None and 'default' in COMMAND_MAP.get(action, {}):
         base_cmd = COMMAND_MAP[action]['default']

    # 5. if no command was determined
    if not base_cmd:
        print(f"Warning: Action '{action}' not mapped or supported for {os_name}. Check COMMAND_MAP.")
        return None

    # Special Handling for Windows 'create_file' (Internal Execution)
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

    # Combine command and arguments for subprocess
    full_cmd = base_cmd + args
    return full_cmd


def execute_command(parsed_command):
    """
    Executes the structured command, handling internal Python actions (cd, psutil)
    and external commands via subprocess.
    """
    if not parsed_command or 'action' not in parsed_command:
        print("❓ Invalid command structure received from parser.")
        return

    action = parsed_command['action']
    args = parsed_command.get('args', [])

    command_list_or_action = get_platform_command(action, args)

    # Handle None return (error finding command)
    if command_list_or_action is None:
        return

    # Handle Internal Python Actions
    if isinstance(command_list_or_action, str):
        # Handle 'cd' success/failure strings
        if command_list_or_action.startswith("PYTHON_HANDLED_CHDIR"):
            status = command_list_or_action.split("_")[-1]
            if status == "SUCCESS":
                 print(f"✅ Directory changed successfully by Python.")
            return

        # Handle psutil memory usage action
        elif command_list_or_action == "PYTHON_PSUTIL_MEM":
            try:
                mem = psutil.virtual_memory()
                gb_divisor = 1024**3 # For GB conversion
                total_gb = mem.total / gb_divisor
                avail_gb = mem.available / gb_divisor
                used_gb = mem.used / gb_divisor
                print("--- Memory Usage (psutil) ---")
                print(f"  Total: {total_gb:.2f} GB")
                print(f"  Available: {avail_gb:.2f} GB")
                print(f"  Used: {used_gb:.2f} GB ({mem.percent}%)")
                print("-----------------------------")
            except ImportError:
                print("❌ Error: psutil library not found")
            except Exception as e:
                print(f"❌ Error getting memory info via psutil: {e}")
            return

        # Handle other PYTHON_HANDLED actions (like Windows file creation)
        elif command_list_or_action == "PYTHON_HANDLED":
             print(f"✅ Action '{action}' completed successfully by Python.")
             return

        else:
            # Unrecognized internal action string
            print(f"❌ Internal Error: Unrecognized string command '{command_list_or_action}'")
            return
    # End of Internal Python Actions

    # Prepare for Subprocess Execution
    # Ensures it's a list before proceeding
    if not isinstance(command_list_or_action, list):
        print(f"❌ Internal Error: Expected command_list to be a list, but got {type(command_list_or_action)}")
        return

    command_list = command_list_or_action

    # Execute Command via Subprocess
    print(f"🛠️ Executing: {' '.join(command_list)}")
    try:
        result = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=False,
            shell=False # Avoid shell=True for security
        )

        # Display Output/Errors
        if result.stdout:
            print("--- Output ---")
            print(result.stdout.strip())
            print("--------------")
        if result.stderr:
            print("--- Errors ---")
            print(result.stderr.strip())
            print("--------------")
        if result.returncode != 0:
            print(f"⚠️ Command finished with exit code: {result.returncode}")

    except FileNotFoundError:
         print(f"❌ Error: Command '{command_list[0]}' not found. Is it installed and in your PATH?")
    except Exception as e:
        print(f"❌ An unexpected error occurred during execution: {e}")
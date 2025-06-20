"""
CLI argument parser for Zyntax
"""

import argparse
import sys
from . import __version__

def create_parser():
    """Create the argument parser for Zyntax CLI."""
    parser = argparse.ArgumentParser(
        prog='zyntax',
        description='A smart NLP-powered terminal for natural language command execution',
        epilog='For more information, visit: https://github.com/racxhit/Zyntax-NLP-Terminal'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'zyntax {__version__}'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        default=True,
        help='Start interactive mode (default)'
    )
    
    return parser

def main():
    """Enhanced main function with argument parsing."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Import here to avoid circular imports
    from .main import main as run_main
    
    if args.interactive:
        run_main()
    else:
        # Future: could add batch mode here
        run_main()

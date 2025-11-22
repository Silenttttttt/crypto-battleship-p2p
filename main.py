#!/usr/bin/env python3
"""
Crypto Battleship P2P - Main Entry Point
Experimental cryptographically secure peer-to-peer Battleship game
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.interface import main as cli_main

if __name__ == "__main__":
    cli_main()

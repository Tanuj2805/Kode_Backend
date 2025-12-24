#!/usr/bin/env python3
"""
Quick script to disable file logging in main.py
Run this if logging is causing performance issues
"""

import re

main_file = '/home/ec2-user/mycompiler/backend/main.py'

# Read the file
with open(main_file, 'r') as f:
    content = f.read()

# Comment out file logging configuration (lines with logging setup)
# Replace the logging config section with a simpler one

new_logging_config = '''import logging

# Simple console-only logging (no file I/O overhead)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler()]
)
'''

# Find and replace the logging configuration
# This is a simple replacement - adjust the pattern as needed
pattern = r'import logging\nfrom pathlib import Path.*?logging\.getLogger\(\'uvicorn\.access\'\)\.setLevel\(logging\.WARNING\)'

if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_logging_config.strip(), content, flags=re.DOTALL)
    
    with open(main_file, 'w') as f:
        f.write(content)
    
    print("✅ File logging disabled")
    print("Backend will now only log to console/journalctl")
    print("")
    print("Restart backend:")
    print("  sudo systemctl restart kodecompiler-backend")
else:
    print("⚠️ Could not find logging configuration")
    print("Please manually comment out file logging in main.py")











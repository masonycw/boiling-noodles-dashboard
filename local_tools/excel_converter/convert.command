#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Checking environment..."

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 could not be found. Please install Python 3."
    exit 1
fi

# Install dependencies if missing (quietly)
echo "Ensuring dependencies are installed..."
pip3 install pandas openpyxl xlrd --quiet

# Run the python script
echo "Starting Converter..."
python3 convert_gui.py

# gm_addon_optimization_tricks
Desktop tool to optimize Garry's Mod addons/maps

## Features
- Material compression and resizing
- Sound compression (WAV to MP3/OGG conversion)
- Remove unused files from addons
- Find and analyze map content
- Easy-to-use desktop interface

## Prerequisites
- Python 3.10 or higher
- Git (for cloning the repository)

## Installation

### Step 1: Clone the Repository
If you're new to Git, follow these steps:

1. Open a terminal (Command Prompt, PowerShell, or Git Bash on Windows)
2. Navigate to where you want to install the tool:
   ```bash
   cd C:\Users\YourUsername\Documents
   ```
3. Clone the repository:
   ```bash
   git clone https://github.com/wrefgtzweve/gm_addon_optimization_tricks.git
   ```
4. Enter the project directory:
   ```bash
   cd gm_addon_optimization_tricks
   ```

### Step 2: Run the Tool

#### Windows (Easy Method)
Simply double-click the `run.bat` file in the project folder.

This will automatically:
- Automatically update tool if needed
- Create a virtual environment
- Install all required dependencies
- Launch the desktop UI

#### Alternative Method (All Platforms)
If you prefer to run it manually:

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python main.py
   ```

## Screenshot
<img width="982" height="752" alt="image" src="https://github.com/user-attachments/assets/d068b89f-aaf2-4ff6-bc1b-e783c99a47d4" />

## Credits
- Originally made in collaboration with [@CFC-Servers](https://github.com/CFC-Servers)
- [sourcepp](https://github.com/craftablescience/sourcepp) python library for various source format handling

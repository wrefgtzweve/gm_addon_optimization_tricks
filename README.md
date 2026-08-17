# gm_content_optimizer
Desktop tool to optimize Garry's Mod addons/maps

## Features
- Material compression and resizing
- Sound compression (referenced WAV/MP3 to OGG conversion, with an option to keep original filenames)
- Remove unused files from addons
## Install (Windows)

1. Open the [Releases page](https://github.com/wrefgtzweve/gm_content_optimizer/releases/latest).
2. Download `gm_content_optimizer.exe` from the latest release's **Assets** section.
3. Place the file in a folder of your choice and double-click it to launch the application.

## Build Locally (Windows)

Install Python 3.11, then run the following from the repository root in PowerShell:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller pillow
pyinstaller --clean --noconfirm --onefile --windowed --name gm_content_optimizer --icon icon.ico --add-data "icon.png;." main.py
```

The executable is created at `dist\gm_content_optimizer.exe`.


2. Run the application:
   ```bash
   python main.py
   ```

## Screenshot
<img width="982" height="752" alt="image" src="https://github.com/user-attachments/assets/93e472cd-0d6d-439c-b941-504d383476f4" />

## Credits
- Originally made in collaboration with [@CFC-Servers](https://github.com/CFC-Servers)
- [sourcepp](https://github.com/craftablescience/sourcepp) python library for various source format handling

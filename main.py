import os
import sys
from contextlib import contextmanager
from io import StringIO
import signal

from PySide6 import QtCore, QtGui, QtWidgets

from utils.formatting import format_size
from unused_files.modelformats import unused_model_formats
from unused_files.content import unused_content
from unused_files.remove_game_files import remove_game_files
from material_compression.resize_and_compress import resize_and_compress
from material_compression.resize_png import clamp_pngs
from material_compression.remove_mipmaps import remove_mipmaps
from sound_compression.wav_to_mp3 import wav_to_mp3
from sound_compression.wav_to_ogg import wav_to_ogg
from sound_compression.mp3_to_ogg import mp3_to_ogg
from sound_compression.trim_empty import trim_empty_audio
from mapping.find_map_content import find_map_content


class SignalStream(QtCore.QObject):
    text_emitted = QtCore.Signal(str)

    def write(self, text: str):
        if text:
            self.text_emitted.emit(str(text))

    def flush(self):
        pass


@contextmanager
def redirect_stdout_stderr(callback):
    """Temporarily redirect stdout/stderr to a Qt signal callback."""
    old_out, old_err = sys.stdout, sys.stderr
    stream = SignalStream()
    stream.text_emitted.connect(callback)
    sys.stdout = stream
    sys.stderr = stream
    try:
        yield
    finally:
        sys.stdout = old_out
        sys.stderr = old_err


class TaskWorker(QtCore.QObject):
    started = QtCore.Signal(str)
    log = QtCore.Signal(str)
    progress = QtCore.Signal(int, int)
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(self, fn, *args, description: str = "Working...", **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.description = description

    @QtCore.Slot()
    def run(self):
        self.started.emit(self.description)
        try:
            with redirect_stdout_stderr(self.log.emit):
                result = self.fn(*self.args, **self.kwargs)
            msg = "Done."
            # If the function returned something meaningful, include it.
            if isinstance(result, tuple):
                try:
                    # Common pattern in this repo is (size, count)
                    size, count = result
                    msg = f"Done. Files: {count}, Size: {format_size(size)}"
                except Exception:
                    pass
            self.finished.emit(msg)
        except Exception as e:
            self.failed.emit(f"Error: {e}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GM Addon Optimization Tools")
        self.resize(980, 720)
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.thread: QtCore.QThread | None = None
        self.worker: TaskWorker | None = None
        self.initial_folder_size: int = 0
        self.current_folder_size: int = 0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)

        # Folder picker
        folder_row = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setPlaceholderText("Absolute path to folder…")
        browse_btn = QtWidgets.QPushButton("Browse…")
        browse_btn.clicked.connect(self.choose_folder)
        folder_row.addWidget(QtWidgets.QLabel("Content folder:"))
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse_btn)
        main_layout.addLayout(folder_row)

        # Folder size counter
        size_row = QtWidgets.QHBoxLayout()
        self.size_label = QtWidgets.QLabel("Folder size: Not calculated yet")
        self.size_label.setStyleSheet("QLabel { padding: 5px; }")
        size_row.addWidget(self.size_label)
        size_row.addStretch()
        main_layout.addLayout(size_row)

        # Legend
        legend_label = QtWidgets.QLabel("💡 <span style='color: #4CAF50;'>Green buttons</span> generally have no downsides and can always be used.")
        legend_label.setTextFormat(QtCore.Qt.RichText)
        main_layout.addWidget(legend_label)

        # Tooltip tip
        tip_label = QtWidgets.QLabel("💡 Hover over buttons to see more information about what they do.")
        main_layout.addWidget(tip_label)

        # Actions organized in group boxes
        actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QVBoxLayout(actions_container)
        actions_layout.setSpacing(12)

        # Helper to add buttons to a grid
        def add_button(grid, row, text, handler, recommended=False, tooltip=None):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(handler)
            if recommended:
                btn.setStyleSheet("QPushButton { color: #4CAF50; font-weight: bold; }")
            if tooltip:
                btn.setToolTip(tooltip)
            grid.addWidget(btn, row // 2, row % 2)
            return btn

        # Textures Materials Group
        textures_group = QtWidgets.QGroupBox("Textures Materials")
        textures_grid = QtWidgets.QGridLayout()
        textures_grid.setHorizontalSpacing(12)
        textures_grid.setVerticalSpacing(8)
        add_button(textures_grid, 0, "Clamp VTF file sizes", self.on_clamp_vtf, 
                   tooltip="Resize VTF textures to a maximum size.\nHelps reduce file size without losing quality for most textures.\n512 is good for most usecases like player models, 1024/2048 for world textures.")
        add_button(textures_grid, 1, "Use DXT for VTFs", self.on_use_dxt, recommended=True,
                   tooltip="Convert VTF textures to DXT compression format. Reduces file size significantly with minimal quality loss.")
        add_button(textures_grid, 2, "Remove mipmaps", self.on_remove_mipmaps,
                   tooltip="Remove mipmaps from textures.\nUseful for closeup textures like viewmodel textures but may cause ugly texture shimmering on large textures viewed from a distance.")
        add_button(textures_grid, 3, "Clamp PNG file sizes", self.on_clamp_png, recommended=True,
                   tooltip="Resize PNG images to a maximum size.\nReduces file size for UI elements and other PNG assets.\nUsually PNG's don't need to be very large as they are often used for icons or UI elements.")
        add_button(textures_grid, 4, "Resave VTF files (autorefresh)", self.on_resave_vtf,
                   tooltip="Resave all VTF files to force the game to refresh cached textures.")
        textures_group.setLayout(textures_grid)
        actions_layout.addWidget(textures_group)

        # Cleanup Utilities Group
        cleanup_group = QtWidgets.QGroupBox("Cleanup Utilities")
        cleanup_grid = QtWidgets.QGridLayout()
        cleanup_grid.setHorizontalSpacing(12)
        cleanup_grid.setVerticalSpacing(8)
        add_button(cleanup_grid, 0, "Unused model formats (scan/remove)", self.on_unused_model_formats, recommended=True,
                   tooltip="Find and remove unused model format files (.phy, .vvd, .dx80.vtx, .dx90.vtx, .sw.vtx) that are unused in garry's mod.")
        add_button(cleanup_grid, 1, "Find unused content (WIP)", self.on_unused_content, recommended=True,
                   tooltip="Scan for content files that aren't referenced anywhere. WARNING: This may remove files that are actually used as it's still WIP!")
        add_button(cleanup_grid, 2, "Remove files already in game (HL2/CSS)", self.on_remove_game_files, recommended=True,
                   tooltip="Remove files that are already provided by base GMod.\nCan reduce size significantly for addons that include EP1/EP2/CSS content.")
        add_button(cleanup_grid, 3, "Find and copy content used by .bsp", self.on_find_map_content,
                   tooltip="Extract all content referenced by a BSP map file and copy it to a new folder for easy map packing.")
        cleanup_group.setLayout(cleanup_grid)
        actions_layout.addWidget(cleanup_group)

        # Audio Compression Group
        audio_group = QtWidgets.QGroupBox("Audio Compression")
        audio_grid = QtWidgets.QGridLayout()
        audio_grid.setHorizontalSpacing(12)
        audio_grid.setVerticalSpacing(8)
        add_button(audio_grid, 0, ".wav to .ogg (skips looped/cued)", self.on_wav_to_ogg,
                   tooltip="Convert WAV audio files to OGG format for better compression. Skips files with loop points or cue points.")
        add_button(audio_grid, 1, ".wav to .mp3 (skips looped/cued)", self.on_wav_to_mp3,
                   tooltip="Convert WAV audio files to MP3 format. Skips files with loop points or cue points.")
        add_button(audio_grid, 2, ".mp3 to .ogg", self.on_mp3_to_ogg,
                   tooltip="Convert MP3 audio files to OGG format. OGG is generally better for Garry's Mod.")
        add_button(audio_grid, 3, "Trim empty audio tail", self.on_trim_empty_audio,
                   tooltip="Remove silent/empty audio at the end of sound files to reduce file size.")
        audio_group.setLayout(audio_grid)
        actions_layout.addWidget(audio_group)

        main_layout.addWidget(actions_container)

        # Progress + Log
        progress_row = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setVisible(False)
        progress_row.addWidget(self.progress)
        main_layout.addLayout(progress_row)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Status and output will appear here…")
        main_layout.addWidget(self.log, 1)

        # A little nicer default look
        QtWidgets.QApplication.setStyle("Fusion")
        self.apply_dark_palette()

    # ------------- Theming -------------
    def apply_dark_palette(self):
        palette = QtGui.QPalette()
        base = QtGui.QColor(45, 45, 45)
        alt = QtGui.QColor(53, 53, 53)
        text = QtGui.QColor(220, 220, 220)
        highlight = QtGui.QColor(42, 130, 218)

        palette.setColor(QtGui.QPalette.Window, alt)
        palette.setColor(QtGui.QPalette.WindowText, text)
        palette.setColor(QtGui.QPalette.Base, base)
        palette.setColor(QtGui.QPalette.AlternateBase, alt)
        palette.setColor(QtGui.QPalette.ToolTipBase, text)
        palette.setColor(QtGui.QPalette.ToolTipText, text)
        palette.setColor(QtGui.QPalette.Text, text)
        palette.setColor(QtGui.QPalette.Button, alt)
        palette.setColor(QtGui.QPalette.ButtonText, text)
        palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
        palette.setColor(QtGui.QPalette.Highlight, highlight)
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
        self.setPalette(palette)

    # ------------- Helpers -------------
    def current_folder(self) -> str:
        return (self.folder_edit.text() or "").strip().strip('"')

    def ensure_folder(self) -> str | None:
        folder = self.current_folder()
        if not folder or not os.path.exists(folder):
            QtWidgets.QMessageBox.warning(self, "Folder missing", "Please choose a valid content folder first.")
            return None
        return folder

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select content folder")
        if folder:
            self.folder_edit.setText(folder)
            self.calculate_initial_folder_size(folder)

    def ask_int(self, title: str, label: str, default: int = 1024) -> int | None:
        value, ok = QtWidgets.QInputDialog.getInt(self, title, label, value=default, minValue=1, maxValue=10_000_000, step=1)
        return value if ok else None

    def ask_yes_no(self, title: str, text: str) -> bool:
        res = QtWidgets.QMessageBox.question(self, title, text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        return res == QtWidgets.QMessageBox.Yes

    def ask_file(self, title: str, filter_str: str) -> str | None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, title, filter=filter_str)
        return path or None

    def ask_directory(self, title: str) -> str | None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title)
        return path or None

    def start_task(self, description: str, fn, *args, determinate: bool = False, **kwargs):
        if self.thread is not None:
            QtWidgets.QMessageBox.information(self, "Busy", "A task is already running. Please wait for it to finish.")
            return
        self.progress.setVisible(True)
        if determinate:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        else:
            self.progress.setRange(0, 0)
        self.log_append(f"Starting: {description}\n")

        self.thread = QtCore.QThread()
        self.worker = TaskWorker(fn, *args, description=description, **kwargs)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.started.connect(lambda msg: None)
        self.worker.log.connect(self.log_append)
        self.worker.progress.connect(self.on_progress_update)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def cleanup_thread(self):
        self.thread = None
        self.worker = None
        self.progress.setVisible(False)

    def on_progress_update(self, current: int, total: int):
        """Update progress bar with current/total values"""
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
        else:
            # If total is 0, use indeterminate mode
            self.progress.setRange(0, 0)

    def on_task_finished(self, msg: str):
        self.log_append(msg + "\n")
        self.update_folder_size()

    def on_task_failed(self, msg: str):
        self.log_append(msg + "\n")
        self.update_folder_size()
        QtWidgets.QMessageBox.critical(self, "Task failed", msg)

    def log_append(self, text: str):
        self.log.moveCursor(QtGui.QTextCursor.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(QtGui.QTextCursor.End)

    def calculate_folder_size(self, folder: str) -> int:
        """Calculate total size of all files in folder"""
        total_size = 0
        try:
            for root, _, files in os.walk(folder):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, FileNotFoundError):
                        pass
        except Exception as e:
            print(f"Error calculating folder size: {e}")
        return total_size

    def calculate_initial_folder_size(self, folder: str):
        """Calculate and store initial folder size"""
        self.size_label.setText("Calculating folder size...")
        QtWidgets.QApplication.processEvents()
        
        size = self.calculate_folder_size(folder)
        self.initial_folder_size = size
        self.current_folder_size = size
        self.update_size_label()

    def update_folder_size(self):
        """Recalculate current folder size after an operation"""
        folder = self.current_folder()
        if folder and os.path.exists(folder):
            self.current_folder_size = self.calculate_folder_size(folder)
            self.update_size_label()

    def update_size_label(self):
        """Update the size label with initial and current sizes"""
        if self.initial_folder_size == 0:
            self.size_label.setText("Folder size: Not folder selected")
            return
        
        initial_str = format_size(self.initial_folder_size)
        current_str = format_size(self.current_folder_size)
        
        if self.initial_folder_size == self.current_folder_size:
            self.size_label.setText(f"Folder size: {current_str}")
        else:
            diff = self.initial_folder_size - self.current_folder_size
            diff_str = format_size(diff)
            percentage = (diff / self.initial_folder_size * 100) if self.initial_folder_size > 0 else 0
            
            if diff > 0:
                # Size reduced
                self.size_label.setText(
                    f"Folder size: <span style='color: #888;'>{initial_str}</span> → "
                    f"<b>{current_str}</b> "
                    f"<span style='color: #4CAF50;'>(−{diff_str}, −{percentage:.2f}%)</span>"
                )
            else:
                # Size increased (shouldn't happen normally)
                self.size_label.setText(
                    f"Folder size: <span style='color: #888;'>{initial_str}</span> → "
                    f"<b>{current_str}</b> "
                    f"<span style='color: #f44336;'>(+{format_size(-diff)})</span>"
                )
        
        self.size_label.setTextFormat(QtCore.Qt.RichText)

    # ------------- Action handlers -------------
    def on_unused_model_formats(self):
        folder = self.ensure_folder()
        if not folder:
            return
        remove = self.ask_yes_no("Remove models?", "Do you want to remove the unused model formats?")

        def task():
            size, count = unused_model_formats(folder, remove, progress_callback=self.worker.progress.emit)
            print((f"Removed {count} unused model formats, saving {format_size(size)}") if remove else (f"Found {count} unused model formats, taking up {format_size(size)}"))
            return size, count

        self.start_task("Unused model formats", task, determinate=True)

    def on_unused_content(self):
        folder = self.ensure_folder()
        if not folder:
            return
        remove = self.ask_yes_no("Remove files?", "Do you want to remove the found unused files? This isn't 100% and can remove used files!")

        def task():
            size, count = unused_content(folder, remove)
            print((f"Removed {count} unused files, saving {format_size(size)}") if remove else (f"Found {count} unused files, taking up {format_size(size)}"))
            return size, count

        self.start_task("Find unused content", task)

    def on_remove_game_files(self):
        folder = self.ensure_folder()
        if not folder:
            return
        remove = self.ask_yes_no("Remove files?", "Do you want to remove the found files? This will remove files that are already provided by the game.")
        gamefolder = self.ask_directory("Absolute path to game folder (eg C:/Program Files (x86)/Steam/steamapps/common/GarrysMod)")
        if not gamefolder or not os.path.exists(os.path.join(gamefolder, "gmod.exe")):
            QtWidgets.QMessageBox.warning(self, "Invalid game folder", "The selected folder doesn't contain gmod.exe")
            return

        self.start_task("Remove files already in game", remove_game_files, folder, gamefolder, remove)

    def on_clamp_vtf(self):
        folder = self.ensure_folder()
        if not folder:
            return
        size = self.ask_int("Clamp VTF size", "Clamp size (pixels)", default=1024)
        if size is None:
            return
        
        def task():
            return resize_and_compress(folder, int(size), progress_callback=self.worker.progress.emit)
        
        self.start_task("Clamp VTF file sizes", task, determinate=True)

    def on_use_dxt(self):
        folder = self.ensure_folder()
        if not folder:
            return
        # Use a very large clamp to force DXT path
        
        def task():
            return resize_and_compress(folder, 1_000_000, progress_callback=self.worker.progress.emit)
        
        self.start_task("Use DXT for VTFs", task, determinate=True)

    def on_remove_mipmaps(self):
        folder = self.ensure_folder()
        if not folder:
            return
        
        def task():
            return remove_mipmaps(folder, progress_callback=self.worker.progress.emit)
        
        self.start_task("Remove mipmaps", task, determinate=True)

    def on_clamp_png(self):
        folder = self.ensure_folder()
        if not folder:
            return
        size = self.ask_int("Clamp PNG size", "Clamp size (pixels)", default=512)
        if size is None:
            return
        
        def task():
            return clamp_pngs(folder, int(size), progress_callback=self.worker.progress.emit)
        
        self.start_task("Clamp PNG file sizes", task, determinate=True)

    def on_wav_to_mp3(self):
        folder = self.ensure_folder()
        if not folder:
            return
        
        def task():
            return wav_to_mp3(folder, progress_callback=self.worker.progress.emit)
        
        self.start_task(".wav to .mp3", task, determinate=True)

    def on_wav_to_ogg(self):
        folder = self.ensure_folder()
        if not folder:
            return
        
        def task():
            return wav_to_ogg(folder, progress_callback=self.worker.progress.emit)
        
        self.start_task(".wav to .ogg", task, determinate=True)

    def on_mp3_to_ogg(self):
        folder = self.ensure_folder()
        if not folder:
            return
        self.start_task(".mp3 to .ogg", mp3_to_ogg, folder)

    def on_trim_empty_audio(self):
        folder = self.ensure_folder()
        if not folder:
            return
        
        def task():
            return trim_empty_audio(folder, progress_callback=self.worker.progress.emit)
        
        self.start_task("Trim empty audio", task, determinate=True)

    def on_find_map_content(self):
        folder = self.ensure_folder()
        if not folder:
            return
        gamefolder = self.ask_directory("Absolute path to game folder (eg C:/Program Files (x86)/Steam/steamapps/common/GarrysMod)")
        if not gamefolder or not os.path.exists(os.path.join(gamefolder, "gmod.exe")):
            QtWidgets.QMessageBox.warning(self, "Invalid game folder", "The selected folder doesn't contain gmod.exe")
            return

        map_file = self.ask_file("Select .bsp map file", "BSP files (*.bsp)")
        if not map_file or not map_file.endswith(".bsp"):
            QtWidgets.QMessageBox.warning(self, "Invalid map file", "Please select a valid .bsp file.")
            return
        dest_folder = self.ask_directory("Folder to copy found content to (will be created if it doesn't exist)")
        if not dest_folder:
            QtWidgets.QMessageBox.warning(self, "Invalid destination", "Please select a destination folder.")
            return
        os.makedirs(dest_folder, exist_ok=True)
        self.start_task("Find/copy content used by map", find_map_content, folder, gamefolder, dest_folder, map_file)

    def on_resave_vtf(self):
        folder = self.ensure_folder()
        if not folder:
            return

        def task():
            count = 0
            for root, _, files in os.walk(folder):
                for filename in files:
                    if filename.lower().endswith(".vtf"):
                        file_path = os.path.join(root, filename)
                        try:
                            with open(file_path, "r+b") as f:
                                data = f.read()
                                f.seek(0)
                                f.write(data)
                                f.truncate()
                            count += 1
                        except Exception as e:
                            print(f"Failed to resave {file_path}: {e}")
            print(f"Resaved {count} VTF files.")
            return 0, count

        self.start_task("Resave VTF files", task)


def main():
    # Set AppUserModelID for Windows taskbar icon
    if sys.platform == 'win32':
        import ctypes
        myappid = 'cfcservers.gmaddonoptimization.tools.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

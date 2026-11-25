"""Build a standalone bridge binary so end users don't need Python installed.

The bridge needs OS access (keyboard listener + clipboard) and tkinter (log
viewer), neither of which Ableton's embedded Python provides — so it has
to run as an external process. Bundling it with PyInstaller removes the
"install Python first" requirement: end users just drop the MidiClipboard
folder (containing the binary) into Live's Remote Scripts.

Run it on the OS you're building for:
    Windows -> MidiClipboard/bridge.exe            (onefile)
    macOS   -> MidiClipboard/bridge-macos/bridge   (onedir, universal2:
                                                    Apple Silicon and Intel)

Why onedir on a Mac: a onefile build unpacks its libraries into a fresh temp
folder on every launch, and macOS checks each new library before loading
it, so every start took ~17 s. A onedir folder is checked once, on its first
launch, and starts in under a second after that.

Requirements (build machine only):
    Windows: pip install pyinstaller
    macOS:   the python.org universal2 Python (it ships Tk for the viewer), then
             pip install pyinstaller pyobjc-framework-Quartz pyobjc-framework-Cocoa

Usage:
    python build_bridge.py     (python3 on a Mac)

The binary serves two roles:
    bridge              -> runs the bridge (keyboard listener + clipboard + UDP)
    bridge --viewer LOG -> runs the tkinter log window
"""

import os
import shutil
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MidiClipboard")
ENTRY = os.path.join(SRC, "bridge.py")
DIST = os.path.join(HERE, "build", "dist")
WORK = os.path.join(HERE, "build", "work")
SPEC = os.path.join(HERE, "build")

IS_MAC = sys.platform == "darwin"
# What PyInstaller writes to DIST, and where it goes in MidiClipboard/.
ARTIFACT = "bridge" if IS_MAC else "bridge.exe"
TARGET = "bridge-macos" if IS_MAC else "bridge.exe"
BACKEND, OTHER_BACKEND = (
    ("bridge_mac", "bridge_win") if IS_MAC else ("bridge_win", "bridge_mac"))


def main():
    if not os.path.exists(ENTRY):
        sys.exit("entry not found: {}".format(ENTRY))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir" if IS_MAC else "--onefile",
    ]
    if not IS_MAC:
        # On a Mac --noconsole makes an .app bundle instead of a plain
        # executable; a plain executable launched by Live shows no window
        # anyway.
        cmd.append("--noconsole")
    cmd += [
        "--name", "bridge",
        "--distpath", DIST,
        "--workpath", WORK,
        "--specpath", SPEC,
        "--paths", SRC,            # let `import viewer` resolve during analysis
        "--hidden-import", "viewer",
        "--hidden-import", BACKEND,
        "--exclude-module", OTHER_BACKEND,
        "--collect-submodules", "tkinter",
        "--noconfirm",
    ]
    if IS_MAC:
        cmd += ["--target-arch", "universal2"]
    cmd.append(ENTRY)
    print("[build] running PyInstaller...")
    print("        " + " ".join(cmd))
    subprocess.check_call(cmd)

    built = os.path.join(DIST, ARTIFACT)
    if not os.path.exists(built):
        sys.exit("[build] expected artifact missing: {}".format(built))

    target = os.path.join(SRC, TARGET)
    if IS_MAC:
        # Replace the whole folder. symlinks=True keeps the framework's
        # links as links, which its code signature expects.
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(built, target, symlinks=True)
        size = sum(os.path.getsize(os.path.join(d, f))
                   for d, _, files in os.walk(target) for f in files
                   if not os.path.islink(os.path.join(d, f)))
        exe = os.path.join(target, ARTIFACT)
    else:
        shutil.copy2(built, target)
        size = os.path.getsize(target)
        exe = target
    print("[build] done -> {} ({:.1f} MB)".format(target, size / (1024 * 1024)))
    print("[build] the remote script will now prefer {} over bridge.py".format(
        os.path.relpath(exe, SRC)))


if __name__ == "__main__":
    main()

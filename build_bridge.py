"""Build a standalone bridge.exe so end users don't need Python installed.

The bridge needs ctypes (keyboard hook + clipboard) and tkinter (log
viewer), neither of which Ableton's embedded Python provides — so it has
to run as an external process. Bundling it with PyInstaller removes the
"install Python first" requirement: end users just drop the MidiClipboard
folder (containing bridge.exe) into Live's Remote Scripts.

Requirements (build machine only):
    pip install pyinstaller

Usage:
    python build_bridge.py

Output:
    MidiClipboard/bridge.exe   (the artifact the remote script launches)

bridge.exe is a single file that serves two roles:
    bridge.exe              -> runs the bridge (hook + clipboard + UDP)
    bridge.exe --viewer LOG -> runs the tkinter log window
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


def main():
    if not os.path.exists(ENTRY):
        sys.exit("entry not found: {}".format(ENTRY))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "bridge",
        "--distpath", DIST,
        "--workpath", WORK,
        "--specpath", SPEC,
        "--paths", SRC,            # let `import viewer` resolve during analysis
        "--hidden-import", "viewer",
        "--collect-submodules", "tkinter",
        "--noconfirm",
        ENTRY,
    ]
    print("[build] running PyInstaller...")
    print("        " + " ".join(cmd))
    subprocess.check_call(cmd)

    built = os.path.join(DIST, "bridge.exe")
    if not os.path.exists(built):
        sys.exit("[build] expected artifact missing: {}".format(built))

    target = os.path.join(SRC, "bridge.exe")
    shutil.copy2(built, target)
    size_mb = os.path.getsize(target) / (1024 * 1024)
    print("[build] done -> {} ({:.1f} MB)".format(target, size_mb))
    print("[build] the remote script will now prefer this exe over python bridge.py")


if __name__ == "__main__":
    main()

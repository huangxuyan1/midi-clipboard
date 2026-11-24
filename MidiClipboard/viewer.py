"""Tkinter log viewer for the MidiClipboard bridge.

Spawned by bridge.py when Ctrl+Shift+L is pressed. Tails the bridge log
file in a small dark window that auto-scrolls as new lines arrive. This is
its own process, so closing the window does not affect the bridge.

Usage: python viewer.py [log_path]
"""

import os
import sys
import tkinter as tk
from tkinter import scrolledtext


DEFAULT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.log")
POLL_MS = 500
TAIL_LINES = 200


class LogViewer:
    def __init__(self, log_path):
        self.log_path = log_path
        self.pos = 0

        self.root = tk.Tk()
        self.root.title("MidiClipboard bridge")
        self.root.geometry("760x440")
        self.root.configure(background="#1e1e1e")

        header = tk.Label(
            self.root, text="watching  {}".format(log_path),
            anchor="w", padx=10, pady=6,
            background="#252526", foreground="#9cdcfe",
            font=("Segoe UI", 9),
        )
        header.pack(fill="x")

        self.text = scrolledtext.ScrolledText(
            self.root, wrap="none", font=("Consolas", 10),
            background="#1e1e1e", foreground="#d4d4d4",
            insertbackground="#d4d4d4", borderwidth=0, padx=8, pady=4,
        )
        self.text.pack(fill="both", expand=True)
        self.text.configure(state="disabled")

        # Bring to front on open.
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))

        self._load_tail()
        self.root.after(POLL_MS, self._poll)
        self.root.mainloop()

    def _append(self, s):
        self.text.configure(state="normal")
        self.text.insert("end", s)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _load_tail(self):
        """Show only the last TAIL_LINES so we don't dump a huge backlog,
        then remember the end position for incremental polling."""
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                self.pos = f.tell()
        except FileNotFoundError:
            self._append("(waiting for {} to appear...)\n".format(self.log_path))
            return
        lines = content.splitlines(keepends=True)
        self._append("".join(lines[-TAIL_LINES:]))

    def _poll(self):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.pos)
                chunk = f.read()
                self.pos = f.tell()
            if chunk:
                self._append(chunk)
        except FileNotFoundError:
            pass
        except Exception as e:
            self._append("[viewer] read error: {}\n".format(e))
        self.root.after(POLL_MS, self._poll)


def run(log_path):
    """Open the log viewer window and block until the user closes it.
    Called by bridge.py's `--viewer` dispatch."""
    LogViewer(log_path)


def main():
    run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG)


if __name__ == "__main__":
    main()

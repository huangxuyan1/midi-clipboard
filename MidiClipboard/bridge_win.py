"""Windows backend for the MidiClipboard bridge: raw Win32 through ctypes.

Moved verbatim out of bridge.py when the bridge was split per OS. The only
change is that the hook callback now calls the core's on_copy / on_paste /
on_viewer callbacks instead of doing the UDP send and thread starts itself.

Why a low-level hook instead of RegisterHotKey: RegisterHotKey is global —
it steals the combo from every app, including Ableton's own. WH_KEYBOARD_LL
sees every keystroke but lets us decide per-event whether to act or pass
through, so we can be foreground-aware.
"""

import ctypes
import ctypes.wintypes as wt
import logging
import subprocess
import sys


log = logging.getLogger("midiclipboard.bridge")

# --- Win32 constants ---
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_C = 0x43
VK_V = 0x56   # paste hotkey
VK_L = 0x4C   # log viewer hotkey

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


LRESULT = ctypes.c_ssize_t  # signed pointer-sized int
HHOOK = wt.HANDLE
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
LowLevelKeyboardProc = HOOKPROC

# --- Explicit argtypes/restype for every Win32 call we make.
# Without these, 64-bit handle returns get truncated to 32 bits and
# SetWindowsHookExW fails with GetLastError=126 (ERROR_MOD_NOT_FOUND).
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE

kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL

kernel32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wt.BOOL

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HMODULE, wt.DWORD]
user32.SetWindowsHookExW.restype = HHOOK

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = wt.BOOL

user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT

user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int  # signed: -1 on error

user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wt.HWND

user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

# --- Clipboard API ---
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL

user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wt.BOOL

user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE

user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE

user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wt.BOOL

kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE

kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p

kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.GlobalUnlock.restype = wt.BOOL

kernel32.GlobalFree.argtypes = [wt.HANDLE]
kernel32.GlobalFree.restype = wt.HANDLE


def get_clipboard_text():
    """Read the OS clipboard as UTF-16 text. Returns None if there's no
    text on the clipboard, or on any error."""
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            return ctypes.c_wchar_p(ptr).value
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text):
    """Put text on the Windows clipboard via CF_UNICODETEXT. Returns True on
    success, False on any failure (logged to stderr by the caller)."""
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        # UTF-16 LE with explicit null terminator (CF_UNICODETEXT requires it).
        payload = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not h_mem:
            return False
        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            kernel32.GlobalFree(h_mem)
            return False
        ctypes.memmove(ptr, payload, len(payload))
        kernel32.GlobalUnlock(h_mem)
        if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
            # Ownership did NOT transfer; we still own the memory.
            kernel32.GlobalFree(h_mem)
            return False
        # On success the system owns h_mem — don't free it.
        return True
    finally:
        user32.CloseClipboard()


def last_error():
    """Detail for the log line after set_clipboard_text returns False."""
    return "GetLastError=%d" % ctypes.GetLastError()


def viewer_popen_kwargs():
    """Windowless so no console flashes; tkinter still creates its own GUI
    window."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def _foreground_exe_lower():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wt.DWORD(512)
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value.lower()
    finally:
        kernel32.CloseHandle(h)


def is_ableton_foreground():
    return "ableton" in _foreground_exe_lower()


# Target keys currently held down. WH_KEYBOARD_LL has no MOD_NOREPEAT, so
# Windows fires WM_KEYDOWN repeatedly while a key is held — without this
# guard, holding Ctrl+Shift+L spawns a window per repeat (and Ctrl+Shift+V
# would paste many times). We act only on the up->down transition. All hook
# calls run on the same (message-pump) thread, so a plain set is safe.
_HOTKEYS = (VK_C, VK_V, VK_L)
_held = set()

# (on_copy, on_paste, on_viewer) from the core, set by run_hotkeys.
_callbacks = None


def _hook_proc(nCode, wParam, lParam):
    try:
        if nCode == 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            if vk in _HOTKEYS:
                if wParam in (WM_KEYUP, WM_SYSKEYUP):
                    _held.discard(vk)
                elif wParam in (WM_KEYDOWN, WM_SYSKEYDOWN) and vk not in _held:
                    _held.add(vk)  # first press; ignore auto-repeats until released
                    ctrl = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
                    shift = (user32.GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0
                    if ctrl and is_ableton_foreground():
                        on_copy, on_paste, on_viewer = _callbacks
                        if vk == VK_C:
                            # Plain Ctrl+C: fires in addition to Ableton's
                            # native copy. Pass-through (CallNextHookEx below)
                            # means Ableton still receives the keystroke.
                            on_copy()
                            log.info("[hotkey] Ctrl+C -> trigger sent")
                        elif vk == VK_V and shift:
                            # Ctrl+Shift+V: the core reads the clipboard on a
                            # worker thread so the hook callback returns fast.
                            on_paste()
                            log.info("[hotkey] Ctrl+Shift+V -> paste requested")
                        elif vk == VK_L and shift:
                            # Ctrl+Shift+L: pop the log viewer.
                            on_viewer()
    except Exception as e:
        log.error("[hotkey] callback error: %s", e)
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# Keep the WINFUNCTYPE thunk alive for the lifetime of the hook.
_hook_thunk = LowLevelKeyboardProc(_hook_proc)


def run_hotkeys(on_copy, on_paste, on_viewer):
    """Install the keyboard hook and pump messages until the process ends."""
    global _callbacks
    _callbacks = (on_copy, on_paste, on_viewer)

    h_module = kernel32.GetModuleHandleW(None)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_thunk, h_module, 0)
    if not hook_handle:
        err = ctypes.GetLastError()
        log.error("[hook] SetWindowsHookExW failed (GetLastError=%d)", err)
        sys.exit(1)
    log.info("[hook] installed; Ctrl+C = copy notes (no-op when nothing "
             "selected), Ctrl+Shift+V = paste notes, Ctrl+Shift+L = log "
             "viewer. All gated on Ableton foreground.")

    msg = wt.MSG()
    try:
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnhookWindowsHookEx(hook_handle)

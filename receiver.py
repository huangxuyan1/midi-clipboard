"""Sidecar receiver for the MidiClipboard Ableton remote script.

Installs a Windows low-level keyboard hook (WH_KEYBOARD_LL) and only fires
on Ctrl+Shift+C while Ableton Live is the foreground application. When that
happens, it sends a UDP trigger to the remote script. Separately, it listens
on the result port and prints any messages the script sends back (status,
detail_clip dumps, selected-notes dumps, hotkey responses, errors).

Why a low-level hook instead of RegisterHotKey: RegisterHotKey is global —
it steals the combo from every app, including Ableton's own. WH_KEYBOARD_LL
sees every keystroke but lets us decide per-event whether to act or pass
through, so we can be foreground-aware.
"""

import ctypes
import ctypes.wintypes as wt
import socket
import sys
import threading


TRIGGER_HOST = "127.0.0.1"
TRIGGER_PORT = 19845
RESULT_HOST = "127.0.0.1"
RESULT_PORT = 19846

# --- Win32 constants ---
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_C = 0x43

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


# Persistent UDP socket for trigger sends; keep at module scope so the hook
# callback (which must be fast) doesn't pay socket-construction cost per key.
_trigger_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def _hook_proc(nCode, wParam, lParam):
    try:
        if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if kb.vkCode == VK_C:
                ctrl = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
                shift = (user32.GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0
                if ctrl and shift and is_ableton_foreground():
                    _trigger_sock.sendto(b"go", (TRIGGER_HOST, TRIGGER_PORT))
                    print("[hotkey] -> trigger sent")
    except Exception as e:
        print("[hotkey] callback error: {}".format(e), file=sys.stderr)
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# Keep the WINFUNCTYPE thunk alive for the lifetime of the hook.
_hook_thunk = LowLevelKeyboardProc(_hook_proc)


def receiver_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((RESULT_HOST, RESULT_PORT))
    except OSError as e:
        print("[receiver] BIND FAILED on {}:{} -> {}".format(
            RESULT_HOST, RESULT_PORT, e), file=sys.stderr)
        print("[receiver] another process is probably holding the port. "
              "Kill stray python.exe instances and re-run.", file=sys.stderr)
        return
    print("[receiver] listening on udp {}:{}".format(RESULT_HOST, RESULT_PORT))
    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except OSError as e:
            print("[receiver] recv error: {}".format(e), file=sys.stderr)
            continue
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = repr(data)
        print("[from {}:{}] {}".format(addr[0], addr[1], text))


def main():
    threading.Thread(target=receiver_loop, daemon=True).start()

    h_module = kernel32.GetModuleHandleW(None)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_thunk, h_module, 0)
    if not hook_handle:
        err = ctypes.GetLastError()
        print("[hook] SetWindowsHookExW failed (GetLastError={})".format(err),
              file=sys.stderr)
        sys.exit(1)
    print("[hook] WH_KEYBOARD_LL installed; Ctrl+Shift+C fires only when "
          "Ableton is foreground.")
    print("[hook] close this window to exit.")

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
        _trigger_sock.close()


if __name__ == "__main__":
    main()

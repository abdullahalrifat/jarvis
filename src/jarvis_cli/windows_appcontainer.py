"""Native Windows AppContainer process launcher used by the command sandbox.

The module is import-safe on non-Windows platforms. Windows-only APIs are
resolved lazily inside ``run_appcontainer``.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
ERROR_ALREADY_EXISTS_HRESULT = 0x800700B7
INFINITE = 0xFFFFFFFF


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", wintypes.LPVOID),
        ("Capabilities", wintypes.LPVOID),
        ("CapabilityCount", wintypes.DWORD),
        ("Reserved", wintypes.DWORD),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", wintypes.LPVOID),
    ]


def wrapper_command(workspace: str | Path, argv: Sequence[str]) -> list[str]:
    return [
        sys.executable,
        "-m",
        "jarvis_cli.windows_appcontainer",
        str(Path(workspace).resolve()),
        "--",
        *[str(item) for item in argv],
    ]


def _profile_name(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()[:20]
    return f"JarvisAgent_{digest}"


def _sid_string(sid: wintypes.LPVOID) -> str:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi32.ConvertSidToStringSidW
    convert.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    convert.restype = wintypes.BOOL
    value = wintypes.LPWSTR()
    if not convert(sid, ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return str(value.value)
    finally:
        kernel32.LocalFree(value)


def _appcontainer_sid(name: str) -> wintypes.LPVOID:
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    sid = wintypes.LPVOID()
    create = userenv.CreateAppContainerProfile
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
    ]
    create.restype = ctypes.c_long
    hr = int(create(name, name, "Jarvis coding-agent sandbox", None, 0, ctypes.byref(sid)))
    unsigned_hr = hr & 0xFFFFFFFF
    if unsigned_hr == ERROR_ALREADY_EXISTS_HRESULT:
        derive = userenv.DeriveAppContainerSidFromAppContainerName
        derive.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
        derive.restype = ctypes.c_long
        hr = int(derive(name, ctypes.byref(sid)))
        unsigned_hr = hr & 0xFFFFFFFF
    if unsigned_hr != 0 or not sid:
        raise OSError(
            f"Could not create/derive AppContainer SID (HRESULT 0x{unsigned_hr:08x})"
        )
    return sid


def _free_sid(sid: wintypes.LPVOID) -> None:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    free_sid = advapi32.FreeSid
    free_sid.argtypes = [wintypes.LPVOID]
    free_sid.restype = wintypes.LPVOID
    free_sid(sid)


def _grant_workspace(workspace: Path, sid: str) -> None:
    completed = subprocess.run(
        ["icacls", str(workspace), "/grant", f"*{sid}:(OI)(CI)M"],
        text=True,
        capture_output=True,
        shell=False,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise OSError(
            "Could not grant AppContainer workspace ACL: "
            + (completed.stdout + completed.stderr)[-2000:]
        )


def _remove_workspace_grant(workspace: Path, sid: str) -> None:
    subprocess.run(
        ["icacls", str(workspace), "/remove", f"*{sid}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        timeout=30,
        check=False,
    )


def run_appcontainer(workspace: Path, argv: list[str]) -> int:
    if os.name != "nt":
        raise RuntimeError("Windows AppContainer launcher can only run on Windows")
    if not argv:
        raise ValueError("no command supplied to AppContainer launcher")

    workspace = workspace.expanduser().resolve()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    sid = _appcontainer_sid(_profile_name(workspace))
    sid_text = _sid_string(sid)
    _grant_workspace(workspace, sid_text)

    size = ctypes.c_size_t(0)
    initialize = kernel32.InitializeProcThreadAttributeList
    initialize.argtypes = [wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    initialize.restype = wintypes.BOOL
    initialize(None, 1, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    attribute_list = ctypes.cast(buffer, wintypes.LPVOID)
    if not initialize(attribute_list, 1, 0, ctypes.byref(size)):
        _remove_workspace_grant(workspace, sid_text)
        _free_sid(sid)
        raise ctypes.WinError(ctypes.get_last_error())

    update = kernel32.UpdateProcThreadAttribute
    update.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.c_size_t,
        wintypes.LPVOID,
        ctypes.c_size_t,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    update.restype = wintypes.BOOL
    security = SECURITY_CAPABILITIES(sid, None, 0, 0)
    try:
        if not update(
            attribute_list,
            0,
            PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(security),
            ctypes.sizeof(security),
            None,
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        startup = STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        startup.lpAttributeList = attribute_list
        process_info = PROCESS_INFORMATION()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        create_process = kernel32.CreateProcessW
        create_process.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFOEXW),
            ctypes.POINTER(PROCESS_INFORMATION),
        ]
        create_process.restype = wintypes.BOOL
        if not create_process(
            None,
            command_line,
            None,
            None,
            False,
            EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
            None,
            str(workspace),
            ctypes.byref(startup),
            ctypes.byref(process_info),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel32.CloseHandle(process_info.hThread)
        try:
            kernel32.WaitForSingleObject(process_info.hProcess, INFINITE)
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(
                process_info.hProcess, ctypes.byref(exit_code)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return int(exit_code.value)
        finally:
            kernel32.CloseHandle(process_info.hProcess)
    finally:
        kernel32.DeleteProcThreadAttributeList(attribute_list)
        _remove_workspace_grant(workspace, sid_text)
        _free_sid(sid)


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" not in values or not values:
        print(
            "usage: python -m jarvis_cli.windows_appcontainer WORKSPACE -- COMMAND...",
            file=sys.stderr,
        )
        return 2
    marker = values.index("--")
    if marker != 1:
        print("expected exactly one WORKSPACE argument before --", file=sys.stderr)
        return 2
    workspace = Path(values[0]).expanduser().resolve()
    command = values[marker + 1 :]
    try:
        return run_appcontainer(workspace, command)
    except Exception as exc:
        print(f"Jarvis AppContainer error: {exc}", file=sys.stderr)
        return 126


if __name__ == "__main__":
    raise SystemExit(main())

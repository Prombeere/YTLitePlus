"""
Reads memory from the emulator process using Windows ReadProcessMemory.
Supports pattern scanning (AOB scan) and pointer chains.
"""

import ctypes
import ctypes.wintypes as wintypes
import struct
from typing import Optional

kernel32 = ctypes.windll.kernel32

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

# Common value types and their struct format strings
_FORMATS = {
    "byte":   ("B", 1),
    "short":  ("h", 2),
    "ushort": ("H", 2),
    "int":    ("i", 4),
    "uint":   ("I", 4),
    "long":   ("q", 8),
    "ulong":  ("Q", 8),
    "float":  ("f", 4),
    "double": ("d", 8),
}


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress",       ctypes.c_size_t),
        ("AllocationBase",    ctypes.c_size_t),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize",        ctypes.c_size_t),
        ("State",             wintypes.DWORD),
        ("Protect",           wintypes.DWORD),
        ("Type",              wintypes.DWORD),
    ]


class MemoryReader:
    def __init__(self, pid: int):
        self.pid = pid
        self._handle: Optional[int] = None
        self.open()

    def open(self) -> bool:
        access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
        self._handle = kernel32.OpenProcess(access, False, self.pid)
        return bool(self._handle)

    def close(self):
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None

    # ------------------------------------------------------------------
    # Raw read
    # ------------------------------------------------------------------

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        if not self._handle:
            return None
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self._handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read))
        if not ok or read.value != size:
            return None
        return bytes(buf)

    # ------------------------------------------------------------------
    # Typed reads
    # ------------------------------------------------------------------

    def read(self, address: int, type_name: str):
        """Read a typed value. type_name: 'int', 'float', 'byte', etc."""
        fmt, size = _FORMATS[type_name]
        data = self.read_bytes(address, size)
        if data is None:
            return None
        return struct.unpack(fmt, data)[0]

    def read_int(self, address: int) -> Optional[int]:
        return self.read(address, "int")

    def read_uint(self, address: int) -> Optional[int]:
        return self.read(address, "uint")

    def read_float(self, address: int) -> Optional[float]:
        return self.read(address, "float")

    def read_string(self, address: int, max_len: int = 256, encoding: str = "utf-8") -> Optional[str]:
        data = self.read_bytes(address, max_len)
        if data is None:
            return None
        end = data.find(b"\x00")
        return data[:end].decode(encoding, errors="replace")

    # ------------------------------------------------------------------
    # Pointer chain
    # ------------------------------------------------------------------

    def follow_pointer_chain(self, base: int, offsets: list[int]) -> Optional[int]:
        """Follow a multilevel pointer chain and return the final address."""
        addr = base
        for off in offsets[:-1]:
            val = self.read_uint(addr + off) if ctypes.sizeof(ctypes.c_void_p) == 4 else self.read(addr + off, "ulong")
            if val is None:
                return None
            addr = val
        return addr + offsets[-1] if offsets else addr

    # ------------------------------------------------------------------
    # AOB (Array-of-Bytes) pattern scan
    # ------------------------------------------------------------------

    def aob_scan(self, pattern: str, module_base: int = 0, module_size: int = 0x7FFFFFFF) -> list[int]:
        """
        Scan for a byte pattern. Use '??' as wildcard.
        Example pattern: 'A1 ?? ?? ?? ?? 8B 40 04'
        Returns list of matching addresses.
        """
        parsed = self._parse_pattern(pattern)
        results: list[int] = []
        addr = module_base

        while addr < module_base + module_size:
            mbi = MEMORY_BASIC_INFORMATION()
            ret = kernel32.VirtualQueryEx(self._handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
            if not ret:
                break
            next_addr = addr + mbi.RegionSize
            readable = (
                mbi.State == MEM_COMMIT
                and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))
            )
            if readable and mbi.RegionSize > 0:
                chunk = self.read_bytes(addr, mbi.RegionSize)
                if chunk:
                    hits = self._scan_chunk(chunk, parsed, addr)
                    results.extend(hits)
            addr = next_addr

        return results

    @staticmethod
    def _parse_pattern(pattern: str) -> list[Optional[int]]:
        parts = pattern.strip().split()
        result = []
        for p in parts:
            result.append(None if p == "??" else int(p, 16))
        return result

    @staticmethod
    def _scan_chunk(data: bytes, pattern: list[Optional[int]], base_addr: int) -> list[int]:
        hits = []
        plen = len(pattern)
        dlen = len(data)
        for i in range(dlen - plen + 1):
            if all(p is None or data[i + j] == p for j, p in enumerate(pattern)):
                hits.append(base_addr + i)
        return hits

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

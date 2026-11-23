# Copyright (c) 2012 Terence Honles <terence@honles.com> (maintainer)
# Copyright (c) 2008 Giorgos Verigakis <verigak@gmail.com> (author)
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


import contextlib
import ctypes
import errno
import functools
import inspect
import logging
import os
import platform
import warnings
from ctypes import CFUNCTYPE, POINTER, c_char_p, c_int, c_size_t, c_ssize_t, c_uint, c_void_p
from ctypes.util import find_library
from signal import SIG_DFL, SIGINT, SIGTERM, signal
from stat import S_IFDIR


if 1:
    c_byte_p = ctypes.POINTER(ctypes.c_byte)
    c_uint64_p = ctypes.POINTER(ctypes.c_uint64)

log = logging.getLogger("fuse")
_system = platform.system()
_machine = platform.machine()

if _system == 'Windows' or _system.startswith('CYGWIN'):

    import sys

    c_win_long = ctypes.c_int64 if sys.maxsize > 0xFFFFFFFF else ctypes.c_int32
    c_win_ulong = ctypes.c_uint64 if sys.maxsize > 0xFFFFFFFF else ctypes.c_uint32


class c_timespec(ctypes.Structure):
    if _system == 'Windows' or _system.startswith('CYGWIN'):
        _fields_ = [('tv_sec', c_win_long), ('tv_nsec', c_win_long)]
    elif _system in ('OpenBSD', 'FreeBSD', 'NetBSD'):

        _fields_ = [('tv_sec', ctypes.c_int64), ('tv_nsec', ctypes.c_long)]
    else:
        _fields_ = [('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long)]


class c_utimbuf(ctypes.Structure):
    _fields_ = [('actime', c_timespec), ('modtime', c_timespec)]

_libfuse_path = os.environ.get('FUSE_LIBRARY_PATH')
if not _libfuse_path:
    if _system == 'Darwin':

        _libiconv = ctypes.CDLL(find_library('iconv'), ctypes.RTLD_GLOBAL)

        _libfuse_path = (
            find_library('fuse4x') or find_library('osxfuse') or find_library('fuse') or find_library('fuse-t')
        )
    elif _system == 'Windows':

        try:
            import _winreg as reg
        except ImportError:
            import winreg as reg

        def reg32_get_value(rootkey, keyname, valname):
            key, val = None, None
            try:
                key = reg.OpenKey(
                    rootkey, keyname, 0, reg.KEY_READ | reg.KEY_WOW64_32KEY
                )
                val = str(reg.QueryValueEx(key, valname)[0])
            except OSError:
                pass
            finally:
                if key is not None:
                    reg.CloseKey(key)
            return val

        _libfuse_path = reg32_get_value(reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinFsp", r"InstallDir")
        if _libfuse_path:
            arch = "x64" if sys.maxsize > 0xFFFFFFFF else "x86"
            _libfuse_path += f"bin\\winfsp-{arch}.dll"

    elif _libfuse_name := os.environ.get('FUSE_LIBRARY_NAME'):
        _libfuse_path = find_library(_libfuse_name)
    else:
        _libfuse_path = find_library('fuse')
        if not _libfuse_path:
            _libfuse_path = find_library('fuse3')

if not _libfuse_path:
    raise OSError('Unable to find libfuse')
_libfuse = ctypes.CDLL(_libfuse_path)

if _system == 'Darwin' and hasattr(_libfuse, 'macfuse_version'):
    _system = 'Darwin-MacFuse'


def get_fuse_version(libfuse):
    version = libfuse.fuse_version()
    if version < 100:
        return version // 10, version % 10
    if version < 1000:
        return version // 100, version % 100
    raise AttributeError(f"Version {version} of found library {_libfuse._name} cannot be parsed!")


fuse_version_major, fuse_version_minor = get_fuse_version(_libfuse)
if fuse_version_major == 2 and fuse_version_minor < 6:
    raise AttributeError(
        f"Found library {_libfuse_path} is too old: {fuse_version_major}.{fuse_version_minor}. "
        "There have been several ABI breaks in each version. Libfuse < 2.6 is not supported!"
    )
if fuse_version_major != 2 and not (fuse_version_major == 3 and _system == 'Linux'):
    raise AttributeError(
        f"Found library {_libfuse_path} has wrong major version: {fuse_version_major}. Expected FUSE 2!"
    )

ENOATTR = getattr(errno, 'ENOATTR', getattr(errno, 'ENODATA', None))

if _system in ('Darwin', 'Darwin-MacFuse', 'FreeBSD'):
    ENOTSUP = 45

    c_dev_t  = ctypes.c_int32
    c_fsblkcnt_t  = ctypes.c_ulong
    c_fsfilcnt_t  = ctypes.c_ulong
    c_gid_t  = ctypes.c_uint32
    c_mode_t  = ctypes.c_uint16
    c_off_t  = ctypes.c_int64
    c_pid_t  = ctypes.c_int32
    c_uid_t  = ctypes.c_uint32
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
        ctypes.c_int,
        ctypes.c_uint32,
    )
    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
    )
    if _system == 'Darwin':
        c_fsblkcnt_t  = ctypes.c_uint
        c_fsfilcnt_t  = ctypes.c_uint

        _c_stat__fields_  = [
            ('st_dev', c_dev_t),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint16),
            ('st_ino', ctypes.c_uint64),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_birthtimespec', c_timespec),
            ('st_size', c_off_t),
            ('st_blocks', ctypes.c_int64),
            ('st_blksize', ctypes.c_int32),
            ('st_flags', ctypes.c_int32),
            ('st_gen', ctypes.c_int32),
            ('st_lspare', ctypes.c_int32),
            ('st_qspare', ctypes.c_int64 * 2),
        ]
    elif _system == 'FreeBSD':

        _c_stat__fields_ = [
            ('st_dev', ctypes.c_uint64),
            ('st_ino', ctypes.c_uint64),
            ('st_nlink', ctypes.c_uint64),
            ('st_mode', c_mode_t),
            ('st_bsdflags', ctypes.c_int16),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_padding1', ctypes.c_uint32),
            ('st_rdev', ctypes.c_uint64),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_birthtimespec', c_timespec),
            ('st_size', c_off_t),
            ('st_blocks', ctypes.c_int64),
            ('st_blksize', ctypes.c_uint32),
            ('st_flags', ctypes.c_uint32),
            ('st_gen', ctypes.c_uint32),
            ('st_filerev', ctypes.c_uint64),
            ('st_spare', ctypes.c_int64 * 9),
        ]
    else:

        _c_stat__fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_uint32),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint16),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_size', c_off_t),
            ('st_blocks', ctypes.c_int64),
            ('st_blksize', ctypes.c_int32),
        ]
elif _system == 'Linux':
    ENOTSUP = 95

    c_fsblkcnt_t = ctypes.c_ulonglong
    c_fsfilcnt_t = ctypes.c_ulonglong

    c_dev_t = ctypes.c_ulonglong
    c_gid_t = ctypes.c_uint
    c_mode_t = ctypes.c_uint
    c_off_t = ctypes.c_longlong
    c_pid_t = ctypes.c_int
    c_uid_t = ctypes.c_uint

    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, c_byte_p, ctypes.c_size_t, ctypes.c_int
    )
    getxattr_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, c_byte_p, ctypes.c_size_t)

    if _machine == 'x86_64':
        _c_stat__fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulong),
            ('st_nlink', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('__pad0', ctypes.c_int),
            ('st_rdev', c_dev_t),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_long),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('reserved', ctypes.c_long * 3),
        ]
    elif _machine == 'aarch64':
        _c_stat__fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad1', ctypes.c_ulong),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_int),
            ('__pad2', ctypes.c_int),
            ('st_blocks', ctypes.c_long),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('__reserved', ctypes.c_ulong),
        ]
    else:

        _c_stat__fields_ = [
            ('st_dev', c_dev_t),
            ('__pad1', ctypes.c_ushort),
            ('__st_ino', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad2', ctypes.c_ushort),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_longlong),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_ino', ctypes.c_ulonglong),
        ]
elif _system == 'Windows' or _system.startswith('CYGWIN'):
    ENOTSUP = 129 if _system == 'Windows' else 134
    c_dev_t = ctypes.c_uint
    c_fsblkcnt_t = c_win_ulong
    c_fsfilcnt_t = c_win_ulong
    c_gid_t = ctypes.c_uint
    c_mode_t = ctypes.c_uint
    c_off_t = ctypes.c_longlong
    c_pid_t = ctypes.c_int
    c_uid_t = ctypes.c_uint
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
        ctypes.c_int,
    )
    getxattr_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, c_byte_p, ctypes.c_size_t)
    _c_stat__fields_ = [
        ('st_dev', c_dev_t),
        ('st_ino', ctypes.c_ulonglong),
        ('st_mode', c_mode_t),
        ('st_nlink', ctypes.c_ushort),
        ('st_uid', c_uid_t),
        ('st_gid', c_gid_t),
        ('st_rdev', c_dev_t),
        ('st_size', c_off_t),
        ('st_atimespec', c_timespec),
        ('st_mtimespec', c_timespec),
        ('st_ctimespec', c_timespec),
        ('st_blksize', ctypes.c_int),
        ('st_blocks', ctypes.c_longlong),
        ('st_birthtimespec', c_timespec),
    ]
elif _system == 'OpenBSD':
    ENOTSUP = 91
    c_dev_t = ctypes.c_int32
    c_uid_t = ctypes.c_uint32
    c_gid_t = ctypes.c_uint32
    c_mode_t = ctypes.c_uint32
    c_off_t = ctypes.c_int64
    c_pid_t = ctypes.c_int32
    c_ino_t = ctypes.c_uint64
    c_nlink_t = ctypes.c_uint32
    c_blkcnt_t = ctypes.c_int64
    c_blksize_t = ctypes.c_int32
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
        ctypes.c_int,
    )
    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
    )
    c_fsblkcnt_t = ctypes.c_uint64
    c_fsfilcnt_t = ctypes.c_uint64
    _c_stat__fields_ = [
        ('st_mode', c_mode_t),
        ('st_dev', c_dev_t),
        ('st_ino', c_ino_t),
        ('st_nlink', c_nlink_t),
        ('st_uid', c_uid_t),
        ('st_gid', c_gid_t),
        ('st_rdev', c_dev_t),
        ('st_atimespec', c_timespec),
        ('st_mtimespec', c_timespec),
        ('st_ctimespec', c_timespec),
        ('st_size', c_off_t),
        ('st_blocks', c_blkcnt_t),
        ('st_blksize', c_blksize_t),
        ('st_flags', ctypes.c_uint32),
        ('st_gen', ctypes.c_uint32),
        ('st_birthtimespec', c_timespec),
    ]
else:
    raise NotImplementedError(_system + ' is not supported.')


class c_stat(ctypes.Structure):
    _fields_ = _c_stat__fields_

if _system == 'FreeBSD':
    c_fsblkcnt_t = ctypes.c_uint64
    c_fsfilcnt_t = ctypes.c_uint64
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
        ctypes.c_int,
    )

    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        c_byte_p,
        ctypes.c_size_t,
    )


class c_statvfs(ctypes.Structure):
    if _system == 'FreeBSD':

        _fields_ = [
            ('f_bavail', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_blocks', c_fsblkcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_bsize', ctypes.c_ulong),
            ('f_flag', ctypes.c_ulong),
            ('f_frsize', ctypes.c_ulong),
            ('f_fsid', ctypes.c_ulong),
            ('f_namemax', ctypes.c_ulong),
        ]
    elif _system == 'Windows' or _system.startswith('CYGWIN'):
        _fields_ = [
            ('f_bsize', c_win_ulong),
            ('f_frsize', c_win_ulong),
            ('f_blocks', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_bavail', c_fsblkcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_fsid', c_win_ulong),
            ('f_flag', c_win_ulong),
            ('f_namemax', c_win_ulong),
        ]
    else:

        _fields_ = [
            ('f_bsize', ctypes.c_ulong),
            ('f_frsize', ctypes.c_ulong),
            ('f_blocks', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_bavail', c_fsblkcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_fsid', ctypes.c_ulong),
            ('f_flag', ctypes.c_ulong),
            ('f_namemax', ctypes.c_ulong),
        ]
        if _system == 'Linux':
            _fields_ += [
                ('f_type', ctypes.c_uint),
                ('__f_spare', ctypes.c_uint * 5),
            ]


if _system == 'Linux':

    class c_flock_t(ctypes.Structure):
        _fields_ = [
            ('l_type', ctypes.c_short),
            ('l_whence', ctypes.c_short),
            ('l_start', c_off_t),
            ('l_len', c_off_t),
            ('l_pid', c_pid_t),
            ('l_sysid', ctypes.c_long),
        ]

elif _system == 'OpenBSD':

    class c_flock_t(ctypes.Structure):
        _fields_ = [
            ('l_start', c_off_t),
            ('l_len', c_off_t),
            ('l_pid', c_pid_t),
            ('l_type', ctypes.c_short),
            ('l_whence', ctypes.c_short),
        ]

else:
    c_flock_t = ctypes.c_void_p

_fuse_int32 = ctypes.c_int32 if (fuse_version_major, fuse_version_minor) >= (3, 17) else ctypes.c_int
_fuse_uint32 = ctypes.c_uint32 if (fuse_version_major, fuse_version_minor) >= (3, 17) else ctypes.c_uint
_fuse_file_info_fields_  = []
_fuse_file_info_fields_bitfield  = []

if 0:
    pass
elif fuse_version_major == 2:
    _fh_old_type = ctypes.c_uint if _system == 'OpenBSD' else ctypes.c_ulong
    _fuse_file_info_fields_ = [
        ('flags', ctypes.c_int),
        ('fh_old', _fh_old_type),
        ('writepage', ctypes.c_int),
        ('direct_io', ctypes.c_uint, 1),
        ('keep_cache', ctypes.c_uint, 1),
        ('flush', ctypes.c_uint, 1),
        ('nonseekable', ctypes.c_uint, 1),
        ('flock_release', ctypes.c_uint, 1),
        ('padding', ctypes.c_uint, 27),
        ('fh', ctypes.c_uint64),
        ('lock_owner', ctypes.c_uint64),
    ]
elif fuse_version_major == 3:
    _fuse_file_info_fields_ = [('flags', _fuse_int32)]


    _fuse_file_info_fields_bitfield = [
        ('writepage', _fuse_uint32, 1),
        ('direct_io', _fuse_uint32, 1),
        ('keep_cache', _fuse_uint32, 1),
    ]

    if fuse_version_minor >= 15 and fuse_version_minor < 17:
        _fuse_file_info_fields_bitfield += [
            ('parallel_direct_writes', _fuse_uint32, 1),
        ]
    _fuse_file_info_fields_bitfield += [
        ('flush', _fuse_uint32, 1),
        ('nonseekable', _fuse_uint32, 1),
        ('flock_release', _fuse_uint32, 1),
    ]
    if fuse_version_minor >= 5:
        _fuse_file_info_fields_bitfield += [('cache_readdir', ctypes.c_uint, 1)]
    if fuse_version_minor >= 11:
        _fuse_file_info_fields_bitfield += [('noflush', ctypes.c_uint, 1)]
    if fuse_version_minor >= 17:
        _fuse_file_info_fields_bitfield += [
            ('parallel_direct_writes', _fuse_uint32, 1),
        ]

    _fuse_file_info_flag_count = sum(x[2] for x in _fuse_file_info_fields_bitfield)
    assert _fuse_file_info_flag_count < ctypes.sizeof(_fuse_uint32) * 8

    _fuse_file_info_fields_ += _fuse_file_info_fields_bitfield
    _fuse_file_info_fields_ += [
        ('padding', _fuse_uint32, ctypes.sizeof(_fuse_uint32) * 8 - _fuse_file_info_flag_count),
        ('padding2', _fuse_uint32),
    ]

    if fuse_version_minor >= 17:
        _fuse_file_info_fields_ += [('padding3', _fuse_uint32)]

    _fuse_file_info_fields_ += [
        ('fh', ctypes.c_uint64),
        ('lock_owner', ctypes.c_uint64),
        ('poll_events', ctypes.c_uint64),
    ]


class fuse_file_info(ctypes.Structure):
    _fields_ = _fuse_file_info_fields_


if ctypes.sizeof(ctypes.c_int) == 4 and (fuse_version_major, fuse_version_minor) >= (3, 17):
    assert ctypes.sizeof(fuse_file_info) == 40


class fuse_context(ctypes.Structure):
    _fields_ = [
        ('fuse', ctypes.c_void_p),
        ('uid', c_uid_t),
        ('gid', c_gid_t),
        ('pid', c_pid_t),
        ('private_data', ctypes.c_void_p),

        ('umask', c_mode_t),
    ]


_libfuse.fuse_get_context.restype = ctypes.POINTER(fuse_context)

fuse_buf_flags = ctypes.c_int


class fuse_buf(ctypes.Structure):
    _fields_ = [
        ('size', ctypes.c_size_t),
        ('flags', fuse_buf_flags),
        ('mem', ctypes.c_void_p),
        ('fd', ctypes.c_int),
        ('pos', c_off_t),
    ]


class fuse_bufvec(ctypes.Structure):
    _fields_ = [
        ('count', ctypes.c_size_t),
        ('idx', ctypes.c_size_t),
        ('off', ctypes.c_size_t),
        ('buf', ctypes.POINTER(fuse_buf)),
    ]


if 1:
    fuse_fi_p = ctypes.POINTER(fuse_file_info)
    c_stat_p = ctypes.POINTER(c_stat)
    c_statvfs_p = ctypes.POINTER(c_statvfs)
    c_utimbuf_p = ctypes.POINTER(c_utimbuf)
    fuse_bufvec_p = ctypes.POINTER(fuse_bufvec)
    fuse_bufvec_pp = ctypes.POINTER(fuse_bufvec_p)

_fuse_conn_info_fields  = [
    ('proto_major', ctypes.c_uint),
    ('proto_minor', ctypes.c_uint),
]

if fuse_version_major == 2 or _system == 'NetBSD':
    _fuse_conn_info_fields += [('async_read', _fuse_uint32)]
_fuse_conn_info_fields += [('max_write', _fuse_uint32)]
if fuse_version_major == 3 or _system == 'NetBSD':
    _fuse_conn_info_fields += [('max_read', _fuse_uint32)]
_fuse_conn_info_fields += [('max_readahead', _fuse_uint32)]
if _system == 'Darwin':
    _fuse_conn_info_fields += [('enable', _fuse_uint32)]
_fuse_conn_info_fields += [
    ('capable', _fuse_uint32),
    ('want', _fuse_uint32),
    ('max_background', _fuse_uint32),
    ('congestion_threshold', _fuse_uint32),
]
if fuse_version_major == 2 and _system != 'NetBSD':
    _fuse_conn_info_fields += [('reserved', _fuse_uint32 * (22 if _system == 'Darwin' else 23))]
elif fuse_version_major == 3 or _system == 'NetBSD':
    _fuse_conn_info_fields += [('time_gran', _fuse_uint32)]
    if fuse_version_minor < 17 or _system == 'NetBSD':
        _fuse_conn_info_fields += [('reserved', _fuse_uint32 * 22)]
    else:
        _fuse_conn_info_fields += [
            ('max_backing_stack_depth', ctypes.c_uint32),
            ('no_interrupt', ctypes.c_uint32, 1),
            ('padding', ctypes.c_uint32, 31),
            ('capable_ext', ctypes.c_uint64),
            ('want_ext', ctypes.c_uint64),
            ('request_timeout', ctypes.c_uint16),
            ('reserved', ctypes.c_uint16 * 31),
        ]

class fuse_conn_info(ctypes.Structure):
    _fields_ = _fuse_conn_info_fields


if (fuse_version_major, fuse_version_minor) >= (3, 17):
    assert ctypes.sizeof(fuse_conn_info) == 128

_fuse_config_fields_  = [
    ('set_gid', _fuse_int32),
    ('gid', _fuse_uint32),
    ('set_uid', _fuse_int32),
    ('uid', _fuse_uint32),
    ('set_mode', _fuse_int32),
    ('umask', _fuse_uint32),
    ('entry_timeout', ctypes.c_double),
    ('negative_timeout', ctypes.c_double),
    ('attr_timeout', ctypes.c_double),
    ('intr', _fuse_int32),
    ('intr_signal', _fuse_int32),
    ('remember', _fuse_int32),
    ('hard_remove', _fuse_int32),
    ('use_ino', _fuse_int32),
    ('readdir_ino', _fuse_int32),
    ('direct_io', _fuse_int32),
    ('kernel_cache', _fuse_int32),
    ('auto_cache', _fuse_int32),
]
if fuse_version_major == 3:

    if fuse_version_minor >= 11 and fuse_version_minor < 17:
        _fuse_config_fields_ += [('no_rofd_flush', ctypes.c_int)]

    _fuse_config_fields_ += [
        ('ac_attr_timeout_set', _fuse_int32),
        ('ac_attr_timeout', ctypes.c_double),

        ('nullpath_ok', _fuse_int32),
    ]

    if fuse_version_minor >= 15 and fuse_version_minor < 17:
        _fuse_config_fields_ += [('parallel_direct_writes', ctypes.c_int)]

    if _system != 'NetBSD':
        _fuse_config_fields_ += [
            ('show_help', _fuse_int32),
            ('modules', ctypes.c_char_p),
            ('debug', _fuse_int32),
        ]

    if fuse_version_minor >= 17:
        _fuse_config_fields_ += [
            ('fmask', ctypes.c_uint32),
            ('dmask', ctypes.c_uint32),
            ('no_rofd_flush', ctypes.c_int32),
            ('parallel_direct_writes', ctypes.c_int32),
            ('flags', ctypes.c_int32),
            ('reserved', ctypes.c_uint64 * 48),
        ]


class fuse_config(ctypes.Structure):
    _fields_ = _fuse_config_fields_


if 1:
    FuseConfigPointer = ctypes.POINTER(fuse_config)
    FuseConnInfoPointer = ctypes.POINTER(fuse_conn_info)


fuse_pollhandle_p = ctypes.c_void_p

_fuse_operations_fields_mknod_to_symlink = [
    ('mknod', CFUNCTYPE(c_int, c_char_p, c_mode_t, c_dev_t)),
    ('mkdir', CFUNCTYPE(c_int, c_char_p, c_mode_t)),
    ('unlink', CFUNCTYPE(c_int, c_char_p)),
    ('rmdir', CFUNCTYPE(c_int, c_char_p)),
    ('symlink', CFUNCTYPE(c_int, c_char_p, c_char_p)),
]
_fuse_operations_fields_open_to_removexattr = [
    ('open', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
    ('read', CFUNCTYPE(c_int, c_char_p, c_byte_p, c_size_t, c_off_t, fuse_fi_p)),
    ('write', CFUNCTYPE(c_int, c_char_p, c_byte_p, c_size_t, c_off_t, fuse_fi_p)),
    ('statfs', CFUNCTYPE(c_int, c_char_p, c_statvfs_p)),
    ('flush', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
    ('release', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
    ('fsync', CFUNCTYPE(c_int, c_char_p, c_int, fuse_fi_p)),
    ('setxattr', setxattr_t),
    ('getxattr', getxattr_t),
    ('listxattr', CFUNCTYPE(c_int, c_char_p, c_byte_p, c_size_t)),
    ('removexattr', CFUNCTYPE(c_int, c_char_p, c_char_p)),
]
_fuse_operations_fields_2_9 = [
    ('poll', CFUNCTYPE(c_int, c_char_p, fuse_fi_p, fuse_pollhandle_p, POINTER(c_uint))),
    ('write_buf', CFUNCTYPE(c_int, c_char_p, fuse_bufvec_p, c_off_t, fuse_fi_p)),
    ('read_buf', CFUNCTYPE(c_int, c_char_p, fuse_bufvec_pp, c_size_t, c_off_t, fuse_fi_p)),
    ('flock', CFUNCTYPE(c_int, c_char_p, fuse_fi_p, c_int)),
    ('fallocate', CFUNCTYPE(c_int, c_char_p, c_int, c_off_t, c_off_t, fuse_fi_p)),
]

if fuse_version_major == 2:
    _fuse_operations_fields  = [
        ('getattr', CFUNCTYPE(c_int, c_char_p, c_stat_p)),
        ('readlink', CFUNCTYPE(c_int, c_char_p, c_byte_p, c_size_t)),
        ('getdir', c_void_p),
        *_fuse_operations_fields_mknod_to_symlink,
        ('rename', CFUNCTYPE(c_int, c_char_p, c_char_p)),
        ('link', CFUNCTYPE(c_int, c_char_p, c_char_p)),
        ('chmod', CFUNCTYPE(c_int, c_char_p, c_mode_t)),
        ('chown', CFUNCTYPE(c_int, c_char_p, c_uid_t, c_gid_t)),
        ('truncate', CFUNCTYPE(c_int, c_char_p, c_off_t)),
        ('utime', c_void_p),
        *_fuse_operations_fields_open_to_removexattr,
    ]
    if fuse_version_minor >= 3:
        _fuse_operations_fields += [
            ('opendir', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
            (
                'readdir',
                CFUNCTYPE(
                    c_int,
                    c_char_p,
                    c_void_p,
                    CFUNCTYPE(c_int, c_void_p, c_char_p, c_stat_p, c_off_t),
                    c_off_t,
                    fuse_fi_p,
                ),
            ),
            ('releasedir', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
            ('fsyncdir', CFUNCTYPE(c_int, c_char_p, c_int, fuse_fi_p)),
            ('init', CFUNCTYPE(c_void_p, POINTER(fuse_conn_info))),
            ('destroy', CFUNCTYPE(c_void_p, c_void_p)),
        ]
    if fuse_version_minor >= 5:
        _fuse_operations_fields += [
            ('access', CFUNCTYPE(c_int, c_char_p, c_int)),
            ('create', CFUNCTYPE(c_int, c_char_p, c_mode_t, fuse_fi_p)),
            ('ftruncate', CFUNCTYPE(c_int, c_char_p, c_off_t, fuse_fi_p)),
            ('fgetattr', CFUNCTYPE(c_int, c_char_p, c_stat_p, fuse_fi_p)),
        ]
    if fuse_version_minor >= 6:
        _fuse_operations_fields += [
            ('lock', CFUNCTYPE(c_int, c_char_p, fuse_fi_p, c_int, POINTER(c_flock_t))),
            ('utimens', CFUNCTYPE(c_int, c_char_p, c_utimbuf_p)),
            ('bmap', CFUNCTYPE(c_int, c_char_p, c_size_t, c_uint64_p)),
        ]
    if fuse_version_minor >= 8:
        _fuse_operations_fields += [
            ('flag_nullpath_ok', c_uint, 1),
            ('flag_nopath', c_uint, 1),
            ('flag_utime_omit_ok', c_uint, 1),
            ('flag_reserved', c_uint, 29),
            ('ioctl', CFUNCTYPE(c_int, c_char_p, c_uint, c_void_p, fuse_fi_p, c_uint, c_void_p)),
        ]
    if fuse_version_minor >= 9:
        _fuse_operations_fields += _fuse_operations_fields_2_9
        if _system == 'Darwin':
            _fuse_operations_fields += [
                ('reserved00', c_void_p),
                ('reserved01', c_void_p),
                ('__todo__', c_void_p * 11),
            ]
elif fuse_version_major == 3:
    fuse_fill_dir_flags = ctypes.c_int
    fuse_fill_dir_t = CFUNCTYPE(c_int, c_void_p, c_char_p, c_stat_p, c_off_t, fuse_fill_dir_flags)

    fuse_readdir_flags = ctypes.c_int

    _fuse_operations_fields = [
        ('getattr', CFUNCTYPE(c_int, c_char_p, c_stat_p, fuse_fi_p)),
        ('readlink', CFUNCTYPE(c_int, c_char_p, c_byte_p, c_size_t)),
        *_fuse_operations_fields_mknod_to_symlink,
        ('rename', CFUNCTYPE(c_int, c_char_p, c_char_p, c_uint)),
        ('link', CFUNCTYPE(c_int, c_char_p, c_char_p)),
        ('chmod', CFUNCTYPE(c_int, c_char_p, c_mode_t, fuse_fi_p)),
        ('chown', CFUNCTYPE(c_int, c_char_p, c_uid_t, c_gid_t, fuse_fi_p)),
        ('truncate', CFUNCTYPE(c_int, c_char_p, c_off_t, fuse_fi_p)),
        *_fuse_operations_fields_open_to_removexattr,
        ('opendir', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
        ('readdir', CFUNCTYPE(
            c_int, c_char_p, c_void_p, fuse_fill_dir_t, c_off_t, fuse_fi_p, fuse_readdir_flags)),
        ('releasedir', CFUNCTYPE(c_int, c_char_p, fuse_fi_p)),
        ('fsyncdir', CFUNCTYPE(c_int, c_char_p, c_int, fuse_fi_p)),
        ('init', CFUNCTYPE(c_void_p, POINTER(fuse_conn_info), POINTER(fuse_config))),
        ('destroy', CFUNCTYPE(c_void_p, c_void_p)),
        ('access', CFUNCTYPE(c_int, c_char_p, c_int)),
        ('create', CFUNCTYPE(c_int, c_char_p, c_mode_t, fuse_fi_p)),
        ('lock', CFUNCTYPE(c_int, c_char_p, fuse_fi_p, c_int, POINTER(c_flock_t))),
        ('utimens', CFUNCTYPE(c_int, c_char_p, c_utimbuf_p, fuse_fi_p)),
        ('bmap', CFUNCTYPE(c_int, c_char_p, c_size_t, c_uint64_p)),
        ('ioctl', CFUNCTYPE(
            c_int, c_char_p, c_int if fuse_version_minor < 5 else c_uint, c_void_p,
            fuse_fi_p, c_uint, c_void_p)),
        *_fuse_operations_fields_2_9,
        (
            'copy_file_range',
            CFUNCTYPE(
                c_ssize_t, c_char_p, fuse_fi_p, c_off_t, c_char_p,
                fuse_fi_p, c_off_t, c_size_t, c_int,
            ),
        ),
        ('lseek', CFUNCTYPE(c_off_t, c_char_p, c_off_t, c_int, fuse_fi_p)),
    ]



class fuse_operations(ctypes.Structure):
    _fields_ = _fuse_operations_fields


if _system == "OpenBSD":

    def fuse_main_real(argc, argv, fuse_ops_v, sizeof_fuse_ops, ctx_p):
        return _libfuse.fuse_main(argc, argv, fuse_ops_v, ctx_p)

else:
    fuse_main_real = _libfuse.fuse_main_real


def time_of_timespec(ts, use_ns  = False)  :
    if use_ns:
        return ts.tv_sec * 10**9 + ts.tv_nsec
    return ts.tv_sec + ts.tv_nsec / 1e9


def set_st_attrs(st, attrs  , use_ns  = False)  :
    for key, val in attrs.items():
        if key in ('st_atime', 'st_mtime', 'st_ctime', 'st_birthtime'):
            timespec = getattr(st, key + 'spec', None)
            if timespec is None:
                continue

            if use_ns:
                timespec.tv_sec, timespec.tv_nsec = divmod(int(val), 10**9)
            else:
                timespec.tv_sec = int(val)
                timespec.tv_nsec = int((val - timespec.tv_sec) * 1e9)
        elif getattr(st, key, None) is not None:
            setattr(st, key, val)


def fuse_get_context()    :
    "a"

    ctxp = _libfuse.fuse_get_context()
    ctx = ctxp.contents
    return ctx.uid, ctx.gid, ctx.pid


def fuse_exit()  :
    "a"

    if _system == "OpenBSD":
        os.kill(os.getpid(), SIGTERM)
        return

    fuse_ptr = ctypes.c_void_p(_libfuse.fuse_get_context().contents.fuse)
    _libfuse.fuse_exit(fuse_ptr)


class FuseOSError(OSError):
    def __init__(self, errno):
        super().__init__(errno, os.strerror(errno))

_LIBFUSE_2_OPTIONS_REMOVED_IN_FUSE_3 = {"-h", "--help"}
_LIBFUSE_2_OPTIONS_MOVED_INTO_FUSE_3_CONFIG = {
    "hard_remove",
    "use_ino",
    "readdir_ino",
    "direct_io",
    "nopath",
    "intr",
    "intr_signal",
}
_LIBFUSE_3_ONLY_OPTIONS = {"no_rofd_flush", "fmask", "dmask", "parallel_direct_write"}


class FUSE(object):
    "a"

    OPTIONS = (
        ('foreground', '-f'),
        ('debug', '-d'),
        ('nothreads', '-s'),
    )

    def __init__(
        self,
        operations,
        mountpoint ,
        raw_fi  = False,
        encoding  = 'utf-8',
        errors  = 'surrogateescape',
        **kwargs,
    )  :
        "a"

        self.operations = operations
        self.raw_fi = raw_fi
        self.encoding = encoding
        self.errors = errors

        self.use_ns = getattr(self.operations, 'use_ns', False)

        args = ['fuse']

        args.extend(flag for arg, flag in self.OPTIONS if kwargs.pop(arg, False))

        kwargs.setdefault('fsname', self.operations.__class__.__name__)
        args.extend(('-o', ','.join(self._normalize_fuse_options(**kwargs)), mountpoint))
        self._libfuse2_options_moved_into_libfuse3_config = {
            key: value for key, value in kwargs.items() if key in _LIBFUSE_2_OPTIONS_MOVED_INTO_FUSE_3_CONFIG
        }

        argsb = [arg.encode(encoding, self.errors) for arg in args]
        argv = (ctypes.c_char_p * len(argsb))(*argsb)

        alternative_callbacks = {
            "readdir": ["readdir_with_offset"],
        }

        fuse_ops = fuse_operations()
        callbacks_to_always_add = {'init'}
        for field in fuse_operations._fields_:
            name, prototype = field[:2]
            is_function = hasattr(prototype, 'argtypes')

            check_name = name

            if check_name in ["ftruncate", "fgetattr"]:
                check_name = check_name[1:]

            value = getattr(self.operations, check_name, None)
            if value is None or getattr(value, 'libfuse_ignore', False):
                skip = check_name not in callbacks_to_always_add
                if skip and check_name in alternative_callbacks:
                    for alternative_name in alternative_callbacks[check_name]:
                        value = getattr(self.operations, alternative_name, None)
                        skip = value is None or getattr(value, 'libfuse_ignore', False)
                        if not skip:
                            break
                if skip:
                    log.debug("Leave libFUSE %s for '%s' uninitialized.", 'callback' if is_function else 'value', name)
                    continue

            if is_function:
                method  = None
                if fuse_version_major == 2:
                    method = getattr(self, name + '_fuse_2', None)
                elif fuse_version_major == 3:
                    method = getattr(self, name + '_fuse_3', None)

                if method is not None and hasattr(self, name):
                    raise RuntimeError(
                        "Internal Error: Only either suffixed or non-suffixed methods must exist!"
                        f"Found both for '{name}'."
                    )

                if method is None:
                    method = getattr(self, name, None)
                    if method is None:
                        raise RuntimeError(f"Internal Error: Method wrapper for FUSE callback '{name}' is missing!")

                log.debug("Set libFUSE callback for '%s' to wrapped %s wrapping %s", name, method, value)
                value = prototype(functools.partial(self._wrapper, method))
            else:
                log.debug("Set libFUSE value for '%s' to %s", name, value)

            setattr(fuse_ops, name, value)

        try:
            old_handler = signal(SIGINT, SIG_DFL)
        except ValueError:
            old_handler = SIG_DFL

        err = fuse_main_real(len(argsb), argv, ctypes.pointer(fuse_ops), ctypes.sizeof(fuse_ops), None)

        try:
            signal(SIGINT, old_handler)
        except ValueError:
            pass

        del self.operations
        if err:
            raise RuntimeError(err)

    @staticmethod
    def _normalize_fuse_options(**kargs):
        for key, value in kargs.items():
            if fuse_version_major == 2:
                if key in _LIBFUSE_3_ONLY_OPTIONS:
                    log.warning("Ignore libfuse3-only option: %s (%s)", key, value)
                    continue
            elif fuse_version_major == 3:
                if key in _LIBFUSE_2_OPTIONS_REMOVED_IN_FUSE_3:
                    log.warning("Ignore libfuse2-only option: %s (%s)", key, value)
                    continue
                if key in _LIBFUSE_2_OPTIONS_MOVED_INTO_FUSE_3_CONFIG:
                    continue

            if isinstance(value, bool):
                if value is True:
                    yield key
            else:
                yield f'{key}={value}'

    def _wrapper(self, func, *args, **kwargs):
        "a"

        try:
            try:
                return func(*args, **kwargs) or 0

            except OSError as e:
                if func.__name__ == "init":
                    raise e
                if isinstance(e.errno, int) and e.errno > 0:
                    is_valid_exception = (func.__name__.startswith("getattr") and e.errno == errno.ENOENT) or (
                        func.__name__ == "getxattr" and e.errno == ENOATTR
                    )

                    error_string = ""
                    with contextlib.suppress(ValueError):
                        error_string = os.strerror(e.errno)

                    log.debug(
                        "FUSE operation %s (%s) raised a %s, returning errno %s (%s).",
                        func.__name__,
                        args,
                        type(e),
                        e.errno,
                        error_string,
                        exc_info=not is_valid_exception,
                    )
                    return -e.errno
                log.exception(
                    "FUSE operation %s raised an OSError with negative errno %s, returning errno.EINVAL.",
                    func.__name__,
                    e.errno,
                )
                return -errno.EINVAL

            except Exception as e:
                if func.__name__ == "init":
                    raise e
                log.exception("Uncaught exception from FUSE operation %s, returning errno.EINVAL.", func.__name__)
                return -errno.EINVAL

        except BaseException as e:
            log.critical(
                "Uncaught critical exception from FUSE operation %s, aborting.",
                func.__name__,
                exc_info=True,
            )

            fuse_exit()
            return -errno.EFAULT

    def getattr_fuse_2(self, path , buf ):
        return self.fgetattr(path, buf, None)

    def getattr_fuse_3(self, path , buf , fip ):
        return self.fgetattr(path, buf, fip)

    def readlink(self, path , buf , bufsize )  :
        ret = self.operations.readlink(path.decode(self.encoding, self.errors)).encode(self.encoding, self.errors)

        data = ctypes.create_string_buffer(ret[: bufsize - 1])
        ctypes.memmove(buf, data, len(data))
        return 0

    def mknod(self, path , mode , dev )  :
        return self.operations.mknod(path.decode(self.encoding, self.errors), mode, dev)

    def mkdir(self, path , mode )  :
        return self.operations.mkdir(path.decode(self.encoding, self.errors), mode)

    def unlink(self, path )  :
        return self.operations.unlink(path.decode(self.encoding, self.errors))

    def rmdir(self, path )  :
        return self.operations.rmdir(path.decode(self.encoding, self.errors))

    def symlink(self, source , target )  :
        "a"

        return self.operations.symlink(
            target.decode(self.encoding, self.errors), source.decode(self.encoding, self.errors)
        )

    def rename_fuse_2(self, old , new )  :
        return self.operations.rename(old.decode(self.encoding, self.errors), new.decode(self.encoding, self.errors))

    def rename_fuse_3(self, old , new , flags )  :
        return self.rename_fuse_2(old, new)

    def link(self, source , target ):
        "a"

        return self.operations.link(
            target.decode(self.encoding, self.errors), source.decode(self.encoding, self.errors)
        )

    def chmod_fuse_2(self, path , mode )  :
        return self.operations.chmod(None if path is None else path.decode(self.encoding, self.errors), mode)

    def chmod_fuse_3(self, path , mode , fip )  :
        return self.operations.chmod(None if path is None else path.decode(self.encoding, self.errors), mode)

    def _chown(self, path , uid , gid )  :

        if c_uid_t(uid + 1).value == 0:
            uid = -1
        if c_gid_t(gid + 1).value == 0:
            gid = -1

        return self.operations.chown(None if path is None else path.decode(self.encoding, self.errors), uid, gid)

    def chown_fuse_2(self, path , uid , gid )  :
        return self._chown(path, uid, gid)

    def chown_fuse_3(self, path , uid , gid , fip )  :
        return self._chown(path, uid, gid)

    def truncate_fuse_2(self, path , length )  :
        return self.operations.truncate(None if path is None else path.decode(self.encoding, self.errors), length)

    def truncate_fuse_3(self, path , length , fip )  :
        return self.operations.truncate(None if path is None else path.decode(self.encoding, self.errors), length)

    def open(self, path , fip)  :
        fi = fip.contents
        if self.raw_fi:
            return self.operations.open(path.decode(self.encoding, self.errors), fi)
        fi.fh = self.operations.open(path.decode(self.encoding, self.errors), fi.flags)
        return 0

    def read(self, path , buf, size , offset , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        ret = self.operations.read(None if path is None else path.decode(self.encoding, self.errors), size, offset, fh)

        if not ret:
            return 0

        retsize = len(ret)
        assert retsize <= size, f'actual amount read {retsize} greater than expected {size}'

        ctypes.memmove(buf, ret, retsize)
        return retsize

    def write(self, path , buf , size , offset , fip )  :
        data = ctypes.string_at(buf, size)
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.write(
            None if path is None else path.decode(self.encoding, self.errors), data, offset, fh
        )

    def statfs(self, path , buf )  :
        stv = buf.contents
        attrs = self.operations.statfs(path.decode(self.encoding, self.errors))
        for key, val in attrs.items():
            if hasattr(stv, key):
                setattr(stv, key, val)

        return 0

    def flush(self, path , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.flush(None if path is None else path.decode(self.encoding, self.errors), fh)

    def release(self, path , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.release(None if path is None else path.decode(self.encoding, self.errors), fh)

    def fsync(self, path , datasync , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.fsync(None if path is None else path.decode(self.encoding, self.errors), datasync, fh)

    def setxattr(self, path , name , value , size , options , *args)  :
        return self.operations.setxattr(
            path.decode(self.encoding, self.errors),
            name.decode(self.encoding, self.errors),
            ctypes.string_at(value, size),
            options,
            *args,
        )

    def getxattr(self, path , name , value , size , *args)  :
        ret = self.operations.getxattr(
            path.decode(self.encoding, self.errors), name.decode(self.encoding, self.errors), *args
        )

        retsize = len(ret)

        if not value:
            return retsize

        if retsize > size:
            return -errno.ERANGE

        buf = ctypes.create_string_buffer(ret, retsize)
        ctypes.memmove(value, buf, retsize)

        return retsize

    def listxattr(self, path , namebuf , size )  :
        attrs = self.operations.listxattr(path.decode(self.encoding, self.errors)) or ''
        ret = '\x00'.join(attrs).encode(self.encoding, self.errors)
        if len(ret) > 0:
            ret += '\x00'.encode(self.encoding, self.errors)

        retsize = len(ret)

        if not namebuf:
            return retsize

        if retsize > size:
            return -errno.ERANGE

        buf = ctypes.create_string_buffer(ret, retsize)
        ctypes.memmove(namebuf, buf, retsize)

        return retsize

    def removexattr(self, path , name )  :
        return self.operations.removexattr(
            path.decode(self.encoding, self.errors), name.decode(self.encoding, self.errors)
        )

    def opendir(self, path , fip )  :

        fip.contents.fh = self.operations.opendir(path.decode(self.encoding, self.errors))
        return 0

    def _readdir(self, path , buf, filler, offset , fip )  :

        st = c_stat()

        decoded_path = None if path is None else path.decode(self.encoding, self.errors)
        use_readdir_with_offset = hasattr(self.operations, "readdir_with_offset") and not getattr(
            self.operations.readdir_with_offset, "libfuse_ignore", False
        )
        if _system == 'OpenBSD' and getattr(getattr(self.operations, "readdir", None), "libfuse_ignore", False):

            use_readdir_with_offset = False
        items = (
            self.operations.readdir_with_offset(decoded_path, offset, fip.contents.fh)
            if use_readdir_with_offset
            else self.operations.readdir(decoded_path, fip.contents.fh)
        )

        encountered_non_zero_offset = False
        for item in items:
            has_stat = False
            if isinstance(item, str):
                has_stat = True
                name = item
                offset = 0
            else:
                name, attrs, offset = item
                if not use_readdir_with_offset and offset != 0:
                    encountered_non_zero_offset = True
                    offset = 0

                if isinstance(attrs, int):
                    st.st_mode = attrs
                    has_stat = True
                elif isinstance(attrs, dict):

                    for key in ['st_mode', 'st_ino']:
                        if key in attrs:
                            setattr(st, key, attrs[key])
                    has_stat = True

            if fuse_version_major == 2:
                if filler(buf, name.encode(self.encoding, self.errors), st if has_stat else None, offset) != 0:
                    break
            elif fuse_version_major == 3:
                if filler(buf, name.encode(self.encoding, self.errors), st if has_stat else None, offset, 0) != 0:
                    break

        if encountered_non_zero_offset and not use_readdir_with_offset:
            log.warning("When returning non-zero offsets from readdir, you should use readdir_with_offset instead.")

        return 0

    def readdir_fuse_2(self, path , buf, filler, offset , fip )  :
        return self._readdir(path, buf, filler, offset, fip)

    def readdir_fuse_3(self, path , buf, filler, offset , fip , flags )  :

        return self._readdir(path, buf, filler, offset, fip)

    def releasedir(self, path , fip )  :

        return self.operations.releasedir(
            None if path is None else path.decode(self.encoding, self.errors), fip.contents.fh
        )

    def fsyncdir(self, path , datasync , fip )  :

        return self.operations.fsyncdir(
            None if path is None else path.decode(self.encoding, self.errors), datasync, fip.contents.fh
        )

    def _init(self, conn , config )  :
        if hasattr(self.operations, "init_with_config") and not getattr(
            self.operations.init_with_config, "libfuse_ignore", False
        ):
            self.operations.init_with_config(
                None if conn is None else conn.contents, None if config is None else config.contents
            )
        elif hasattr(self.operations, "init") and not getattr(self.operations.init, "libfuse_ignore", False):
            self.operations.init("/")

    def init_fuse_2(self, conn )  :
        self._init(conn, None)

    def init_fuse_3(self, conn , config )  :
        if getattr(self.operations, 'flag_nopath', False) and getattr(self.operations, 'flag_nullpath_ok', False):
            config.contents.nullpath_ok = True
        if config:
            for key, value in self._libfuse2_options_moved_into_libfuse3_config.items():
                setattr(config.contents, key, value)
        self._init(conn, config)

    def destroy(self, private_data )  :
        return self.operations.destroy('/')

    def access(self, path , amode )  :
        return self.operations.access(path.decode(self.encoding, self.errors), amode)

    def create(self, path , mode , fip )  :
        fi = fip.contents
        decoded_path = path.decode(self.encoding, self.errors)

        if self.raw_fi:
            return self.operations.create(decoded_path, mode, fi)
        if len(inspect.signature(self.operations.create).parameters) == 2:
            fi.fh = self.operations.create(decoded_path, mode)
        else:
            fi.fh = self.operations.create(decoded_path, mode, fi.flags)
        return 0

    def ftruncate(self, path , length , fip )  :
        fh = (fip.contents if self.raw_fi else fip.contents.fh) if fip else None
        return self.operations.truncate(None if path is None else path.decode(self.encoding, self.errors), length, fh)

    def fgetattr(self, path , buf , fip )  :
        ctypes.memset(buf, 0, ctypes.sizeof(c_stat))

        st = buf.contents
        fh = (fip.contents if self.raw_fi else fip.contents.fh) if fip else None

        attrs = self.operations.getattr(None if path is None else path.decode(self.encoding, self.errors), fh)
        set_st_attrs(st, attrs, use_ns=self.use_ns)
        return 0

    def lock(self, path , fip , cmd , lock)  :
        fh = (fip.contents if self.raw_fi else fip.contents.fh) if fip else None
        return self.operations.lock(None if path is None else path.decode(self.encoding, self.errors), fh, cmd, lock)

    def utimens_fuse_2(self, path , buf )  :
        if buf:
            atime = time_of_timespec(buf.contents.actime, use_ns=self.use_ns)
            mtime = time_of_timespec(buf.contents.modtime, use_ns=self.use_ns)
            times = (atime, mtime)
        else:
            times = None

        return self.operations.utimens(None if path is None else path.decode(self.encoding, self.errors), times)

    def utimens_fuse_3(self, path , buf , fip )  :
        return self.utimens_fuse_2(path, buf)

    def bmap(self, path , blocksize , idx )  :
        return self.operations.bmap(path.decode(self.encoding, self.errors), blocksize, idx)

    def ioctl(self, path , cmd , arg , fip , flags , data )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.ioctl(
            None if path is None else path.decode(self.encoding, self.errors), cmd, arg, fh, flags, data
        )

    def poll(self, path , fip , ph, reventsp)  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.poll(None if path is None else path.decode(self.encoding, self.errors), fh, ph, reventsp)

    def write_buf(self, path , buf , offset , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.write_buf(path.decode(self.encoding, self.errors), buf, offset, fh)

    def read_buf(self, path , bufpp , size , offset , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.read_buf(path.decode(self.encoding, self.errors), bufpp, size, offset, fh)

    def flock(self, path , fip , op )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.flock(path.decode(self.encoding, self.errors), fh, op)

    def fallocate(self, path , mode , offset , size , fip )  :
        fh = fip.contents if self.raw_fi else fip.contents.fh
        return self.operations.fallocate(
            None if path is None else path.decode(self.encoding, self.errors), mode, offset, size, fh
        )


class Operations(object):
    pass

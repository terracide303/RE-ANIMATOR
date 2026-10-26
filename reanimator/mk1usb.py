"""The one MK1 access RE-ANIMATOR makes itself: the LCD backlight, before the bridge starts.

The bridge never switches the backlight on, so after power-up the LCDs can stay dark. This writes MK1 LED bank B
(offset 0x1E) with only the backlight (device position 57 = 30 + 27) set, over EP1 OUT, without touching the alternate
setting: anything more (alternate setting 1, auto-reports, display init, LED bank A) makes the next bridge hang at
"MK1 arrived — opening" until the MK1 is unplugged (found 2026-10-26).

libusb is loaded from the app bundle (Frameworks/libusb-1.0.0.dylib, LGPL-2.1, see licenses/) or from Homebrew.
"""
import ctypes
import os
import sys

VID, PID = 0x17CC, 0x0808          # Native Instruments Maschine MK1 (firmware loaded)
EP_CMD_OUT = 0x01
CMD_DIMM_LEDS = 0x0C
BANK_B, BACKLIGHT_INDEX, BRIGHT = 0x1E, 27, 63


def _libusb():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(getattr(sys, '_MEIPASS', here), 'libusb-1.0.0.dylib'),
        os.path.join(here, '..', 'Frameworks', 'libusb-1.0.0.dylib'),
        '/opt/homebrew/lib/libusb-1.0.dylib',
        '/usr/local/lib/libusb-1.0.dylib',
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ctypes.CDLL(path)
            except OSError:
                continue
    return None


def set_backlight(on):
    """True if the command reached the MK1. False if libusb, the MK1 or its interface is not available."""
    lib = _libusb()
    if lib is None:
        return False
    vp = ctypes.c_void_p
    lib.libusb_init.argtypes = [ctypes.POINTER(vp)]
    lib.libusb_open_device_with_vid_pid.restype = vp
    lib.libusb_open_device_with_vid_pid.argtypes = [vp, ctypes.c_uint16, ctypes.c_uint16]
    lib.libusb_claim_interface.argtypes = [vp, ctypes.c_int]
    lib.libusb_release_interface.argtypes = [vp, ctypes.c_int]
    lib.libusb_close.argtypes = [vp]
    lib.libusb_exit.argtypes = [vp]
    lib.libusb_bulk_transfer.argtypes = [vp, ctypes.c_ubyte, ctypes.c_char_p, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
    ctx = vp()
    if lib.libusb_init(ctypes.byref(ctx)) != 0:
        return False
    try:
        handle = lib.libusb_open_device_with_vid_pid(ctx, VID, PID)
        if not handle:
            return False
        try:
            if lib.libusb_claim_interface(handle, 0) != 0:
                return False
            values = bytearray(33)
            values[BACKLIGHT_INDEX] = BRIGHT if on else 0
            data = bytes([CMD_DIMM_LEDS, BANK_B]) + bytes(values)
            done = ctypes.c_int()
            rc = lib.libusb_bulk_transfer(handle, EP_CMD_OUT, data, len(data), ctypes.byref(done), 200)
            lib.libusb_release_interface(handle, 0)
            return rc == 0 and done.value == len(data)
        finally:
            lib.libusb_close(handle)
    finally:
        lib.libusb_exit(ctx)

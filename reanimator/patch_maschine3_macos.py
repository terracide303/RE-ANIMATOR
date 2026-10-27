"""RE-ANIMATOR patcher for Maschine 3 on macOS: makes a patched COPY of Maschine 3 that drives an older controller
(today: the MK1) with Maschine's own controller class for it. The installed app is never modified.

    python3 patch_maschine3_macos.py "/Applications/Native Instruments/Maschine 3/Maschine 3.app" <dest folder> [--model mk1]
    python3 patch_maschine3_macos.py <Maschine 3.app> --check [--model mk1]      # find everything, write nothing

What it changes (experiment 18, notes/live-experiment-1.md), in every slice of the executable:
  1. the Maschine Jam subscription's vtable entry for onDeviceAdded -> the model's onDeviceAdded, so the subscription
     that Maschine 3 still runs on macOS creates the model's controller instead of a Jam;
  2. the Jam device ID in that subscription's subscribeToDevice (0x1500) -> the model's (MK1: 0x0808).

It finds everything by SYMBOL NAME (the executable keeps its symbols), not by address, so it works on Maschine 3
versions it has never seen, as long as these classes exist. Every patch site must be found exactly once and hold the
expected bytes, or it aborts without writing anything. The copy is then re-signed ad hoc (keeping Maschine's
entitlements). Nothing from Native Instruments is stored here: it patches the user's own installation, locally.
"""
import argparse
import os
import plistlib
import shutil
import struct
import subprocess
import sys

MODELS = {  # model -> (subscription class as mangled in the symbols, device ID)
    'mk1': ('MaschineMK112Subscription', 0x0808),
    # BETA: the MK2 is driven by NI's own NIHardwareAgent (it still has the MK2 class), so it needs no bridge;
    # the patch is the same two changes as the MK1's. Like the Windows MK2 patch, it takes the Jam's slot.
    'mk2': ('MaschineMK212Subscription', 0x1140),
    # BETA: the Mikros are USB HID devices, which macOS drives without NI's old kernel drivers, and NI's own
    # agent still has both classes, so like the MK2 they need no bridge. They take the Jam's slot as well.
    'mikro1': ('MaschineMikroMK112Subscription', 0x1110),
    'mikro2': ('MaschineMikroMK212Subscription', 0x1200),
}
JAM, JAM_PID = 'MaschineJam12Subscription', 0x1500
SUB = 'ControllerSubscriptionINS_4NHL2'           # NI::MASCOMMON::HW::ControllerSubscription<NI::NHL2::<model>::Subscription, ...>
VTABLE = '__ZTVN2NI9MASCOMMON2HW22' + SUB

FAT_MAGIC, MH_MAGIC_64 = 0xCAFEBABE, 0xFEEDFACF
LC_SEGMENT_64, LC_SYMTAB = 0x19, 0x2
CPU = {0x01000007: 'x86_64', 0x0100000C: 'arm64'}
TARGET_MASK = (1 << 36) - 1                       # DYLD_CHAINED_PTR_64_OFFSET: runtime offset of the target


class Abort(Exception):
    pass


def slices(data):
    """[(arch, offset, size)] of a fat (or thin) Mach-O file."""
    magic = struct.unpack_from('>I', data, 0)[0]
    if magic == FAT_MAGIC:
        n = struct.unpack_from('>I', data, 4)[0]
        out = []
        for i in range(n):
            cputype, _, off, size, _ = struct.unpack_from('>iiIII', data, 8 + 20 * i)
            out.append((CPU.get(cputype & 0xFFFFFFFF, hex(cputype)), off, size))
        return out
    if struct.unpack_from('<I', data, 0)[0] == MH_MAGIC_64:
        return [(CPU.get(struct.unpack_from('<I', data, 4)[0], '?'), 0, len(data))]
    raise Abort('not a Mach-O executable')


class Slice:
    def __init__(self, data, arch, base):
        self.data, self.arch, self.base = data, arch, base     # data: the whole file (bytearray); base: slice offset
        magic, cputype, _, _, ncmds, _, _, _ = struct.unpack_from('<IiIIIIII', data, base)
        if magic != MH_MAGIC_64:
            raise Abort('%s: not a 64-bit Mach-O slice' % arch)
        self.segments, self.symbols, self.addresses, self.sorted_addresses = [], {}, set(), None
        p = base + 32
        for _ in range(ncmds):
            cmd, size = struct.unpack_from('<II', data, p)
            if cmd == LC_SEGMENT_64:
                name = data[p + 8:p + 24].rstrip(b'\0').decode()
                vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, p + 24)
                self.segments.append((name, vmaddr, vmsize, fileoff, filesize))
            elif cmd == LC_SYMTAB:
                symoff, nsyms, stroff, _ = struct.unpack_from('<IIII', data, p + 8)
                self._read_symbols(symoff, nsyms, stroff)
            p += size
        text = [s for s in self.segments if s[0] == '__TEXT']
        if not text:
            raise Abort('%s: no __TEXT segment' % arch)
        self.image_base = text[0][1]

    def _read_symbols(self, symoff, nsyms, stroff):
        d, b = self.data, self.base
        for i in range(nsyms):
            strx, ntype, sect, _, value = struct.unpack_from('<IBBhQ', d, b + symoff + 16 * i)
            if sect == 0 or ntype & 0xE0:                # undefined or debug (stab) entries
                continue
            self.addresses.add(value)                    # every defined symbol bounds a function
            end = d.index(b'\0', b + stroff + strx)
            name = d[b + stroff + strx:end].decode('latin-1')
            if 'Maschine' in name and SUB in name:       # only what we need: keeps it fast
                self.symbols[name] = value

    def file_offset(self, vmaddr):
        for _, va, vs, fo, fs in self.segments:
            if va <= vmaddr < va + min(vs, fs):
                return self.base + fo + vmaddr - va
        raise Abort('%s: address %#x is not in the file' % (self.arch, vmaddr))

    def one(self, *parts, prefix=''):
        hits = [(n, a) for n, a in self.symbols.items() if n.startswith(prefix) and all(p in n for p in parts)]
        if len(hits) != 1:
            raise Abort('%s: expected one symbol with %s, found %d' % (self.arch, ' + '.join(parts), len(hits)))
        return hits[0]

    def function_end(self, start):
        """the next symbol after `start` (all symbols of the slice, so the function's range is tight)"""
        later = [a for a in self.all_addresses() if a > start]
        return min(later) if later else start + 0x400

    def all_addresses(self):
        if self.sorted_addresses is None:
            self.sorted_addresses = sorted(self.addresses)
        return self.sorted_addresses


def plan_slice(s, model_class, model_pid):
    """[(file offset, original bytes, new bytes, description)] for one slice; Abort if anything is ambiguous."""
    patches = []
    jam_added = s.one(JAM, '13onDeviceAdded', prefix='__ZN')[1]
    model_added = s.one(model_class, '13onDeviceAdded', prefix='__ZN')[1]
    vtable = s.one(JAM, prefix=VTABLE)[1]

    # 1. vtable: the entry whose chained-fixup target is Jam's onDeviceAdded
    jam_off, model_off = jam_added - s.image_base, model_added - s.image_base
    hits = []
    for k in range(2, 16):                               # skip offset-to-top and typeinfo
        fo = s.file_offset(vtable + 8 * k)
        value = struct.unpack_from('<Q', s.data, fo)[0]
        if value >> 63 == 0 and value & TARGET_MASK == jam_off:
            hits.append((fo, value))
    if len(hits) != 1:
        raise Abort('%s: Jam onDeviceAdded found %d times in its vtable (expected once)' % (s.arch, len(hits)))
    fo, value = hits[0]
    new = (value & ~TARGET_MASK) | model_off
    patches.append((fo, struct.pack('<Q', value), struct.pack('<Q', new),
                    'vtable slot %d: onDeviceAdded Jam %#x -> model %#x' % ((fo - s.file_offset(vtable)) // 8,
                                                                         jam_added, model_added)))

    # 2. the device ID in Jam's subscribeToDevice
    start = s.one(JAM, '17subscribeToDevice', prefix='__ZN')[1]
    lo, hi = s.file_offset(start), s.file_offset(start) + (s.function_end(start) - start)
    code = s.data[lo:hi]
    hits = []
    if s.arch == 'arm64':                                # MOVZ Wd, #0x1500 (32-bit, no shift)
        for i in range(0, len(code) - 3, 4):
            word = struct.unpack_from('<I', code, i)[0]
            if word & 0xFFE00000 == 0x52800000 and (word >> 5) & 0xFFFF == JAM_PID:
                patches_new = (word & ~(0xFFFF << 5)) | (model_pid << 5)
                hits.append((lo + i, struct.pack('<I', word), struct.pack('<I', patches_new)))
    else:                                                # MOV r32, imm32 0x1500 (B8+r)
        imm = struct.pack('<I', JAM_PID)
        for i in range(len(code) - 4):
            if 0xB8 <= code[i] <= 0xBF and code[i + 1:i + 5] == imm:
                hits.append((lo + i + 1, imm, struct.pack('<I', model_pid)))
    if len(hits) != 1:
        raise Abort('%s: device ID %#x found %d times in subscribeToDevice (expected once)' % (s.arch, JAM_PID, len(hits)))
    fo, old, new = hits[0]
    patches.append((fo, old, new, 'subscribeToDevice: device ID %#06x -> %#06x' % (JAM_PID, model_pid)))
    return patches


EXE = 'Maschine 3'
# The copy's executable is called "Maschine 2": the bundled MK1 Revive bridge decides whether Maschine is running with
# `pgrep -x 'Maschine 2'` (it was made for Maschine 2), and with a process called "Maschine 3" it shows its idle screen
# instead of Maschine's within two seconds. Info.plist's CFBundleExecutable is changed to match.
COPY_EXE = 'Maschine 2'


def executable(app):
    """the app's executable, as its Info.plist names it"""
    try:
        with open(os.path.join(app, 'Contents', 'Info.plist'), 'rb') as f:
            name = plistlib.load(f).get('CFBundleExecutable') or EXE
    except (OSError, plistlib.InvalidFileException):
        name = EXE
    return os.path.join(app, 'Contents', 'MacOS', name)
COPY_PREFIX = 'Maschine 3 (RE-ANIMATOR '


def app_version(app):
    with open(os.path.join(app, 'Contents', 'Info.plist'), 'rb') as f:
        return plistlib.load(f).get('CFBundleShortVersionString', '?')


def check(app, model):
    """(version, data, plan) for patching `app` for `model`; raises Abort if anything is ambiguous. Writes nothing."""
    model_class, model_pid = MODELS[model]
    data = bytearray(open(executable(app), 'rb').read())
    plan = []
    for arch, off, _ in slices(data):
        plan += [(arch,) + p for p in plan_slice(Slice(data, arch, off), model_class, model_pid)]
    for arch, fo, old, new, desc in plan:
        if data[fo:fo + len(old)] != old:
            raise Abort('%s: bytes at %#x changed under us' % (arch, fo))
    return app_version(app), data, plan


def patch(app, dest, model, force=False):
    """Writes and signs the patched copy; returns its path. Raises Abort before writing anything if a check fails."""
    _, data, plan = check(app, model)
    copy = os.path.join(dest, COPY_PREFIX + model.upper() + ').app')
    if os.path.exists(dest) and os.path.samefile(app, dest):
        raise Abort('the destination must not be the app itself')
    if os.path.exists(copy):
        if not force:
            raise Abort('%s exists (replace it, or clean first)' % copy)
        if patched_model(copy) is None:
            raise Abort('%s exists but is not a RE-ANIMATOR copy: not touching it' % copy)
        shutil.rmtree(copy)
    os.makedirs(dest, exist_ok=True)
    subprocess.run(['ditto', app, copy], check=True)
    for arch, fo, old, new, desc in plan:
        data[fo:fo + len(new)] = new
    os.remove(executable(copy))
    with open(os.path.join(copy, 'Contents', 'MacOS', COPY_EXE), 'wb') as f:
        f.write(data)
    os.chmod(os.path.join(copy, 'Contents', 'MacOS', COPY_EXE), 0o755)
    plist_path = os.path.join(copy, 'Contents', 'Info.plist')
    with open(plist_path, 'rb') as f:
        info = plistlib.load(f)
    info['CFBundleExecutable'] = COPY_EXE
    with open(plist_path, 'wb') as f:
        plistlib.dump(info, f)
    entitlements = subprocess.run(['codesign', '-d', '--entitlements', ':-', app], capture_output=True).stdout
    ent_file = os.path.join(dest, '.entitlements.plist')
    with open(ent_file, 'wb') as f:
        f.write(entitlements)
    sign = ['codesign', '-f', '-s', '-'] + (['--entitlements', ent_file] if entitlements.strip() else []) + [copy]
    r = subprocess.run(sign, capture_output=True, text=True)
    os.remove(ent_file)
    if r.returncode != 0:
        raise Abort('patched, but re-signing failed: ' + r.stderr.strip())
    return copy


_PATCHED = {}  # executable path -> ((mtime, size), model): reading a 600 MB executable takes ~0.8 s


def patched_model(app):
    """The model a RE-ANIMATOR copy is patched for (its Jam vtable entry points to that model's onDeviceAdded),
    or None for anything else, the original Maschine 3 included. Remembered until the executable changes."""
    exe = executable(app)
    try:
        st = os.stat(exe)
    except OSError:
        return None
    key = (st.st_mtime, st.st_size)
    if exe in _PATCHED and _PATCHED[exe][0] == key:
        return _PATCHED[exe][1]
    model = _patched_model(app)
    _PATCHED[exe] = (key, model)
    return model


def _patched_model(app):
    try:
        data = open(executable(app), 'rb').read()
        for arch, off, _ in slices(data):
            s = Slice(data, arch, off)
            vtable = s.one(JAM, prefix=VTABLE)[1]
            # Jam's own entries only: the vtable ends at the next one's offset-to-top (0). Reading a fixed 14
            # ran into the NEXT vtable -- the Mikro MK1 subscription's, with its own onDeviceAdded -- so a Mikro
            # MK2 copy was taken for a Mikro MK1 (found 2026-10-27 when the Mikros were added).
            entries = []
            for k in range(2, 32):
                v = struct.unpack_from('<Q', data, s.file_offset(vtable + 8 * k))[0]
                if v == 0:
                    break
                entries.append(v)
            for model, (cls, _) in MODELS.items():
                target = s.one(cls, '13onDeviceAdded', prefix='__ZN')[1] - s.image_base
                if any(v >> 63 == 0 and v & TARGET_MASK == target for v in entries):
                    return model
            return None
    except (Abort, OSError, struct.error):
        return None
    return None


def find_copies(dest):
    """[(path, model)] of the RE-ANIMATOR copies in `dest`: named like one AND carrying our patch."""
    if not os.path.isdir(dest):
        return []
    out = []
    for name in sorted(os.listdir(dest)):
        path = os.path.join(dest, name)
        if name.startswith(COPY_PREFIX) and name.endswith('.app') and os.path.isdir(path):
            model = patched_model(path)
            if model:
                out.append((path, model))
    return out


def clean(dest):
    """Removes the RE-ANIMATOR copies in `dest` (only those, see find_copies); returns the removed paths."""
    removed = []
    for path, _ in find_copies(dest):
        shutil.rmtree(path)
        removed.append(path)
    return removed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('app', nargs='?', default='/Applications/Native Instruments/Maschine 3/Maschine 3.app',
                    help='the installed Maschine 3.app (only read)')
    ap.add_argument('dest', nargs='?', help='folder for the patched copy')
    ap.add_argument('--model', default='mk1', choices=sorted(MODELS))
    ap.add_argument('--check', action='store_true', help='find and verify every patch site, write nothing')
    ap.add_argument('--force', action='store_true', help='replace an existing RE-ANIMATOR copy in dest')
    ap.add_argument('--clean', metavar='FOLDER', help='remove the RE-ANIMATOR copies in FOLDER (nothing else)')
    ap.add_argument('--yes', action='store_true', help='with --clean: do not ask')
    a = ap.parse_args()

    if a.clean:
        copies = find_copies(a.clean)
        if not copies:
            print('no RE-ANIMATOR copies in %s' % a.clean)
            return
        for path, model in copies:
            print('  %s  (%s)' % (path, model))
        if not a.yes and input('remove these %d copies? [y/N] ' % len(copies)).strip().lower() != 'y':
            print('nothing removed')
            return
        for path in clean(a.clean):
            print('removed %s' % path)
        return

    try:
        version, _, plan = check(a.app, a.model)
    except Abort as e:
        sys.exit('ABORTED (nothing written): %s' % e)
    print('Maschine %s, model %s (%#06x)' % (version, a.model, MODELS[a.model][1]))
    for arch, fo, old, new, desc in plan:
        print('  %-6s @ %#011x  %s -> %s  %s' % (arch, fo, old.hex(), new.hex(), desc))
    if a.check:
        print('check only: nothing written')
        return
    if not a.dest:
        sys.exit('give a destination folder (or --check)')
    try:
        print('written and signed: %s' % patch(a.app, a.dest, a.model, a.force))
    except Abort as e:
        sys.exit('ABORTED: %s' % e)


if __name__ == '__main__':
    main()

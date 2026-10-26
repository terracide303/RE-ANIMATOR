"""The MK1 bridge for RE-ANIMATOR: the program that stands in for NI's hardware agent and drives the MK1.

Today that is andy83's MK1 Revive bridge (`mk1-bridge`), bundled unchanged in vendor/ (permission:
docs/licenses/MK1-Revive.md); a user's own install is the fallback. Our own stand-in will replace it behind the same functions.

Only one program can own the MK1 and NI's port, so starting the bridge first moves the others aside:
NI's hardware agent (quit, and started again on stop if it ran before) and our mk1-controller daemon (stopped).
"""
import os
import plistlib
import signal
import sys
import subprocess
import time

BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))   # inside the .app: its resources
# The bridge (MK1 Revive by andy83, unchanged; docs/licenses/MK1-Revive.md): in the .app just its executable,
# vendor/mk1-bridge (a nested .app does not survive packaging); in this folder the whole MK1 Revive.app.
VENDOR = os.path.join(BASE, 'vendor', 'mk1-bridge')
VENDOR_DEV = os.path.join(BASE, 'vendor', 'MK1 Revive.app', 'Contents', 'MacOS', 'mk1-bridge')
VENDOR_APP = os.path.join(BASE, '..', 'Resources', 'vendor', 'mk1-bridge')   # copied in after packaging, unsigned by us
CANDIDATES = [
    VENDOR_APP,
    VENDOR,
    VENDOR_DEV,
    '/Applications/MK1 Revive.app/Contents/MacOS/mk1-bridge',
    os.path.expanduser('~/Applications/MK1 Revive.app/Contents/MacOS/mk1-bridge'),
]
NI_AGENT = 'NIHardwareAgent'
NI_AGENT_APP = '/Library/Application Support/Native Instruments/Hardware/NIHardwareAgent.app'
MK1D = 'daemon/mk1d.py'                       # our mk1-controller daemon (its command line contains this)
LOG = os.path.expanduser('~/Library/Logs/RE-ANIMATOR-bridge.log')



def pids(pattern, exact=False):
    r = subprocess.run(['pgrep', '-x' if exact else '-f', pattern], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def find_bridge():
    for path in CANDIDATES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def bridge_running():
    return bool(pids('mk1-bridge', exact=True))


def ni_agent_running():
    return bool(pids(NI_AGENT, exact=True))


def mk1d_running():
    return bool(pids(MK1D))


def _stop(pid_list, wait=5.0):
    for pid in pid_list:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    end = time.time() + wait
    while time.time() < end and any(_alive(p) for p in pid_list):
        time.sleep(0.2)
    for pid in pid_list:
        if _alive(pid):
            os.kill(pid, signal.SIGKILL)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Bridge:
    """Starts and stops the bridge, and puts NI's agent back if it moved it aside."""

    def __init__(self, path):
        self.path = path
        self.stopped_ni_agent = False

    def start(self, stop_mk1d=False):
        """-> list of what it did (for the user)"""
        done = []
        if bridge_running():
            return ['The MK1 bridge was already running.']
        if mk1d_running():
            if not stop_mk1d:
                raise RuntimeError('our MK1 daemon (mk1-controller) is using the MK1')
            _stop(pids(MK1D))
            done.append('Stopped the mk1-controller daemon (it was using the MK1).')
        if ni_agent_running():
            subprocess.run(['osascript', '-e', 'tell application "%s" to quit' % NI_AGENT], capture_output=True)
            time.sleep(1.5)
            if ni_agent_running():
                _stop(pids(NI_AGENT, exact=True))
            self.stopped_ni_agent = True
            done.append("Quit NI's hardware agent (it is started again when you stop the bridge).")
        # Backlight on first: the bridge never switches it on itself. Only the command channel is touched (see lights):
        # our full driver init (alternate setting 1, auto-reports, display init) makes the bridge hang at "opening".
        if lights(backlight=True):
            done.append('Switched the MK1 backlight on.')
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        # NI's agent may still hold its port name for a moment after quitting: then the bridge logs "FAILED to register"
        # and stays up without its port. Wait for "waiting for Maschine software" (it owns the port), else retry.
        for attempt in range(3):
            mark = _bridge_log_size()
            with open(LOG, 'ab') as log:
                subprocess.Popen([self.path], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            outcome = _wait_for_bridge(mark, 15.0)
            if outcome == 'ok':
                done.append('Started the MK1 bridge.')
                return done
            _stop(pids('mk1-bridge', exact=True), wait=20.0)
            time.sleep(2.0)
        raise RuntimeError("the bridge could not take NI's port (is NI's hardware agent running?); log: %s" % BRIDGE_LOG)

    def restart(self):
        """shows the bridge's idle screen again (used when Maschine quits: the bridge does not always notice)"""
        _stop(pids('mk1-bridge', exact=True), wait=20.0)
        with open(LOG, 'ab') as log:
            subprocess.Popen([self.path], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

    def stop(self):
        done = []
        if bridge_running():
            # Let it shut down cleanly (it closes the MK1 itself, which takes a few seconds): a bridge killed
            # hard leaves the MK1 half set up, and the next one hangs at "opening" until the MK1 is unplugged.
            _stop(pids('mk1-bridge', exact=True), wait=20.0)
            done.append('Stopped the MK1 bridge.')
        # Nothing is written to the MK1 on stop: a second access (backlight off now, on at the next start) made the next
        # bridge hang at "opening" (seen 2026-10-26). The LCDs keep their last picture until the next START.
        if self.stopped_ni_agent and os.path.isdir(NI_AGENT_APP):
            subprocess.run(['open', '-g', NI_AGENT_APP])
            self.stopped_ni_agent = False
            done.append("Started NI's hardware agent again.")
        return done or ['The MK1 bridge was not running.']


def copy_running(copy):
    """is the patched Maschine 3 copy at `copy` running? A plain text match on the process list: pgrep -f takes a
    regular expression, and the copy's name has parentheses ("Maschine 3 (RE-ANIMATOR MK1).app"), so it never matched."""
    try:
        with open(os.path.join(copy, 'Contents', 'Info.plist'), 'rb') as f:
            name = plistlib.load(f).get('CFBundleExecutable', 'Maschine 3')
    except (OSError, plistlib.InvalidFileException):
        name = 'Maschine 3'
    exe = os.path.join(copy, 'Contents', 'MacOS', name)
    r = subprocess.run(['ps', '-axo', 'command='], capture_output=True, text=True)
    return any(line.startswith(exe) for line in r.stdout.splitlines())




def lights(backlight):
    """The LCD backlight on or off, the one access the bridge tolerates (see mk1usb.py). Called before it starts."""
    if bridge_running():
        return False
    import mk1usb
    try:
        return mk1usb.set_backlight(backlight)
    except Exception:  # noqa: BLE001 -- the backlight is a nicety: never stop START for it
        return False


BRIDGE_LOG = '/tmp/maschine-mk1-revive/bridge.log'    # written by the bridge itself


def _bridge_log_size():
    try:
        return os.path.getsize(BRIDGE_LOG)
    except OSError:
        return 0


def _wait_for_bridge(mark, timeout):
    """'ok' once the bridge owns NI's port, 'failed' if it could not, 'timeout' otherwise (reads the log after mark)"""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(BRIDGE_LOG, 'rb') as f:
                if os.path.getsize(BRIDGE_LOG) < mark:      # the bridge wrapped its log: read it all
                    mark = 0
                f.seek(mark)
                text = f.read().decode('utf-8', 'replace')
        except OSError:
            text = ''
        if 'waiting for Maschine software' in text:
            return 'ok'
        if 'FAILED to register' in text or 'Failed to start IPC server' in text:
            return 'failed'
        time.sleep(0.3)
    return 'timeout'

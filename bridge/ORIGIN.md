# The MK1 bridge: where it comes from

RE-ANIMATOR's MK1 bridge is **our version of `mk1-bridge` from MK1 Revive by andy83**
(<https://github.com/andy83-projects/maschine-mk1-revive>), forked from tag **v0.3.6** (commit `bc270dc`,
2026-04-29). Only the parts the bridge needs are here: `mk1-bridge/`, `mk1-usb/` and `mk1-ipc/`. The upstream
repository has no licence file; **andy83 gave Dennis permission to include and change it, on the condition that he
is credited** (see `../docs/licenses/MK1-Revive.md`). The credit is on RE-ANIMATOR's main window and in its README.

It contains no Native Instruments code or data: the MK1 loads its own firmware, and the bridge speaks the USB and
IPC protocols that andy83 worked out (with biappi/Macchina as his prior art).

Build: `./build.sh` here, or RE-ANIMATOR's own `../build.sh`, which builds it and puts it in the app.

## What we changed (newest last)

* **2026-10-27 · Maschine 3 is recognised.** The bridge decides whether Maschine runs with `pgrep -x`; upstream only
  looks for `Maschine 2`, so with Maschine 3 it showed its idle screen two seconds after connecting. It now matches
  `Maschine 2` and `Maschine 3` (`MASCHINE_PROCESS` in `mk1-bridge/main.c`). RE-ANIMATOR's patched copy still names
  its executable `Maschine 2`, so the original bridge keeps working with it too.

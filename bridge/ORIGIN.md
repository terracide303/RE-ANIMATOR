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
* **2026-10-27 · RE-ANIMATOR's own screen animation instead of the UFO and cat.** Drawn by `anim/make_anim.py` (our
  own artwork, inspired by the film, nothing copied) into `reanimator.anim`, which the bridge loads from beside its
  binary (`anim_load` in `mk1-bridge/main.c`): a flatline, a syringe of glowing reagent, a heartbeat, one big
  RE-ANIMATOR logo over both screens that splits into one logo per screen, then a living loop (drips that fall and
  grow back, a small heartbeat, a pulse on each beat). The intro replays every 30 s while it waits for Maschine.
  Without the file, andy83's UFO-and-cat animation plays as before. Tested on the MK1 on 2026-10-27.
* **2026-10-27 · The screens are really cleared on connect.** On arrival the bridge cleared both screens with one
  `mk1_set_display` call per screen (10880 bytes), which refuses anything over 508 bytes ("payload too large" in the
  log), so stale pixels stayed. It now goes through `send_fb_to_display`, which sends a frame in pieces.
* **2026-10-27 · The reconnect message** no longer says "restart Maschine 2 manually" but what to do: quit Maschine and
  start it again (in RE-ANIMATOR: START). Checked and left alone: the backlight (kept on by `emit_led_state`, also
  after Maschine quits) and the auto-open of Maschine 2 (off unless `MK1_AUTO_OPEN_MASCHINE` is set).
* **2026-10-27 · Pads, lights and screen updates, after oskarmust's fork.** oskarmust's fork of MK1 Revive
  (<https://github.com/oskarmust/maschine-mk1-revive>, "SPITE") found these upstream faults; it has no licence, so
  none of its code is used: the fixes are written here from what the faults are.
  * **Pads** (`mk1-usb/mk1_device.c`): each word of a pad report carries its pad number (top 4 bits) and pressure
    (12 bits), and a report can begin at any pad. Upstream took the pad from the word's position, dropped reports
    that did not begin at pad 0 and subtracted a first-report baseline: missed and dropped hits. Now the pad number
    comes from the word, and a report without all sixteen pad numbers in both passes is skipped.
  * **Lights**: LEDs Maschine switches off (value 0) were not copied, so they kept their old level.
  * **Black screen updates** were skipped, so cleared areas kept old pixels.
  * **Screen updates between two sends** kept only the newest rectangle; the pending area now grows to cover them all.
  **Played on Dennis's MK1 with Maschine 3 on 2026-10-27: works fine** (no systematic pad test yet).
* **2026-10-27 · More scenes while it waits:** after the living logos, "Rufus" (a dead cat on the lab table, the
  syringe, a flash, the cat alive and hissing) and the lab (bubbling flasks, a brain in a jar with sparks). Our own drawing, inspired by
  the film. The bridge now plays the whole file in a loop when it is longer than the 30 s replay.
* **2026-10-27 · The split lands where the logos drip:** each copy moves and shrinks from the big logo's exact place to
  the small logo's exact place (it landed 10 px lower as a shrunk picture and was then redrawn, which made the E look
  broken when the drips started). The morgue scene is gone (Dennis: it looked dumb).
* **2026-10-27 · Sharp letters, a clean E, a spraying needle.** All text is drawn without anti-aliasing and the small
  logos use Avenir Next Bold 24 instead of Heavy 22, whose E closed up into a lump on the 255x64 screens. In the cat
  scene the reagent now sprays from the needle across both screens to the cat. The scientist scene was tried and
  removed.
* **2026-10-27 · The logos glow slowly and come back between the scenes:** after the intro the file runs logos (8.8 s,
  three slow glows) -> Rufus -> logos -> the lab, about 41 s, then the bridge starts it over.
* **2026-10-27 · An Amiga-style sine scroller** runs under the glowing logos over both screens: what RE-ANIMATOR is,
  how it keeps gear out of the e-waste and brings it back to Maschine 3 and 2, and greetings to andy83 and oskarmust.
  It carries on from one stretch of logos to the next (13.2 s each now); one round of the file is about 49 s.


# RE-ANIMATOR

[![Support me on Ko-fi](https://img.shields.io/badge/Support%20me%20on%20Ko--fi-%E2%98%95-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/terracide)
*This is free and always will be: no paywall, no catch. I build it in my spare time and don't earn a cent from it. If it saved you an evening or brought your gear back to life, a coffee on [Ko-fi](https://ko-fi.com/terracide) would honestly help me a lot to keep going.*

**Old controllers, new life.** RE-ANIMATOR runs **Maschine 3** on a **Maschine MK1**, a controller that Maschine 3
no longer supports on macOS. Keep your gear out of the e-waste.

![RE-ANIMATOR](docs/screenshot.png)

> **Beta (0.1).** Unofficial; not made, supported or endorsed by Native Instruments. Use at your own risk.

## In plain words

**What it does.** Maschine 3 still has the MK1 support built in; Native Instruments switched it off. RE-ANIMATOR:

1. **makes a copy** of Maschine 3 and switches the MK1 support back on in that copy (two small changes);
2. **starts a small helper** (our version of MK1 Revive by andy83) that talks to the MK1 over USB: Maschine's screens on the MK1, and
   the pads, buttons and knobs back to Maschine;
3. **opens the copy.** When you quit Maschine, the helper stops too.

**Why it is safe.**

* **Your original Maschine 3 is never touched.** It is only read; everything happens in the copy.
* **Your MK1 is not changed.** No firmware is written; it is only controlled over USB, just like NI's own software
  does.
* **It refuses instead of guessing.** If your Maschine version doesn't look exactly as expected, nothing is changed.
* **Fully undoable.** *Clean* deletes the copy; delete the app and everything is as before.
* **Open:** all the code is here to read.

> **This is the `betatest` branch: version 0.4 beta.** It adds the Maschine MK2 and both Maschine Mikros (MK1 and
> MK2), untested on a Mac so far, our own
> version of the MK1 bridge with pad, light and screen fixes, and RE-ANIMATOR's own startup animation on the MK1's
> screens. The stable version is on `main`.

## Maschine MK2 (beta)

The MK2 works differently from the MK1, and more simply: **Native Instruments' own hardware agent still knows the
MK2**, so it needs no bridge. RE-ANIMATOR makes a patched copy of Maschine 3 for the MK2 (the same two small
changes as for the MK1), makes sure NI's agent runs, and opens the copy.

* Choose **Maschine MK2 (beta)** under *Options → Controller*, then press START.
* **A Maschine Jam does not work while you use the MK2 this way**: the MK2 takes the Jam's place in Maschine 3 (the
  same trade-off as the known Windows MK2 patch). Your original Maschine 3 still runs the Jam as before.
* Nobody has confirmed this on a Mac yet. **Beta testers: please report** what works (screens, pads, buttons,
  knobs, LEDs) and what does not, with your macOS and Maschine 3 versions and the logs listed below.

## Maschine Mikro MK1 and MK2 (beta)

The Mikros work like the MK2: they are standard USB HID devices that macOS drives without NI's old drivers, and NI's
own agent still has both, so **no bridge** is needed. Choose **Maschine Mikro MK1 (beta)** or **Maschine Mikro MK2
(beta)** as the controller (it is picked for you when one is plugged in) and press START. As with the MK2, a Maschine
Jam does not work in that copy of Maschine 3. With Maschine 2 the Mikro MK2 is supported by NI anyway.

## Maschine 2 (beta)

Maschine 2 still knows the MK1 and the MK2, so it needs **no patch**. Choose **Software: Maschine 2** on
the main screen and press START: for the MK1 RE-ANIMATOR starts the bridge and opens Maschine 2 as installed, and
stops the bridge when you quit it; the MK2 runs on NI's own agent, as NI made it.

## How it works

* It makes a **patched copy** of your installed Maschine 3 in its own folder (by default `~/Applications/RE-ANIMATOR`).
  Your **original Maschine 3 is only read and stays exactly as it is**. The copy switches on Maschine 3's own MK1
  support, which is still in the program but no longer used on macOS.
* It starts the **MK1 bridge** (our version of MK1 Revive by andy83, included), which stands in for NI's hardware agent and drives the
  MK1: its displays, LEDs, pads, buttons and knobs.
* When you quit Maschine 3, the bridge stops by itself.

Nothing from Native Instruments is in this repository or in the app: RE-ANIMATOR patches *your* installation, on your
Mac.

## Requirements

* A Mac with **Apple Silicon** (M1 or later).
* **Maschine 3**, installed and activated. **Confirmed working:** 3.6.0 (iMac, Apple Silicon) and 3.7 (Mac mini M4, a beta tester, 2026-10-27). Other versions are checked before anything is patched: if
  RE-ANIMATOR does not find exactly what it expects, it refuses and changes nothing.
* A **Maschine MK1** connected over USB.
* About 1 GB of free disk space for the patched copy.

## Install (beta testers)

1. Download `RE-ANIMATOR-0.1-beta-arm64.zip` from the [Releases](../../releases) page and unzip it.
2. Move **RE-ANIMATOR.app** to your Applications folder.
3. First start: **right-click → Open → Open** (the app is not notarized by Apple, so macOS asks once). If macOS still
   blocks it: *System Settings → Privacy & Security → Open Anyway*.

## Use

1. Connect the MK1.
2. Open RE-ANIMATOR. The main screen shows the controller and the Maschine 3 version it found.
3. Press **START**. The first time it makes the patched copy (about a minute); then it starts the bridge and the copy.
4. Maschine 3 connects to the MK1 **after its plugin scan**, which can take a while with many plugins.
5. Quit Maschine 3 when you are done: the bridge stops by itself.

**Options** (folded away): choose Maschine 3, the folder for the copy, or the bridge by hand; **Clean** removes the
patched copies (only those: never your original or anything else).

## If something goes wrong

* **LCDs stay dark or frozen:** quit Maschine 3, press *Stop bridge*, unplug the MK1 and plug it back in, press START.
* **NI's own hardware agent** (NIHardwareAgent) holds the MK1 and its port: RE-ANIMATOR quits it on START and starts
  it again when you stop the bridge.
* **Logs** (please send them with a report):
  * `~/Library/Logs/RE-ANIMATOR-app.log` — what START and the watcher did
  * `~/Library/Logs/RE-ANIMATOR-bridge.log` and `/tmp/maschine-mk1-revive/*.log` — the bridge
* Report: open an issue with your macOS version, your Maschine 3 version, what you did, what happened, and the logs.

## Remove

Open Options → **Clean** (removes the patched copy), quit, and delete RE-ANIMATOR.app. Your original Maschine 3 was never
changed.

## Build from source

```sh
brew install libusb        # bundled into the app (LGPL-2.1, licence included)
./build.sh                 # -> dist/RE-ANIMATOR.app and dist/RE-ANIMATOR-<version>-arm64.zip
```

Source: `reanimator/` — `reanimator_app.py` (the window), `patch_maschine3_macos.py` (the patcher: finds every patch
point by symbol name, refuses if anything is ambiguous; also usable on its own, see `--help`), `bridge.py` (starting
and stopping the bridge), `mk1usb.py` (the one MK1 access RE-ANIMATOR makes itself: the LCD backlight).

## Credits

* **MK1 bridge: based on MK1 Revive by andy83** — <https://github.com/andy83-projects/maschine-mk1-revive>. Our changed version is in `bridge/` (what changed: `bridge/ORIGIN.md`). 
* **Pad, light and screen fixes** in our bridge follow faults found by **oskarmust**'s fork of MK1 Revive
  (<https://github.com/oskarmust/maschine-mk1-revive>); our code is written independently (`bridge/ORIGIN.md`).
* **libusb** (LGPL-2.1) — <https://libusb.info>.
* Artwork: our own (`docs/licenses/artwork.md`).

Maschine and Native Instruments are trademarks of Native Instruments GmbH. RE-ANIMATOR is not affiliated with them.

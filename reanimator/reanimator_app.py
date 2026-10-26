#!/usr/bin/env python3
"""RE-ANIMATOR: one START button that runs Maschine 3 on an older controller.

    python3 reanimator_app.py

START checks the installed Maschine 3, makes the patched copy if there is none (or if Maschine 3 was updated since),
starts the MK1 bridge and opens the copy. When Maschine 3 quits, the bridge is stopped and the MK1 cleared. The
installed Maschine 3 is only ever read: it stays exactly as it is. Options (folded away): where Maschine 3, the copy and
the bridge are, the controller, Clean.
"""
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge as B  # noqa: E402
import patch_maschine3_macos as P  # noqa: E402

DEFAULT_APP = '/Applications/Native Instruments/Maschine 3/Maschine 3.app'
DEFAULT_DEST = os.path.expanduser('~/Applications/RE-ANIMATOR')
BUNDLE_ID = 'com.native-instruments.Maschine 3'
GOOD, BAD, NOTE, GREY = '#1a7f37', '#c62828', '#9a6700', '#6e6e73'
MODEL_NAMES = {'mk1': 'Maschine MK1'}
VERSION = '0.1 beta'
APP_LOG = os.path.expanduser('~/Library/Logs/RE-ANIMATOR-app.log')


def log(text):
    """one line in ~/Library/Logs/RE-ANIMATOR-app.log (what START and the watcher did, for finding problems)"""
    try:
        with open(APP_LOG, 'a') as f:
            f.write('%s  %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), text))
    except OSError:
        pass


def signer(app):
    r = subprocess.run(['codesign', '-dv', '--verbose=2', app], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if line.startswith('Authority='):
            return line.split('=', 1)[1]
    return 'ad hoc (no developer)' if 'Signature=adhoc' in r.stderr else 'not signed'


def find_maschine3():
    if os.path.isdir(DEFAULT_APP):
        return DEFAULT_APP
    r = subprocess.run(['mdfind', "kMDItemCFBundleIdentifier == '%s'" % BUNDLE_ID], capture_output=True, text=True)
    for path in r.stdout.splitlines():
        if os.path.basename(path) == 'Maschine 3.app' and P.patched_model(path) is None:
            return path
    return None


class App:
    def __init__(self, root):
        self.root = root
        root.title('RE-ANIMATOR %s' % VERSION)
        root.minsize(640, 360)
        f = self.frame = ttk.Frame(root, padding=20)
        f.grid(sticky='nsew')
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        assets = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), 'assets')
        # The Right to Repair logo and the e-waste picture are only used when they are there: they are left out of the
        # beta package until their permission is in docs/licenses/artwork.md.
        self.images = {n: ImageTk.PhotoImage(Image.open(os.path.join(assets, n + '.png')))
                       for n in ('right-to-repair', 'e-waste-ring') if os.path.isfile(os.path.join(assets, n + '.png'))}
        banner = Image.open(os.path.join(assets, 'banner.png'))                 # our own (design/reanimator-cover.png)
        self.images['banner'] = ImageTk.PhotoImage(banner.resize((520, int(520 * banner.height / banner.width))))
        ttk.Label(f, image=self.images['banner']).grid(row=0, column=0, sticky='w')
        ttk.Label(f, text='Version %s. Runs Maschine 3 on your older controller. Your original Maschine 3 stays exactly '
                          'as it is.' % VERSION,
                  foreground=GREY).grid(row=1, column=0, sticky='w', pady=(0, 16))
        if 'right-to-repair' in self.images:
            ttk.Label(f, image=self.images['right-to-repair']).grid(row=0, column=1, rowspan=3, sticky='ne', padx=(12, 0))

        top = ttk.Frame(f)
        top.grid(row=2, column=0, sticky='w')
        self.summary = tk.Label(top, text='', font=('Helvetica', 14), anchor='w', justify='left')
        self.summary.pack(side='top', anchor='w', pady=(0, 10))
        main = ttk.Frame(top)
        main.pack(side='top', anchor='w')
        style = ttk.Style()
        style.configure('Start.TButton', font=('Helvetica', 18, 'bold'), padding=(28, 12))
        self.start_button = ttk.Button(main, text='START', style='Start.TButton', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(main, text='Stop bridge', command=self.stop_bridge)
        self.stop_button.pack(side='left', padx=(16, 0))

        self.result = tk.Label(f, text='', font=('Helvetica', 14), justify='left', anchor='w', wraplength=600)
        self.result.grid(row=3, column=0, sticky='we', pady=(16, 8))

        foot = ttk.Frame(f)
        foot.grid(row=6, column=0, columnspan=2, sticky='we', pady=(16, 0))
        if 'e-waste-ring' in self.images:
            ttk.Label(foot, image=self.images['e-waste-ring']).pack(side='left')
        words = ttk.Frame(foot)
        words.pack(side='left', padx=(12, 0))
        ttk.Label(words, text='Old controllers, new life: keep your gear out of the e-waste.',
                  foreground=GREY, font=('Helvetica', 12, 'italic')).pack(anchor='w')
        ttk.Label(words, text='MK1 bridge: MK1 Revive by andy83 — github.com/andy83-projects/maschine-mk1-revive',
                  foreground=GREY, font=('Helvetica', 11)).pack(anchor='w', pady=(4, 0))

        self.opened = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text='Options', variable=self.opened, command=self.toggle_options).grid(
            row=4, column=0, sticky='w', pady=(8, 0))
        self.options = ttk.Frame(f)
        self.options.columnconfigure(1, weight=1)
        self.build_options(self.options)

        self.app_path, self.dest_path, self.bridge = None, DEFAULT_DEST, None
        self.detect()

    # --- options (folded away) -----------------------------------------------------------------------------------
    def build_options(self, o):
        self.app_status, self.app_detail = self.row(o, 0, 'Maschine 3', self.pick_app)
        self.dest_status, self.dest_detail = self.row(o, 2, 'Copy goes to', self.pick_dest)
        self.bridge_status, self.bridge_detail = self.row(o, 4, 'MK1 bridge', self.pick_bridge)
        ttk.Label(o, text='Controller', font=('Helvetica', 13, 'bold')).grid(row=6, column=0, sticky='w', pady=(8, 0))
        self.model = tk.StringVar(value=MODEL_NAMES['mk1'])
        ttk.Combobox(o, textvariable=self.model, values=[MODEL_NAMES[m] for m in sorted(P.MODELS)],
                     state='readonly', width=18).grid(row=6, column=1, sticky='w', padx=10, pady=(8, 0))
        bar = ttk.Frame(o)
        bar.grid(row=7, column=0, columnspan=3, sticky='w', pady=(12, 0))
        ttk.Button(bar, text='Clean…', command=self.clean).pack(side='left')
        self.show = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text='Show details', variable=self.show, command=self.toggle_details).pack(
            side='left', padx=(16, 0))
        self.details = tk.Text(o, height=8, font=('Menlo', 11), foreground=GREY, relief='flat')
        self.detail_lines = []

    def row(self, o, r, title, pick):
        ttk.Label(o, text=title, font=('Helvetica', 13, 'bold')).grid(row=r, column=0, sticky='nw', pady=(8, 0))
        status = tk.Label(o, text='', font=('Helvetica', 13), anchor='w', justify='left')
        status.grid(row=r, column=1, sticky='we', padx=10, pady=(8, 0))
        detail = tk.Label(o, text='', foreground=GREY, font=('Helvetica', 11), anchor='w', justify='left', wraplength=460)
        detail.grid(row=r + 1, column=1, sticky='we', padx=10)
        ttk.Button(o, text='Choose…', command=pick).grid(row=r, column=2, sticky='ne', pady=(8, 0))
        return status, detail

    def toggle_options(self):
        if self.opened.get():
            self.options.grid(row=5, column=0, sticky='nsew', pady=(4, 0))
        else:
            self.options.grid_remove()

    def toggle_details(self):
        if self.show.get():
            self.details.grid(row=8, column=0, columnspan=3, sticky='nsew', pady=(8, 0))
            self.note(self.detail_lines)
        else:
            self.details.grid_remove()

    def note(self, lines):
        self.detail_lines = list(lines)
        if self.show.get():
            self.details.delete('1.0', 'end')
            self.details.insert('end', '\n'.join(self.detail_lines))

    def tell(self, text, color):
        self.result.config(text=text, foreground=color)

    def model_key(self):
        return {v: k for k, v in MODEL_NAMES.items()}[self.model.get()]

    # --- what is where -------------------------------------------------------------------------------------------
    def detect(self):
        self.set_app(find_maschine3())
        self.set_dest(DEFAULT_DEST)
        self.set_bridge(B.find_bridge())
        self.idle()

    def show_summary(self):
        """the controller and the Maschine version, on the main screen"""
        software = ('Maschine 3 %s' % P.app_version(self.app_path)) if self.app_path else 'Maschine 3 not found'
        copy = ' · patched copy ready' if self.app_path and self.current_copy() else (
            ' · copy made on START' if self.app_path else '')
        self.summary.config(text='Controller: %s    ·    Software: %s%s' % (self.model.get(), software, copy),
                            foreground='black' if self.app_path else BAD)

    def idle(self):
        self.start_button.state(['!disabled'])
        self.show_summary()
        if not self.app_path:
            self.tell('Maschine 3 was not found. Open Options to choose it.', BAD)
        elif not self.bridge:
            self.tell('The MK1 bridge was not found. Open Options to choose it.', BAD)
        else:
            copy = self.current_copy()
            self.tell('Press START. ' + ('Your patched copy is ready.' if copy else
                                         'The first start makes the patched copy (about a minute).'), GREY)

    def set_app(self, path):
        self.app_path = path
        if not path:
            self.app_status.config(text='✗  Not found', foreground=BAD)
            self.app_detail.config(text='')
            return
        if P.patched_model(path):
            self.app_status.config(text='✗  That is a RE-ANIMATOR copy, not the original', foreground=BAD)
            self.app_detail.config(text=path)
            self.app_path = None
            return
        who = signer(path)
        official = 'Native Instruments' in who
        self.app_status.config(text='✓  Detected: Maschine 3 %s' % P.app_version(path), foreground=GOOD)
        self.app_detail.config(text=path + ('' if official else
                                            '\nNote: not signed by Native Instruments (signed by: %s).' % who),
                               foreground=GREY if official else NOTE)

    def set_dest(self, path):
        self.dest_path = path
        copies = P.find_copies(path)
        self.dest_status.config(text=path.replace(os.path.expanduser('~'), '~'), foreground='black')
        self.dest_detail.config(text=('Has: %s' % ', '.join(os.path.basename(p) for p, _ in copies)) if copies
                                else ('Empty' if os.path.isdir(path) else 'Will be created'))
        if self.app_path is not None or hasattr(self, 'summary'):
            self.show_summary()

    def bridge_button(self):
        """the bridge button says what it will do: Stop bridge while it runs, Start bridge otherwise"""
        running = B.bridge_running()
        self.stop_button.config(text='Stop bridge' if running else 'Start bridge',
                                command=self.stop_bridge if running else self.start_bridge)

    def start_bridge(self):
        if not self.bridge:
            self.idle()
            return
        stop_mk1d = B.mk1d_running() and messagebox.askyesno(
            'MK1 in use', 'The mk1-controller daemon is using the MK1.\n\nStop it so the bridge can use the MK1?')
        if B.mk1d_running() and not stop_mk1d:
            return

        def run():
            try:
                out = self.bridge.start(stop_mk1d)
                color = GOOD
            except Exception as e:  # noqa: BLE001 -- shown to the user
                out, color = ['Could not start the bridge: %s' % e], BAD
            self.root.after(0, lambda: (self.set_bridge(self.bridge.path), self.note(out),
                                        self.tell(('✓  ' if color == GOOD else '✗  ') + ' '.join(out), color)))
        threading.Thread(target=run, daemon=True).start()

    def set_bridge(self, path):
        self.bridge = B.Bridge(path) if path else None
        if not path:
            self.bridge_status.config(text='✗  Not found', foreground=BAD)
            self.bridge_detail.config(text='')
            return
        self.bridge_status.config(text='✓  Running' if B.bridge_running() else '✓  Ready', foreground=GOOD)
        self.bridge_button()
        bundled = os.path.abspath(path) in (os.path.abspath(B.VENDOR_APP), os.path.abspath(B.VENDOR), os.path.abspath(B.VENDOR_DEV))
        self.bridge_detail.config(text='Included: MK1 Revive by andy83' if bundled else path.split('/Contents/')[0])

    def pick_app(self):
        path = filedialog.askopenfilename(initialdir='/Applications', title='Choose Maschine 3.app')
        if path:
            self.set_app(path.split('.app')[0] + '.app')
            self.idle()

    def pick_dest(self):
        path = filedialog.askdirectory(initialdir=os.path.expanduser('~'), title='Folder for the patched copy')
        if path:
            self.set_dest(path)
            self.idle()

    def pick_bridge(self):
        path = filedialog.askopenfilename(initialdir='/Applications', title='Choose MK1 Revive.app (or mk1-bridge)')
        if path:
            path = path.split('.app')[0] + '.app/Contents/MacOS/mk1-bridge' if '.app' in path else path
            self.set_bridge(path if os.path.isfile(path) else None)
            self.idle()

    def current_copy(self):
        """the patched copy for this controller, if it was made from the Maschine 3 version installed now"""
        for path, model in P.find_copies(self.dest_path):
            if (model == self.model_key() and self.app_path and P.app_version(path) == P.app_version(self.app_path)
                    and os.path.basename(P.executable(path)) == P.COPY_EXE):   # older copies: made again
                return path
        return None

    # --- START, stop, clean --------------------------------------------------------------------------------------
    def start(self):
        if not self.app_path or not self.bridge:
            self.idle()
            return
        stop_mk1d = False
        if B.mk1d_running() and not B.bridge_running():
            if not messagebox.askyesno('MK1 in use', 'The mk1-controller daemon is using the MK1.\n\n'
                                                     'Stop it so Maschine 3 can use the MK1?'):
                return
            stop_mk1d = True
        self.start_button.state(['disabled'])
        app, dest, model = self.app_path, self.dest_path, self.model_key()

        def step(text):
            self.root.after(0, lambda: self.tell(text, GREY))

        def job():
            log = []
            copy = self.current_copy()
            if not copy:
                step('Checking Maschine 3…')
                version, _, plan = P.check(app, model)
                log.append('Maschine %s can be patched: all %d patch points found.' % (version, len(plan)))
                step('Making the patched copy (about a minute; your original stays unchanged)…')
                copy = P.patch(app, dest, model, force=True)
                log.append('Patched copy: %s' % copy)
            step('Starting the MK1 bridge…')
            log += self.bridge.start(stop_mk1d)
            globals()['log'](' / '.join(log))
            step('Opening Maschine 3…')
            subprocess.run(['open', copy])
            log.append('Opened %s' % copy)
            return copy, log

        def run():
            try:
                copy, log = job()
            except Exception as e:  # noqa: BLE001 -- shown to the user
                self.root.after(0, lambda: (self.tell('✗  Could not start: %s\nYour original Maschine 3 was not '
                                                      'changed.' % e, BAD), self.start_button.state(['!disabled'])))
                return
            self.root.after(0, lambda: (self.set_dest(self.dest_path), self.set_bridge(self.bridge.path), self.note(log),
                                        self.tell('✓  Running. Maschine 3 connects to the MK1 after its plugin scan.\n'
                                                  'Quit Maschine 3 when you are done: the bridge stops by itself.',
                                                  GOOD)))
            self.watch(copy)
        threading.Thread(target=run, daemon=True).start()

    def watch(self, copy):
        """waits for the copy to run and quit, then stops the bridge"""
        try:
            log('watch: waiting for %s' % copy)
            for _ in range(90):
                if B.copy_running(copy):
                    break
                time.sleep(1)
            else:
                log('watch: the copy never appeared in the process list')
            log('watch: running = %s' % B.copy_running(copy))
            while B.copy_running(copy):
                time.sleep(1)
            log('watch: Maschine 3 quit; stopping the bridge')
            self.root.after(0, lambda: self.tell('Maschine 3 has quit: stopping the bridge…', GREY))
            out = self.bridge.stop() if self.bridge else []
            log('watch: %s' % out)
        except Exception as e:  # noqa: BLE001 -- never leave START greyed out silently
            log('watch: ERROR %r' % e)
            out = ['Could not stop the bridge: %s' % e]
        self.root.after(0, lambda: (self.set_bridge(self.bridge.path) if self.bridge else None, self.note(out),
                                    self.start_button.state(['!disabled']),
                                    self.tell('Maschine 3 has quit, so the bridge was stopped.\n'
                                              'Press START to play again.', GREY)))

    def stop_bridge(self):
        if not self.bridge:
            return
        self.tell('Stopping the bridge…', GREY)
        self.stop_button.state(['disabled'])

        def run():
            out = self.bridge.stop()
            self.root.after(0, lambda: (self.stop_button.state(['!disabled']), self.set_bridge(self.bridge.path),
                                        self.note(out), self.tell('✓  ' + ' '.join(out), GOOD)))
        threading.Thread(target=run, daemon=True).start()

    def clean(self):
        copies = P.find_copies(self.dest_path)
        if not copies:
            self.tell('Nothing to clean: no RE-ANIMATOR copies in that folder.', GREY)
            return
        names = '\n'.join(os.path.basename(p) for p, _ in copies)
        if not messagebox.askyesno('Clean', 'Remove these RE-ANIMATOR copies?\n\n%s\n\nOnly these copies are removed. '
                                            'Your original Maschine 3 and everything else stay.' % names):
            return
        self.tell('Removing the copy… (your original Maschine 3 stays)', GREY)
        self.start_button.state(['disabled'])
        dest = self.dest_path

        def run():
            try:
                removed, error = P.clean(dest), None
            except Exception as e:  # noqa: BLE001 -- shown to the user
                removed, error = [], e

            def done():
                self.start_button.state(['!disabled'])
                self.set_dest(dest)
                if error:
                    self.tell('✗  Clean failed: %s' % error, BAD)
                    return
                self.note(removed)
                self.tell('✓  Removed %d cop%s. Your original Maschine 3 is unchanged. The next START makes a new one.'
                          % (len(removed), 'y' if len(removed) == 1 else 'ies'), GOOD)
            self.root.after(0, done)
        threading.Thread(target=run, daemon=True).start()

if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()

"""Instrument testbed — play the instrument bank live.

  python testbed/piano_testbed.py

Audio runs on a Rust audio thread (core/io via instrument_core.Live); this
GUI is only a control surface. Input: on-screen keyboard (mouse, with
glissando), computer keys (Z/Q rows, arrows shift octave), a connected MIDI
keyboard, or MIDI file playback (File > Open / built-in demo).
Space = sustain pedal. Esc = all notes off.
"""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "core", "dist"))
import instrument_core  # noqa: E402

LOW, HIGH = 21, 108  # A0..C8
BLACK = {1, 3, 6, 8, 10}
WHITE_W, WHITE_H = 15, 110
BLACK_W, BLACK_H = 9, 68

QUALITY_PRESETS = {
    "Full": dict(),
    "High (48 partials)": dict(max_partials=48),
    "Medium (32 partials)": dict(max_partials=32),
    "Low (24p, 12 symp)": dict(max_partials=24, max_symp_lines=12),
    "Floor (16p, 8s, no noise)": dict(max_partials=16, max_symp_lines=8, noise=False),
}

KEYROWS = {  # computer-keyboard note map, semitone offsets from base octave C
    "z": 0, "s": 1, "x": 2, "d": 3, "c": 4, "v": 5, "g": 6, "b": 7,
    "h": 8, "n": 9, "j": 10, "m": 11, "comma": 12,
    "q": 12, "2": 13, "w": 14, "3": 15, "e": 16, "r": 17, "5": 18,
    "t": 19, "6": 20, "y": 21, "7": 22, "u": 23, "i": 24,
}


def find_instruments():
    out = {}
    inst_dir = os.path.join(ROOT, "instruments")
    for name in sorted(os.listdir(inst_dir)):
        params = os.path.join(inst_dir, name, "params")
        if os.path.isdir(params):
            for f in sorted(os.listdir(params)):
                if f.endswith(".json"):
                    out[f"{name} / {f[:-5]}"] = os.path.join(params, f)
    return out


def demo_events():
    """Built-in demo: (seconds, kind, midi, vel) — a short progression."""
    ev = []
    t = 0.0
    prog = [  # (chord midis, melody midi)
        ([48, 55, 64], 72), ([45, 52, 60], 76), ([50, 57, 65], 74),
        ([43, 55, 62], 79), ([48, 55, 64], 76), ([41, 53, 60], 77),
        ([43, 55, 62], 74), ([48, 52, 60], 72),
    ]
    ev.append((0.0, "pedal", 1, 0))
    for chord, mel in prog:
        ev.append((t, "pedal", 0, 0))
        ev.append((t + 0.02, "pedal", 1, 0))
        for m in chord:
            ev.append((t, "on", m, 62))
            ev.append((t + 1.15, "off", m, 0))
        ev.append((t + 0.05, "on", mel, 88))
        ev.append((t + 0.65, "off", mel, 0))
        ev.append((t + 0.7, "on", mel - 3, 70))
        ev.append((t + 1.1, "off", mel - 3, 0))
        t += 1.2
    ev.append((t + 0.5, "pedal", 0, 0))
    ev.sort(key=lambda e: e[0])
    return ev


def midifile_events(path):
    import mido
    ev, t = [], 0.0
    for msg in mido.MidiFile(path):
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            ev.append((t, "on", msg.note, msg.velocity))
        elif msg.type in ("note_off", "note_on"):
            ev.append((t, "off", msg.note, 0))
        elif msg.type == "control_change" and msg.control == 64:
            ev.append((t, "pedal", 1 if msg.value >= 64 else 0, 0))
    return ev


class Testbed:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Instrument Testbed")
        self.instruments = find_instruments()
        self.live = None
        self.base_octave = 60  # C4 for the Z row
        self.key_items = {}    # midi -> canvas item
        self.down_mouse = None
        self.down_keys = {}    # keysym -> midi
        self.pending_release = {}
        self.playback = None   # (events, index, t0)
        self._build_ui()
        self._start_live(next(iter(self.instruments.values())))
        self._poll_meters()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")

        ttk.Label(top, text="Instrument").grid(row=0, column=0, sticky="w")
        self.inst_var = tk.StringVar(value=next(iter(self.instruments)))
        inst = ttk.Combobox(top, textvariable=self.inst_var, state="readonly",
                            values=list(self.instruments), width=18)
        inst.grid(row=1, column=0, padx=(0, 10))
        inst.bind("<<ComboboxSelected>>",
                  lambda e: self._start_live(self.instruments[self.inst_var.get()]))

        ttk.Label(top, text="Quality").grid(row=0, column=1, sticky="w")
        self.quality_var = tk.StringVar(value="Full")
        qual = ttk.Combobox(top, textvariable=self.quality_var, state="readonly",
                            values=list(QUALITY_PRESETS), width=22)
        qual.grid(row=1, column=1, padx=(0, 10))
        qual.bind("<<ComboboxSelected>>", lambda e: self._apply_quality())

        ttk.Label(top, text="Velocity").grid(row=0, column=2, sticky="w")
        self.vel = tk.IntVar(value=90)
        ttk.Scale(top, from_=1, to=127, variable=self.vel, length=110).grid(
            row=1, column=2, padx=(0, 10))

        ttk.Label(top, text="Volume").grid(row=0, column=3, sticky="w")
        self.vol = tk.DoubleVar(value=0.25)
        ttk.Scale(top, from_=0.02, to=0.8, variable=self.vol, length=110,
                  command=lambda e: self.live and self.live.set_gain(self.vol.get())
                  ).grid(row=1, column=3, padx=(0, 10))

        self.pedal_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Pedal (Space)", variable=self.pedal_var,
                        command=lambda: self._pedal(self.pedal_var.get())
                        ).grid(row=1, column=4, padx=(0, 10))

        ttk.Button(top, text="Panic (Esc)", command=self._panic).grid(row=1, column=5)

        midi = ttk.Frame(self.root, padding=(6, 0, 6, 4))
        midi.pack(fill="x")
        ttk.Label(midi, text="MIDI in:").pack(side="left")
        self.midi_var = tk.StringVar(value="(none)")
        self.midi_box = ttk.Combobox(midi, textvariable=self.midi_var,
                                     state="readonly", width=30, values=["(none)"])
        self.midi_box.pack(side="left", padx=4)
        ttk.Button(midi, text="Rescan", command=self._rescan_midi).pack(side="left")
        ttk.Button(midi, text="Connect", command=self._connect_midi).pack(side="left", padx=4)
        ttk.Separator(midi, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(midi, text="Open MIDI file…", command=self._open_midi_file).pack(side="left")
        ttk.Button(midi, text="Play demo", command=lambda: self._play(demo_events())).pack(
            side="left", padx=4)
        ttk.Button(midi, text="Stop", command=self._stop_playback).pack(side="left")

        self.status = tk.StringVar(value="starting…")
        ttk.Label(self.root, textvariable=self.status, padding=(6, 0)).pack(fill="x")

        n_white = sum(1 for m in range(LOW, HIGH + 1) if m % 12 not in BLACK)
        w = n_white * WHITE_W + 2
        self.canvas = tk.Canvas(self.root, width=w, height=WHITE_H + 2,
                                bg="#222", highlightthickness=0)
        self.canvas.pack(padx=6, pady=(2, 6))
        self._draw_keys()
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)

        self.root.bind("<KeyPress>", self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)

    def _draw_keys(self):
        x = 1
        white_x = {}
        for m in range(LOW, HIGH + 1):
            if m % 12 not in BLACK:
                white_x[m] = x
                self.key_items[m] = self.canvas.create_rectangle(
                    x, 1, x + WHITE_W, WHITE_H, fill="white", outline="#555")
                x += WHITE_W
        for m in range(LOW, HIGH + 1):
            if m % 12 in BLACK:
                # centered on the boundary of the previous white key
                px = white_x[m - 1] + WHITE_W - BLACK_W // 2 - 1
                self.key_items[m] = self.canvas.create_rectangle(
                    px, 1, px + BLACK_W, BLACK_H, fill="#111", outline="#000")

    def _key_at(self, x, y):
        for m in range(LOW, HIGH + 1):  # blacks on top: check them first
            if m % 12 in BLACK:
                x0, y0, x1, y1 = self.canvas.coords(self.key_items[m])
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return m
        for m in range(LOW, HIGH + 1):
            if m % 12 not in BLACK:
                x0, y0, x1, y1 = self.canvas.coords(self.key_items[m])
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return m
        return None

    def _flash(self, midi, down):
        item = self.key_items.get(midi)
        if item:
            black = midi % 12 in BLACK
            fill = ("#7ec8ff" if down else ("#111" if black else "white"))
            self.canvas.itemconfig(item, fill=fill)

    # ------------------------------------------------------------- engine

    def _start_live(self, table_path):
        self._stop_playback()
        if self.live:
            self.live.all_notes_off()
            self.live = None
        try:
            self.live = instrument_core.Live(table_path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Audio", str(e))
            return
        self._apply_quality()
        self.live.set_gain(self.vol.get())
        self.status.set(f"{os.path.basename(table_path)} @ {self.live.sr} Hz "
                        f"on {self.live.device_name}")
        self._rescan_midi()

    def _apply_quality(self):
        if self.live:
            self.live.set_quality(**QUALITY_PRESETS[self.quality_var.get()])

    def _pedal(self, down):
        self.pedal_var.set(down)
        if self.live:
            self.live.set_pedal(down)

    def _panic(self):
        self._stop_playback()
        if self.live:
            self.live.all_notes_off()

    def _note_on(self, midi, vel=None):
        if self.live and LOW <= midi <= HIGH:
            self.live.note_on(midi, vel or self.vel.get())
            self._flash(midi, True)

    def _note_off(self, midi):
        if self.live and LOW <= midi <= HIGH:
            self.live.note_off(midi)
            self._flash(midi, False)

    # -------------------------------------------------------------- mouse

    def _mouse_down(self, e):
        m = self._key_at(e.x, e.y)
        if m is not None:
            self.down_mouse = m
            self._note_on(m)

    def _mouse_drag(self, e):
        m = self._key_at(e.x, e.y)
        if m != self.down_mouse:
            if self.down_mouse is not None:
                self._note_off(self.down_mouse)
            self.down_mouse = m
            if m is not None:
                self._note_on(m)

    def _mouse_up(self, _e):
        if self.down_mouse is not None:
            self._note_off(self.down_mouse)
            self.down_mouse = None

    # ----------------------------------------------- computer keyboard

    def _key_down(self, e):
        ks = e.keysym.lower()
        if ks in self.pending_release:  # auto-repeat: cancel the fake release
            self.root.after_cancel(self.pending_release.pop(ks))
            return
        if ks == "space":
            self._pedal(True)
        elif ks == "escape":
            self._panic()
        elif ks in ("left", "minus"):
            self.base_octave = max(24, self.base_octave - 12)
            self.status.set(f"keyboard base: MIDI {self.base_octave}")
        elif ks in ("right", "equal"):
            self.base_octave = min(96, self.base_octave + 12)
            self.status.set(f"keyboard base: MIDI {self.base_octave}")
        elif ks in KEYROWS and ks not in self.down_keys:
            midi = self.base_octave + KEYROWS[ks]
            self.down_keys[ks] = midi
            self._note_on(midi)

    def _key_up(self, e):
        ks = e.keysym.lower()
        if ks == "space":
            self.pending_release[ks] = self.root.after(
                40, lambda: (self.pending_release.pop(ks, None), self._pedal(False)))
            return
        if ks in self.down_keys:
            def do_release(ks=ks):
                self.pending_release.pop(ks, None)
                midi = self.down_keys.pop(ks, None)
                if midi is not None:
                    self._note_off(midi)
            self.pending_release[ks] = self.root.after(40, do_release)

    # ----------------------------------------------------------- MIDI in

    def _rescan_midi(self):
        ports = instrument_core.Live.midi_ports()
        self.midi_box["values"] = ["(none)"] + ports
        if not ports:
            self.midi_var.set("(none)")

    def _connect_midi(self):
        if not self.live:
            return
        sel = self.midi_var.get()
        ports = list(self.midi_box["values"])[1:]
        if sel in ports:
            try:
                name = self.live.midi_connect(ports.index(sel))
                self.status.set(f"MIDI in: {name}")
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("MIDI", str(e))
        else:
            self.live.midi_disconnect()

    # ------------------------------------------------------- playback

    def _open_midi_file(self):
        path = filedialog.askopenfilename(filetypes=[("MIDI", "*.mid *.midi")])
        if path:
            try:
                self._play(midifile_events(path))
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("MIDI file", str(e))

    def _play(self, events):
        import time
        self._stop_playback()
        self.playback = {"events": events, "i": 0, "t0": time.perf_counter()}
        self._pump_playback()

    def _pump_playback(self):
        import time
        pb = self.playback
        if not pb:
            return
        now = time.perf_counter() - pb["t0"]
        ev = pb["events"]
        while pb["i"] < len(ev) and ev[pb["i"]][0] <= now:
            _, kind, a, b = ev[pb["i"]]
            if kind == "on":
                self._note_on(a, b)
            elif kind == "off":
                self._note_off(a)
            elif kind == "pedal":
                self._pedal(bool(a))
            pb["i"] += 1
        if pb["i"] >= len(ev):
            self.playback = None
            self.status.set("playback finished")
        else:
            self.root.after(10, self._pump_playback)

    def _stop_playback(self):
        if self.playback:
            self.playback = None
            if self.live:
                self.live.all_notes_off()
                self._pedal(False)
            for m in list(self.key_items):
                self._flash(m, False)

    # -------------------------------------------------------------- meters

    def _poll_meters(self):
        if self.live:
            v, load, peak = self.live.meters()
            self.root.title(f"Instrument Testbed — {v} voices · "
                            f"DSP {load:4.0%} · peak {peak:4.2f}")
        self.root.after(150, self._poll_meters)


def main():
    root = tk.Tk()
    root.resizable(False, False)
    Testbed(root)
    root.mainloop()


if __name__ == "__main__":
    main()

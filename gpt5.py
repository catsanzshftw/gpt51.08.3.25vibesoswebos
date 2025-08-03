#!/usr/bin/env python3
# webos_win95_vibes_one_shot.py
# Single-file retro desktop with terminal using Tkinter + Pygame (headless loop)
# No external assets, all vibes in one shot.

import os
import sys
import time
import threading
import queue
import math
import random
from datetime import datetime

# Ensure Pygame runs headless (no window). We only use its clock/timing.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    print("Tkinter is required.")
    sys.exit(1)

try:
    import pygame
    from pygame import time as pyg_time
except Exception:
    print("Pygame is required. Install with: pip install pygame")
    sys.exit(1)


class RetroPalette:
    BG = "#c0c0c0"  # classic gray
    BTN_LIGHT = "#ffffff"
    BTN_DARK = "#808080"
    BTN_SHADOW = "#404040"
    BTN_FACE = "#c0c0c0"
    TEXT = "#000000"
    DESKTOP_GREEN = "#008080"  # teal-ish
    TASKBAR = "#c0c0c0"
    TASKBAR_DARK = "#808080"
    TASKBAR_LIGHT = "#ffffff"
    HILIGHT = "#000080"
    HILIGHT_TEXT = "#ffffff"


def draw_95_button(widget, relief="raised", padx=6, pady=2):
    # Give a Win95-like border feel using ttk styles is tricky; we’ll simulate
    # by wrapping in a Frame with raised edges and a flat button.
    container = tk.Frame(
        widget.master,
        bg=RetroPalette.BTN_FACE,
        highlightthickness=0,
        bd=0,
    )
    border = tk.Frame(container, bg=RetroPalette.BTN_FACE, bd=2, relief="raised")
    widget.master = border  # re-parent visually
    widget.pack(in_=border, padx=padx, pady=pady)
    border.pack(fill="both", expand=True)
    return container


class Win95Window(tk.Frame):
    def __init__(self, master, title="Window", w=420, h=260, x=80, y=80):
        super().__init__(master, bg=RetroPalette.BG, bd=2, relief="ridge")
        self.place(x=x, y=y, width=w, height=h)

        self._drag = {"x": 0, "y": 0, "active": False}
        # Title bar
        self.titlebar = tk.Frame(self, bg=RetroPalette.HILIGHT, height=22)
        self.titlebar.pack(fill="x", side="top")
        self.title_lbl = tk.Label(
            self.titlebar,
            text=title,
            fg=RetroPalette.HILIGHT_TEXT,
            bg=RetroPalette.HILIGHT,
            font=("MS Sans Serif", 9, "bold"),
            anchor="w",
            padx=6,
        )
        self.title_lbl.pack(side="left", fill="x", expand=True)

        self.btn_close = tk.Button(
            self.titlebar,
            text="X",
            relief="raised",
            width=3,
            command=self.destroy_window,
        )
        self.btn_close.pack(side="right", padx=2, pady=2)

        # Content area
        self.content = tk.Frame(self, bg=RetroPalette.BG)
        self.content.pack(fill="both", expand=True)

        # Resize grip
        self.grip = tk.Sizegrip(self)
        self.grip.place(relx=1.0, rely=1.0, anchor="se")

        # Bind move
        for wdg in (self.titlebar, self.title_lbl):
            wdg.bind("<ButtonPress-1>", self.on_drag_start)
            wdg.bind("<B1-Motion>", self.on_drag_move)
            wdg.bind("<ButtonRelease-1>", self.on_drag_end)

        # Raise on click
        self.bind("<Button-1>", lambda e: self.lift())
        self.titlebar.bind("<Button-1>", lambda e: self.lift())
        self.title_lbl.bind("<Button-1>", lambda e: self.lift())

    def destroy_window(self):
        self.place_forget()
        self.destroy()

    def on_drag_start(self, event):
        self._drag["x"] = event.x
        self._drag["y"] = event.y
        self._drag["active"] = True
        self.lift()

    def on_drag_move(self, event):
        if not self._drag["active"]:
            return
        dx = event.x - self._drag["x"]
        dy = event.y - self._drag["y"]
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.place(x=x, y=y)

    def on_drag_end(self, _):
        self._drag["active"] = False


class Win95Taskbar(tk.Frame):
    def __init__(self, master, height=28, start_callback=None):
        super().__init__(master, bg=RetroPalette.TASKBAR, height=height, bd=2, relief="ridge")
        self.pack(side="bottom", fill="x")

        self.start_btn = tk.Button(
            self,
            text="Start",
            relief="raised",
            width=8,
            command=start_callback if start_callback else lambda: None,
        )
        self.start_btn.pack(side="left", padx=6, pady=2)

        self.winlist = tk.Label(
            self, text=" webOS 95 vibes", bg=RetroPalette.TASKBAR, anchor="w"
        )
        self.winlist.pack(side="left", fill="x", expand=True, padx=6)

        self.clock_lbl = tk.Label(self, text="--:--:--", bg=RetroPalette.TASKBAR)
        self.clock_lbl.pack(side="right", padx=8)

        self.fps_lbl = tk.Label(self, text="FPS: ---", bg=RetroPalette.TASKBAR)
        self.fps_lbl.pack(side="right", padx=8)

    def set_clock(self, text):
        self.clock_lbl.config(text=text)

    def set_fps(self, text):
        self.fps_lbl.config(text=text)


class TerminalWindow(Win95Window):
    def __init__(self, master, on_command=None, **kwargs):
        super().__init__(master, title="Terminal", **kwargs)
        self.on_command = on_command

        self.text = tk.Text(
            self.content,
            bg="#000000",
            fg="#00ff00",
            insertbackground="#00ff00",
            font=("Consolas", 10),
            wrap="word",
        )
        self.text.pack(fill="both", expand=True)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<Key>", self._on_key)
        self.prompt = "C:\\webos95> "
        self._append_line("webOS 95 Terminal")
        self._append_line("Type 'help' for commands.")
        self._write_prompt()

        self._lock_input_to_end = True
        self._input_start_idx = self.text.index("end-1c")

    def _append_line(self, s=""):
        self.text.insert("end", s + "\n")
        self.text.see("end")

    def _write_prompt(self):
        self.text.insert("end", self.prompt)
        self._input_start_idx = self.text.index("end-1c")
        self.text.see("end")

    def _on_key(self, event):
        # Prevent editing above prompt
        try:
            insert_idx = self.text.index("insert")
            if self._lock_input_to_end:
                # If cursor is before input start, move it to end
                if self.text.compare(insert_idx, "<", self._input_start_idx):
                    self.text.mark_set("insert", "end-1c")
            # Prevent backspace beyond prompt
            if event.keysym == "BackSpace":
                if self.text.compare(self.text.index("insert"), "<=", self._input_start_idx):
                    return "break"
        except Exception:
            pass
        return None

    def _on_return(self, event):
        # Capture command
        line = self.text.get(self._input_start_idx, "end-1c")
        cmd = line.strip()
        self._append_line("")  # move to new line after input
        self.handle_command(cmd)
        self._write_prompt()
        return "break"

    def handle_command(self, cmd):
        if self.on_command:
            out = self.on_command(cmd)
        else:
            out = self._default_commands(cmd)
        if out:
            for line in out.split("\n"):
                self._append_line(line)

    def _default_commands(self, cmd):
        parts = cmd.split()
        if not parts:
            return ""
        name = parts[0].lower()
        args = parts[1:]

        if name in ("help", "?"):
            return (
                "Commands:\n"
                "  help          Show this help\n"
                "  echo [text]   Echo text\n"
                "  time          Show current time\n"
                "  clear         Clear screen\n"
                "  about         About this OS\n"
                "  vibes         Show vibe status\n"
            )
        if name == "echo":
            return " ".join(args)
        if name == "time":
            return time.strftime("%Y-%m-%d %H:%M:%S")
        if name == "clear":
            self.text.delete("1.0", "end")
            return ""
        if name == "about":
            return (
                "webOS 95 Vibes — single shot, Tkinter + Pygame headless loop.\n"
                "Everything 100% in one file. FPS vibes on."
            )
        if name == "vibes":
            return "Vibes = ON. 600 fps spirit mode."
        return f"Unknown command: {name}"


class RetroDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("webOS 95 Vibes - One Shot")
        self.geometry("1000x640+120+80")
        self.configure(bg=RetroPalette.DESKTOP_GREEN)

        # Fake Win95-esque wallpaper pattern with canvas
        self.canvas = tk.Canvas(self, bg=RetroPalette.DESKTOP_GREEN, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._draw_wallpaper)

        # Taskbar
        self.taskbar = Win95Taskbar(self, start_callback=self._on_start_menu)

        # Start menu popup
        self.start_menu = None

        # Terminal
        self.terminal = None

        # Status
        self.running = True
        self.fps_value = 0.0

        # Inter-thread queue
        self.event_q = queue.Queue()

        # Schedule UI ticks
        self._schedule_clock()
        self._schedule_ui_tick()

        # Launch vibes loop in background
        self._start_headless_pygame_loop()

        # Open Terminal by default
        self.after(300, self.open_terminal)

    def _draw_wallpaper(self, event=None):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        # Draw subtle retro diamonds
        step = 24
        for y in range(0, h + step, step):
            for x in range(0, w + step, step):
                r = 8
                # alternating lighter dots
                if ((x // step) + (y // step)) % 2 == 0:
                    self.canvas.create_oval(
                        x - 2, y - 2, x + 2, y + 2, fill="#70b0b0", width=0
                    )
        # Desktop icons (fake)
        self.canvas.create_rectangle(20, 20, 20 + 36, 20 + 28, fill="#b0d0d0", width=1)
        self.canvas.create_text(38, 58, text="My Web", fill="white")
        self.canvas.create_rectangle(20, 90, 20 + 36, 90 + 28, fill="#c0b0d0", width=1)
        self.canvas.create_text(38, 128, text="Terminal", fill="white")

        # Clickable icon to open terminal
        self.canvas.tag_bind("term_icon", "<Button-1>", lambda e: self.open_terminal())
        # Use a tag by creating a small hidden rect to bind
        r = self.canvas.create_rectangle(20, 90, 56, 118, outline="", fill="", tags=("term_icon",))

    def _on_start_menu(self):
        if self.start_menu and tk.Toplevel.winfo_exists(self.start_menu):
            self.start_menu.destroy()
            self.start_menu = None
            return

        self.start_menu = tk.Toplevel(self)
        self.start_menu.overrideredirect(True)
        self.start_menu.configure(bg=RetroPalette.BG, bd=2, relief="ridge")

        # Position above start button
        bx = self.taskbar.start_btn.winfo_rootx()
        by = self.taskbar.start_btn.winfo_rooty()
        h = self.taskbar.start_btn.winfo_height()
        self.start_menu.geometry(f"200x240+{bx}+{by - 240}")

        # Menu items
        def add_item(text, cmd):
            btn = tk.Button(self.start_menu, text="  " + text, anchor="w", command=lambda: (cmd(), self._close_start()))
            btn.pack(fill="x")

        add_item("Open Terminal", self.open_terminal)
        add_item("About", self._about_dialog)
        add_item("Vibes: ON", lambda: None)
        add_item("Exit", self.quit_app)

        # Close on focus out
        self.start_menu.bind("<FocusOut>", lambda e: self._close_start())
        self.start_menu.focus_force()

    def _close_start(self):
        if self.start_menu and tk.Toplevel.winfo_exists(self.start_menu):
            self.start_menu.destroy()
        self.start_menu = None

    def open_terminal(self):
        if self.terminal and self.terminal.winfo_exists():
            try:
                self.terminal.lift()
                return
            except Exception:
                pass
        self.terminal = TerminalWindow(self, w=560, h=320, x=120, y=120)

    def _about_dialog(self):
        w = Win95Window(self, title="About webOS 95", w=360, h=160, x=180, y=160)
        lbl = tk.Label(
            w.content,
            text=(
                "webOS 95 Vibes\n"
                "Single-shot Python script\n"
                "Tkinter UI + Pygame timing\n"
                "Vibes = ON"
            ),
            bg=RetroPalette.BG,
            justify="center",
        )
        lbl.pack(expand=True)

    def _schedule_clock(self):
        self.taskbar.set_clock(time.strftime("%H:%M:%S"))
        self.after(250, self._schedule_clock)

    def _schedule_ui_tick(self):
        # Process queued events from pygame loop
        try:
            while True:
                evt = self.event_q.get_nowait()
                if evt.get("type") == "fps":
                    self.fps_value = evt.get("value", 0.0)
                elif evt.get("type") == "vibe":
                    pass
        except queue.Empty:
            pass

        # Update FPS label
        self.taskbar.set_fps(f"FPS: {int(round(self.fps_value))}")
        self.after(16, self._schedule_ui_tick)  # ~60Hz UI tick for Tk

    def _start_headless_pygame_loop(self):
        t = threading.Thread(target=self._pygame_loop, daemon=True)
        t.start()

    def _pygame_loop(self):
        pygame.init()
        clock = pyg_time.Clock()

        # 600 FPS target for vibes only
        target_fps = 600
        acc_time = 0.0
        frames = 0
        last_report = time.time()

        # Simple vibe oscillator
        phase = 0.0

        while self.running:
            # Tick
            dt_ms = clock.tick(target_fps)
            dt = dt_ms / 1000.0
            frames += 1
            acc_time += dt
            phase += dt * 2.0 * math.pi  # unused but we could post vibe

            now = time.time()
            if now - last_report >= 0.25:
                fps = frames / (now - last_report)
                frames = 0
                last_report = now
                try:
                    self.event_q.put_nowait({"type": "fps", "value": fps})
                except Exception:
                    pass

        pygame.quit()

    def quit_app(self):
        self.running = False
        self.after(50, self.destroy)


def main():
    app = RetroDesktop()
    app.protocol("WM_DELETE_WINDOW", app.quit_app)
    app.mainloop()


if __name__ == "__main__":
    main()

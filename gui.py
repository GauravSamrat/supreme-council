"""Minimal desktop UI for Supreme Council."""
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

ROOT = Path(__file__).resolve().parent
root = tk.Tk()
root.title("Supreme Council v0.3")
root.geometry("880x680")
root.minsize(660, 480)
style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame", background="#f3f0e9")
style.configure("TLabel", background="#f3f0e9", foreground="#252827")
style.configure("TCheckbutton", background="#f3f0e9")
frame = ttk.Frame(root, padding=20)
frame.pack(fill="both", expand=True)
ttk.Label(frame, text="Supreme Council", font=("Segoe UI", 23)).pack(anchor="w")
ttk.Label(frame, text="Adaptive routing for eligible free models.").pack(anchor="w", pady=(2,12))
prompt = tk.Text(frame, height=10, wrap="word", font=("Segoe UI", 12), undo=True,
                 relief="flat", padx=12, pady=10, bg="#ffffff", fg="#252827")
prompt.pack(fill="both", expand=True)
size = tk.StringVar()
ttk.Label(frame, textvariable=size).pack(anchor="e")
def count(event=None):
    n = len(prompt.get("1.0","end-1c").encode("utf-8"))
    size.set(f"{n:,} / 12,000 bytes" + (" — shorten brief" if n > 12000 else ""))
prompt.bind("<<Modified>>", lambda e: (prompt.edit_modified(False), count()) if prompt.edit_modified() else None)
count()
bar = ttk.Frame(frame)
bar.pack(fill="x", pady=8)
mode = tk.StringVar(value="auto")
private = tk.BooleanVar()
dark = tk.BooleanVar()
words = tk.StringVar(value="250")
synth = tk.BooleanVar(value=True)
for label,var,values in [("Mode",mode,["auto","quick","council","supreme"]),("Words / AI",words,["100","250","500"])]:
    ttk.Label(bar,text=label).pack(side="left",padx=4)
    ttk.Combobox(bar,textvariable=var,values=values,state="readonly",width=10).pack(side="left")
ttk.Checkbutton(bar,text="Synthesis",variable=synth).pack(side="left",padx=10)
ttk.Checkbutton(bar,text="Confidential",variable=private).pack(side="left")
log = tk.Text(frame,height=10,wrap="word",state="disabled",relief="flat",bg="#252827",fg="#e8e3d8",padx=10,pady=10)
log.pack(fill="both",expand=True,pady=(0,10))
buttons = ttk.Frame(frame)
buttons.pack(fill="x")
events = queue.Queue()
proc = None
busy = False
report = None
cancelled = threading.Event()
marker = None
def append(text):
    log.config(state="normal")
    log.insert("end",text)
    log.see("end")
    log.config(state="disabled")
def start(discover=False):
    global busy,report,marker
    if busy: return
    text = prompt.get("1.0","end-1c")
    if not discover:
        if not text.strip() or len(text.encode("utf-8")) > 12000:
            messagebox.showwarning("Brief","Enter a nonempty brief of at most 12,000 UTF-8 bytes.")
            return
        if not private.get() and not messagebox.askokcancel("Cloud consent","Send the brief to eligible free cloud models and allow bounded replacements and optional synthesis? Free-tier services may retain or train on submitted text."):
            return
    busy=True
    report=None
    cancelled.clear()
    runbtn.config(state="disabled")
    discbtn.config(state="disabled")
    append("\nStarting...\n")
    args=[sys.executable,"-u",str(ROOT/"council.py"),"discover" if discover else "run"]
    if not discover:
        args += ["--mode",mode.get(),"--words",words.get(),"--yes"]
        if synth.get(): args.append("--synthesize")
    if private.get(): args.append("--confidential")
    def worker():
        global proc, marker
        try:
            with tempfile.TemporaryDirectory(prefix="supreme-council-") as directory:
                marker = Path(directory)/"cancel"
                args.extend(["--cancel-file", str(marker)])
                if not discover:
                    path = Path(directory)/"brief.txt"
                    path.write_text(text, encoding="utf-8")
                    args.extend(["--file", str(path)])
                if cancelled.is_set():
                    return
                proc = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                with proc.stdout:
                    for line in proc.stdout:
                        events.put(("line", line))
                events.put(("line", f"Exit code: {proc.wait()}\n"))
        except OSError as error:
            events.put(("line", f"Launch error: {type(error).__name__}\n"))
        finally:
            proc = None
            marker = None
            events.put(("done", ""))
    threading.Thread(target=worker,daemon=True).start()
    poll()
def poll():
    global busy,report
    while not events.empty():
        kind,value=events.get_nowait()
        if kind=="done":
            busy=False
            runbtn.config(state="normal")
            discbtn.config(state="normal")
        else:
            append(value)
            if value.startswith("Report: "): report=Path(value[8:].strip())
    if busy:
        root.after(100,poll)
def open_report(copy=False):
    if not report or not report.is_file():
        messagebox.showinfo("Report","No completed report. Partial files may be in runs/.")
        return
    if copy:
        root.clipboard_clear()
        root.clipboard_append(report.read_text(encoding="utf-8"))
    else: os.startfile(str(report))
def cancel():
    cancelled.set()
    if marker:
        try:
            marker.touch()
        except FileNotFoundError:
            pass
def close():
    if busy:
        messagebox.showinfo("Council running","Cancel the run before closing.")
    else: root.destroy()
def load():
    p=filedialog.askopenfilename(filetypes=[("Text","*.txt *.md"),("All files","*.*")])
    if p:
        try:
            text=Path(p).read_text(encoding="utf-8-sig")
            prompt.delete("1.0","end")
            prompt.insert("1.0",text)
            count()
        except (OSError,UnicodeError): messagebox.showerror("Load","Unable to read this file.")
def appearance():
    bg, fg, paper = ("#232724", "#eeeeea", "#303633") if dark.get() else (
        "#f3f0e9", "#252827", "#ffffff")
    for widget in ("TFrame", "TLabel", "TCheckbutton"):
        style.configure(widget, background=bg, foreground=fg)
    prompt.configure(bg=paper, fg=fg, insertbackground=fg)


def view(path):
    if path and path.is_file():
        window = tk.Toplevel(root)
        window.title(path.name)
        contents = tk.Text(window, wrap="word", padx=14, pady=12)
        contents.pack(fill="both", expand=True)
        contents.insert("1.0", path.read_text(encoding="utf-8"))
        contents.configure(state="disabled")


def browse_report():
    chosen = filedialog.askopenfilename(initialdir=ROOT/"runs", filetypes=[("Markdown", "*.md")])
    if chosen:
        view(Path(chosen))


def export():
    if report and report.is_file():
        selected = filedialog.asksaveasfilename(defaultextension=".md", initialfile="master_report.md")
        if selected:
            Path(selected).write_bytes(report.read_bytes())


def config_help():
    path = ROOT/"config.local.json"
    if not path.is_file():
        path.write_text("{}\n", encoding="utf-8")
    messagebox.showinfo("Provider settings", "Keep keys in .env. Configure provider approvals, "
                        "exact models and limits in config.local.json. See README for the format.")
    os.startfile(str(path))


runbtn=ttk.Button(buttons,text="Run Council",command=start)
runbtn.pack(side="left")
discbtn=ttk.Button(buttons,text="Discover",command=lambda:start(True))
discbtn.pack(side="left",padx=3)
for name,fn in [("Cancel",cancel),("View report",lambda:view(report)),("Copy report",lambda:open_report(True)),("Load brief",load)]:
    ttk.Button(buttons,text=name,command=fn).pack(side="left",padx=3)
tools = ttk.Frame(frame)
tools.pack(fill="x", pady=(6,0))
for name, fn in [("History / responses", browse_report), ("Export", export), ("Provider settings", config_help)]:
    ttk.Button(tools, text=name, command=fn).pack(side="left", padx=3)
ttk.Checkbutton(tools, text="Dark appearance", variable=dark, command=appearance).pack(side="right")
root.protocol("WM_DELETE_WINDOW",close)
root.mainloop()

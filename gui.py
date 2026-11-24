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
root.title("Supreme Council v0.2")
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
ttk.Label(frame, text="One brief. Many independent perspectives. Free-tier only.").pack(anchor="w", pady=(2,12))
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
mode = tk.StringVar(value="council")
words = tk.StringVar(value="250")
synth = tk.BooleanVar(value=True)
for label,var,values in [("Mode",mode,["quick","council","supreme"]),("Words / AI",words,["100","250","500"])]:
    ttk.Label(bar,text=label).pack(side="left",padx=4)
    ttk.Combobox(bar,textvariable=var,values=values,state="readonly",width=10).pack(side="left")
ttk.Checkbutton(bar,text="Synthesis",variable=synth).pack(side="left",padx=10)
log = tk.Text(frame,height=10,wrap="word",state="disabled",relief="flat",bg="#252827",fg="#e8e3d8",padx=10,pady=10)
log.pack(fill="both",expand=True,pady=(0,10))
buttons = ttk.Frame(frame)
buttons.pack(fill="x")
events = queue.Queue()
proc = None
busy = False
report = None
cancelled = threading.Event()
def append(text):
    log.config(state="normal")
    log.insert("end",text)
    log.see("end")
    log.config(state="disabled")
def start(discover=False):
    global busy,report
    if busy: return
    text = prompt.get("1.0","end-1c")
    if not discover:
        if not text.strip() or len(text.encode("utf-8")) > 12000:
            messagebox.showwarning("Brief","Enter a nonempty brief of at most 12,000 UTF-8 bytes.")
            return
        if not messagebox.askokcancel("Cloud consent","Send your brief to eligible free cloud models, including up to two replacements and optional synthesis? Do not send confidential data."):
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
    def worker():
        global proc
        path=None
        try:
            if not discover:
                with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",suffix=".txt",delete=False) as f:
                    f.write(text)
                    path=f.name
                args.extend(["--file",path])
            if cancelled.is_set(): return
            proc=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding="utf-8",errors="replace",env={**os.environ,"PYTHONIOENCODING":"utf-8"})
            if cancelled.is_set(): proc.terminate()
            for line in proc.stdout: events.put(("line",line))
            events.put(("line",f"Exit code: {proc.wait()}\n"))
        except Exception as e:
            events.put(("line",f"Launch error: {type(e).__name__}\n"))
        finally:
            proc=None
            if path: Path(path).unlink(missing_ok=True)
            events.put(("done",""))
    threading.Thread(target=worker,daemon=True).start()
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
    if proc and proc.poll() is None: proc.terminate()
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
runbtn=ttk.Button(buttons,text="Run Council",command=start)
runbtn.pack(side="left")
discbtn=ttk.Button(buttons,text="Discover",command=lambda:start(True))
discbtn.pack(side="left",padx=3)
for name,fn in [("Cancel",cancel),("Open report",open_report),("Copy report",lambda:open_report(True)),("Load brief",load)]:
    ttk.Button(buttons,text=name,command=fn).pack(side="left",padx=3)
root.protocol("WM_DELETE_WINDOW",close)
poll()
root.mainloop()

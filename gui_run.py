# gui_run.py
# shorts_new 폴더 안에 놓고 사용하세요.
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import sys
import threading
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable
MAIN_SCRIPT = os.path.join(BASE_DIR, "src", "main.py")

_PROGRESS_RE = re.compile(r'\d+%\|')
_last_was_progress = False


def _is_progress_line(line: str) -> bool:
    return bool(_PROGRESS_RE.search(line)) and ("it/s" in line or "/s]" in line)


def log(msg):
    global _last_was_progress
    is_progress = _is_progress_line(msg)

    if is_progress and _last_was_progress:
        output.delete("end-2l", "end-1l")

    output.insert(tk.END, msg + "\n")
    output.see(tk.END)
    _last_was_progress = is_progress


def run_job():
    global _last_was_progress
    text = input_box.get("1.0", tk.END).strip()
    upload = upload_var.get()

    if not text:
        log("오류: 스크립트 텍스트를 붙여넣어 주세요.")
        return

    tmp_path = os.path.join(BASE_DIR, "_gui_input.txt")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)

    args = [PYTHON_EXE, MAIN_SCRIPT, "--input", tmp_path]
    if not upload:
        args += ["--no-upload"]

    run_button.config(state="disabled")
    _last_was_progress = False
    log("\n" + "=" * 50)
    log(f"실행 시작 (업로드: {'예' if upload else '아니오'})")
    log("=" * 50)

    def worker():
        global _last_was_progress
        try:
            # 자식 프로세스가 Windows 콘솔 기본 인코딩(cp949) 대신
            # 항상 UTF-8로 출력하도록 강제 (한글 깨짐 방지)
            child_env = dict(os.environ)
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"

            proc = subprocess.Popen(
                args, cwd=BASE_DIR, env=child_env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            for line in proc.stdout:
                log(line.rstrip())
            proc.wait()
            _last_was_progress = False
            log(f"\n=== 종료 코드: {proc.returncode} ===")
        except Exception as e:
            log(f"실행 오류: {e}")
        finally:
            run_button.config(state="normal")

    threading.Thread(target=worker, daemon=True).start()


root = tk.Tk()
root.title("오늘의 말씀 - 영상 생성기")
root.geometry("700x600")

top_frame = ttk.Frame(root, padding=12)
top_frame.pack(fill="x")

ttk.Label(top_frame, text="아래에 스크립트 텍스트를 통째로 붙여넣으세요 (여러 날짜/시기 가능)").pack(anchor="w")

input_box = scrolledtext.ScrolledText(root, height=14)
input_box.pack(fill="both", expand=False, padx=12, pady=(0, 8))

options_frame = ttk.Frame(root, padding=(12, 0))
options_frame.pack(fill="x")

upload_var = tk.BooleanVar(value=True)
upload_check = ttk.Checkbutton(options_frame, text="유튜브 업로드까지 진행 (해제하면 로컬 생성만)", variable=upload_var)
upload_check.pack(anchor="w")

run_button = ttk.Button(options_frame, text="실행", command=run_job)
run_button.pack(anchor="w", pady=8)

output = scrolledtext.ScrolledText(root, height=14)
output.pack(fill="both", expand=True, padx=12, pady=(0, 12))

root.mainloop()

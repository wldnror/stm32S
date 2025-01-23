#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil
import stat
import time
import threading
import random

os.environ['DISPLAY'] = ':0'

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) GDSClientLinux의 절대 경로 설정 (실제 환경에 맞게 수정)
GDSCLIENT_PATH = "/home/gdseng/GDS_Release_20250110/GDSClientLinux"

# 2) TFTP 서버 루트 디렉토리 (실제 환경에 맞게 수정)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

# 전역 스레드/이벤트 객체
auto_thread = None                 # 자동 업그레이드 반복 스레드
stop_event = threading.Event()     # 중지 신호 전달용 이벤트

# ----- (A) 로그를 안전하게 UI에 표시하는 함수 ----- #
def async_log_print(msg: str):
    def insert_log():
        log_text.insert(tk.END, msg.rstrip() + "\n")
        log_text.see(tk.END)  # 자동 스크롤
    root.after(0, insert_log)

# ----- (B) 실시간 로그를 읽는 subprocess 실행 함수 ----- #
def run_command_realtime(args):
    """
    subprocess.Popen으로 args를 실행하고,
    stdout을 한 줄씩 읽어 async_log_print로 실시간 표시한다.
    결과 코드(0=성공, 그 외=에러)를 리턴.
    """
    try:
        p = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
    except FileNotFoundError:
        async_log_print(f"[오류] 실행 파일을 찾을 수 없습니다: {args[0]}")
        return -1

    while True:
        line = p.stdout.readline()
        if not line:
            break
        async_log_print(line)

    p.wait()
    return p.returncode

# ----- (C) GDSClient 실행 권한 부여 체크 & tftpd-hpa 설치 체크 ----- #
def ensure_gdsclientlinux_executable():
    if not os.path.isfile(GDSCLIENT_PATH):
        async_log_print(f"[오류] GDSClientLinux 파일을 찾을 수 없습니다: {GDSCLIENT_PATH}")
        return False

    file_stat = os.stat(GDSCLIENT_PATH)
    if not (file_stat.st_mode & stat.S_IXUSR):
        async_log_print("[정보] GDSClientLinux에 실행 권한이 없어 설정합니다...")
        ret = run_command_realtime(["sudo", "chmod", "+x", GDSCLIENT_PATH])
        if ret != 0:
            async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패")
            return False

    return True

def check_and_install_tftpd():
    async_log_print("[정보] tftpd-hpa 설치 여부 확인 중...")
    try:
        check_install = subprocess.check_output(
            ["dpkg", "-l", "tftpd-hpa"],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        if "tftpd-hpa" in check_install:
            async_log_print("[정보] tftpd-hpa가 이미 설치되어 있습니다.")
            return True
    except subprocess.CalledProcessError:
        pass

    async_log_print("[정보] tftpd-hpa가 설치되어 있지 않아 설치를 진행합니다...")
    ret = run_command_realtime(["sudo", "apt-get", "update"])
    if ret != 0:
        async_log_print("[오류] apt-get update 실패")
        return False

    ret = run_command_realtime(["sudo", "apt-get", "-y", "install", "tftpd-hpa"])
    if ret == 0:
        return True
    else:
        async_log_print("[오류] tftpd-hpa 설치 실패")
        return False

def start_tftp_server():
    async_log_print("[정보] TFTP 서버를 시작합니다...")
    run_command_realtime(["sudo", "systemctl", "enable", "tftpd-hpa"])
    run_command_realtime(["sudo", "systemctl", "start", "tftpd-hpa"])

# ----- (D) 업그레이드 절차에 필요한 파일 복사 함수 ----- #
def copy_to_tftp(file_path):
    if not os.path.isfile(file_path):
        async_log_print(f"[오류] 파일이 존재하지 않습니다: {file_path}")
        return False

    if not os.path.exists(TFTP_ROOT_DIR):
        async_log_print(f"[오류] TFTP 루트 디렉토리가 없습니다: {TFTP_ROOT_DIR}")
        return False

    file_name = os.path.basename(file_path)
    dest_path = os.path.join(TFTP_ROOT_DIR, file_name)

    try:
        shutil.copy(file_path, dest_path)
        async_log_print(f"[파일 복사] {file_path} -> {dest_path}")
        run_command_realtime(["sudo", "chmod", "644", dest_path])
        return True
    except Exception as e:
        async_log_print(f"[오류] 파일 복사 중 문제 발생: {e}")
        return False

# ----- (E) 업그레이드 단일 실행 프로세스 (모드 전환 후 업그레이드) ----- #
def upgrade_task(detector_ip, tftp_ip, upgrade_file_paths):
    """
    업그레이드 절차:
    1) 파일 리스트 중 무작위 선택
    2) 선택된 파일을 TFTP 루트 디렉토리에 복사
    3) TFTP 서버 실행
    4) 디텍터를 업그레이드 모드로 변경 (cmd:4 1)
    5) 잠시 대기 (2초)
    6) 업그레이드 명령 (cmd:5, tftp_ip, file_name)
    """
    # 파일 리스트 파싱
    files = [f.strip() for f in upgrade_file_paths.split(",") if f.strip()]
    if not files:
        async_log_print("[오류] 업그레이드할 파일이 선택되지 않았습니다.")
        return
    
    # 무작위 파일 선택
    selected_file = random.choice(files)
    
    # 1. 파일 복사
    if not copy_to_tftp(selected_file):
        return
    
    # 2. TFTP 서버 기동
    start_tftp_server()
    
    # 3. 모드 변경
    ret1 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "4", "1"])
    time.sleep(2)  # 디텍터가 모드 전환될 시간
    
    # 4. 업그레이드
    file_name = os.path.basename(selected_file)
    ret2 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "5", tftp_ip, file_name])
    
    if ret2 == 0:
        async_log_print(f"[알림] 업그레이드 명령을 성공적으로 마쳤습니다. 사용된 파일: {file_name}")
    else:
        async_log_print("[알림] 업그레이드 명령 중 오류가 발생했습니다.")

# ----- (F) 업그레이드(단발) 호출 함수 ----- #
def upgrade_once():
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file_paths:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    threading.Thread(
        target=upgrade_task,
        args=(detector_ip, tftp_ip, upgrade_file_paths),
        daemon=True
    ).start()

# ============================================================
# =============== 랜덤 반복 업그레이드 관련 로직 ===============
# ============================================================
def auto_upgrade_loop():
    """
    stop_event가 꺼질 때까지
    무작위 간격(42초 ~ 300초)으로 업그레이드를 반복 수행
    """
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()

    while not stop_event.is_set():
        # 업그레이드 실행
        upgrade_task(detector_ip, tftp_ip, upgrade_file_paths)

        if stop_event.is_set():
            break

        # 42초 ~ 300초 사이 랜덤 대기
        wait_sec = random.randint(10, 300)
        async_log_print(f"[자동모드] 다음 업그레이드까지 대기: {wait_sec}초")
        for _ in range(wait_sec):
            if stop_event.is_set():
                break
            time.sleep(1)

def start_auto_upgrade():
    # 전역변수를 함수 내부에서 수정/참조하려면 첫 줄에 선언
    global auto_thread

    # GDSClientLinux 파일 체크
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 또는 파일이 없습니다.")
        return

    # tftpd-hpa 설치 체크
    if not check_and_install_tftpd():
        async_log_print("[오류] tftpd-hpa 설치가 안 되어 업그레이드를 진행할 수 없습니다.")
        return

    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()
    if not detector_ip or not tftp_ip or not upgrade_file_paths:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    # 이미 동작 중인지 확인
    if not auto_thread or not auto_thread.is_alive():
        # 이벤트 초기화 후 스레드 시작
        stop_event.clear()
        async_log_print("[자동모드] 무작위 업그레이드 시작")
        auto_thread = threading.Thread(target=auto_upgrade_loop, daemon=True)
        auto_thread.start()
    else:
        async_log_print("[자동모드] 이미 동작 중입니다.")

def stop_auto_upgrade():
    global auto_thread

    if auto_thread and auto_thread.is_alive():
        async_log_print("[자동모드] 중지 명령 전송")
        stop_event.set()
    else:
        async_log_print("[자동모드] 현재 동작 중이 아닙니다.")

# ----- (G) 파일 선택 ----- #
def select_files():
    filepaths = filedialog.askopenfilenames(title="업그레이드 파일 선택")
    if filepaths:
        file_entry.delete(0, tk.END)
        # 파일 경로를 콤마로 구분하여 저장
        file_entry.insert(0, ",".join(filepaths))

# ============================================================== #
# ======================= Tkinter UI 구성 ======================= #
# ============================================================== #
root = tk.Tk()
root.title("자동 업그레이드 테스트 UI")

info_label = tk.Label(
    root,
    text=(
        "GDSClientLinux를 이용하여 랜덤 간격(42~300초)으로\n"
        "자동 업그레이드를 반복 실행하는 테스트 툴입니다.\n"
        "CPU Bug Test 등을 위해 무한 반복됩니다.\n"
        "업그레이드 파일을 여러 개 선택하면 업그레이드 시 무작위로 선택됩니다."
    ),
    fg="blue"
)
info_label.pack(padx=10, pady=5)

# IP 입력 프레임
frame_ip = tk.Frame(root)
frame_ip.pack(padx=10, pady=5, fill="x")

tk.Label(frame_ip, text="Detector IP:").grid(row=0, column=0, sticky="e")
detector_ip_entry = tk.Entry(frame_ip, width=15)
detector_ip_entry.grid(row=0, column=1, padx=5)

tk.Label(frame_ip, text="TFTP IP:").grid(row=0, column=2, sticky="e")
tftp_ip_entry = tk.Entry(frame_ip, width=15)
tftp_ip_entry.grid(row=0, column=3, padx=5)

# 파일 선택 프레임
frame_file = tk.Frame(root)
frame_file.pack(padx=10, pady=5, fill="x")

tk.Label(frame_file, text="업그레이드 파일:").grid(row=0, column=0, sticky="e")
file_entry = tk.Entry(frame_file, width=60)
file_entry.grid(row=0, column=1, padx=5)
file_btn = tk.Button(frame_file, text="파일 선택", command=select_files)
file_btn.grid(row=0, column=2, padx=5)

# 명령 버튼들 (자동 시작/중지, 단발 업그레이드)
frame_buttons = tk.Frame(root)
frame_buttons.pack(padx=10, pady=5)

btn_start_auto = tk.Button(frame_buttons, text="자동 업그레이드 시작", width=20, command=start_auto_upgrade)
btn_start_auto.grid(row=0, column=0, padx=5, pady=5)

btn_stop_auto = tk.Button(frame_buttons, text="자동 업그레이드 중지", width=20, command=stop_auto_upgrade)
btn_stop_auto.grid(row=0, column=1, padx=5, pady=5)

btn_upgrade_once = tk.Button(frame_buttons, text="단발 업그레이드 실행", width=20, command=upgrade_once)
btn_upgrade_once.grid(row=0, column=2, padx=5, pady=5)

# 로그 창
log_text = scrolledtext.ScrolledText(root, width=80, height=15)
log_text.pack(padx=10, pady=10)

# 마우스 우클릭 > 복사
def copy_selection():
    log_text.event_generate("<<Copy>>")

context_menu = tk.Menu(log_text, tearoff=0)
context_menu.add_command(label="복사", command=copy_selection)

def show_context_menu(event):
    context_menu.tk_popup(event.x_root, event.y_root)

log_text.bind("<Button-3>", show_context_menu)

# 처음 실행 시 GDSClient 권한 및 tftpd 상태 체크, IP 기본값 설정
def on_start():
    if ensure_gdsclientlinux_executable():
        check_and_install_tftpd()

    # 예시 기본값
    tftp_ip_entry.delete(0, tk.END)
    tftp_ip_entry.insert(0, "192.168.0.4")

    detector_ip_entry.delete(0, tk.END)
    detector_ip_entry.insert(0, "192.168.0.")  # 끝자리만 변경하도록 유도

root.after(100, on_start)

root.mainloop()

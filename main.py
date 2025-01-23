#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil
import stat
import time
import threading
import socket
import json

os.environ['DISPLAY'] = ':0'

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) GDSClientLinux의 절대 경로 설정을 제거 (동적으로 설정)
# 2) 설정 파일 경로 설정
CONFIG_FILE = os.path.expanduser("~/.gds_client_config.json")

# 3) TFTP 서버 루트 디렉토리(예: /srv/tftp)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

# --------------------- (A) 로그 업데이트를 안전하게 수행하는 함수 --------------------- #
def async_log_print(msg: str):
    """
    다른 스레드에서 호출하면,
    메인 스레드가 log_text에 안전하게 append하도록 해준다.
    """
    def insert_log():
        log_text.insert(tk.END, msg.rstrip() + "\n")
        log_text.see(tk.END)  # 자동 스크롤
    root.after(0, insert_log)

# --------------------- (B) 실시간 출력 받는 subprocess 실행 함수 --------------------- #
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

    # 한 줄씩 읽어 UI에 표시
    while True:
        line = p.stdout.readline()
        if not line:
            break
        async_log_print(line)

    p.wait()  # 프로세스 종료 대기
    return p.returncode

# --------------------- (C) 설정 파일 관리 함수 --------------------- #
def load_config():
    """
    설정 파일을 로드하여 딕셔너리로 반환합니다.
    설정 파일이 없거나 읽을 수 없는 경우 빈 딕셔너리를 반환합니다.
    """
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        async_log_print(f"[오류] 설정 파일을 로드할 수 없습니다: {e}")
        return {}

def save_config(config):
    """
    딕셔너리를 설정 파일로 저장합니다.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        async_log_print(f"[오류] 설정 파일을 저장할 수 없습니다: {e}")

def select_gdsclientlinux():
    """
    사용자에게 GDSClientLinux 실행 파일을 선택하도록 요청하고, 설정 파일에 저장합니다.
    """
    filepath = filedialog.askopenfilename(
        title="GDSClientLinux 실행 파일 선택",
        filetypes=[("Executable Files", "GDSClientLinux*"), ("All Files", "*.*")]
    )
    if filepath:
        config = load_config()
        config['GDSCLIENT_PATH'] = filepath
        save_config(config)
        async_log_print(f"[설정] GDSClientLinux 경로가 설정되었습니다: {filepath}")
        return filepath
    else:
        async_log_print("[경고] GDSClientLinux 실행 파일을 선택하지 않았습니다.")
        return None

def get_gdsclient_path():
    """
    설정 파일에서 GDSClientLinux 경로를 불러오거나, 경로가 유효하지 않으면 사용자에게 선택을 요청합니다.
    """
    config = load_config()
    gds_path = config.get('GDSCLIENT_PATH', None)
    if gds_path and os.path.isfile(gds_path):
        return gds_path
    else:
        async_log_print("[정보] GDSClientLinux 경로가 설정되지 않았거나 유효하지 않습니다.")
        gds_path = select_gdsclientlinux()
        if gds_path:
            return gds_path
        else:
            messagebox.showerror("오류", "GDSClientLinux 실행 파일 경로가 설정되지 않았습니다.")
            root.quit()
            return None

# --------------------- (D) 단일 명령(조회, 재부팅, 모드변경 등)을 실행하는 함수들 --------------------- #
def get_chip_size():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        run_command_realtime([GDSCLIENT_PATH, ip, "0"])
    threading.Thread(target=task, daemon=True).start()

def get_mode():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        run_command_realtime([GDSCLIENT_PATH, ip, "1"])
    threading.Thread(target=task, daemon=True).start()

def get_version():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        run_command_realtime([GDSCLIENT_PATH, ip, "2"])
    threading.Thread(target=task, daemon=True).start()

def reboot():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        run_command_realtime([GDSCLIENT_PATH, ip, "3"])
    threading.Thread(target=task, daemon=True).start()

def change_mode():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        run_command_realtime([GDSCLIENT_PATH, ip, "4", "1"])
    threading.Thread(target=task, daemon=True).start()

def select_file():
    filepath = filedialog.askopenfilename(title="업그레이드 파일 선택")
    if filepath:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, filepath)

# --------------------- (E) 업그레이드 전체 프로세스 (백그라운드 스레드) ---------------------- #
def upgrade_task(detector_ip, tftp_ip, upgrade_file_path):
    """
    업그레이드 절차:
    1) 파일을 TFTP 루트 디렉토리에 복사
    2) TFTP 서버 실행
    3) 모드 변경 (cmd:4)
    4) 대기 2초
    5) 업그레이드 (cmd:5)
    """
    # 1. 파일 복사
    if not copy_to_tftp(upgrade_file_path):
        return

    # 2. TFTP 서버 기동
    start_tftp_server()

    # 3. 모드 변경
    ret1 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "4", "1"])

    # 4. 약간 대기 (디텍터가 업그레이드 모드로 전환될 시간)
    time.sleep(2)

    # 5. 업그레이드
    file_name = os.path.basename(upgrade_file_path)
    ret2 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "5", tftp_ip, file_name])

    if ret2 == 0:
        async_log_print("[알림] 업그레이드 명령을 성공적으로 마쳤습니다.")
    else:
        async_log_print("[알림] 업그레이드 명령 중 오류가 발생했습니다.")

def upgrade():
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_path = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file_path:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    # 백그라운드 스레드로 실행
    t = threading.Thread(
        target=upgrade_task,
        args=(detector_ip, tftp_ip, upgrade_file_path),
        daemon=True
    )
    t.start()

# --------------------- (F) Tkinter UI ---------------------- #
root = tk.Tk()
root.title("GDS 클라이언트 UI (실시간 로그 & IP 자동 설정)")

info_label = tk.Label(
    root,
    text=(
        "라즈베리파이/Ubuntu에서 TFTP 서버를 자동 구동하고,\n"
        "GDSClientLinux 명령을 실시간 로그로 표시합니다.\n"
        "sudo 권한으로 실행해야 정상 동작합니다."
    ),
    fg="blue"
)
info_label.pack(padx=10, pady=5)

# IP 입력 프레임
frame_ip = tk.Frame(root)
frame_ip.pack(padx=10, pady=5, fill="x")

tk.Label(frame_ip, text="Detector IP:").grid(row=0, column=0, sticky="e")
detector_ip_entry = tk.Entry(frame_ip, width=20)
detector_ip_entry.grid(row=0, column=1, padx=5)

tk.Label(frame_ip, text="TFTP IP:").grid(row=0, column=2, sticky="e")
tftp_ip_entry = tk.Entry(frame_ip, width=20)
tftp_ip_entry.grid(row=0, column=3, padx=5)

# 파일 선택 프레임
frame_file = tk.Frame(root)
frame_file.pack(padx=10, pady=5, fill="x")

tk.Label(frame_file, text="업그레이드 파일:").grid(row=0, column=0, sticky="e")
file_entry = tk.Entry(frame_file, width=40)
file_entry.grid(row=0, column=1, padx=5)
file_btn = tk.Button(frame_file, text="파일 선택", command=select_file)
file_btn.grid(row=0, column=2, padx=5)

# 명령 버튼들
frame_buttons = tk.Frame(root)
frame_buttons.pack(padx=10, pady=5)

btn_chip_size = tk.Button(frame_buttons, text="칩 크기 조회", width=15, command=get_chip_size)
btn_chip_size.grid(row=0, column=0, padx=5, pady=5)

btn_mode = tk.Button(frame_buttons, text="모드 조회 (뱅크)", width=15, command=get_mode)
btn_mode.grid(row=0, column=1, padx=5, pady=5)

btn_version = tk.Button(frame_buttons, text="버전 조회", width=15, command=get_version)
btn_version.grid(row=0, column=2, padx=5, pady=5)

btn_reboot = tk.Button(frame_buttons, text="재부팅", width=15, command=reboot)
btn_reboot.grid(row=1, column=0, padx=5, pady=5)

btn_change_mode = tk.Button(frame_buttons, text="모드 변경 (4 1)", width=15, command=change_mode)
btn_change_mode.grid(row=1, column=1, padx=5, pady=5)

btn_upgrade = tk.Button(frame_buttons, text="업그레이드", width=15, command=upgrade)
btn_upgrade.grid(row=1, column=2, padx=5, pady=5)

# 로그 창
log_text = scrolledtext.ScrolledText(root, width=80, height=15)
log_text.pack(padx=10, pady=10)

# Ctrl + C, V, X 바인딩
log_text.bind("<Control-c>", lambda event: log_text.event_generate("<<Copy>>"))
log_text.bind("<Control-v>", lambda event: log_text.event_generate("<<Paste>>"))
log_text.bind("<Control-x>", lambda event: log_text.event_generate("<<Cut>>"))

# 마우스 우클릭 메뉴 (복사)
def copy_selection():
    log_text.event_generate("<<Copy>>")

context_menu = tk.Menu(log_text, tearoff=0)
context_menu.add_command(label="복사", command=copy_selection)

def show_context_menu(event):
    context_menu.tk_popup(event.x_root, event.y_root)

log_text.bind("<Button-3>", show_context_menu)

# --------------------- (G) 시작 시 자동 설정 ---------------------- #
def get_local_ip():
    """
    로컬 IP 주소를 반환합니다.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 외부에 연결하지 않고도 로컬 IP를 얻을 수 있습니다.
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'  # 실패 시 루프백 주소 반환
    finally:
        s.close()
    return IP

def on_start():
    global GDSCLIENT_PATH

    # 1. GDSClientLinux 실행 경로 가져오기
    GDSCLIENT_PATH = get_gdsclient_path()
    if not GDSCLIENT_PATH:
        return  # 경로 설정 실패 시 종료

    # 2. GDSClientLinux 실행 권한 확인
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 혹은 파일이 없습니다.")

    # 3. tftpd-hpa 설치 확인 & 자동 설치
    if check_and_install_tftpd():
        start_tftp_server()

    # 4. TFTP IP & Detector IP 자동 설정
    local_ip = get_local_ip()
    async_log_print(f"[정보] 로컬 IP 주소 감지: {local_ip}")

    # TFTP IP 설정
    tftp_ip_entry.delete(0, tk.END)
    tftp_ip_entry.insert(0, local_ip)

    # Detector IP의 서브넷 설정 (예: "192.168.0.")
    try:
        base_ip = '.'.join(local_ip.split('.')[:3]) + '.'
    except Exception:
        base_ip = "192.168.0."  # 실패 시 기본값 사용
        async_log_print("[경고] 로컬 IP 분석 실패, 기본값 '192.168.0.' 사용")

    detector_ip_entry.delete(0, tk.END)
    detector_ip_entry.insert(0, base_ip)

# --------------------- (C) 기존에 사용하던 함수들 (권한 체크, TFTP 설치 등) --------------------- #
def ensure_gdsclientlinux_executable():
    if not os.path.isfile(GDSCLIENT_PATH):
        async_log_print(f"[오류] GDSClientLinux 파일을 찾을 수 없습니다: {GDSCLIENT_PATH}")
        return False

    # 실행 권한 확인
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

    # 미설치 시 자동 설치
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

# --------------------- (G) 시작 시 자동 설정 ---------------------- #

# 메인 윈도우 표시 후 on_start 실행 (100ms 후)
root.after(100, on_start)
root.mainloop()

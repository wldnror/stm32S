#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil
import stat  # 실행 권한 체크를 위해 필요
import time
import threading

os.environ['DISPLAY'] = ':0'

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) GDSClientLinux의 절대 경로 설정 (예시: Ubuntu x86_64 환경)
#    실제 설치된 경로에 맞추어 수정하세요.
GDSCLIENT_PATH = "/home/gdseng/GDS_Release_20250110/GDSClientLinux"

# 2) TFTP 서버 루트 디렉토리(예: /srv/tftp)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


# --------------------- (1) 로그 업데이트를 안전하게 수행하는 도우미 함수 --------------------- #
def async_log_print(msg: str):
    """
    다른 스레드(백그라운드)에서 이 함수를 호출하면,
    Tkinter 메인 스레드가 log_text에 안전하게 append하도록 해줌.
    """
    # strip()을 한 뒤, 맨 뒤에 개행(\n)을 붙여서 줄 단위로 출력
    def insert_log():
        log_text.insert(tk.END, msg.rstrip() + "\n")
        log_text.see(tk.END)  # 자동 스크롤
    root.after(0, insert_log)


def run_command(args):
    """
    (기존) subprocess.check_output로 명령을 실행하고 결과를 리턴.
    예전에는 여기서 바로 log_text.insert 했지만,
    스레드 사용 시에는 직접 insert 하지 않고, 결과만 return 시키거나
    필요하면 async_log_print를 이용해 메인 스레드에 로그 기록 요청을 보냄.
    """
    try:
        output = subprocess.check_output(
            args, stderr=subprocess.STDOUT, universal_newlines=True
        )
        return output
    except subprocess.CalledProcessError as e:
        return f"[오류]\n{e.output}\n"


def ensure_gdsclientlinux_executable():
    """
    GDSClientLinux 절대 경로가 존재하는지, 실행 권한이 있는지 확인.
    없다면 오류 메시지를 표시하거나 자동으로 chmod +x를 수행한다.
    """
    if not os.path.isfile(GDSCLIENT_PATH):
        async_log_print(f"[오류] GDSClientLinux 파일을 찾을 수 없습니다: {GDSCLIENT_PATH}")
        return False

    # 실행 권한 확인
    file_stat = os.stat(GDSCLIENT_PATH)
    if not (file_stat.st_mode & stat.S_IXUSR):
        async_log_print("[정보] GDSClientLinux에 실행 권한이 없어 설정합니다...")
        try:
            out = run_command(["sudo", "chmod", "+x", GDSCLIENT_PATH])
            if out:
                async_log_print(out)
        except Exception as e:
            async_log_print(f"[오류] GDSClientLinux 실행 권한 설정 실패: {e}")
            return False

    return True


def check_and_install_tftpd():
    """
    tftpd-hpa 패키지가 설치되어 있는지 확인하고,
    없다면 자동으로 설치 (sudo 권한 필요).
    """
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
    try:
        out = run_command(["sudo", "apt-get", "update"])
        if out:
            async_log_print(out)
        out = run_command(["sudo", "apt-get", "-y", "install", "tftpd-hpa"])
        if out:
            async_log_print(out)
        return True
    except Exception as e:
        async_log_print(f"[오류] tftpd-hpa 설치 실패: {e}")
        return False


def start_tftp_server():
    """
    tftpd-hpa 서비스를 enable하고 start한다 (이미 실행 중이면 그대로 유지).
    """
    async_log_print("[정보] TFTP 서버를 시작합니다...")
    out = run_command(["sudo", "systemctl", "enable", "tftpd-hpa"])
    if out:
        async_log_print(out)

    out = run_command(["sudo", "systemctl", "start", "tftpd-hpa"])
    if out:
        async_log_print(out)


def copy_to_tftp(file_path):
    """
    업그레이드 파일을 TFTP 루트 디렉토리에 복사 후 권한 설정.
    """
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
        out = run_command(["sudo", "chmod", "644", dest_path])
        if out:
            async_log_print(out)
        return True
    except Exception as e:
        async_log_print(f"[오류] 파일 복사 중 문제 발생: {e}")
        return False


# --------------------- GDSClientLinux 관련 명령 함수들 (단일 명령) ---------------------- #
def get_chip_size():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        out = run_command([GDSCLIENT_PATH, ip, "0"])
        if out:
            async_log_print(out)
    threading.Thread(target=task, daemon=True).start()


def get_mode():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        out = run_command([GDSCLIENT_PATH, ip, "1"])
        if out:
            async_log_print(out)
    threading.Thread(target=task, daemon=True).start()


def get_version():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        out = run_command([GDSCLIENT_PATH, ip, "2"])
        if out:
            async_log_print(out)
    threading.Thread(target=task, daemon=True).start()


def reboot():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        out = run_command([GDSCLIENT_PATH, ip, "3"])
        if out:
            async_log_print(out)
    threading.Thread(target=task, daemon=True).start()


def change_mode():
    ip = detector_ip_entry.get().strip()
    if not ip:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")
        return

    def task():
        out = run_command([GDSCLIENT_PATH, ip, "4", "1"])
        if out:
            async_log_print(out)
    threading.Thread(target=task, daemon=True).start()


def select_file():
    filepath = filedialog.askopenfilename(title="업그레이드 파일 선택")
    if filepath:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, filepath)


# --------------------- (2) 업그레이드 전체 프로세스 (백그라운드 스레드) ---------------------- #
def upgrade_task(detector_ip, tftp_ip, upgrade_file_path):
    """
    백그라운드에서 실행할 실제 업그레이드 로직
    """
    # 1. 파일 복사
    if not copy_to_tftp(upgrade_file_path):
        return

    # 2. TFTP 서버 기동
    start_tftp_server()

    # 3. 모드 변경 (4,1)
    out = run_command([GDSCLIENT_PATH, detector_ip, "4", "1"])
    if out:
        async_log_print(out)

    # 3.5. 약간 대기 (디텍터가 업그레이드 모드로 전환되는 시간)
    time.sleep(2)

    # 4. 업그레이드 (5, tftpIp, fileName)
    file_name = os.path.basename(upgrade_file_path)
    out = run_command([GDSCLIENT_PATH, detector_ip, "5", tftp_ip, file_name])
    if out:
        async_log_print(out)


def upgrade():
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_path = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file_path:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    # 백그라운드 스레드로 작업 수행
    t = threading.Thread(
        target=upgrade_task,
        args=(detector_ip, tftp_ip, upgrade_file_path),
        daemon=True
    )
    t.start()


# --------------------- (3) UI 초기화 및 이벤트 설정 ---------------------- #
root = tk.Tk()
root.title("GDS 클라이언트 UI (TFTP 서버 자동화 + 절대경로 사용, 스레딩 적용)")

info_label = tk.Label(
    root,
    text=(
        "라즈베리파이/Ubuntu에서 TFTP 서버를 자동 구동하고,\n"
        "GDSClientLinux 명령을 절대 경로로 실행합니다.\n"
        "sudo 권한으로 실행해야 정상 동작합니다.\n"
        "업그레이드 시에도 UI가 멈추지 않도록 스레드를 사용합니다."
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


# [추가] Detector IP에서 포커스가 빠져나갈 때(또는 엔터) 같은 대역으로 TFTP IP 설정 (예: x.x.x.4)
def auto_set_tftp_ip(event):
    """
    Detector IP를 예: 192.168.0.5 라 입력하고 포커스가 빠지면,
    TFTP IP를 같은 앞 3옥텟 + '.4' 로 자동 설정하는 예시
    """
    detector_ip = detector_ip_entry.get().strip()
    if not detector_ip:
        return

    parts = detector_ip.split(".")
    if len(parts) == 4:
        # 앞 3옥텟 + .4 로 구성
        prefix = ".".join(parts[:3])
        # 지금 TFTP IP가 비어있거나, 혹은 다른 망이면 덮어쓰기
        # (원하는 정책에 따라 조건을 수정 가능)
        current_tftp = tftp_ip_entry.get().strip()
        if not current_tftp or current_tftp.startswith(prefix + ".") is False:
            tftp_ip_entry.delete(0, tk.END)
            tftp_ip_entry.insert(0, prefix + ".4")


detector_ip_entry.bind("<FocusOut>", auto_set_tftp_ip)
detector_ip_entry.bind("<Return>", auto_set_tftp_ip)  # 엔터 입력 시에도 반응


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

### [추가됨] Ctrl + C, Ctrl + V, Ctrl + X 바인딩
log_text.bind("<Control-c>", lambda event: log_text.event_generate("<<Copy>>"))
log_text.bind("<Control-v>", lambda event: log_text.event_generate("<<Paste>>"))
log_text.bind("<Control-x>", lambda event: log_text.event_generate("<<Cut>>"))

### [추가됨] 마우스 우클릭 메뉴 (복사)
def copy_selection():
    log_text.event_generate("<<Copy>>")

context_menu = tk.Menu(log_text, tearoff=0)
context_menu.add_command(label="복사", command=copy_selection)

def show_context_menu(event):
    context_menu.tk_popup(event.x_root, event.y_root)

log_text.bind("<Button-3>", show_context_menu)


# --------------------- (4) 시작 시 초기화 작업 ---------------------- #
def on_start():
    # 1. GDSClientLinux 실행 권한 확인
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패, 혹은 파일이 없습니다.")

    # 2. tftpd-hpa 설치 확인 & 자동 설치
    if check_and_install_tftpd():
        start_tftp_server()

    # 3. 라즈베리파이/Ubuntu IP 자동 입력 (첫 번째 IP 사용)
    try:
        all_ips = subprocess.check_output(["hostname", "-I"], universal_newlines=True).strip().split()
        if all_ips:
            tftp_ip_entry.delete(0, tk.END)
            tftp_ip_entry.insert(0, all_ips[0])  # 첫 번째 IP를 TFTP IP에 자동 입력
    except:
        pass


# 메인 윈도우 표시 후 on_start 실행
root.after(100, on_start)
root.mainloop()

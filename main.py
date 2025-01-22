#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil
import stat  # 실행 권한 체크를 위해 필요
import time  # (추가) 모드 전환 후 잠시 대기 위해 사용

os.environ['DISPLAY'] = ':0'

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) GDSClientLinux의 절대 경로 설정 (예시: Ubuntu x86_64 환경)
#    실제 설치된 경로에 맞추어 수정하세요.
GDSCLIENT_PATH = "/home/gdseng/GDS_Release_20250110/GDSClientLinux"

# 2) TFTP 서버 루트 디렉토리(예: /srv/tftp)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

def run_command(args):
    """
    subprocess.check_output로 명령을 실행하고 결과를 로그창에 표시.
    오류 발생 시 로그창에 오류 내용을 표시한다.
    """
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True)
        log_text.insert(tk.END, output + "\n")
    except subprocess.CalledProcessError as e:
        log_text.insert(tk.END, f"[오류]\n{e.output}\n")

def ensure_gdsclientlinux_executable():
    """
    GDSClientLinux 절대 경로가 존재하는지, 실행 권한이 있는지 확인.
    없다면 오류 메시지를 표시하거나 자동으로 chmod +x를 수행한다.
    """
    if not os.path.isfile(GDSCLIENT_PATH):
        log_text.insert(tk.END, f"[오류] GDSClientLinux 파일을 찾을 수 없습니다: {GDSCLIENT_PATH}\n")
        return False

    # 실행 권한 확인
    file_stat = os.stat(GDSCLIENT_PATH)
    if not (file_stat.st_mode & stat.S_IXUSR):
        log_text.insert(tk.END, "[정보] GDSClientLinux에 실행 권한이 없어 설정합니다...\n")
        try:
            run_command(["sudo", "chmod", "+x", GDSCLIENT_PATH])
        except Exception as e:
            log_text.insert(tk.END, f"[오류] GDSClientLinux 실행 권한 설정 실패: {e}\n")
            return False

    return True

def check_and_install_tftpd():
    """
    tftpd-hpa 패키지가 설치되어 있는지 확인하고,
    없다면 자동으로 설치 (sudo 권한 필요).
    """
    log_text.insert(tk.END, "[정보] tftpd-hpa 설치 여부 확인 중...\n")
    try:
        check_install = subprocess.check_output(
            ["dpkg", "-l", "tftpd-hpa"],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        if "tftpd-hpa" in check_install:
            log_text.insert(tk.END, "[정보] tftpd-hpa가 이미 설치되어 있습니다.\n")
            return True
    except subprocess.CalledProcessError:
        pass

    # 미설치 시 자동 설치
    log_text.insert(tk.END, "[정보] tftpd-hpa가 설치되어 있지 않아 설치를 진행합니다...\n")
    try:
        run_command(["sudo", "apt-get", "update"])
        run_command(["sudo", "apt-get", "-y", "install", "tftpd-hpa"])
        return True
    except Exception as e:
        log_text.insert(tk.END, f"[오류] tftpd-hpa 설치 실패: {e}\n")
        return False

def start_tftp_server():
    """
    tftpd-hpa 서비스를 enable하고 start한다 (이미 실행 중이면 그대로 유지).
    """
    log_text.insert(tk.END, "[정보] TFTP 서버를 시작합니다...\n")
    run_command(["sudo", "systemctl", "enable", "tftpd-hpa"])
    run_command(["sudo", "systemctl", "start", "tftpd-hpa"])

def copy_to_tftp(file_path):
    """
    업그레이드 파일을 TFTP 루트 디렉토리에 복사 후 권한 설정.
    """
    if not os.path.isfile(file_path):
        log_text.insert(tk.END, f"[오류] 파일이 존재하지 않습니다: {file_path}\n")
        return False

    if not os.path.exists(TFTP_ROOT_DIR):
        log_text.insert(tk.END, f"[오류] TFTP 루트 디렉토리가 없습니다: {TFTP_ROOT_DIR}\n")
        return False

    file_name = os.path.basename(file_path)
    dest_path = os.path.join(TFTP_ROOT_DIR, file_name)

    try:
        shutil.copy(file_path, dest_path)
        log_text.insert(tk.END, f"[파일 복사] {file_path} -> {dest_path}\n")
        run_command(["sudo", "chmod", "644", dest_path])
        return True
    except Exception as e:
        log_text.insert(tk.END, f"[오류] 파일 복사 중 문제 발생: {e}\n")
        return False

# --------------------- GDSClientLinux 관련 명령 함수들 ---------------------- #
def get_chip_size():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command([GDSCLIENT_PATH, ip, "0"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_mode():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command([GDSCLIENT_PATH, ip, "1"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_version():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command([GDSCLIENT_PATH, ip, "2"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def reboot():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command([GDSCLIENT_PATH, ip, "3"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def change_mode():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command([GDSCLIENT_PATH, ip, "4", "1"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def select_file():
    filepath = filedialog.askopenfilename(title="업그레이드 파일 선택")
    if filepath:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, filepath)

def upgrade():
    """
    업그레이드 절차:
      1) 파일을 TFTP 루트 디렉토리에 복사
      2) TFTP 서버 실행 확인
      3) 모드 변경 (4,1)
      4) 일정 시간 대기 (2초 정도)
      5) 업그레이드 (5, tftpIp, fileName)
    """
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_path = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file_path:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    # 1. 파일 복사
    if not copy_to_tftp(upgrade_file_path):
        return

    # 2. TFTP 서버 기동
    start_tftp_server()

    # 3. 모드 변경
    run_command([GDSCLIENT_PATH, detector_ip, "4", "1"])

    # (추가) 4. 디텍터가 업그레이드 모드로 전환될 시간을 준다 (2초 대기)
    time.sleep(2)

    # 5. 업그레이드
    file_name = os.path.basename(upgrade_file_path)
    run_command([GDSCLIENT_PATH, detector_ip, "5", tftp_ip, file_name])

# --------------------- GUI 초기화 ---------------------- #
root = tk.Tk()
root.title("GDS 클라이언트 UI (TFTP 서버 자동화 + 절대경로 사용)")

info_label = tk.Label(
    root,
    text=(
        "라즈베리파이/Ubuntu에서 TFTP 서버를 자동 구동하고,\n"
        "GDSClientLinux 명령을 절대 경로로 실행합니다.\n"
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

def on_start():
    # 1. GDSClientLinux 실행 권한 확인
    if not ensure_gdsclientlinux_executable():
        log_text.insert(tk.END, "[오류] GDSClientLinux 실행 권한 설정 실패, 혹은 파일이 없습니다.\n")

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

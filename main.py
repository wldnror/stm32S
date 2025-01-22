#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil

os.environ['DISPLAY'] = ':0'

# tftpd-hpa의 TFTP 루트 디렉토리 (예: /srv/tftp)
TFTP_ROOT_DIR = "/srv/tftp"

# GDSClientLinux 실행 함수
def run_command(args):
    """
    subprocess.check_output로 명령을 실행하고,
    결과(표준출력) 또는 에러를 로그창에 표시한다.
    """
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True)
        log_text.insert(tk.END, output + "\n")
    except subprocess.CalledProcessError as e:
        log_text.insert(tk.END, f"오류: {e.output}\n")

def start_tftp_server():
    """
    tftpd-hpa 서비스를 시작하는 함수.
    (이미 설치되어 있어야 하며, /etc/default/tftpd-hpa 설정이 되어있어야 함)
    """
    # 서비스가 설치되어 있는지 간단히 확인 (optional)
    # dpkg -l | grep tftpd-hpa
    try:
        check_install = subprocess.check_output(["dpkg", "-l", "tftpd-hpa"], stderr=subprocess.STDOUT, universal_newlines=True)
        if "tftpd-hpa" not in check_install:
            log_text.insert(tk.END, "tftpd-hpa가 설치되지 않았습니다. 설치 후 다시 시도해주세요.\n")
            return
    except subprocess.CalledProcessError as e:
        log_text.insert(tk.END, "tftpd-hpa 패키지가 설치되지 않았습니다. apt-get install tftpd-hpa 해주세요.\n")
        return

    # tftpd-hpa 서비스를 시작
    log_text.insert(tk.END, "[TFTP 서버 시작] 명령 실행 중...\n")
    run_command(["sudo", "systemctl", "start", "tftpd-hpa"])

def copy_to_tftp(file_path):
    """
    선택한 업그레이드 파일을 TFTP 루트 디렉토리로 복사한다.
    """
    if not os.path.isfile(file_path):
        log_text.insert(tk.END, f"파일이 존재하지 않습니다: {file_path}\n")
        return

    if not os.path.exists(TFTP_ROOT_DIR):
        log_text.insert(tk.END, f"TFTP 루트 디렉토리가 존재하지 않습니다: {TFTP_ROOT_DIR}\n")
        return

    # 파일명만 추출
    file_name = os.path.basename(file_path)
    dest_path = os.path.join(TFTP_ROOT_DIR, file_name)
    
    try:
        # 관리자 권한이 필요한 경우가 많으므로, sudo를 써서 cp 할 수도 있음
        # 여기서는 Python shutil 사용 (실행 자체를 sudo로 해야 함)
        shutil.copy(file_path, dest_path)
        log_text.insert(tk.END, f"[파일 복사] {file_path} -> {dest_path}\n")

        # 권한 설정 (tftpd-hpa가 읽을 수 있도록)
        run_command(["sudo", "chmod", "644", dest_path])
    except Exception as e:
        log_text.insert(tk.END, f"파일 복사 중 오류 발생: {e}\n")

def get_chip_size():
    detector_ip = detector_ip_entry.get().strip()
    if detector_ip:
        run_command(["./GDSClientLinux", detector_ip, "0"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_mode():
    detector_ip = detector_ip_entry.get().strip()
    if detector_ip:
        run_command(["./GDSClientLinux", detector_ip, "1"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_version():
    detector_ip = detector_ip_entry.get().strip()
    if detector_ip:
        run_command(["./GDSClientLinux", detector_ip, "2"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def reboot():
    detector_ip = detector_ip_entry.get().strip()
    if detector_ip:
        run_command(["./GDSClientLinux", detector_ip, "3"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def change_mode():
    detector_ip = detector_ip_entry.get().strip()
    if detector_ip:
        run_command(["./GDSClientLinux", detector_ip, "4", "1"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def select_file():
    filepath = filedialog.askopenfilename(title="업그레이드 파일 선택")
    if filepath:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, filepath)

def upgrade():
    """
    1) 업그레이드 파일을 TFTP 디렉토리에 복사
    2) 모드 변경 (4 1)
    3) 업그레이드 (5 tftpIp filename)
    """
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file:
        messagebox.showwarning("경고", "모든 입력 항목을 채워주세요 (Detector IP, TFTP IP, 업그레이드 파일)")
        return

    # 파일을 TFTP 루트 디렉토리로 복사
    copy_to_tftp(upgrade_file)

    # (옵션) TFTP 서버가 이미 실행 중인지 모를 경우, 자동으로 시작 시도
    start_tftp_server()

    # 1단계: 모드를 변경 (Normal -> Upgrade)
    run_command(["./GDSClientLinux", detector_ip, "4", "1"])
    
    # 2단계: 업그레이드를 실행
    file_name = os.path.basename(upgrade_file)  # TFTP에서 받을 때는 파일명만 사용
    run_command(["./GDSClientLinux", detector_ip, "5", tftp_ip, file_name])

# 메인 윈도우 생성
root = tk.Tk()
root.title("GDS 클라이언트 UI + TFTP 서버 제어")

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

# 명령 버튼 프레임
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

# 추가 버튼: TFTP 서버 시작 (원한다면 수동으로도 가능)
btn_tftp_start = tk.Button(frame_buttons, text="TFTP 서버 시작", width=15, command=start_tftp_server)
btn_tftp_start.grid(row=2, column=1, padx=5, pady=5)

# 로그 출력 창 (scrolledtext)
log_text = scrolledtext.ScrolledText(root, width=70, height=15)
log_text.pack(padx=10, pady=10)

root.mainloop()

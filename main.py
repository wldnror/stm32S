#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import shutil

os.environ['DISPLAY'] = ':0'

# TFTP 서버 루트 디렉토리
TFTP_ROOT_DIR = "/srv/tftp"

def run_command(args):
    """
    터미널 명령어를 실행하고 결과(표준출력)를 로그창에 보여준다.
    오류 발생 시 로그창에 오류 내용을 표시한다.
    """
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True)
        log_text.insert(tk.END, output + "\n")
    except subprocess.CalledProcessError as e:
        log_text.insert(tk.END, f"[오류]\n{e.output}\n")

def check_and_install_tftpd():
    """
    tftpd-hpa 패키지가 설치되어 있는지 확인하고,
    없다면 자동으로 설치한다. (sudo 권한 필요)
    """
    log_text.insert(tk.END, "[정보] tftpd-hpa 설치 여부 확인 중...\n")
    try:
        # dpkg -l tftpd-hpa
        check_install = subprocess.check_output(["dpkg", "-l", "tftpd-hpa"], stderr=subprocess.STDOUT, universal_newlines=True)
        if "tftpd-hpa" in check_install:
            log_text.insert(tk.END, "[정보] tftpd-hpa가 이미 설치되어 있습니다.\n")
            return True
    except subprocess.CalledProcessError:
        pass

    # 미설치 시 자동 설치 진행
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
    tftpd-hpa 서비스를 enable하고 start한다.
    (이미 실행 중이면 그대로 유지)
    """
    log_text.insert(tk.END, "[정보] TFTP 서버를 시작합니다...\n")

    # 부팅 시 자동 실행
    run_command(["sudo", "systemctl", "enable", "tftpd-hpa"])
    # 서버 시작
    run_command(["sudo", "systemctl", "start", "tftpd-hpa"])

def copy_to_tftp(file_path):
    """
    업그레이드 파일을 TFTP 루트 디렉토리로 복사 후 권한 설정
    """
    if not os.path.isfile(file_path):
        log_text.insert(tk.END, f"[오류] 해당 파일이 존재하지 않습니다: {file_path}\n")
        return False

    if not os.path.exists(TFTP_ROOT_DIR):
        log_text.insert(tk.END, f"[오류] TFTP 루트 디렉토리가 존재하지 않습니다: {TFTP_ROOT_DIR}\n")
        return False

    file_name = os.path.basename(file_path)
    dest_path = os.path.join(TFTP_ROOT_DIR, file_name)

    try:
        shutil.copy(file_path, dest_path)
        log_text.insert(tk.END, f"[파일 복사] {file_path} -> {dest_path}\n")
        # 권한 설정 (읽기 가능하도록)
        run_command(["sudo", "chmod", "644", dest_path])
        return True
    except Exception as e:
        log_text.insert(tk.END, f"[오류] 파일 복사 중 문제 발생: {e}\n")
        return False

# --------------------- GDSClientLinux 관련 명령 함수들 ---------------------- #
def get_chip_size():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command(["./GDSClientLinux", ip, "0"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_mode():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command(["./GDSClientLinux", ip, "1"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def get_version():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command(["./GDSClientLinux", ip, "2"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def reboot():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command(["./GDSClientLinux", ip, "3"])
    else:
        messagebox.showwarning("경고", "Detector IP를 입력하세요")

def change_mode():
    ip = detector_ip_entry.get().strip()
    if ip:
        run_command(["./GDSClientLinux", ip, "4", "1"])
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
    2) TFTP 서버 실행 확인
    3) 모드 변경 (4 1)
    4) 업그레이드 (5 tftpIp fileName)
    """
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_path = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file_path:
        messagebox.showwarning("경고", "모든 입력 항목(Detector IP, TFTP IP, 업그레이드 파일)을 입력하세요.")
        return

    # 1. 파일을 TFTP 디렉토리로 복사
    if not copy_to_tftp(upgrade_file_path):
        return  # 파일 복사 실패 시 중단

    # 2. TFTP 서버 자동 실행
    start_tftp_server()

    # 3. 모드 변경
    run_command(["./GDSClientLinux", detector_ip, "4", "1"])

    # 4. 업그레이드
    file_name = os.path.basename(upgrade_file_path)
    run_command(["./GDSClientLinux", detector_ip, "5", tftp_ip, file_name])

# --------------------- GUI 초기화 ---------------------- #
root = tk.Tk()
root.title("GDS 클라이언트 UI (TFTP 서버 자동화)")

# 상단 안내 문구
info_label = tk.Label(root, text="라즈베리파이에서 자동으로 TFTP 서버 구동 + GDSClientLinux 명령을 사용합니다.\n"
                                 "관리자 권한(sudo)으로 실행되어야 정상 동작합니다.",
                      fg="blue")
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

# 로그 영역
log_text = scrolledtext.ScrolledText(root, width=80, height=15)
log_text.pack(padx=10, pady=10)

# 프로그램 실행 시 초기 작업 (TFTP 서버 확인 등)
def on_start():
    # 1. tftpd-hpa 설치 확인 & 필요 시 설치
    if check_and_install_tftpd():
        # 설치되어 있다면, TFTP 서버 자동 시작
        start_tftp_server()

    # 2. 라즈베리파이 IP 자동 입력 (첫 번째 IP만 사용)
    try:
        # hostname -I 명령을 사용해 IP 목록 가져오기
        all_ips = subprocess.check_output(["hostname", "-I"], universal_newlines=True).strip().split()
        if all_ips:
            # TFTP IP 항목에 첫 번째 IP를 자동으로 입력
            tftp_ip_entry.delete(0, tk.END)
            tftp_ip_entry.insert(0, all_ips[0])
    except:
        # 실패 시 무시
        pass

# 윈도우가 완전히 표시된 직후에 실행
root.after(100, on_start)

root.mainloop()

#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os

os.environ['DISPLAY'] = ':0'
pygame.mixer.init()
# GDSClientLinux 실행 함수
def run_command(args):
    try:
        # 명령 실행 (예: subprocess.check_output)
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True)
        log_text.insert(tk.END, output + "\n")
    except subprocess.CalledProcessError as e:
        log_text.insert(tk.END, f"Error: {e.output}\n")

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
    detector_ip = detector_ip_entry.get().strip()
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file = file_entry.get().strip()

    if not detector_ip or not tftp_ip or not upgrade_file:
        messagebox.showwarning("경고", "모든 입력 항목을 채워주세요 (Detector IP, TFTP IP, 업그레이드 파일)")
        return

    # 1단계: 모드를 변경합니다 (Normal -> Upgrade)
    run_command(["./GDSClientLinux", detector_ip, "4", "1"])
    
    # 2단계: 업그레이드를 실행합니다.
    run_command(["./GDSClientLinux", detector_ip, "5", tftp_ip, upgrade_file])

# 메인 윈도우 생성
root = tk.Tk()
root.title("GDS Client UI")

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

tk.Label(frame_file, text="Upgrade File:").grid(row=0, column=0, sticky="e")
file_entry = tk.Entry(frame_file, width=40)
file_entry.grid(row=0, column=1, padx=5)
file_btn = tk.Button(frame_file, text="파일 선택", command=select_file)
file_btn.grid(row=0, column=2, padx=5)

# 명령 버튼 프레임
frame_buttons = tk.Frame(root)
frame_buttons.pack(padx=10, pady=5)

btn_chip_size = tk.Button(frame_buttons, text="Get ChipSize", width=15, command=get_chip_size)
btn_chip_size.grid(row=0, column=0, padx=5, pady=5)

btn_mode = tk.Button(frame_buttons, text="Get Mode(Bank)", width=15, command=get_mode)
btn_mode.grid(row=0, column=1, padx=5, pady=5)

btn_version = tk.Button(frame_buttons, text="Get Version", width=15, command=get_version)
btn_version.grid(row=0, column=2, padx=5, pady=5)

btn_reboot = tk.Button(frame_buttons, text="Reboot", width=15, command=reboot)
btn_reboot.grid(row=1, column=0, padx=5, pady=5)

btn_change_mode = tk.Button(frame_buttons, text="Change Mode (4 1)", width=15, command=change_mode)
btn_change_mode.grid(row=1, column=1, padx=5, pady=5)

btn_upgrade = tk.Button(frame_buttons, text="Upgrade", width=15, command=upgrade)
btn_upgrade.grid(row=1, column=2, padx=5, pady=5)

# 로그 출력 창 (scrolledtext)
log_text = scrolledtext.ScrolledText(root, width=70, height=15)
log_text.pack(padx=10, pady=10)

root.mainloop()

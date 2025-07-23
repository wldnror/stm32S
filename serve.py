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
import socket
import json

# 추가: pymodbus 모듈 임포트
from pymodbus.client import ModbusTcpClient

# 디스플레이 환경 변수 설정 (리눅스에서 GUI를 사용할 경우 필요)
os.environ['DISPLAY'] = ':0'

# ------------------- Tkinter 루트 생성 -------------------
root = tk.Tk()
root.title("자동 업그레이드 테스트 UI (다중 장비)")

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) 설정 파일 경로 설정
CONFIG_FILE = os.path.expanduser("~/.gds_client_config_auto_upgrade.json")

# 2) TFTP 서버 루트 디렉토리 (실제 환경에 맞게 수정)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

# 전역 스레드/이벤트 객체
auto_thread = None                 # 자동 업그레이드 반복 스레드
stop_event = threading.Event()     # 중지 신호 전달용 이벤트

# --------------------- (A) 로그 업데이트 함수 --------------------- #
def async_log_print(msg: str):
    def insert_log():
        log_text.insert(tk.END, msg.rstrip() + "\n")
        log_text.see(tk.END)  # 자동 스크롤
    root.after(0, insert_log)

# --------------------- (B) subprocess 실행 함수 --------------------- #
def run_command_realtime(args):
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

# --------------------- (C) 설정 파일 관리 --------------------- #
def load_config():
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        async_log_print(f"[오류] 설정 파일을 로드할 수 없습니다: {e}")
        return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        async_log_print(f"[오류] 설정 파일을 저장할 수 없습니다: {e}")

def select_gdsclientlinux():
    filepath = filedialog.askopenfilename(
        title="GDSClientLinux 실행 파일 선택",
        filetypes=[("Executable Files", "GDSClientLinux"), ("All Files", "*.*")]
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

# --------------------- (D) 실행 권한 & tftpd-hpa 설치 체크 --------------------- #
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

# --------------------- (E) 파일 복사 (고정 이름) --------------------- #
def copy_to_tftp(file_path, dest_name="ASGD3000E_H.bin"):
    if not os.path.isfile(file_path):
        async_log_print(f"[오류] 파일이 존재하지 않습니다: {file_path}")
        return False
    if not os.path.exists(TFTP_ROOT_DIR):
        async_log_print(f"[오류] TFTP 루트 디렉토리가 없습니다: {TFTP_ROOT_DIR}")
        return False

    dest_path = os.path.join(TFTP_ROOT_DIR, dest_name)
    try:
        shutil.copy(file_path, dest_path)
        async_log_print(f"[파일 복사] {file_path} -> {dest_path}")
        run_command_realtime(["sudo", "chmod", "644", dest_path])
        return True
    except Exception as e:
        async_log_print(f"[오류] 파일 복사 중 문제 발생: {e}")
        return False

# --------------------- (F) 업그레이드 작업 (고정 이름) --------------------- #
def upgrade_task(detector_ip, tftp_ip, upgrade_file_paths):
    files = [f.strip() for f in upgrade_file_paths.split(",") if f.strip()]
    if not files:
        async_log_print("[오류] 업그레이드할 파일이 선택되지 않았습니다.")
        return
    selected_file = random.choice(files)
    fixed_name = "ASGD3000E_H.bin"

    if not copy_to_tftp(selected_file, dest_name=fixed_name):
        return
    start_tftp_server()
    ret1 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "4", "1"])
    time.sleep(2)
    ret2 = run_command_realtime([GDSCLIENT_PATH, detector_ip, "5", tftp_ip, fixed_name])
    if ret2 == 0:
        async_log_print(f"[알림] {detector_ip} 업그레이드 명령을 성공적으로 마쳤습니다. 사용된 파일: {fixed_name}")
    else:
        async_log_print(f"[알림] {detector_ip} 업그레이드 명령 중 오류가 발생했습니다.")

# --------------------- (G) 단발 업그레이드 호출 --------------------- #
def get_detector_ips():
    ip_text = detector_ip_entry.get().strip()
    ips = [ip.strip() for ip in ip_text.split(",") if ip.strip()]
    return ips

def upgrade_once_multiple():
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()
    detector_ips = get_detector_ips()
    if not detector_ips or not tftp_ip or not upgrade_file_paths:
        messagebox.showwarning("경고", "모든 입력 항목(장비 IP(들), TFTP IP, 업그레이드 파일)을 입력하세요.")
        return
    for ip in detector_ips:
        threading.Thread(
            target=upgrade_task,
            args=(ip, tftp_ip, upgrade_file_paths),
            daemon=True
        ).start()

# ============================================================
# =============== 랜덤 반복 업그레이드 로직 (다중 장비) ===============
# ============================================================
def auto_upgrade_loop_multiple():
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()
    detector_ips = get_detector_ips()
    files = [f.strip() for f in upgrade_file_paths.split(",") if f.strip()]
    if not files:
        async_log_print("[오류] 업그레이드할 파일이 선택되지 않았습니다.")
        return
    while not stop_event.is_set():
        threads = []
        for ip in detector_ips:
            th = threading.Thread(
                target=upgrade_task,
                args=(ip, tftp_ip, upgrade_file_paths),
                daemon=True
            )
            th.start()
            threads.append(th)
        for th in threads:
            th.join()
        if stop_event.is_set():
            break
        wait_sec = random.randint(42, 300)
        async_log_print(f"[자동모드] 다음 업그레이드까지 대기: {wait_sec}초")
        for _ in range(wait_sec):
            if stop_event.is_set():
                break
            time.sleep(1)

def start_auto_upgrade_multiple():
    global auto_thread
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 또는 파일이 없습니다.")
        return
    if not check_and_install_tftpd():
        async_log_print("[오류] tftpd-hpa 설치가 안 되어 업그레이드를 진행할 수 없습니다.")
        return
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()
    detector_ips = get_detector_ips()
    if not detector_ips or not tftp_ip or not upgrade_file_paths:
        messagebox.showwarning("경고", "모든 입력 항목(장비 IP(들), TFTP IP, 업그레이드 파일)을 입력하세요.")
        return
    if not auto_thread or not auto_thread.is_alive():
        stop_event.clear()
        async_log_print("[자동모드] 다중 장비에 대해 무작위 업그레이드 시작")
        auto_thread = threading.Thread(target=auto_upgrade_loop_multiple, daemon=True)
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

# ----- (H) 파일 선택 ----- #
def select_files():
    filepaths = filedialog.askopenfilenames(title="업그레이드 파일 선택")
    if filepaths:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, ",".join(filepaths))

# --------------------- (I) 로컬 IP 주소 가져오기 --------------------- #
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --------------------- Modbus TCP 테스트 기능 --------------------- #
def modbus_test():
    ip_text = detector_ip_entry.get().strip()
    if not ip_text:
        messagebox.showwarning("경고", "장비 IP(들)를 입력하세요.")
        return
    modbus_ip = ip_text.split(",")[0].strip()
    try:
        client = ModbusTcpClient(modbus_ip, port=502, timeout=3)
        if client.connect():
            # 단일 레지스터 읽기
            result = client.read_holding_registers(0)
            if not result.isError():
                data = result.registers[0]
                async_log_print(f"[Modbus 테스트] {modbus_ip} 연결 성공. 데이터: {data}")
                messagebox.showinfo("Modbus 테스트", f"{modbus_ip} 연결 성공.\n데이터: {data}")
            else:
                async_log_print(f"[Modbus 테스트] {modbus_ip} 읽기 실패: {result}")
                messagebox.showerror("Modbus 테스트", f"{modbus_ip} 읽기 실패: {result}")
            client.close()
        else:
            async_log_print(f"[Modbus 테스트] {modbus_ip}에 연결할 수 없습니다.")
            messagebox.showerror("Modbus 테스트", f"{modbus_ip}에 연결할 수 없습니다.")
    except Exception as e:
        async_log_print(f"[Modbus 테스트] 예외 발생: {e}")
        messagebox.showerror("Modbus 테스트", f"예외 발생: {e}")

# ====================== Modbus Polling 기능 추가 ======================
modbus_pollers = {}  # key: ip, value: ModbusPoller instance
modbus_labels = {}   # key: ip, value: Label widget

class ModbusPoller:
    def __init__(self, ip, update_callback, poll_interval=0.02):
        self.ip = ip
        self.update_callback = update_callback
        self.poll_interval = poll_interval
        self.client = ModbusTcpClient(ip, port=502, timeout=1)
        self.running = False
        self.thread = None

    def start(self):
        if not self.client.connect():
            self.update_callback(self.ip, None, "연결 실패")
            return
        # older 버전에서는 unit_id를 별도로 전달하지 않습니다.
        self.running = True
        self.thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.thread.start()

    def poll_loop(self):
        # pymodbus의 구버전에서는 read_holding_registers가 단일 레지스터만 지원하므로,
        # 0번부터 10번까지 개별적으로 호출합니다.
        while self.running:
            try:
                regs = []
                for addr in range(11):
                    result = self.client.read_holding_registers(addr)
                    if result.isError():
                        regs.append("err")
                    else:
                        regs.append(result.registers[0])
                # 추출: 40001 -> regs[0], 40005 -> regs[4], 40007 -> regs[7], 40011 -> regs[10]
                display_data = (
                    f"40001: {regs[0]}, "
                    f"40005: {regs[4]}, "
                    f"40007: {regs[7]}, "
                    f"40011: {regs[10]}"
                )
                self.update_callback(self.ip, display_data, "정상")
            except Exception as e:
                self.update_callback(self.ip, None, f"예외: {e}")
            time.sleep(self.poll_interval)

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1)
        self.client.close()

def update_modbus_label(ip, data, status):
    def update():
        if data is None:
            text = f"IP: {ip} | 상태: {status}"
        else:
            text = f"IP: {ip} | {data} | 상태: {status}"
        if ip in modbus_labels:
            modbus_labels[ip].config(text=text)
        else:
            lbl = tk.Label(frame_modbus, text=text, anchor="w")
            lbl.pack(fill="x", padx=5, pady=2)
            modbus_labels[ip] = lbl
    root.after(0, update)

def start_modbus_polling():
    ip_text = detector_ip_entry.get().strip()
    ips = [ip.strip() for ip in ip_text.split(",") if ip.strip()]
    if not ips:
        messagebox.showwarning("경고", "Modbus 폴링을 시작할 IP 주소를 입력하세요.")
        return
    for ip in ips:
        if ip not in modbus_pollers:
            poller = ModbusPoller(ip, update_modbus_label, poll_interval=0.2)
            modbus_pollers[ip] = poller
            poller.start()
            async_log_print(f"[Modbus 폴링] {ip}에 대해 폴링 시작")
        else:
            async_log_print(f"[Modbus 폴링] {ip}는 이미 폴링 중입니다.")

def stop_modbus_polling():
    for ip, poller in list(modbus_pollers.items()):
        poller.stop()
        async_log_print(f"[Modbus 폴링] {ip} 폴링 중지")
        del modbus_pollers[ip]

# ====================== Modbus Polling UI 추가 ======================
frame_modbus = tk.Frame(root)
frame_modbus.pack(padx=10, pady=5, fill="x")
lbl_modbus_title = tk.Label(frame_modbus, text="Modbus Polling 데이터", fg="green", font=("Helvetica", 10, "bold"))
lbl_modbus_title.pack(anchor="w", padx=5)

# ======================= Tkinter UI 구성 =======================
info_label = tk.Label(
    root,
    text=(
        "GDSClientLinux를 이용하여 랜덤 간격(42~300초)으로\n"
        "자동 업그레이드를 반복 실행하는 테스트 툴입니다.\n"
        "여러 장비(Detector IP)를 동시에 처리할 수 있습니다.\n"
        "업그레이드 파일을 여러 개 선택하면 업그레이드 시 무작위로 선택됩니다.\n\n"
        "※ Modbus 테스트는 '장비 IP(들)' 입력란의 첫 번째 IP를 사용합니다."
    ),
    fg="blue"
)
info_label.pack(padx=10, pady=5)

# IP 입력 프레임
frame_ip = tk.Frame(root)
frame_ip.pack(padx=10, pady=5, fill="x")

tk.Label(frame_ip, text="장비 IP(들):").grid(row=0, column=0, sticky="e")
detector_ip_entry = tk.Entry(frame_ip, width=30)
detector_ip_entry.grid(row=0, column=1, padx=5)

tk.Label(frame_ip, text="TFTP IP:").grid(row=0, column=2, sticky="e")
tftp_ip_entry = tk.Entry(frame_ip, width=15)
tftp_ip_entry.grid(row=0, column=3, padx=5)

# Modbus 테스트 버튼 (추가)
modbus_test_btn = tk.Button(frame_ip, text="Modbus 테스트", command=modbus_test)
modbus_test_btn.grid(row=1, column=1, padx=5, pady=5, sticky="w")

# 파일 선택 프레임
frame_file = tk.Frame(root)
frame_file.pack(padx=10, pady=5, fill="x")

tk.Label(frame_file, text="업그레이드 파일:").grid(row=0, column=0, sticky="e")
file_entry = tk.Entry(frame_file, width=60)
file_entry.grid(row=0, column=1, padx=5)
file_btn = tk.Button(frame_file, text="파일 선택", command=select_files)
file_btn.grid(row=0, column=2, padx=5)

# 명령 버튼들 (자동 시작/중지, 단발 업그레이드, Modbus Polling 제어)
frame_buttons = tk.Frame(root)
frame_buttons.pack(padx=10, pady=5)
btn_start_auto = tk.Button(frame_buttons, text="자동 업그레이드 시작 (다중)", width=25, command=start_auto_upgrade_multiple)
btn_start_auto.grid(row=0, column=0, padx=5, pady=5)
btn_stop_auto = tk.Button(frame_buttons, text="자동 업그레이드 중지", width=25, command=stop_auto_upgrade)
btn_stop_auto.grid(row=0, column=1, padx=5, pady=5)
btn_upgrade_once = tk.Button(frame_buttons, text="단발 업그레이드 실행 (다중)", width=25, command=upgrade_once_multiple)
btn_upgrade_once.grid(row=0, column=2, padx=5, pady=5)
btn_start_modbus = tk.Button(frame_buttons, text="Modbus Polling 시작", width=25, command=start_modbus_polling)
btn_start_modbus.grid(row=1, column=0, padx=5, pady=5)
btn_stop_modbus = tk.Button(frame_buttons, text="Modbus Polling 중지", width=25, command=stop_modbus_polling)
btn_stop_modbus.grid(row=1, column=1, padx=5, pady=5)

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

# --------------------- (K) 시작 시 자동 설정 --------------------- #
def on_start():
    global GDSCLIENT_PATH
    GDSCLIENT_PATH = get_gdsclient_path()
    if not GDSCLIENT_PATH:
        return
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 혹은 파일이 없습니다.")
    if check_and_install_tftpd():
        start_tftp_server()
    local_ip = get_local_ip()
    async_log_print(f"[정보] 로컬 IP 주소 감지: {local_ip}")
    tftp_ip_entry.delete(0, tk.END)
    tftp_ip_entry.insert(0, local_ip)
    try:
        base_ip = '.'.join(local_ip.split('.')[:3]) + '.'
    except Exception:
        base_ip = "192.168.0."
        async_log_print("[경고] 로컬 IP 분석 실패, 기본값 '192.168.0.' 사용")
    detector_ip_entry.delete(0, tk.END)
    detector_ip_entry.insert(0, base_ip)

root.after(100, on_start)
root.mainloop()

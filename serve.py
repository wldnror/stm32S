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

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# 1) 설정 파일 경로 설정
CONFIG_FILE = os.path.expanduser("~/.gds_client_config_auto_upgrade.json")

# 2) TFTP 서버 루트 디렉토리 (실제 환경에 맞게 수정)
TFTP_ROOT_DIR = "/srv/tftp"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

# 전역 스레드/이벤트 객체
auto_thread = None                 # 자동 업그레이드 반복 스레드
stop_event = threading.Event()     # 중지 신호 전달용 이벤트

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

    while True:
        line = p.stdout.readline()
        if not line:
            break
        async_log_print(line)

    p.wait()
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

# --------------------- (D) GDSClient 실행 권한 부여 체크 & tftpd-hpa 설치 체크 --------------------- #
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

# --------------------- (E) 업그레이드 절차에 필요한 파일 복사 함수 --------------------- #
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

# --------------------- (F) 업그레이드 단일 실행 프로세스 (모드 전환 후 업그레이드) --------------------- #
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
        async_log_print(f"[알림] {detector_ip} 업그레이드 명령을 성공적으로 마쳤습니다. 사용된 파일: {file_name}")
    else:
        async_log_print(f"[알림] {detector_ip} 업그레이드 명령 중 오류가 발생했습니다.")

# --------------------- (G) 업그레이드(단발) 호출 함수 (다중 장비 지원) --------------------- #
def get_detector_ips():
    """
    detector_ip_entry의 값을 콤마로 분리하여 IP 리스트로 반환합니다.
    """
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

    # 각 detector IP마다 별도의 스레드에서 업그레이드 작업 수행
    for ip in detector_ips:
        threading.Thread(
            target=upgrade_task,
            args=(ip, tftp_ip, upgrade_file_paths),
            daemon=True
        ).start()

# ============================================================
# =============== 랜덤 반복 업그레이드 관련 로직 (다중 장비) ===============
# ============================================================
def auto_upgrade_loop_multiple():
    tftp_ip = tftp_ip_entry.get().strip()
    upgrade_file_paths = file_entry.get().strip()
    detector_ips = get_detector_ips()

    # 파일 리스트 파싱
    files = [f.strip() for f in upgrade_file_paths.split(",") if f.strip()]
    if not files:
        async_log_print("[오류] 업그레이드할 파일이 선택되지 않았습니다.")
        return

    while not stop_event.is_set():
        # 모든 detector IP에 대해 업그레이드 작업을 동시에 수행
        threads = []
        for ip in detector_ips:
            th = threading.Thread(
                target=upgrade_task,
                args=(ip, tftp_ip, upgrade_file_paths),
                daemon=True
            )
            th.start()
            threads.append(th)

        # 각 작업이 완료될 때까지 기다림
        for th in threads:
            th.join()

        if stop_event.is_set():
            break

        # 42초 ~ 300초 사이 랜덤 대기
        wait_sec = random.randint(42, 300)
        async_log_print(f"[자동모드] 다음 업그레이드까지 대기: {wait_sec}초")
        for _ in range(wait_sec):
            if stop_event.is_set():
                break
            time.sleep(1)

def start_auto_upgrade_multiple():
    global auto_thread

    # GDSClientLinux 파일 체크
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 또는 파일이 없습니다.")
        return

    # tftpd-hpa 설치 체크
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
        # 파일 경로를 콤마로 구분하여 저장
        file_entry.insert(0, ",".join(filepaths))

# --------------------- (I) 컴퓨터의 로컬 IP 주소를 가져오는 함수 --------------------- #
def get_local_ip():
    """
    로컬 IP 주소를 반환합니다.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --------------------- 추가: Modbus TCP 테스트 기능 (통합 IP 입력란 사용) --------------------- #
def modbus_test():
    """
    Detector IP(들) 입력란에 입력된 IP들 중 첫 번째 IP로 Modbus TCP 연결 테스트를 수행합니다.
    여러 IP가 입력된 경우, 첫 번째 IP로 테스트합니다.
    """
    ip_text = detector_ip_entry.get().strip()
    if not ip_text:
        messagebox.showwarning("경고", "장비 IP(들)를 입력하세요.")
        return
    modbus_ip = ip_text.split(",")[0].strip()
    try:
        client = ModbusTcpClient(modbus_ip, port=502, timeout=3)
        if client.connect():
            response = client.read_holding_registers(0, count=1)
            if not response.isError():
                data = response.registers[0]
                async_log_print(f"[Modbus 테스트] {modbus_ip} 연결 성공. 데이터: {data}")
                messagebox.showinfo("Modbus 테스트", f"{modbus_ip} 연결 성공.\n데이터: {data}")
            else:
                async_log_print(f"[Modbus 테스트] {modbus_ip} 읽기 실패: {response}")
                messagebox.showerror("Modbus 테스트", f"{modbus_ip} 읽기 실패: {response}")
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
    def __init__(self, ip, update_callback, poll_interval=0.2):
        self.ip = ip
        self.update_callback = update_callback  # UI 업데이트를 위한 콜백 함수
        self.poll_interval = poll_interval
        self.client = ModbusTcpClient(ip, port=502, timeout=1)
        self.running = False
        self.thread = None

    def start(self):
        if not self.client.connect():
            self.update_callback(self.ip, None, "연결 실패")
            return
        self.running = True
        self.thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.thread.start()

    def poll_loop(self):
        while self.running:
            try:
                response = self.client.read_holding_registers(0, 1)
                if response.isError():
                    self.update_callback(self.ip, None, "에러 발생")
                else:
                    data = response.registers[0]
                    self.update_callback(self.ip, data, "정상")
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
        text = f"IP: {ip} | 데이터: {data} | 상태: {status}"
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

# 명령 버튼들 (자동 시작/중지, 단발 업그레이드) UI 하단에 Modbus Polling 제어 버튼 추가
frame_buttons = tk.Frame(root)
frame_buttons.pack(padx=10, pady=5)
btn_start_auto = tk.Button(frame_buttons, text="자동 업그레이드 시작 (다중)", width=25, command=start_auto_upgrade_multiple)
btn_start_auto.grid(row=0, column=0, padx=5, pady=5)
btn_stop_auto = tk.Button(frame_buttons, text="자동 업그레이드 중지", width=25, command=stop_auto_upgrade)
btn_stop_auto.grid(row=0, column=1, padx=5, pady=5)
btn_upgrade_once = tk.Button(frame_buttons, text="단발 업그레이드 실행 (다중)", width=25, command=upgrade_once_multiple)
btn_upgrade_once.grid(row=0, column=2, padx=5, pady=5)

# 추가: Modbus Polling 제어 버튼 (새로운 행)
btn_start_modbus = tk.Button(frame_buttons, text="Modbus Polling 시작", width=25, command=start_modbus_polling)
btn_start_modbus.grid(row=1, column=0, padx=5, pady=5)
btn_stop_modbus = tk.Button(frame_buttons, text="Modbus Polling 중지", width=25, command=stop_modbus_polling)
btn_stop_modbus.grid(row=1, column=1, padx=5, pady=5)

# ----- 로그 창 -----
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

    # 1. GDSClientLinux 실행 경로 가져오기
    GDSCLIENT_PATH = get_gdsclient_path()
    if not GDSCLIENT_PATH:
        return

    # 2. GDSClientLinux 실행 권한 확인
    if not ensure_gdsclientlinux_executable():
        async_log_print("[오류] GDSClientLinux 실행 권한 설정 실패 혹은 파일이 없습니다.")

    # 3. tftpd-hpa 설치 확인 & 자동 설치
    if check_and_install_tftpd():
        start_tftp_server()

    # 4. TFTP IP & 장비 IP 자동 설정
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

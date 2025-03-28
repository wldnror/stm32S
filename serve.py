#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
import threading
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

# 단순 예제: 각 장비에서 두 개의 홀딩 레지스터(40001, 40002)를 읽어온다고 가정
class ModbusPoller:
    def __init__(self, ip, update_callback, poll_interval=0.2):
        self.ip = ip
        self.update_callback = update_callback  # UI 업데이트를 위한 콜백 함수
        self.poll_interval = poll_interval
        self.client = ModbusTcpClient(ip, port=502, timeout=1)
        self.running = False
        self.thread = None

    def start(self):
        # 연결 시도
        if not self.client.connect():
            self.update_callback(self.ip, None, f"연결 실패")
            return
        self.running = True
        self.thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.thread.start()

    def poll_loop(self):
        while self.running:
            try:
                # 예제: 40001~40002 레지스터 읽기 (주소 0부터 시작)
                response = self.client.read_holding_registers(0, 2)
                if response.isError():
                    data = None
                    status = "에러 발생"
                else:
                    data = response.registers
                    status = "정상"
                # 읽은 데이터를 콜백으로 전달 (UI 업데이트는 메인스레드에서 처리)
                self.update_callback(self.ip, data, status)
            except (ConnectionException, ModbusIOException) as e:
                self.update_callback(self.ip, None, f"예외: {e}")
                self.running = False
            except Exception as e:
                self.update_callback(self.ip, None, f"알 수 없는 오류: {e}")
                self.running = False
            time.sleep(self.poll_interval)

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1)
        self.client.close()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("멀티 Modbus Polling (200ms 주기)")
        self.geometry("700x400")
        self.pollers = {}  # ip: ModbusPoller 객체 관리
        self.create_widgets()

    def create_widgets(self):
        # IP 주소 입력란 (콤마로 구분)
        frame_input = tk.Frame(self)
        frame_input.pack(pady=10)

        tk.Label(frame_input, text="Modbus 장비 IP (콤마로 구분):").pack(side="left", padx=5)
        self.ip_entry = tk.Entry(frame_input, width=50)
        self.ip_entry.pack(side="left", padx=5)
        self.ip_entry.insert(0, "192.168.0.10,192.168.0.11")  # 예제 기본값

        # 시작/중지 버튼
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        self.start_button = tk.Button(btn_frame, text="Polling 시작", command=self.start_polling)
        self.start_button.pack(side="left", padx=10)
        self.stop_button = tk.Button(btn_frame, text="Polling 중지", command=self.stop_polling)
        self.stop_button.pack(side="left", padx=10)

        # 데이터 출력 텍스트 창
        self.text = tk.Text(self, state="disabled", height=15)
        self.text.pack(pady=10, padx=10, fill="both", expand=True)

    def append_text(self, message):
        self.text.config(state="normal")
        self.text.insert("end", message)
        self.text.see("end")
        self.text.config(state="disabled")

    def update_ui(self, ip, data, status):
        # 이 함수는 polling 스레드에서 호출하므로, 메인스레드에서 UI 업데이트하도록 after() 사용
        def update():
            timestamp = time.strftime("%H:%M:%S")
            if data is None:
                msg = f"[{timestamp}] {ip}: {status}\n"
            else:
                msg = f"[{timestamp}] {ip}: 데이터 {data} ({status})\n"
            self.append_text(msg)
        self.after(0, update)

    def start_polling(self):
        ips = [ip.strip() for ip in self.ip_entry.get().split(",") if ip.strip()]
        if not ips:
            messagebox.showwarning("경고", "하나 이상의 IP 주소를 입력하세요.")
            return
        # 이미 polling 중인 IP가 있으면 중복 생성하지 않음
        for ip in ips:
            if ip not in self.pollers:
                poller = ModbusPoller(ip, self.update_ui, poll_interval=0.2)
                self.pollers[ip] = poller
                poller.start()
                self.append_text(f"{ip}에 대해 polling 시작\n")

    def stop_polling(self):
        for ip, poller in list(self.pollers.items()):
            poller.stop()
            self.append_text(f"{ip} polling 중지\n")
            del self.pollers[ip]

if __name__ == "__main__":
    app = App()
    app.mainloop()

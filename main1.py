#!/usr/bin/env python3
import socket, struct
from pymodbus.client import ModbusTcpClient

class GDSClient:
    BASE = 40001  # Modbus 주소 오프셋

    def __init__(self, host, port=502, unit_id=1):
        self.client = ModbusTcpClient(host, port=port)
        self.unit_id = unit_id
        if not self.client.connect():
            raise ConnectionError(f"Cannot connect to {host}:{port}")

    def _addr(self, reg):
        """40001 기준으로 실제 읽기/쓰기할 레지스터 오프셋 계산"""
        return reg - self.BASE

    def read_register(self, reg):
        rr = self.client.read_holding_registers(self._addr(reg), 1, unit=self.unit_id)
        return rr.registers[0]

    def write_register(self, reg, value):
        self.client.write_register(self._addr(reg), value, unit=self.unit_id)

    def write_registers(self, reg, values):
        self.client.write_registers(self._addr(reg), values, unit=self.unit_id)

    # 1) 읽기 기능
    def get_version(self):
        return self.read_register(40022)  # BIT0~15: 버전 정보 :contentReference[oaicite:7]{index=7}

    def get_upgrade_status(self):
        return self.read_register(40023)  # BIT 필드: 업그레이드/롤백 상태 :contentReference[oaicite:8]{index=8}

    def get_download_progress(self):
        val = self.read_register(40024)
        progress = val & 0xFF               # BIT0~7: 진행률(0~100) 
        remaining = (val >> 8) & 0xFF      # BIT8~15: 예상 남은 시간(초)
        return progress, remaining

    # 2) TFTP 서버 IP 설정
    def set_tftp_server(self, ip_addr: str):
        # IPv4 문자열 → 4바이트 → 2개의 16bit 값으로 분할
        packed = socket.inet_aton(ip_addr)
        hi, lo = struct.unpack('>HH', packed)
        self.write_registers(40088, [hi, lo])  # 40088,40089 :contentReference[oaicite:9]{index=9}

    # 3) 업그레이드/롤백/제로캘리/재부팅
    def start_upgrade(self):   self.write_register(40091, 1)  # BIT0~1=1: 시작 :contentReference[oaicite:10]{index=10}
    def cancel_upgrade(self):  self.write_register(40091, 0)  # 취소
    def rollback(self):        self.write_register(40091, 2)  # 롤백

    def zero_calibration(self):
        self.write_register(40092, 1)  # BIT0=1: 제로 캘리브레이션 :contentReference[oaicite:11]{index=11}

    def reboot(self):
        self.write_register(40093, 1)  # BIT0=1: 재부팅 :contentReference[oaicite:12]{index=12}

    def close(self):
        self.client.close()

# --------------------
# 사용 예시
# --------------------
if __name__ == "__main__":
    gds = GDSClient("192.168.0.15")
    print("Version:", gds.get_version())
    status = gds.get_upgrade_status()
    print("Upgrade Status:", bin(status))
    prog, remain = gds.get_download_progress()
    print(f"Download: {prog}% remaining {remain}s")

    # 설정 변경 예:
    # gds.set_tftp_server("109.3.55.2")
    # gds.start_upgrade()
    # gds.zero_calibration()
    # gds.reboot()

    gds.close()

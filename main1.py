#!/usr/bin/env python3
import socket
import struct
from pymodbus import __version__ as _pymodbus_version

# pymodbus v2.x/v3.x 호환을 위한 import
try:
    # pymodbus 2.x
    from pymodbus.client.sync import ModbusTcpClient
except (ImportError, ModuleNotFoundError):
    try:
        # pymodbus 3.x
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        # pymodbus 3.x alternate path
        from pymodbus.client.tcp import ModbusTcpClient

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
        rr = self.client.read_holding_registers(self._addr(reg), 1, slave=self.unit_id)
        if rr.isError():
            raise IOError(f"Read error at register {reg}")
        return rr.registers[0]

    def write_register(self, reg, value):
        wr = self.client.write_register(self._addr(reg), value, slave=self.unit_id)
        if wr.isError():
            raise IOError(f"Write error at register {reg}")

    def write_registers(self, reg, values):
        wr = self.client.write_registers(self._addr(reg), values, slave=self.unit_id)
        if wr.isError():
            raise IOError(f"Write error at registers starting {reg}")

    # 읽기 기능
    def get_version(self):
        """레지스터 40022 읽기: 펌웨어 버전"""
        return self.read_register(40022)

    def get_upgrade_status(self):
        """레지스터 40023 읽기: 업그레이드/롤백 상태 비트필드"""
        return self.read_register(40023)

    def get_download_progress(self):
        """레지스터 40024 읽기: 다운로드 진행률(하위 8비트) 및 남은 시간(상위 8비트)"""
        val = self.read_register(40024)
        progress = val & 0xFF
        remaining = (val >> 8) & 0xFF
        return progress, remaining

    # TFTP 서버 IP 설정 (40088–40089)
    def set_tftp_server(self, ip_addr: str):
        packed = socket.inet_aton(ip_addr)
        hi, lo = struct.unpack('>HH', packed)
        self.write_registers(40088, [hi, lo])

    # 업그레이드/롤백/취소 (40091)
    def start_upgrade(self):
        self.write_register(40091, 1)

    def cancel_upgrade(self):
        self.write_register(40091, 0)

    def rollback(self):
        self.write_register(40091, 2)

    # 제로 캘리브레이션 (40092)
    def zero_calibration(self):
        self.write_register(40092, 1)

    # 재부팅 (40093)
    def reboot(self):
        self.write_register(40093, 1)

    def close(self):
        self.client.close()


if __name__ == "__main__":
    # 사용 예시
    HOST = "192.168.0.15"    # 실제 GDS 장치 IP로 변경하세요
    UNIT_ID = 1              # Modbus 슬레이브 ID

    print("pymodbus version:", _pymodbus_version)
    gds = GDSClient(HOST, unit_id=UNIT_ID)

    try:
        ver = gds.get_version()
        print(f"Firmware Version (40022): {ver}")

        status = gds.get_upgrade_status()
        print(f"Upgrade Status  (40023): 0b{status:016b}")

        prog, rem = gds.get_download_progress()
        print(f"Download Progress (40024): {prog}% remaining {rem}s")

        # 예시: TFTP 서버 IP 설정
        # gds.set_tftp_server("109.3.55.2")

        # 예시: 업그레이드 시작
        # gds.start_upgrade()

        # 예시: 제로 캘리브레이션
        # gds.zero_calibration()

        # 예시: 재부팅
        # gds.reboot()

    finally:
        gds.close()

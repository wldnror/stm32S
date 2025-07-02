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
        """40001 기준으로 실제 레지스터 오프셋 계산"""
        return reg - self.BASE

    def read_register(self, reg):
        rr = self.client.read_holding_registers(
            address=self._addr(reg),
            count=1,
            slave=self.unit_id
        )
        if rr.isError():
            raise IOError(f"Read error at register {reg}")
        return rr.registers[0]

    def write_register(self, reg, value):
        wr = self.client.write_register(
            address=self._addr(reg),
            value=value,
            slave=self.unit_id
        )
        if wr.isError():
            raise IOError(f"Write error at register {reg}")

    def write_registers(self, reg, values):
        wr = self.client.write_registers(
            address=self._addr(reg),
            values=values,
            slave=self.unit_id
        )
        if wr.isError():
            raise IOError(f"Write error at registers starting {reg}")

    # === 읽기 기능 ===
    def get_version(self):
        """레지스터 40022: 펌웨어 버전"""
        return self.read_register(40022)

    def get_upgrade_status(self):
        """레지스터 40023: 업그레이드/롤백 상태"""
        return self.read_register(40023)

    def get_download_progress(self):
        """레지스터 40024: 진행률(하위 8비트) + 남은 시간(상위 8비트)"""
        val = self.read_register(40024)
        prog = val & 0xFF
        rem  = (val >> 8) & 0xFF
        return prog, rem

    # === TFTP 서버 IP 설정 (40088–40089) ===
    def set_tftp_server(self, ip_addr: str):
        packed = socket.inet_aton(ip_addr)
        hi, lo = struct.unpack('>HH', packed)
        self.write_registers(40088, [hi, lo])

    # === 업그레이드 / 취소 / 롤백 (40091) ===
    def start_upgrade(self):
        self.write_register(40091, 1)
    def cancel_upgrade(self):
        self.write_register(40091, 0)
    def rollback(self):
        self.write_register(40091, 2)

    # === 제로 캘리브레이션 (40092) ===
    def zero_calibration(self):
        self.write_register(40092, 1)

    # === 재부팅 (40093) ===
    def reboot(self):
        self.write_register(40093, 1)

    def close(self):
        self.client.close()


if __name__ == "__main__":
    HOST    = "192.168.0.15"  # GDS 장치 IP
    UNIT_ID = 1               # Modbus 슬레이브 ID

    print("pymodbus version:", _pymodbus_version)
    gds = GDSClient(HOST, unit_id=UNIT_ID)
    try:
        # 읽기 예시
        print("Firmware Version (40022):", gds.get_version())
        status = gds.get_upgrade_status()
        print("Upgrade Status  (40023): 0b{:016b}".format(status))
        prog, rem = gds.get_download_progress()
        print(f"Download Progress (40024): {prog}% remaining {rem}s")

        # 쓰기 예시
        # gds.set_tftp_server("109.3.55.2")
        # gds.start_upgrade()
        # gds.zero_calibration()
        # gds.reboot()

    finally:
        gds.close()

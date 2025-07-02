#!/usr/bin/env python3
import socket
import struct
import argparse
from pymodbus import __version__ as _pymodbus_version

# pymodbus v2.x/v3.x 호환 import
try:
    # pymodbus 2.x
    from pymodbus.client.sync import ModbusTcpClient
except (ImportError, ModuleNotFoundError):
    try:
        # pymodbus 3.x
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        # alternate path
        from pymodbus.client.tcp import ModbusTcpClient

class GDSClient:
    BASE = 40001  # Modbus 주소 오프셋

    def __init__(self, host, port=502, unit_id=1):
        # timeout=5초, 재시도 5회, 응답 없을 때 재시도
        self.client = ModbusTcpClient(
            host, port=port,
            timeout=5,
            retries=5,
            retry_on_empty=True
        )
        self.unit_id = unit_id
        if not self.client.connect():
            raise ConnectionError(f"Cannot connect to {host}:{port}")

    def _addr(self, reg):
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

    # === 읽기 메서드 ===
    def get_version(self):
        return self.read_register(40022)            # 펌웨어 버전

    def get_upgrade_status(self):
        return self.read_register(40023)            # 업그레이드/롤백 상태

    def get_download_progress(self):
        val = self.read_register(40024)
        return val & 0xFF, (val >> 8) & 0xFF        # (진행률, 남은시간)

    # === 쓰기 메서드 ===
    def set_tftp_server(self, ip):
        """
        TFTP 서버 IP 설정 (레지스터 40088–40089).
        Ubuntu 머신에서 TFTP 서버를 띄우셨다면, 이 머신의 IP를 지정하세요.
        예: "192.168.0.4" 또는 로컬호스트 "127.0.0.1"
        """
        packed = socket.inet_aton(ip)
        hi, lo = struct.unpack('>HH', packed)
        try:
            # multiple-register 쓰기 시도
            self.write_registers(40088, [hi, lo])
        except Exception:
            # 실패 시 단일 레지스터로 분할 쓰기
            print("!!! WriteMultipleRegisters 실패, 단일 레지스터로 재시도합니다.")
            self.write_register(40088, hi)
            self.write_register(40089, lo)

    def start_upgrade(self):    self.write_register(40091, 1)
    def cancel_upgrade(self):   self.write_register(40091, 0)
    def rollback(self):         self.write_register(40091, 2)
    def zero_calibration(self): self.write_register(40092, 1)
    def reboot(self):           self.write_register(40093, 1)

    def close(self):
        self.client.close()


def main():
    parser = argparse.ArgumentParser(description="GDS Modbus TCP CLI")
    parser.add_argument("host", help="GDS 장치 IP (예: 192.168.0.15)")
    parser.add_argument("--unit", type=int, default=1, help="Modbus 슬레이브 ID (기본: 1)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="펌웨어 버전 조회")
    sub.add_parser("status",  help="업그레이드 상태 조회")
    sub.add_parser("progress",help="다운로드 진행률 조회")

    tftp = sub.add_parser("set-tftp", help="TFTP 서버 IP 설정")
    tftp.add_argument("ip", help="설정할 TFTP 서버 IP (예: Ubuntu 머신 IP)")

    sub.add_parser("start",   help="업그레이드 시작")
    sub.add_parser("cancel",  help="업그레이드 취소")
    sub.add_parser("rollback",help="롤백 실행")
    sub.add_parser("zero",    help="제로 캘리브레이션")
    sub.add_parser("reboot",  help="장치 재부팅")

    args = parser.parse_args()

    print(f"pymodbus version: {_pymodbus_version}")
    client = GDSClient(args.host, unit_id=args.unit)

    try:
        if args.cmd == "version":
            print("Firmware Version:", client.get_version())

        elif args.cmd == "status":
            st = client.get_upgrade_status()
            print("Upgrade Status: 0b{:016b}".format(st))

        elif args.cmd == "progress":
            prog, rem = client.get_download_progress()
            print(f"Download Progress: {prog}% remaining {rem}s")

        elif args.cmd == "set-tftp":
            client.set_tftp_server(args.ip)
            print("TFTP 서버 IP 설정 완료:", args.ip)

        elif args.cmd == "start":
            client.start_upgrade()
            print("업그레이드 시작 명령 전송됨")

        elif args.cmd == "cancel":
            client.cancel_upgrade()
            print("업그레이드 취소 명령 전송됨")

        elif args.cmd == "rollback":
            client.rollback()
            print("롤백 명령 전송됨")

        elif args.cmd == "zero":
            client.zero_calibration()
            print("제로 캘리브레이션 명령 전송됨")

        elif args.cmd == "reboot":
            client.reboot()
            print("재부팅 명령 전송됨")

    finally:
        client.close()


if __name__ == "__main__":
    main()

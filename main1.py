#!/usr/bin/env python3
import socket
import struct
import argparse
from pymodbus import __version__ as _pymodbus_version

# pymodbus v2.x/v3.x 호환 import
try:
    from pymodbus.client.sync import ModbusTcpClient
except (ImportError, ModuleNotFoundError):
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from pymodbus.client.tcp import ModbusTcpClient

class GDSClient:
    BASE = 40001

    def __init__(self, host, port=502, unit_id=1):
        self.client = ModbusTcpClient(host, port=port)
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
        return self.read_register(40022)

    def get_upgrade_status(self):
        return self.read_register(40023)

    def get_download_progress(self):
        val = self.read_register(40024)
        return val & 0xFF, (val >> 8) & 0xFF

    # === 쓰기 메서드 ===
    def set_tftp_server(self, ip):
        packed = socket.inet_aton(ip)
        hi, lo = struct.unpack('>HH', packed)
        self.write_registers(40088, [hi, lo])

    def start_upgrade(self):   self.write_register(40091, 1)
    def cancel_upgrade(self):  self.write_register(40091, 0)
    def rollback(self):        self.write_register(40091, 2)
    def zero_calibration(self):self.write_register(40092, 1)
    def reboot(self):          self.write_register(40093, 1)

    def close(self):
        self.client.close()


def main():
    p = argparse.ArgumentParser(description="GDS Modbus TCP 간편 CLI")
    p.add_argument("host", help="GDS 장치 IP")
    p.add_argument("--unit",   type=int, default=1, help="Modbus 슬레이브 ID (기본: 1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="펌웨어 버전 읽기")
    sub.add_parser("status",  help="업그레이드 상태 읽기")
    sub.add_parser("progress",help="다운로드 진행률 읽기")

    tftp = sub.add_parser("set-tftp", help="TFTP 서버 IP 설정")
    tftp.add_argument("ip", help="설정할 IP 주소")

    sub.add_parser("start",  help="업그레이드 시작")
    sub.add_parser("cancel", help="업그레이드 취소")
    sub.add_parser("rollback",help="롤백 실행")
    sub.add_parser("zero",   help="제로 캘리브레이션")
    sub.add_parser("reboot", help="장치 재부팅")

    args = p.parse_args()

    print(f"pymodbus version: {_pymodbus_version}")
    g = GDSClient(args.host, unit_id=args.unit)

    try:
        if args.cmd == "version":
            print("Firmware Version:", g.get_version())

        elif args.cmd == "status":
            st = g.get_upgrade_status()
            print("Upgrade Status: 0b{:016b}".format(st))

        elif args.cmd == "progress":
            prog, rem = g.get_download_progress()
            print(f"Download: {prog}%  Remaining: {rem}s")

        elif args.cmd == "set-tftp":
            g.set_tftp_server(args.ip)
            print("TFTP 서버 IP 설정 완료:", args.ip)

        elif args.cmd == "start":
            g.start_upgrade();  print("업그레이드 명령 전송됨")

        elif args.cmd == "cancel":
            g.cancel_upgrade(); print("업그레이드 취소 명령 전송됨")

        elif args.cmd == "rollback":
            g.rollback();       print("롤백 명령 전송됨")

        elif args.cmd == "zero":
            g.zero_calibration(); print("제로 캘리브레이션 명령 전송됨")

        elif args.cmd == "reboot":
            g.reboot();         print("재부팅 명령 전송됨")

    finally:
        g.close()

if __name__ == "__main__":
    main()

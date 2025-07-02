#!/usr/bin/env python3
import socket, struct
from pymodbus.client.sync import ModbusTcpClient

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
        rr = self.client.read_holding_registers(self._addr(reg), 1, slave=self.unit_id)
        if rr.isError():
            raise IOError(f"Read error at {reg}")
        return rr.registers[0]

    def write_register(self, reg, value):
        wr = self.client.write_register(self._addr(reg), value, slave=self.unit_id)
        if wr.isError():
            raise IOError(f"Write error at {reg}")

    def write_registers(self, reg, values):
        wr = self.client.write_registers(self._addr(reg), values, slave=self.unit_id)
        if wr.isError():
            raise IOError(f"Write error at {reg}")

    # ======== 주요 메서드 ========

    def get_version(self):
        return self.read_register(40022)

    def get_upgrade_status(self):
        return self.read_register(40023)

    def get_download_progress(self):
        val = self.read_register(40024)
        prog = val & 0xFF
        rem  = (val >> 8) & 0xFF
        return prog, rem

    def set_tftp_server(self, ip_addr: str):
        packed = socket.inet_aton(ip_addr)
        hi, lo = struct.unpack('>HH', packed)
        self.write_registers(40088, [hi, lo])

    def start_upgrade(self):   self.write_register(40091, 1)
    def cancel_upgrade(self):  self.write_register(40091, 0)
    def rollback(self):        self.write_register(40091, 2)

    def zero_calibration(self):
        self.write_register(40092, 1)

    def reboot(self):
        self.write_register(40093, 1)

    def close(self):
        self.client.close()


if __name__ == "__main__":
    gds = GDSClient("192.168.0.15")
    print("Version:", gds.get_version())
    print("Upgrade Status:", bin(gds.get_upgrade_status()))
    prog, rem = gds.get_download_progress()
    print(f"Download: {prog}% remaining {rem}s")
    gds.close()

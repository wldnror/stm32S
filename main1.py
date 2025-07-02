#!/usr/bin/env python3
"""
GDS Modbus TCP Test Utility

This script allows you to test the GDS device's Modbus TCP registers
as defined in 'GDS Modbus TCP Address Map - 20250701.pdf'. 

Usage examples:
  # Read version info
  python3 test_modbus_gds.py --host 192.168.0.100 read-version

  # Read upgrade status bits
  python3 test_modbus_gds.py --host 192.168.0.100 read-status

  # Read download progress
  python3 test_modbus_gds.py --host 192.168.0.100 read-progress

  # Set TFTP server IP to 109.3.55.2
  python3 test_modbus_gds.py --host 192.168.0.100 set-tftp --ip 109.3.55.2

  # Start upgrade
  python3 test_modbus_gds.py --host 192.168.0.100 command --action upgrade

  # Rollback
  python3 test_modbus_gds.py --host 192.168.0.100 command --action rollback

  # Zero calibration
  python3 test_modbus_gds.py --host 192.168.0.100 zero-cal

  # Reboot
  python3 test_modbus_gds.py --host 192.168.0.100 reboot
"""

import argparse
import ipaddress
from pymodbus.client.sync import ModbusTcpClient

# Register addresses (40001-based)
REG_VERSION            = 40022  # ファームウェア 버전
REG_UPGRADE_STATUS     = 40023  # 업그레이드 상태
REG_DOWNLOAD_PROGRESS  = 40024  # 진행률 및 남은 시간
REG_TFTP_IP1           = 40088
REG_TFTP_IP2           = 40089
REG_COMMAND            = 40091
REG_ZERO_CAL           = 40092
REG_REBOOT             = 40093

UNIT_ID = 1
PORT = 502

def read_holding(client, reg, count=1):
    address = reg - 40001  # zero-based offset
    rr = client.read_holding_registers(address, count, unit=UNIT_ID)
    if rr.isError():
        raise Exception(f"Error reading register {reg}: {rr}")
    return rr.registers

def write_single(client, reg, value):
    address = reg - 40001
    rr = client.write_register(address, value, unit=UNIT_ID)
    if rr.isError():
        raise Exception(f"Error writing register {reg}: {rr}")
    return rr

def write_multiple(client, reg, values):
    address = reg - 40001
    rr = client.write_registers(address, values, unit=UNIT_ID)
    if rr.isError():
        raise Exception(f"Error writing registers starting at {reg}: {rr}")
    return rr

def parse_status(bits):
    return {
        'upgrade_success':  bool(bits & (1 << 0)),
        'upgrade_fail':     bool(bits & (1 << 1)),
        'upgrading':        bool(bits & (1 << 2)),
        'rollback_success': bool(bits & (1 << 4)),
        'rollback_fail':    bool(bits & (1 << 5)),
        'rollbacking':      bool(bits & (1 << 6)),
        'error_code':       (bits >> 8) & 0xFF,
    }

def cmd_read_version(client):
    regs = read_holding(client, REG_VERSION)
    print(f"Firmware version: {regs[0]}")

def cmd_read_status(client):
    regs = read_holding(client, REG_UPGRADE_STATUS)
    status = parse_status(regs[0])
    print("Upgrade / Rollback Status:")
    for k, v in status.items():
        print(f"  {k}: {v}")

def cmd_read_progress(client):
    regs = read_holding(client, REG_DOWNLOAD_PROGRESS)
    prog = regs[0]
    percent = prog & 0xFF
    time_left = (prog >> 8) & 0xFF
    print(f"Download Progress: {percent}%")
    print(f"Estimated time left: {time_left} seconds")

def cmd_set_tftp(client, ip_str):
    ip = ipaddress.ip_address(ip_str)
    high = (int(ip) >> 16) & 0xFFFF
    low = int(ip) & 0xFFFF
    write_multiple(client, REG_TFTP_IP1, [high, low])
    print(f"TFTP server IP set to {ip_str}")

def cmd_command(client, action):
    actions = {'cancel': 0, 'upgrade': 1, 'rollback': 2}
    if action not in actions:
        raise ValueError("Invalid action. Choose from cancel, upgrade, rollback.")
    write_single(client, REG_COMMAND, actions[action])
    print(f"Command '{action}' sent.")

def cmd_zero_cal(client):
    write_single(client, REG_ZERO_CAL, 1)
    print("Zero calibration triggered.")

def cmd_reboot(client):
    write_single(client, REG_REBOOT, 1)
    print("Reboot command sent.")

def main():
    parser = argparse.ArgumentParser(description="GDS Modbus TCP Test Utility")
    parser.add_argument('--host', required=True, help="Device IP address")
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('read-version')
    sub.add_parser('read-status')
    sub.add_parser('read-progress')

    p = sub.add_parser('set-tftp')
    p.add_argument('--ip', required=True, help="TFTP server IP")

    p2 = sub.add_parser('command')
    p2.add_argument('--action', required=True, choices=['cancel','upgrade','rollback'])

    sub.add_parser('zero-cal')
    sub.add_parser('reboot')

    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=PORT)
    if not client.connect():
        print(f"Unable to connect to {args.host}:{PORT}")
        return

    try:
        if args.cmd == 'read-version':
            cmd_read_version(client)
        elif args.cmd == 'read-status':
            cmd_read_status(client)
        elif args.cmd == 'read-progress':
            cmd_read_progress(client)
        elif args.cmd == 'set-tftp':
            cmd_set_tftp(client, args.ip)
        elif args.cmd == 'command':
            cmd_command(client, args.action)
        elif args.cmd == 'zero-cal':
            cmd_zero_cal(client)
        elif args.cmd == 'reboot':
            cmd_reboot(client)
    finally:
        client.close()

if __name__ == "__main__":
    main()

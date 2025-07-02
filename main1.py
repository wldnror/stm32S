     from pymodbus.server.sync import ModbusTcpServer
     from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
     from threading import Thread

     class SimpleModbusTcpServer:
         def __init__(self, host='0.0.0.0', port=502):
             self.host = host
             self.port = port
             self.context = None
             self.server = None
             self.thread = None

         def start(self):
             # 데이터 저장소 초기화
             store = ModbusSlaveContext(
                 di=ModbusSequentialDataBlock(0, [17] * 100),
                 co=ModbusSequentialDataBlock(0, [17] * 100),
                 hr=ModbusSequentialDataBlock(0, [17] * 100),
                 ir=ModbusSequentialDataBlock(0, [17] * 100)
             )
             self.context = ModbusServerContext(slaves=store, single=True)

             # 서버 시작
             self.server = ModbusTcpServer(self.context, address=(self.host, self.port))
             self.thread = Thread(target=self.server.serve_forever)
             self.thread.start()
             print(f"Modbus TCP server listening on {self.host}:{self.port}")

         def stop(self):
             if self.server:
                 self.server.shutdown()
                 self.thread.join()
                 print("Modbus TCP server stopped.")

     if __name__ == "__main__":
         server = SimpleModbusTcpServer()
         try:
             server.start()
             # 서버 실행 유지 (예: 10초 동안)
             import time
             time.sleep(10)
         except KeyboardInterrupt:
             print("Exiting...")
         finally:
             server.stop()

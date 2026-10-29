import socket
import struct
import time

MSG_LOGIN = 2
MSG_PING = 6
MSG_HARDWARE = 20
MSG_OK = 200

class Blynk:
    def __init__(self, auth, server="blynk.cloud", port=80):
        self.auth = auth
        self.server = server
        self.port = port
        self.callbacks = {}
        self.conn = None
        self.msg_id = 1
        self.connect()

    def connect(self):
        print("Đang kết nối tới Blynk server...")
        try:
            addr = socket.getaddrinfo(self.server, self.port)[0][-1]
            self.conn = socket.socket()
            self.conn.connect(addr)
            self.conn.settimeout(0.05)
            self.send(MSG_LOGIN, self.auth)
            time.sleep(0.5)
            print("Kết nối Blynk thành công!")
        except Exception as e:
            print("Lỗi kết nối Blynk:", e)

    def send(self, cmd, body):
        self.msg_id += 1
        if self.msg_id > 0xFFFF:
            self.msg_id = 1
        data = struct.pack("!BHH", cmd, self.msg_id, len(body)) + body.encode()
        self.conn.send(data)

    def on(self, pin):
        def decorator(func):
            self.callbacks[pin] = func
            return func
        return decorator

    def run(self):
        try:
            data = self.conn.recv(1024)
            if data:
                msg = data.decode('utf-8', 'ignore')
                for pin_name, func in self.callbacks.items():
                    if pin_name in msg:
                        # Extract value if present
                        parts = msg.split(pin_name)
                        if len(parts) > 1:
                            val = parts[1].split('\x00')[0].strip()
                            if val:
                                func([val])
        except:
            pass

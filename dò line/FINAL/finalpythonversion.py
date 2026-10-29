"""Xe dò line ESP32 dùng MicroPython và điều khiển qua Blynk Cloud.
Sửa wifiName, wifiPassword và blynkToken trước khi nạp vào ESP32.
Tên biến và hàm viết bằng tiếng Anh; phần giải thích viết bằng tiếng Việt.
"""
import time
import socket
import struct
import network
from machine import Pin, PWM, time_pulse_us

# ===== 1. THÔNG TIN WIFI VÀ BLYNK: SỬA Ở ĐÂY =====
wifiName = "YourWifiName"
wifiPassword = "YourWifiPassword"
blynkToken = "YourNewBlynkToken"
blynkTemplateId = "TMPL6flcgKxLQ"
blynkHost = "blynk.cloud"
blynkPort = 80  # Giữ cổng 80 như chương trình Arduino gốc

# ===== 2. KẾT NỐI CHÂN: GIỮ NGUYÊN SỐ CHÂN CỦA XE =====
in1, in2 = Pin(27, Pin.OUT), Pin(26, Pin.OUT)
in3, in4 = Pin(25, Pin.OUT), Pin(33, Pin.OUT)
ena = PWM(Pin(14), freq=1000)
enb = PWM(Pin(32), freq=1000)
lineSensors = [Pin(pinNumber, Pin.IN) for pinNumber in (18, 19, 21, 22, 23)]
trigPin = Pin(4, Pin.OUT, value=0)
echoPin = Pin(13, Pin.IN)
buzzer = Pin(15, Pin.OUT, value=0)
led1 = Pin(2, Pin.OUT, value=0)
led2 = Pin(5, Pin.OUT, value=0)

lineActive = 0
weights = (-2.0, -1.0, 0.0, 1.0, 2.0)
kp, ki, kd = 150.0, 0.0, 1.8
baseSpeed, maxSpeed, pidInterval = 380, 800, 20
manualSpeed, manualTurnSpeed = 750, 900
lostSpinSpeed = 500
turnSpeed, junctionForwardMs = 380, 110
turn90Ms, turn180Ms, turnTimeoutMs = 350, 750, 1400
junctionLockMs, junctionConfirm = 300, 3
obstacleDistance, obstacleConfirm, sonarInterval = 13, 2, 80
avoidSpeed = 450
avoidBackwardMs, avoidTurn90Ms = 300, 650
avoidSideMs, avoidParallelMs, avoidReturnMs = 800, 400, 700
# Hai tham số tìm vạch khai báo trong code gốc nhưng chưa được sử dụng.

robotMode = 0  # 0 = dừng; 1 = tự động; 2 = điều khiển tay
currentStatus = "Dung"
currentDistance = -1.0
lineLost = False
obstacleAlert = False
lastError, integral, lastDirection = 0.0, 0.0, 1
lastPidTime = time.ticks_ms()
lastSonarTime = lastPidTime
lastJunctionTime = lastPidTime
obstacleSamples = 0
manualDirection = 0  # Mỗi lúc chỉ chạy một hướng
manualObstacleSamples = 0
lastTelemetry = lastPidTime
lastSentStatus = ""


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def setPwmSpeed(left, right):
    # Giữ thang tốc độ 0..1023; PWM MicroPython dùng 0..65535.
    ena.duty_u16(int(clamp(left, 0, 1023) * 65535 // 1023))
    enb.duty_u16(int(clamp(right, 0, 1023) * 65535 // 1023))


def stopMotors():
    in1.off()
    in2.off()
    in3.off()
    in4.off()
    setPwmSpeed(0, 0)


def drive(left, right, leftSpeed, rightSpeed):
    in1.value(left > 0)
    in2.value(left < 0)
    in3.value(right > 0)
    in4.value(right < 0)
    setPwmSpeed(leftSpeed, rightSpeed)


def forward(speed):
    drive(1, 1, speed, speed)


def backward(speed):
    drive(-1, -1, speed, speed)


def spinLeft(speed):
    drive(-1, 1, speed, speed)


def spinRight(speed):
    drive(1, -1, speed, speed)


def moveMotorsPid(leftMotorSpeed, rightMotorSpeed):
    drive(1 if leftMotorSpeed >= 0 else -1,
          1 if rightMotorSpeed >= 0 else -1,
          abs(leftMotorSpeed), abs(rightMotorSpeed))


def brakeMotors(durationMs=60):
    # Phanh L298N: cho hai chân cùng mức cao, sau đó dừng động cơ.
    in1.on()
    in2.on()
    in3.on()
    in4.on()
    setPwmSpeed(1023, 1023)
    if durationMs:
        waitAndService(durationMs)
    stopMotors()


def setAlert(state):
    buzzer.value(state)
    led1.value(state)
    led2.value(state)


def blinkAlert(blinkPeriodMs=100):
    setAlert((time.ticks_ms() // blinkPeriodMs) % 2 == 0)


def readLine():
    return [int(pin.value() == lineActive) for pin in lineSensors]


def getDistanceCm():
    trigPin.off()
    time.sleep_us(2)
    trigPin.on()
    time.sleep_us(10)
    trigPin.off()
    pulseWidth = time_pulse_us(echoPin, 1, 3000)
    return pulseWidth / 58.0 if pulseWidth > 0 else -1.0


def resetPid():
    global lastError, integral
    lastError = 0.0
    integral = 0.0


def followPid(sensorValues):
    global lastError, integral, lastDirection
    activeCount = sum(sensorValues)
    if not activeCount:
        return False
    # Vạch lệch sang bên nào thì sai số mang dấu theo bên đó.
    error = sum(weights[index] for index in range(5) if sensorValues[index]) / activeCount
    if error > 0.15:
        lastDirection = 1
    elif error < -0.15:
        lastDirection = -1
    sampleTime = pidInterval / 1000.0
    integral = clamp(integral + error * sampleTime, -2.0, 2.0)
    # PID điều chỉnh tốc độ hai bánh để xe quay về giữa vạch.
    correction = kp * error + ki * integral + kd * (error - lastError) / sampleTime
    lastError = error
    left = int(clamp(baseSpeed + correction, -maxSpeed, maxSpeed))
    right = int(clamp(baseSpeed - correction, -maxSpeed, maxSpeed))
    moveMotorsPid(left, right)
    return True


# ===== 3. GIAO TIẾP BLYNK =====
# Phần này thay thư viện Arduino BlynkSimpleEsp32.h.
# Chỉ cần sửa thông tin kết nối ở mục 1; không cần sửa mã giao thức.
class BlynkClient:
    responseCode, pingCode, syncCode, internalCode, hardwareCode, loginCode, redirectCode = 0, 6, 16, 17, 20, 29, 41

    def __init__(self, host, port, token, callback):
        self.host, self.port = host, port
        self.token, self.callback = token, callback
        self.sock = None
        self.online = False
        self.receivedData = b""
        self.messageCounter = 0
        self.loginId = 0
        self.lastReceived = time.ticks_ms()
        self.lastSent = self.lastReceived
        self.lastAttempt = time.ticks_add(self.lastReceived, -3000)
        self.redirectCount = 0

    def disconnect(self):
        wasOnline = self.online
        self.online = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.receivedData = b""
        if wasOnline:
            emergencyStop()  # Mất kết nối thì dừng xe

    def sendPacket(self, command, body=b"", messageId=None, statusCode=None):
        if self.sock is None:
            return
        if messageId is None:
            self.messageCounter = self.messageCounter % 65535 + 1
            messageId = self.messageCounter
        header = struct.pack("!BHH", command, messageId,
                             statusCode if command == self.responseCode else len(body))
        try:
            packet = header + body
            index = 0
            while index < len(packet):
                bytesSent = self.sock.send(packet[index:])
                if not bytesSent:
                    raise OSError("socket send returned zero")
                index += bytesSent
            self.lastSent = time.ticks_ms()
        except OSError:
            self.disconnect()
        return messageId

    def connectServer(self):
        self.lastAttempt = time.ticks_ms()
        self.disconnect()
        try:
            address = socket.getaddrinfo(self.host, self.port)[0][-1]
            newSocket = socket.socket()
            newSocket.settimeout(3)
            newSocket.connect(address)
            newSocket.setblocking(False)
            self.sock = newSocket
            self.loginId = self.sendPacket(self.loginCode, self.token.encode())
            self.lastReceived = time.ticks_ms()
            print("Blynk: TCP connected, authenticating")
        except OSError as exc:
            print("Blynk connection error:", exc)
            self.disconnect()

    def virtualWrite(self, pin, value):
        if self.online:
            self.sendPacket(self.hardwareCode, b"vw\0" + str(pin).encode() + b"\0" + str(value).encode())

    def syncVirtual(self, pin):
        if self.online:
            self.sendPacket(self.syncCode, b"vr\0" + str(pin).encode())

    def poll(self):
        if self.sock is None:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.lastReceived) > 15000:
            print("Blynk: timed out")
            self.disconnect()
            return
        if self.online and time.ticks_diff(now, self.lastSent) >= 10000:
            self.sendPacket(self.pingCode)
        try:
            chunk = self.sock.recv(512)
            if not chunk:
                self.disconnect()
                return
            self.receivedData += chunk
        except OSError as exc:
            # Các mã này báo chưa có dữ liệu mới trên socket.
            if exc.args and exc.args[0] not in (11, 35, 110, 115):
                print("Blynk receive error:", exc)
                self.disconnect()
            return
        self.lastReceived = time.ticks_ms()
        while len(self.receivedData) >= 5:
            command, messageId, length = struct.unpack("!BHH", self.receivedData[:5])
            if messageId == 0 or (command != self.responseCode and length > 1024):
                self.disconnect()
                return
            endIndex = 5 if command == self.responseCode else 5 + length
            if len(self.receivedData) < endIndex:
                break
            body = self.receivedData[5:endIndex]
            self.receivedData = self.receivedData[endIndex:]
            if command == self.responseCode:
                if messageId == self.loginId and not self.online:
                    if length != 200:
                        print("Blynk login rejected, status:", length)
                        self.disconnect()
                        return
                    self.online = True
                    # Gửi thông tin thiết bị, rồi đồng bộ lại chế độ V0.
                    deviceInfo = ("ver", "py-1.0", "h-beat", "10", "buff-in", "1024",
                            "dev", "esp32-micropython", "tmpl", blynkTemplateId,
                            "fw-type", blynkTemplateId, "fw", "1.0")
                    self.sendPacket(self.internalCode, "\0".join(deviceInfo).encode())
                    self.syncVirtual(0)
                    print("Blynk: online")
            elif command == self.pingCode:
                self.sendPacket(self.responseCode, messageId=messageId, statusCode=200)
            elif command in (self.hardwareCode, self.syncCode):
                parts = body.split(b"\0")
                if len(parts) >= 3 and parts[0] == b"vw":
                    try:
                        self.callback(int(parts[1]), parts[2].decode())
                    except (ValueError, UnicodeError):
                        pass
            elif command == self.redirectCode:
                try:
                    host, port = body.decode().split("\0")[:2]
                    if host and int(port) == 80 and self.redirectCount < 3:
                        print("Blynk: following server redirect")
                        self.host, self.port = host, 80
                        self.redirectCount += 1
                        self.disconnect()
                        # Thử kết nối lại sau vài giây.
                        return
                except (ValueError, UnicodeError):
                    pass
                print("Blynk: unsupported redirect")
                self.disconnect()
                return


wlan = network.WLAN(network.STA_IF)
wlan.active(True)
blynk = BlynkClient(blynkHost, blynkPort, blynkToken, None)
lastWifiAttempt = time.ticks_add(time.ticks_ms(), -5000)


# ===== 4. ĐIỀU KHIỂN TỪ ĐIỆN THOẠI =====
def emergencyStop():
    global robotMode, lineLost, obstacleAlert, manualDirection
    robotMode = 0
    lineLost = False
    obstacleAlert = False
    manualDirection = 0
    stopMotors()
    setAlert(False)


def applyManual():
    if robotMode != 2:
        return
    if manualDirection == 1:
        forward(manualSpeed)
    elif manualDirection == 7:
        backward(manualSpeed)
    elif manualDirection == 8:
        spinLeft(manualTurnSpeed)
    elif manualDirection == 9:
        spinRight(manualTurnSpeed)
    else:
        stopMotors()


def onVirtual(pin, rawValue):
    global robotMode, lineLost, obstacleAlert
    global manualDirection, baseSpeed, kp, currentStatus
    try:
        if pin == 0:
            mode = int(rawValue)
            if mode not in (0, 1, 2):
                return
            if mode == 0:
                emergencyStop()
            else:
                stopMotors()
                robotMode = mode
                manualDirection = 0
                lineLost = False
                obstacleAlert = False
                setAlert(False)
                resetPid()
        elif pin in (1, 7, 8, 9):
            state = int(rawValue)
            if state == 1:
                robotMode = 2
                manualDirection = pin
                obstacleAlert = False
                applyManual()
            elif manualDirection == pin:
                manualDirection = 0
                stopMotors()
        elif pin == 2 and int(rawValue) == 1:
            emergencyStop()
            blynk.virtualWrite(0, 0)
            currentStatus = "Dung"
        elif pin == 5:
            baseSpeed = int(clamp(int(rawValue), 0, maxSpeed))
        elif pin == 6:
            kp = float(clamp(float(rawValue), 0, 1000))
    except ValueError:
        pass


blynk.callback = onVirtual


def serviceNetwork():
    """Nhận lệnh Blynk và thử kết nối lại khi xe đang dừng."""
    global lastWifiAttempt, lastTelemetry, lastSentStatus
    now = time.ticks_ms()
    if not wlan.isconnected():
        if blynk.sock is not None:
            blynk.disconnect()
        if robotMode != 0:
            emergencyStop()
        if time.ticks_diff(now, lastWifiAttempt) >= 5000:
            lastWifiAttempt = now
            wlan.connect(wifiName, wifiPassword)
        return
    if blynk.sock is None:
        if robotMode == 0 and time.ticks_diff(now, blynk.lastAttempt) >= 3000:
            blynk.connectServer()
        return
    blynk.poll()
    now = time.ticks_ms()
    if blynk.online and time.ticks_diff(now, lastTelemetry) >= 300:
        lastTelemetry = now
        if currentDistance >= 0:
            blynk.virtualWrite(4, int(currentDistance))
        if currentStatus != lastSentStatus:
            blynk.virtualWrite(3, currentStatus)
            lastSentStatus = currentStatus


def waitAndService(durationMs, alert=False, requiredMode=None):
    """Trong lúc chờ vẫn đọc Blynk để nút dừng khẩn cấp hoạt động."""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < durationMs:
        serviceNetwork()
        if requiredMode is not None and robotMode != requiredMode:
            stopMotors()
            return False
        if alert:
            blinkAlert()
        time.sleep_ms(5)
    return True


def autoWait(durationMs, alert=False):
    return waitAndService(durationMs, alert, requiredMode=1)


def autoBrake(durationMs):
    in1.on()
    in2.on()
    in3.on()
    in4.on()
    setPwmSpeed(1023, 1023)
    ok = autoWait(durationMs, obstacleAlert)
    stopMotors()
    return ok


# ===== 5. DÒ LINE, GIAO LỘ VÀ NÉ VẬT CẢN =====
def rotateToLine(direction, targetMs):
    start = time.ticks_ms()
    stableCount = 0
    minimumTime = int(targetMs * 0.75)
    while time.ticks_diff(time.ticks_ms(), start) < turnTimeoutMs:
        if robotMode != 1:
            stopMotors()
            return False
        if direction == -1:
            spinLeft(turnSpeed)
        else:
            spinRight(turnSpeed)
        if time.ticks_diff(time.ticks_ms(), start) >= minimumTime:
            stableCount = stableCount + 1 if readLine()[2] else 0
            if stableCount >= 3:
                if not autoBrake(40):
                    return False
                resetPid()
                return True
        if not autoWait(10):
            return False
    autoBrake(40)
    return False


def handleJunction(leftSeen, rightSeen):
    global currentStatus
    currentStatus = "Giao lo"
    forward(baseSpeed)
    if not autoWait(junctionForwardMs):
        return False
    stopMotors()
    straightExists = bool(readLine()[2])
    if leftSeen:
        currentStatus = "Re trai"
        return rotateToLine(-1, turn90Ms)
    if straightExists:
        currentStatus = "Di thang"
        resetPid()
        return True
    if rightSeen:
        currentStatus = "Re phai"
        return rotateToLine(1, turn90Ms)
    currentStatus = "Duong cut"
    return rotateToLine(1, turn180Ms)


def avoidObstacle():
    global currentStatus, obstacleAlert, lastDirection
    currentStatus = "Ne vat can"
    obstacleAlert = True
    if not autoBrake(70):
        return False
    if not autoWait(50, True):
        return False
    # Lùi, rẽ phải, đi sang bên, vượt vật cản rồi quay về vạch.
    avoidSteps = (
        (backward, avoidBackwardMs, 40),
        (spinRight, avoidTurn90Ms, 30),
        (forward, avoidSideMs, 30),
        (spinLeft, avoidTurn90Ms, 30),
        (forward, avoidParallelMs, 30),
        (spinLeft, avoidReturnMs, 50),
    )
    for motion, duration, pause in avoidSteps:
        motion(avoidSpeed)
        if not autoWait(duration, True):
            return False
        if not autoBrake(30):
            return False
        if not autoWait(pause, True):
            return False

    # Tìm vạch bằng ba mắt trái/giữa; cần thấy ba lần liên tiếp.
    start = time.ticks_ms()
    foundLine = False
    confirmed = 0
    while time.ticks_diff(time.ticks_ms(), start) < 4500:
        if robotMode != 1:
            stopMotors()
            return False
        forward(avoidSpeed)
        blinkAlert()
        sensorValues = readLine()
        confirmed = confirmed + 1 if any(sensorValues[:3]) else 0
        if confirmed >= 3:
            creepStart = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), creepStart) < 140:
                if robotMode != 1:
                    stopMotors()
                    return False
                forward(avoidSpeed)
                if readLine()[2]:
                    break
                if not autoWait(5, True):
                    return False
            foundLine = True
            break
        if not autoWait(10, True):
            return False
    if not autoBrake(40):
        return False
    if not autoWait(30, True):
        return False

    # Chỉnh hướng xe; nếu mất vạch thì dừng quay.
    if foundLine:
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 350:
            if robotMode != 1:
                stopMotors()
                return False
            blinkAlert()
            lineValues = readLine()
            if (sum(lineValues) == 0 or
                    (lineValues[2] and not lineValues[0]) or
                    lineValues[3] or lineValues[4]):
                break
            spinRight(avoidSpeed)
            if not autoWait(10, True):
                return False
        if not autoBrake(40):
            return False
        resetPid()
        lastDirection = 1
        currentStatus = "Bam line"
        obstacleAlert = False
        setAlert(False)
        return True
    return False


# ===== 6. VÒNG LẶP CHÍNH =====
def main():
    global currentStatus, currentDistance, obstacleSamples
    global lastSonarTime, lastPidTime, lastJunctionTime
    global lineLost, obstacleAlert, manualObstacleSamples
    stopMotors()
    setAlert(False)
    buzzer.on()
    time.sleep_ms(150)
    buzzer.off()
    print("Đang khởi động. Wi-Fi và Blynk sẽ kết nối khi xe dừng.")
    while True:
        serviceNetwork()
        now = time.ticks_ms()
        if robotMode == 0:
            currentStatus = "Dung"
            setAlert(False)
            time.sleep_ms(20)
            continue
        if robotMode == 2:
            currentStatus = "Dieu khien tay"
            # Khi điều khiển tay, vẫn đọc siêu âm để báo vật cản.
            if time.ticks_diff(now, lastSonarTime) >= sonarInterval:
                lastSonarTime = now
                currentDistance = getDistanceCm()
                manualObstacleSamples = (manualObstacleSamples + 1 if
                    0 < currentDistance <= obstacleDistance else 0)
            if manualObstacleSamples >= obstacleConfirm:
                blinkAlert()
                currentStatus = "Canh bao vat can"
            else:
                buzzer.off()
                led1.on()
                led2.off()
            time.sleep_ms(10)
            continue
        # Tự động: kiểm tra vật cản trước khi bám vạch bằng PID.
        if time.ticks_diff(now, lastSonarTime) >= sonarInterval:
            lastSonarTime = now
            currentDistance = getDistanceCm()
            obstacleSamples = obstacleSamples + 1 if 0 < currentDistance <= obstacleDistance else 0
            if obstacleSamples >= obstacleConfirm:
                obstacleSamples = 0
                success = avoidObstacle()
                if robotMode == 1 and not success:
                    lineLost = True
                    currentStatus = "Xoay tim line..."
                lastPidTime = time.ticks_ms()
                lastJunctionTime = lastPidTime
                continue
        if time.ticks_diff(now, lastPidTime) < pidInterval:
            time.sleep_ms(1)
            continue
        lastPidTime = now
        sensorValues = readLine()
        if sum(sensorValues) == 0:
            currentStatus = "Xoay tim line..."
            lineLost = True
            if obstacleAlert:
                blinkAlert()
            else:
                led1.value((time.ticks_ms() // 200) % 2)
            if lastDirection == -1:
                spinLeft(lostSpinSpeed)
            else:
                spinRight(lostSpinSpeed)
            lastPidTime = time.ticks_ms()
            continue
        if obstacleAlert:
            obstacleAlert = False
            setAlert(False)
        if lineLost:
            lineLost = False
            if not autoBrake(30):
                continue
            resetPid()
            led1.off()
            currentStatus = "Bam line"
        leftBranch = bool(sensorValues[0] and sensorValues[1])
        rightBranch = bool(sensorValues[3] and sensorValues[4])
        if (time.ticks_diff(now, lastJunctionTime) > junctionLockMs
                and (leftBranch or rightBranch)):
            confirmed = 0
            for _ in range(junctionConfirm):
                sample = readLine()
                if (sample[0] and sample[1]) or (sample[3] and sample[4]):
                    confirmed += 1
                if not autoWait(5):
                    break
            if robotMode != 1:
                continue
            if confirmed >= 2:
                success = handleJunction(leftBranch, rightBranch)
                lastJunctionTime = time.ticks_ms()
                lastPidTime = lastJunctionTime
                if robotMode == 1 and not success:
                    lineLost = True
                    currentStatus = "Xoay tim line..."
                continue
        buzzer.off()
        led1.off()
        led2.off()
        currentStatus = "Bam line"
        followPid(sensorValues)


try:
    main()
except KeyboardInterrupt:
    emergencyStop()
    blynk.disconnect()
    raise
except Exception:
    emergencyStop()
    blynk.disconnect()
    raise


from machine import Pin, PWM
import time


IN1 = Pin(27, Pin.OUT)
IN2 = Pin(26, Pin.OUT)
IN3 = Pin(25, Pin.OUT)
IN4 = Pin(33, Pin.OUT)

ENA = PWM(Pin(14), freq=1000)
ENB = PWM(Pin(32), freq=1000)

SENSOR_PINS = [18, 19, 21, 22, 23]

sensors = [
    Pin(pin, Pin.IN)
    for pin in SENSOR_PINS
]

# 0 = phat hien vach den
LINE_ACTIVE = 0

SPEED_NORMAL = 300
SPEED_SLOW = 180
SPEED_TURN = 320
SPEED_SHARP = 360
SPEED_SEARCH = 270

READ_INTERVAL_MS = 10

LOST_CONFIRM_MS = 40


SEARCH_TIMEOUT_MS = 400


TURN_TIMEOUT_MS = 1400

TURN90_MIN_MS = 200
TURN180_MIN_MS = 600

# Xu ly giao lo
ENABLE_JUNCTIONS = True
JUNCTION_FORWARD_MS = 100
JUNCTION_LOCK_MS = 450

last_direction = 1

last_junction_time = time.ticks_ms()
last_read_time = time.ticks_ms()

lost_start = None
running = True

def clamp(value, low, high):
    return max(low, min(high, int(value)))


def motor_left(speed):

    speed = clamp(speed, -1023, 1023)

    if speed > 0:
        IN1.value(1)
        IN2.value(0)

    elif speed < 0:
        IN1.value(0)
        IN2.value(1)

    else:
        IN1.value(0)
        IN2.value(0)

    ENA.duty(abs(speed))


def motor_right(speed):

    speed = clamp(speed, -1023, 1023)

    if speed > 0:
        IN3.value(1)
        IN4.value(0)

    elif speed < 0:
        IN3.value(0)
        IN4.value(1)

    else:
        IN3.value(0)
        IN4.value(0)

    ENB.duty(abs(speed))


def move(left, right):
    motor_left(left)
    motor_right(right)


def stop():
    move(0, 0)


def forward(speed):
    move(speed, speed)


def spin_left(speed):
    move(-speed, speed)


def spin_right(speed):
    move(speed, -speed)

def read_line():

    return [
        1 if sensor.value() == LINE_ACTIVE else 0
        for sensor in sensors
    ]


def center_detected():
    return read_line()[2] == 1


def any_line():
    return sum(read_line()) > 0



def follow_line(values):

    global last_direction

    s1, s2, s3, s4, s5 = values

    if s1 == 1 and s5 == 0:

        last_direction = -1
        spin_left(SPEED_SHARP)
        return

    # Vach lech phai rat nhieu
    if s5 == 1 and s1 == 0:

        last_direction = 1
        spin_right(SPEED_SHARP)
        return

    # Vach lech trai
    if s2 == 1 and s4 == 0:

        last_direction = -1
        move(SPEED_SLOW, SPEED_TURN)
        return

    # Vach lech phai
    if s4 == 1 and s2 == 0:

        last_direction = 1
        move(SPEED_TURN, SPEED_SLOW)
        return

    # Vach o giua
    if s3 == 1:

        forward(SPEED_NORMAL)
        return

    # Nhieu mat thay line, chua ro huong
    forward(SPEED_SLOW)

#  XOAY TIM LINE

def rotate_to_line(direction, min_ms):

    start = time.ticks_ms()
    stable = 0

    while time.ticks_diff(
        time.ticks_ms(), start
    ) < TURN_TIMEOUT_MS:

        if direction < 0:
            spin_left(SPEED_TURN)
        else:
            spin_right(SPEED_TURN)

        elapsed = time.ticks_diff(
            time.ticks_ms(), start
        )

        values = read_line()

        # Khong bat lai line qua som
        if elapsed >= min_ms:

            if values[2] == 1:
                stable += 1
            else:
                stable = 0

            if stable >= 3:
                stop()
                return True

        time.sleep_ms(5)

    stop()
    return False


def turn_left():
    print("RE TRAI")
    return rotate_to_line(-1, TURN90_MIN_MS)


def turn_right():
    print("RE PHAI")
    return rotate_to_line(1, TURN90_MIN_MS)


def turn_around():
    print("QUAY DAU")
    return rotate_to_line(1, TURN180_MIN_MS)


# XU LY NGA RE

def detect_junction(values):

    s1, s2, s3, s4, s5 = values

    # Phat hien nhanh trai
    left = (
        s1 == 1
        and s2 == 1
        and s3 == 1
    )

    # Phat hien nhanh phai
    right = (
        s3 == 1
        and s4 == 1
        and s5 == 1
    )

    return left, right


def handle_junction(left, right):

    print("PHAT HIEN GIAO LO")

    # Tien qua tam giao lo
    forward(SPEED_SLOW)
    time.sleep_ms(JUNCTION_FORWARD_MS)
    stop()

    values = read_line()
    straight = values[2] == 1

    # Uu tien trai -> thang -> phai
    if left:
        return turn_left()

    elif straight:
        print("DI THANG")
        return True

    elif right:
        return turn_right()

    else:
        return turn_around()


# XU LY MAT LINE


def recover_line():

    print("MAT LINE - DANG TIM")

    start = time.ticks_ms()
    stable = 0

    # Tim theo huong lech cu
    while time.ticks_diff(
        time.ticks_ms(), start
    ) < SEARCH_TIMEOUT_MS:

        if last_direction < 0:
            spin_left(SPEED_SEARCH)
        else:
            spin_right(SPEED_SEARCH)

        if center_detected():
            stable += 1
        else:
            stable = 0

        if stable >= 3:
            stop()
            print("DA TIM LAI LINE")
            return True

        time.sleep_ms(5)

    stop()

    # Neu khong thay, thu quay dau
    print("THU QUAY DAU 180 DO")

    if turn_around():
        return True

    stop()
    return False



# CHUONG TRINH CHINH


stop()
time.sleep_ms(1000)

print("============================")
print("ESP32 LINE FOLLOWER READY")
print("NO PID + JUNCTION + U-TURN")
print("============================")

last_junction_time = time.ticks_add(
    time.ticks_ms(), -JUNCTION_LOCK_MS - 1
)

try:
    while running:

        now = time.ticks_ms()

        if time.ticks_diff(
            now, last_read_time
        ) < READ_INTERVAL_MS:

            time.sleep_ms(1)
            continue

        last_read_time = now

        values = read_line()

        # A. MAT LINE

        if sum(values) == 0:

            if lost_start is None:
                lost_start = now
                stop()

            elif time.ticks_diff(
                now, lost_start
            ) >= LOST_CONFIRM_MS:

                if not recover_line():
                    running = False

                lost_start = None
                last_read_time = time.ticks_ms()

            continue

        lost_start = None
     
        # B. PHAT HIEN NGA RE
        

        if ENABLE_JUNCTIONS:

            allowed = time.ticks_diff(
                now, last_junction_time
            ) > JUNCTION_LOCK_MS

            left, right = detect_junction(values)

            if allowed and (left or right):

                confirmed = 0

                for _ in range(3):
                    v = read_line()
                    l, r = detect_junction(v)

                    if l or r:
                        confirmed += 1

                    time.sleep_ms(5)

                if confirmed >= 2:

                    success = handle_junction(
                        left, right
                    )

                    last_junction_time = time.ticks_ms()
                    last_read_time = time.ticks_ms()

                    if not success:
                        if not recover_line():
                            running = False

                    continue

        # C. DO LINE BINH THUONG


        follow_line(values)

except KeyboardInterrupt:
    print("STOP BY USER")

finally:
    stop()
    print("ROBOT STOPPED")

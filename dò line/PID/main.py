from machine import Pin, PWM
import time

#khai báo

IN1 = Pin(27, Pin.OUT)
IN2 = Pin(26, Pin.OUT)
IN3 = Pin(25, Pin.OUT)
IN4 = Pin(33, Pin.OUT)

ENA = PWM(Pin(14), freq=1000)
ENB = PWM(Pin(32), freq=1000)

#trái sang phải
SENSOR_PINS = [18, 19, 21, 22, 23]

sensors = [
    Pin(pin, Pin.IN)
    for pin in SENSOR_PINS
]

# 0 = vach den, 1 = nen trang

LINE_ACTIVE = 0

WEIGHTS = [-2, -1, 0, 1, 2]

#PID

KP = 150.0
KI = 0.0
KD = 1.8

BASE_SPEED = 380
MAX_SPEED = 800

PID_INTERVAL = 20

last_error = 0.0
last_direction = 1
integral = 0.0



TURN_SPEED = 380
SEARCH_SPEED = 260

JUNCTION_FORWARD_MS = 110

TURN90_MS = 350
TURN180_MS = 750

TURN_TIMEOUT_MS = 1400
LOST_SEARCH_MS = 350

JUNCTION_LOCK_MS = 300

JUNCTION_CONFIRM = 3

#động cow

def clamp(value, low, high):
    return max(low, min(high, int(value)))

#trai
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

#phai
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

#theo dõi 
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

def line_detected():
    return sum(read_line()) > 0

def center_detected():
    values = read_line()
    return values[2] == 1

def reset_pid():

    global last_error, integral

    last_error = 0.0
    integral = 0.0

def follow_pid(values):

    global last_error
    global last_direction
    global integral

    count = sum(values)

    if count == 0:
        return False

    #sai lệch
    error = sum(
        WEIGHTS[i] * values[i]
        for i in range(5)
    ) / count

    if error > 0.15:
        last_direction = 1

    elif error < -0.15:
        last_direction = -1

    dt = PID_INTERVAL / 1000.0

    integral += error * dt
    integral = clamp(integral * 1000, -2000, 2000) / 1000

    derivative = (error - last_error) / dt

    correction = (
        KP * error
        + KI * integral
        + KD * derivative
    )

    last_error = error

    left_speed = clamp(
        BASE_SPEED + correction,
        -MAX_SPEED,
        MAX_SPEED
    )

    right_speed = clamp(
        BASE_SPEED - correction,
        -MAX_SPEED,
        MAX_SPEED
    )

    move(left_speed, right_speed)

    return True


#TH mất line

def rotate_to_line(direction, target_ms):

    start = time.ticks_ms()
    stable_count = 0

    min_time = int(target_ms * 0.75)

    while time.ticks_diff(
        time.ticks_ms(), start
    ) < TURN_TIMEOUT_MS:

        if direction == -1:
            spin_left(TURN_SPEED)
        else:
            spin_right(TURN_SPEED)

        elapsed = time.ticks_diff(
            time.ticks_ms(), start
        )

        if elapsed >= min_time:

            values = read_line()

            if values[2] == 1:
                stable_count += 1
            else:
                stable_count = 0

            if stable_count >= 3:

                stop()
                reset_pid()

                return True

        time.sleep_ms(10)

    stop()
    return False


def turn_left():
    print("RE TRAI")
    return rotate_to_line(-1, TURN90_MS)


def turn_right():
    print("RE PHAI")
    return rotate_to_line(1, TURN90_MS)


def turn_around():
    print("QUAY DAU 180 DO")
    return rotate_to_line(1, TURN180_MS)

#ngã rẽ

def handle_junction(left_seen, right_seen):

    print("PHAT HIEN GIAO LO")

    # Tien qua giao lo
    forward(BASE_SPEED)

    time.sleep_ms(JUNCTION_FORWARD_MS)

    stop()

    values = read_line()

    straight_exists = values[2] == 1

    # Uu tien:
    # TRAI -> THANG -> PHAI -> QUAY DAU

    if left_seen:

        print("CHON RE TRAI")
        return turn_left()

    elif straight_exists:

        print("CHON DI THANG")
        reset_pid()
        return True

    elif right_seen:

        print("CHON RE PHAI")
        return turn_right()

    else:

        print("DUONG CUT")
        return turn_around()

# MAT LINE

def recover_line():

    print("MAT LINE - DANG TIM")

    start = time.ticks_ms()

    # Tim theo huong sai lech truoc do
    while time.ticks_diff(
        time.ticks_ms(), start
    ) < LOST_SEARCH_MS:

        if last_direction == -1:
            spin_left(SEARCH_SPEED)
        else:
            spin_right(SEARCH_SPEED)

        if center_detected():

            stop()
            reset_pid()

            print("TIM LAI LINE THANH CONG")

            return True

        time.sleep_ms(10)

    stop()

    # Tim khong duoc thi quay dau
    print("KHONG THAY LINE - QUAY DAU")

    if turn_around():
        return True

    stop()

    print("LOI: KHONG TIM THAY LINE")
    return False


stop()

time.sleep_ms(1000)

print("==============================")
print("ESP32 LINE FOLLOWER READY")
print("PID + JUNCTION + U-TURN")
print("==============================")

last_pid_time = time.ticks_ms()

last_junction_time = time.ticks_add(
    time.ticks_ms(),
    -1000
)

junction_count = 0
running = True

while running:

    now = time.ticks_ms()

    # Chu ky PID 20 ms
    if time.ticks_diff(
        now, last_pid_time
    ) < PID_INTERVAL:

        time.sleep_ms(1)
        continue

    last_pid_time = now

    values = read_line()

    # =====================================
    # A. MAT LINE
    # =====================================

    if sum(values) == 0:

        if not recover_line():
            running = False

        last_pid_time = time.ticks_ms()
        continue

    # =====================================
    # B. PHAT HIEN NGA RE
    # =====================================

    left_branch = (
        values[0] == 1
        and values[1] == 1
    )

    right_branch = (
        values[3] == 1
        and values[4] == 1
    )

    junction_allowed = (
        time.ticks_diff(
            now, last_junction_time
        ) > JUNCTION_LOCK_MS
    )

    if junction_allowed and (
        left_branch or right_branch
    ):

        # Xac nhan giao lo nhieu lan
        confirmed = 0

        for i in range(JUNCTION_CONFIRM):

            sample = read_line()

            sample_left = (
                sample[0] == 1
                and sample[1] == 1
            )

            sample_right = (
                sample[3] == 1
                and sample[4] == 1
            )

            if sample_left or sample_right:
                confirmed += 1

            time.sleep_ms(5)

        if confirmed >= 2:

            junction_count += 1

            print(
                "GIAO LO SO:",
                junction_count
            )

            success = handle_junction(
                left_branch,
                right_branch
            )

            last_junction_time = time.ticks_ms()
            last_pid_time = time.ticks_ms()

            if not success:

                if not recover_line():
                    running = False

            continue

    # =====================================
    # C. PID DO LINE BINH THUONG
    # =====================================

    follow_pid(values)

#  KET THUC

stop()
print("ROBOT STOPPED")
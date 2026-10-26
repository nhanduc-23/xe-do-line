#define BLYNK_TEMPLATE_ID "TMPL6flcgKxLQ"
#define BLYNK_TEMPLATE_NAME "Xe điều khiển từ xa"
#define BLYNK_AUTH_TOKEN "LAOtFNTlTHNJPXC2crH7ijnrfv8v7ruP"

#define BLYNK_PRINT Serial

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>

// ====================================================
// 1. THÔNG TIN CẤU HÌNH WI-FI
// ====================================================
char ssid[] = "TP-LINK_E90E";
char pass[] = "123456789";

// ====================================================
// 2. KHAI BÁO CHÂN PHẦN CỨNG
// ====================================================
// Động cơ (Driver L298N)
#define IN1 27
#define IN2 26
#define IN3 25
#define IN4 33
#define ENA 14
#define ENB 32

// Cảm biến Line (5 mắt)
const int SENSOR_PINS[5] = {18, 19, 21, 22, 23};

// Cảm biến siêu âm HC-SR04
#define TRIG 4
#define ECHO 13

// Thiết bị cảnh báo (Còi & Đèn)
#define BUZZER_PIN 15  // Còi báo (D15)
#define LED1_PIN 2     // Đèn 1 (D2)
#define LED2_PIN 5     // Đèn 2 (D5)

// ====================================================
// 3. BIẾN ĐIỀU KHIỂN & TRẠNG THÁI
// ====================================================
volatile int robot_mode = 0;          // 0: STOP, 1: AUTO, 2: MANUAL
String current_status = "Dung";
float current_distance = 0.0;
bool line_lost_standby = false;
bool obstacle_alert = false;          // Cờ bật còi bíp liên tục khi gặp vật cản

// Cấu hình cảm biến Line
const int LINE_ACTIVE = 0;            // Mức LOW (0) khi phát hiện vạch đen
const float WEIGHTS[5] = {-2.0, -1.0, 0.0, 1.0, 2.0};

// Bộ điều khiển PID
float KP = 150.0;
float KI = 0.0;
float KD = 1.8;

int BASE_SPEED = 380;                 // Tốc độ điều khiển Blynk (V5)
int MAX_SPEED = 800;
const int PID_INTERVAL = 20;

// Tốc độ điều khiển thủ công
int MANUAL_SPEED = 750;
int MANUAL_TURN_SPEED = 900;

// Tốc độ xoay tìm line khi mất dấu
int LOST_SPIN_SPEED = 500;

float last_error = 0.0;
int last_direction = 1;
float integral = 0.0;

// Tham số ngã rẽ
int TURN_SPEED = 380;
int JUNCTION_FORWARD_MS = 110;
int TURN90_MS = 350;
int TURN180_MS = 750;
int TURN_TIMEOUT_MS = 1400;
int JUNCTION_LOCK_MS = 300;
int JUNCTION_CONFIRM = 3;

// Tham số né vật cản
int OBSTACLE_DIST = 13;               // Khoảng cách bắt đầu né (cm)
int OBSTACLE_CONFIRM = 2;             // Số lần đọc xác nhận liên tiếp
int SONAR_INTERVAL = 80;              // Chu kỳ quét siêu âm (ms)

// XUNG CỐ ĐỊNH DUY NHẤT CHO CHUỖI NÉ VẬT CẢN (0 - 1023)
const int AVOID_FIXED_SPEED = 450;

// Thời gian từng pha né vật cản (Đã giữ các mốc bạn đã chỉnh thực tế)
int AVOID_BACKWARD_MS = 300;          // Lùi lại tạo khoảng cách an toàn (300ms)
int AVOID_TURN_90_MS  = 650;          // Thời gian quay góc 90 độ (650ms)
int AVOID_SIDE_MS     = 800;          // Đi ngang dạt ra ngoài (800ms)
int AVOID_PARALLEL_MS = 400;          // Đi song song vượt vật cản (400ms)
int AVOID_TURN_70_MS  = 700;          // Thời gian quay hướng về line (700ms)

// Tham số tìm vạch
int GAP_FORWARD_MS = 150;
int SWEEP_TIME_MS = 220;

// ====================================================
// 4. HÀM ĐIỀU KHIỂN ĐỘNG CƠ, CÒI & ĐÈN
// ====================================================
void buzzer_beep(int ms) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(ms);
  digitalWrite(BUZZER_PIN, LOW);
}

void set_alert(bool state) {
  digitalWrite(BUZZER_PIN, state ? HIGH : LOW);
  digitalWrite(LED1_PIN, state ? HIGH : LOW);
  digitalWrite(LED2_PIN, state ? HIGH : LOW);
}

// Trễ có bíp còi nhịp 100ms
void delay_beep(int duration_ms, int beep_cycle_ms = 100) {
  unsigned long start = millis();
  while (millis() - start < duration_ms) {
    bool beep_on = ((millis() / beep_cycle_ms) % 2 == 0);
    digitalWrite(BUZZER_PIN, beep_on ? HIGH : LOW);
    digitalWrite(LED1_PIN, beep_on ? HIGH : LOW);
    digitalWrite(LED2_PIN, beep_on ? HIGH : LOW);
    delay(5);
  }
}

void setPwmSpeed(int left_pwm, int right_pwm) {
  analogWrite(ENA, constrain(left_pwm, 0, 1023));
  analogWrite(ENB, constrain(right_pwm, 0, 1023));
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
  setPwmSpeed(0, 0);
}

void forward(int speed) {
  setPwmSpeed(speed, speed);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}

void backward(int speed) {
  setPwmSpeed(speed, speed);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
}

void spin_left(int speed) {
  setPwmSpeed(speed, speed);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}

void spin_right(int speed) {
  setPwmSpeed(speed, speed);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
}

void brakeMotors(int duration_ms = 60) {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, HIGH);
  setPwmSpeed(1023, 1023);
  delay(duration_ms);
  stopMotors();
}

void moveMotorsPID(int left_speed, int right_speed) {
  if (left_speed >= 0) {
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  } else {
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  }

  if (right_speed >= 0) {
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  } else {
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  }

  setPwmSpeed(abs(left_speed), abs(right_speed));
}

// ====================================================
// 5. HÀM ĐỌC CẢM BIẾN
// ====================================================
void read_line(int values[5]) {
  for (int i = 0; i < 5; i++) {
    values[i] = (digitalRead(SENSOR_PINS[i]) == LINE_ACTIVE) ? 1 : 0;
  }
}

bool line_detected() {
  int values[5];
  read_line(values);
  int sum = 0;
  for (int i = 0; i < 5; i++) sum += values[i];
  return sum > 0;
}

float get_distance_cm() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  
  long duration = pulseIn(ECHO, HIGH, 3000); 
  if (duration <= 0) return -1.0;
  return duration / 58.0;
}

// ====================================================
// 6. THUẬT TOÁN PID BÁM LINE
// ====================================================
void reset_pid() {
  last_error = 0.0;
  integral = 0.0;
}

bool follow_pid(int values[5]) {
  int count = 0;
  float weighted_sum = 0.0;
  for (int i = 0; i < 5; i++) {
    if (values[i] == 1) {
      count++;
      weighted_sum += WEIGHTS[i];
    }
  }

  if (count == 0) return false;

  float error = weighted_sum / count;

  if (error > 0.15) last_direction = 1;
  else if (error < -0.15) last_direction = -1;

  float dt = PID_INTERVAL / 1000.0;
  integral += error * dt;
  integral = constrain(integral * 1000.0, -2000.0, 2000.0) / 1000.0;
  float derivative = (error - last_error) / dt;

  float correction = KP * error + KI * integral + KD * derivative;
  last_error = error;

  int left_speed = constrain(BASE_SPEED + correction, -MAX_SPEED, MAX_SPEED);
  int right_speed = constrain(BASE_SPEED - correction, -MAX_SPEED, MAX_SPEED);
  moveMotorsPID(left_speed, right_speed);
  return true;
}

// ====================================================
// 7. XỬ LÝ GIAO LỘ & NÉ VẬT CẢN (XUNG CỐ ĐỊNH & LỌC NHIỄU)
// ====================================================
bool rotate_to_line(int direction, int target_ms) {
  unsigned long start = millis();
  int stable_count = 0;
  int min_time = (int)(target_ms * 0.75);

  while (millis() - start < TURN_TIMEOUT_MS) {
    if (direction == -1) spin_left(TURN_SPEED);
    else spin_right(TURN_SPEED);

    if (millis() - start >= min_time) {
      int values[5];
      read_line(values);
      if (values[2] == 1) stable_count++;
      else stable_count = 0;

      if (stable_count >= 3) {
        brakeMotors(40);
        reset_pid();
        return true;
      }
    }
    delay(10);
  }
  brakeMotors(40);
  return false;
}

bool handle_junction(bool left_seen, bool right_seen) {
  current_status = "Giao lo";
  forward(BASE_SPEED);
  delay(JUNCTION_FORWARD_MS);
  stopMotors();

  int values[5];
  read_line(values);
  bool straight_exists = (values[2] == 1);

  if (left_seen) {
    current_status = "Re trai";
    return rotate_to_line(-1, TURN90_MS);
  } else if (straight_exists) {
    current_status = "Di thang";
    reset_pid();
    return true;
  } else if (right_seen) {
    current_status = "Re phai";
    return rotate_to_line(1, TURN90_MS);
  } else {
    current_status = "Duong cut";
    return rotate_to_line(1, TURN180_MS);
  }
}

// Thuật toán né vật cản chạy xung cố định hoàn chỉnh
bool avoid_obstacle() {
  current_status = "Ne vat can";
  obstacle_alert = true;

  brakeMotors(70);
  delay_beep(50);

  // PHA 0: Lùi tạo khoảng cách an toàn tại xung cố định
  backward(AVOID_FIXED_SPEED);
  delay_beep(AVOID_BACKWARD_MS);
  brakeMotors(30);
  delay_beep(40);

  // PHA 1: Rẽ phải 90 độ & đi ngang dạt ra ngoài
  spin_right(AVOID_FIXED_SPEED);
  delay_beep(AVOID_TURN_90_MS);
  brakeMotors(30);
  delay_beep(30);

  forward(AVOID_FIXED_SPEED);
  delay_beep(AVOID_SIDE_MS);
  brakeMotors(30);
  delay_beep(30);

  // PHA 2: Rẽ trái 90 độ & đi song song vượt vật cản
  spin_left(AVOID_FIXED_SPEED);
  delay_beep(AVOID_TURN_90_MS);
  brakeMotors(30);
  delay_beep(30);

  forward(AVOID_FIXED_SPEED);
  delay_beep(AVOID_PARALLEL_MS);
  brakeMotors(30);
  delay_beep(30);

  // PHA 3: Rẽ trái hướng đầu về line
  spin_left(AVOID_FIXED_SPEED);
  delay_beep(AVOID_TURN_70_MS);
  brakeMotors(30);
  delay_beep(50);

  // PHA 4: Tiến về line - CÓ BỘ LỌC XÁC NHẬN CHỐNG NHIỄU ẢO
  unsigned long start_search = millis();
  bool found_line = false;
  int line_confirm_count = 0;

  while (millis() - start_search < 4500) {
    forward(AVOID_FIXED_SPEED);

    bool b_state = ((millis() / 100) % 2 == 0);
    digitalWrite(BUZZER_PIN, b_state ? HIGH : LOW);
    digitalWrite(LED1_PIN, b_state ? HIGH : LOW);
    digitalWrite(LED2_PIN, b_state ? HIGH : LOW);

    int vals[5];
    read_line(vals);

    // Kiểm tra các mắt có chạm vạch thật không
    if (vals[0] == 1 || vals[1] == 1 || vals[2] == 1) {
      line_confirm_count++;
    } else {
      line_confirm_count = 0; // Xóa đếm nếu chỉ là xung nhiễu chớp tắt
    }

    // Bắt buộc xác nhận chạm vạch liên tiếp 3 chu kỳ
    if (line_confirm_count >= 3) {
      unsigned long creep_start = millis();
      while (millis() - creep_start < 140) {
        forward(AVOID_FIXED_SPEED);
        int v[5];
        read_line(v);
        if (v[2] == 1) break; // Mắt giữa chạm vạch -> dừng nhích
        delay(5);
      }
      found_line = true;
      break;
    }
    delay(10);
  }
  
  brakeMotors(40);
  delay_beep(30);

  // PHA 5: NẮN THẲNG XE CÓ KHÓA AN TOÀN CHỐNG QUAY MÙ
  if (found_line) {
    unsigned long align_start = millis();
    while (millis() - align_start < 350) {
      bool a_state = ((millis() / 100) % 2 == 0);
      digitalWrite(BUZZER_PIN, a_state ? HIGH : LOW);
      digitalWrite(LED1_PIN, a_state ? HIGH : LOW);
      digitalWrite(LED2_PIN, a_state ? HIGH : LOW);

      int vals[5];
      read_line(vals);

      int sum = 0;
      for (int i = 0; i < 5; i++) sum += vals[i];

      // KHÓA AN TOÀN: Nếu mất hẳn dấu vạch thì dừng xoay ngay, không quay mù
      if (sum == 0) {
        break;
      }

      // Điều kiện chuẩn: Mắt giữa đã vào vạch và mắt trái đã thoát ra, hoặc mắt phải chạm
      if ((vals[2] == 1 && vals[0] == 0) || vals[3] == 1 || vals[4] == 1) {
        break;
      }

      spin_right(AVOID_FIXED_SPEED);
      delay(10);
    }

    brakeMotors(40);
    reset_pid();
    last_direction = 1;
    current_status = "Bam line";

    obstacle_alert = false;
    set_alert(false);
    return true;
  }
  
  return false;
}

// ====================================================
// 8. XỬ LÝ SỰ KIỆN BLYNK
// ====================================================
BLYNK_CONNECTED() {
  Blynk.syncVirtual(V0);
}

BLYNK_WRITE(V0) {
  robot_mode = param.asInt();
  line_lost_standby = false;
  if (robot_mode == 0) {
    brakeMotors(50);
    obstacle_alert = false;
    set_alert(false);
  }
}

// Nút Tiến (V1)
BLYNK_WRITE(V1) {
  int state = param.asInt();
  if (state == 1) {
    robot_mode = 2;
    forward(MANUAL_SPEED);
  } else {
    stopMotors();
  }
}

// Nút Lùi (V7)
BLYNK_WRITE(V7) {
  int state = param.asInt();
  if (state == 1) {
    robot_mode = 2;
    backward(MANUAL_SPEED);
  } else {
    stopMotors();
  }
}

// Nút Rẽ Trái (V8)
BLYNK_WRITE(V8) {
  int state = param.asInt();
  if (state == 1) {
    robot_mode = 2;
    spin_left(MANUAL_TURN_SPEED);
  } else {
    stopMotors();
  }
}

// Nút Rẽ Phải (V9)
BLYNK_WRITE(V9) {
  int state = param.asInt();
  if (state == 1) {
    robot_mode = 2;
    spin_right(MANUAL_TURN_SPEED);
  } else {
    stopMotors();
  }
}

// Phanh khẩn cấp (V2)
BLYNK_WRITE(V2) {
  if (param.asInt() == 1) {
    robot_mode = 0;
    line_lost_standby = false;
    obstacle_alert = false;
    Blynk.virtualWrite(V0, 0);
    brakeMotors(80);
    set_alert(false);
  }
}

BLYNK_WRITE(V5) { BASE_SPEED = param.asInt(); }
BLYNK_WRITE(V6) { KP = param.asFloat(); }

// Task chạy Blynk trên Core 0
void BlynkTask(void *pvParameters) {
  unsigned long last_telemetry = millis();
  String last_sent_status = "";

  for (;;) {
    Blynk.run();
    unsigned long now = millis();

    if (now - last_telemetry >= 300) {
      last_telemetry = now;
      if (current_distance >= 0) {
        Blynk.virtualWrite(V4, (int)current_distance);
      }
      if (current_status != last_sent_status) {
        Blynk.virtualWrite(V3, current_status);
        last_sent_status = current_status;
      }
    }
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// ====================================================
// 9. SETUP VÀ LOOP (Core 1)
// ====================================================
void setup() {
  Serial.begin(115200);

  // Cấu hình chân Động cơ
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);

  // Cấu hình 10-bit PWM độc lập từng chân ENA, ENB
  analogWriteResolution(ENA, 10); // Cấu hình 10-bit PWM cho chân ENA
  analogWriteResolution(ENB, 10); // Cấu hình 10-bit PWM cho chân ENB

  // Cấu hình chân Cảm biến Line
  for (int i = 0; i < 5; i++) {
    pinMode(SENSOR_PINS[i], INPUT);
  }

  // Cấu hình chân Siêu âm
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  digitalWrite(TRIG, LOW);

  // Cấu hình chân Còi & Đèn
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);
  
  set_alert(false);
  buzzer_beep(150);

  WiFi.begin(ssid, pass);
  Serial.print("Dang ket noi Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi Connected! IP: " + WiFi.localIP().toString());

  Blynk.config(BLYNK_AUTH_TOKEN, "blynk.cloud", 80);
  Blynk.connect();

  xTaskCreatePinnedToCore(
    BlynkTask,
    "BlynkTask",
    8192,
    NULL,
    1,
    NULL,
    0
  );

  stopMotors();
  delay(1000);
}

unsigned long last_pid_time = 0;
unsigned long last_sonar_time = 0;
unsigned long last_junction_time = 0;
int obstacle_samples = 0;

void loop() {
  // ------------------------------------------------
  // CHẾ ĐỘ 0: DỪNG HẲN (STOP)
  // ------------------------------------------------
  if (robot_mode == 0) {
    current_status = "Dung";
    obstacle_alert = false;
    set_alert(false);
    delay(50);
    return;
  }

  // ------------------------------------------------
  // CHẾ ĐỘ 2: ĐIỀU KHIỂN THỦ CÔNG (MANUAL)
  // ------------------------------------------------
  if (robot_mode == 2) {
    current_status = "Dieu khien tay";
    digitalWrite(LED1_PIN, HIGH);
    delay(50);
    return;
  }

  // ------------------------------------------------
  // CHẾ ĐỘ 1: TỰ ĐỘNG DÒ LINE & NÉ VẬT CẢN (AUTO)
  // ------------------------------------------------
  unsigned long now = millis();

  // A. Quét cảm biến siêu âm mỗi 80ms
  if (now - last_sonar_time >= SONAR_INTERVAL) {
    last_sonar_time = now;
    current_distance = get_distance_cm();

    if (current_distance > 0 && current_distance <= OBSTACLE_DIST) {
      obstacle_samples++;
    } else {
      obstacle_samples = 0;
    }

    if (obstacle_samples >= OBSTACLE_CONFIRM) {
      obstacle_samples = 0;
      if (!avoid_obstacle()) {
        line_lost_standby = true;
        current_status = "Xoay tim line...";
      }
      last_pid_time = millis();
      last_junction_time = millis();
      return;
    }
  }

  // B. Chu kỳ lấy mẫu PID 20ms
  if (now - last_pid_time < PID_INTERVAL) {
    delay(1);
    return;
  }

  last_pid_time = now;
  int values[5];
  read_line(values);

  int sum_val = 0;
  for (int i = 0; i < 5; i++) sum_val += values[i];

  // ====================================================
  // C. XỬ LÝ MẤT LINE: TIẾP TỤC BÍP NẾU CHƯA THẤY VẠCH
  // ====================================================
  if (sum_val == 0) {
    current_status = "Xoay tim line...";
    line_lost_standby = true;

    if (obstacle_alert) {
      bool b_state = ((millis() / 100) % 2 == 0);
      digitalWrite(BUZZER_PIN, b_state ? HIGH : LOW);
      digitalWrite(LED1_PIN, b_state ? HIGH : LOW);
      digitalWrite(LED2_PIN, b_state ? HIGH : LOW);
    } else {
      digitalWrite(LED1_PIN, (millis() / 200) % 2);
    }

    if (last_direction == -1) {
      spin_left(LOST_SPIN_SPEED);
    } else {
      spin_right(LOST_SPIN_SPEED);
    }

    last_pid_time = millis();
    return;
  } else {
    if (obstacle_alert) {
      obstacle_alert = false;
      set_alert(false);
    }

    if (line_lost_standby) {
      line_lost_standby = false;
      brakeMotors(30);
      reset_pid();
      digitalWrite(LED1_PIN, LOW);
      current_status = "Bam line";
    }
  }

  // D. PHÁT HIỆN NGÃ RẼ / GIAO LỘ
  bool left_branch = (values[0] == 1 && values[1] == 1);
  bool right_branch = (values[3] == 1 && values[4] == 1);
  bool junction_allowed = (now - last_junction_time > JUNCTION_LOCK_MS);

  if (junction_allowed && (left_branch || right_branch)) {
    int confirmed = 0;
    for (int k = 0; k < JUNCTION_CONFIRM; k++) {
      int sample[5];
      read_line(sample);
      if ((sample[0] == 1 && sample[1] == 1) || (sample[3] == 1 && sample[4] == 1)) {
        confirmed++;
      }
      delay(5);
    }

    if (confirmed >= 2) {
      bool success = handle_junction(left_branch, right_branch);
      last_junction_time = millis();
      last_pid_time = millis();
      if (!success) {
        line_lost_standby = true;
        current_status = "Xoay tim line...";
      }
      return;
    }
  }

  // E. BÁM VẠCH PID BÌNH THƯỜNG (SỬ DỤNG BASE_SPEED TỪ BLYNK)
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  current_status = "Bam line";
  follow_pid(values);
}

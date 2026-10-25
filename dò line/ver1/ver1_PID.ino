#include <Arduino.h>

// Arduino Uno + L298N + five DIGITAL line sensors
// Physical order of sensors: left -> right.
const byte IN1 = 2, IN2 = 3, IN3 = 4, IN4 = 5;
const byte ENA = 10, ENB = 11;  // PWM pins on Uno
const byte S[5] = {6, 7, 8, 9, 12};
const byte LINE_LEVEL = LOW;   // Change to HIGH if black produces HIGH

// Initial values; must be tuned on the actual car.
const int BASE_PWM = 115, CURVE_PWM = 85;
const int MAX_PWM = 190, PIVOT_PWM = 125;
const int SEARCH_PWM = 110;
const float KP = 42.0f, KI = 0.0f, KD = 0.25f;
const unsigned long PERIOD_MS = 10;
const unsigned long LOST_CONFIRM_MS = 35;
const unsigned long SEARCH_MS = 450;
const unsigned long REVERSE_MS = 180;
const unsigned long UTURN_SEARCH_MS = 1600;
const unsigned long JUNCTION_ADVANCE_MS = 85;
const unsigned long JUNCTION_COOLDOWN_MS = 350;
const unsigned long TURN_MIN_MS = 140;
const unsigned long TURN_TIMEOUT_MS = 1200;
const bool ENABLE_JUNCTIONS = true;

int lastDir = 1;  // -1 left, +1 right
float prevError = 0.0f, integ = 0.0f;
unsigned long lastPID = 0, lastJunction = 0, lastLoop = 0;
unsigned long lostSince = 0;
bool halted = false;

void driveOne(byte a, byte b, byte en, int speed) {
  speed = constrain(speed, -255, 255);
  if (speed > 0) { digitalWrite(a, HIGH); digitalWrite(b, LOW); }
  else if (speed < 0) { digitalWrite(a, LOW); digitalWrite(b, HIGH); }
  else { digitalWrite(a, LOW); digitalWrite(b, LOW); }
  analogWrite(en, abs(speed));
}
void drive(int left, int right) {
  driveOne(IN1, IN2, ENA, left);  // Motor A = left
  driveOne(IN3, IN4, ENB, right); // Motor B = right
}
void stopCar() { drive(0, 0); }
void spin(int direction, int pwm) {
  if (direction < 0) drive(-pwm, pwm);
  else drive(pwm, -pwm);
}
void readLine(byte h[5]) {
  for (byte i = 0; i < 5; ++i) h[i] = (digitalRead(S[i]) == LINE_LEVEL);
}
byte countLine(const byte h[5]) {
  byte n = 0;
  for (byte i = 0; i < 5; ++i) n += h[i];
  return n;
}
void resetPID() {
  prevError = 0;
  integ = 0;
  lastPID = millis();
}
void followPID(const byte h[5]) {
  const int weight[5] = {-2, -1, 0, 1, 2};
  byte n = countLine(h);
  if (!n) return;
  int weighted = 0;
  for (byte i = 0; i < 5; ++i) weighted += weight[i] * h[i];
  float err = float(weighted) / n;
  if (err > 0.2f) lastDir = 1;
  else if (err < -0.2f) lastDir = -1;

  // Narrow, sharp corner: pivot instead of overshooting.
  if ((h[0] && !h[1] && !h[2] && !h[3] && !h[4]) || err <= -1.75f) {
    spin(-1, PIVOT_PWM); resetPID(); return;
  }
  if ((h[4] && !h[0] && !h[1] && !h[2] && !h[3]) || err >= 1.75f) {
    spin(1, PIVOT_PWM); resetPID(); return;
  }

  unsigned long now = millis();
  float dt = float(now - lastPID) / 1000.0f;
  if (dt < 0.005f) dt = 0.005f;
  if (dt > 0.050f) dt = 0.050f;
  integ = constrain(integ + err * dt, -2.0f, 2.0f);
  float deriv = constrain((err - prevError) / dt, -80.0f, 80.0f);
  float correction = KP * err + KI * integ + KD * deriv;
  int base = BASE_PWM - int((BASE_PWM - CURVE_PWM) * min(fabs(err)/2.0f, 1.0f));
  int left = constrain(int(base + correction), 0, MAX_PWM);
  int right = constrain(int(base - correction), 0, MAX_PWM);
  drive(left, right);
  prevError = err;
  lastPID = now;
}

// Rotate until center detects the line at least three consecutive readings.
// Timing is only an estimate: it does NOT measure exact 90/180 degrees.
bool rotateFind(int direction, unsigned long minMs, unsigned long maxMs) {
  stopCar(); delay(80);
  unsigned long start = millis();
  byte stable = 0;
  while (millis() - start < maxMs) {
    spin(direction, SEARCH_PWM);
    byte h[5]; readLine(h);
    if (millis() - start >= minMs && h[2]) ++stable;
    else stable = 0;
    if (stable >= 3) { stopCar(); resetPID(); return true; }
    delay(8);
  }
  stopCar(); return false;
}

bool recover() {
  Serial.println(F("LOST: search"));
  if (rotateFind(lastDir, 0, SEARCH_MS)) return true;
  Serial.println(F("LOST: reverse"));
  drive(-CURVE_PWM, -CURVE_PWM);
  delay(REVERSE_MS);
  stopCar(); delay(80);
  Serial.println(F("LOST: try U-turn"));
  // A five-sensor array cannot guarantee 180 degrees; may stop on another stripe.
  return rotateFind(lastDir, 450, UTURN_SEARCH_MS);
}

// Junction *candidates*, not guaranteed classification with 5 digital eyes.
bool leftBranch(const byte h[5])  { return h[0] && h[1] && h[2]; }
bool rightBranch(const byte h[5]) { return h[2] && h[3] && h[4]; }

bool junctionAction(bool left, bool right) {
  Serial.println(F("JUNCTION"));
  drive(CURVE_PWM, CURVE_PWM);
  delay(JUNCTION_ADVANCE_MS);
  stopCar();
  byte h[5]; readLine(h);
  bool straight = h[2];
  // Policy: left > straight > right > U-turn.
  if (left) {
    Serial.println(F("LEFT"));
    return rotateFind(-1, TURN_MIN_MS, TURN_TIMEOUT_MS);
  }
  if (straight) { Serial.println(F("STRAIGHT")); resetPID(); return true; }
  if (right) {
    Serial.println(F("RIGHT"));
    return rotateFind(1, TURN_MIN_MS, TURN_TIMEOUT_MS);
  }
  Serial.println(F("U-TURN"));
  return rotateFind(1, 450, UTURN_SEARCH_MS);
}

void setup() {
  Serial.begin(115200);
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  for (byte i = 0; i < 5; ++i) pinMode(S[i], INPUT);
  stopCar();
  delay(1000);
  lastJunction = millis() - JUNCTION_COOLDOWN_MS;
  resetPID();
  Serial.println(F("UNO LINE PID READY"));
}

void loop() {
  if (halted) { stopCar(); return; }
  unsigned long now = millis();
  if (now - lastLoop < PERIOD_MS) return;
  lastLoop = now;
  byte h[5]; readLine(h);
  if (!countLine(h)) {
    if (!lostSince) { lostSince = now; stopCar(); }
    if (now - lostSince >= LOST_CONFIRM_MS) {
      bool found = recover();
      lostSince = 0;
      lastLoop = millis();
      lastJunction = millis();
      if (!found) { halted = true; Serial.println(F("STOP: line not found")); }
    }
    return;
  }
  lostSince = 0;
  if (ENABLE_JUNCTIONS && now - lastJunction > JUNCTION_COOLDOWN_MS) {
    bool left = leftBranch(h), right = rightBranch(h);
    if (left || right) {
      byte matches = 0;
      for (byte j = 0; j < 3; ++j) {
        byte check[5]; readLine(check);
        if (leftBranch(check) || rightBranch(check)) ++matches;
        delay(3);
      }
      if (matches >= 2) {
        bool ok = junctionAction(left, right);
        lastJunction = millis();
        lastLoop = millis();
        if (!ok && !recover()) { halted = true; Serial.println(F("STOP: turn failed")); }
        return;
      }
    }
  }
  followPID(h);
}

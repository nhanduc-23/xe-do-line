// Định nghĩa các chân điều khiển động cơ
#define inA1 2 
#define inA2 3 
#define inB1 4
#define inB2 5 

// Định nghĩa 5 mắt cảm biến hồng ngoại (Xếp từ trái qua phải: 1 - 2 - 3 - 4 - 5)
#define hongngoai1 6
#define hongngoai2 7
#define hongngoai3 8  // Mắt ở chính giữa dòng Line
#define hongngoai4 9
#define hongngoai5 12 // ĐÃ ĐỔI TỪ CHÂN 1 SANG CHÂN 12 ĐỂ TRÁNH TRÙNG CHÂN SERIAL TX

#define ENA 10
#define ENB 11

void setup() {
  pinMode(inA1, OUTPUT);
  pinMode(inA2, OUTPUT);
  pinMode(inB1, OUTPUT);
  pinMode(inB2, OUTPUT);
  
  pinMode(hongngoai1, INPUT);
  pinMode(hongngoai2, INPUT);
  pinMode(hongngoai3, INPUT);
  pinMode(hongngoai4, INPUT);
  pinMode(hongngoai5, INPUT); // Thêm khai báo cấu hình đầu vào cho mắt số 5
  
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  
  Serial.begin(9600);
  analogWrite(ENA, 120);
  analogWrite(ENB, 120); // Đi chậm cho khỏi trượt Line
}

void loop() {
  // Đọc giá trị từ cả 5 cảm biến (Giả định: 1 là thấy vạch, 0 là ngoài vạch)
  int h1 = digitalRead(hongngoai1);
  int h2 = digitalRead(hongngoai2);
  int h3 = digitalRead(hongngoai3);
  int h4 = digitalRead(hongngoai4);
  int h5 = digitalRead(hongngoai5); // Đọc giá trị mắt số 5

  // TH 1: Mắt giữa (h3) nhận line hoặc cả 3 mắt giữa nhận line -> Đi thẳng
  if (h3 == 0 && h2 == 0 && h4 == 0 && h1 == 1 && h5 == 1) {
    Serial.println("Đi thẳng");
    dithang();
  }
  // TH 2: Lệch sang phải ít (mắt h4 chạm line) -> Rẽ phải nhẹ
  else if (h4 == 0 && h5 == 1) {
    Serial.println("Lệch phải nhẹ -> Quay phải");
    quayphai();
  }
  // TH 3: Lệch sang phải nhiều (mắt ngoài cùng h5 chạm line) -> Rẽ phải gấp (Tăng tốc bánh trái)
  else if (h5 == 0) {
    Serial.println("Lệch phải nặng -> Quay phải gấp");
    analogWrite(ENA, 160); // Tăng tốc động cơ A để qua cua gắt
    quayphai();
    analogWrite(ENA, 
    ; // Trả lại tốc độ cũ
  }
  // TH 4: Lệch sang trái ít (mắt h2 chạm line) -> Rẽ trái nhẹ
  else if (h2 == 0 && h1 == 1) {
    Serial.println("Lệch trái nhẹ -> Quay trái");
    quaytrai();
  }
  // TH 5: Lệch sang trái nhiều (mắt ngoài cùng h1 chạm line) -> Rẽ trái gấp (Tăng tốc bánh phải)
  else if (h1 == 0) {
    Serial.println("Lệch trái nặng -> Quay trái gấp");
    analogWrite(ENB, 160); // Tăng tốc động cơ B để qua cua gắt
    quaytrai();
    analogWrite(ENB, 120); // Trả lại tốc độ cũ
  }
  // TH 6: Tất cả các mắt không thấy line -> Lùi lại tìm line
  else if (h1 == 1 && h2 == 1 && h3 == 1 && h4 == 1 && h5 == 1) {
    Serial.println("Mất Line -> Lùi lại");
    lui();
  }
}

void dithang() {
  digitalWrite(inA1, HIGH);
  digitalWrite(inA2, LOW);
  digitalWrite(inB1, HIGH);
  digitalWrite(inB2, LOW);
}

void lui() {
  digitalWrite(inA1, LOW);
  digitalWrite(inA2, HIGH);
  digitalWrite(inB1, LOW);
  digitalWrite(inB2, HIGH);
}

void quaytrai() {
  digitalWrite(inA1, HIGH);
  digitalWrite(inA2, LOW);
  digitalWrite(inB1, LOW);
  digitalWrite(inB2, LOW);
}

void quayphai() {
  digitalWrite(inA1, LOW);
  digitalWrite(inA2, LOW);
  digitalWrite(inB1, HIGH);
  digitalWrite(inB2, LOW);
}

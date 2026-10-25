# LINE FOLLOWING ROBOT
### Design, Implementation and Development of an Autonomous Line-Following Robot

**Dự án nghiên cứu, thiết kế và phát triển xe robot dò line**

**Thời gian phát triển:** 3 tháng  
**Lĩnh vực:** Robotics · Embedded Systems · Automatic Control  
**Nền tảng:** ESP32 · Arduino · MicroPython · C/C++  
**Trạng thái:** Đang phát triển, thử nghiệm và tối ưu hóa (Under Development)

---

## 1. Giới thiệu dự án (Project Overview)

Line Following Robot là dự án nghiên cứu và xây dựng một robot di động có khả năng nhận biết và di chuyển theo vạch dẫn đường thông qua hệ thống cảm biến hồng ngoại.

Dự án được phát triển theo phương pháp từng bước (Incremental Development), bắt đầu từ những chức năng cơ bản như điều khiển động cơ, đọc tín hiệu cảm biến, sau đó mở rộng sang các thuật toán điều khiển và xử lý tình huống phức tạp.

Trong quá trình phát triển 3 tháng, dự án tập trung nghiên cứu:

- Điều khiển hai động cơ DC thông qua module L298N.
- Giao tiếp với hệ thống cảm biến hồng ngoại 5 kênh.
- Phát triển thuật toán dò line theo điều kiện (Rule-Based Control).
- Nghiên cứu và triển khai bộ điều khiển PID.
- Cải thiện khả năng bám vạch trên đường thẳng và các khúc cua.
- Xây dựng logic phát hiện và xử lý giao lộ.
- Thiết kế cơ chế tìm kiếm, khôi phục và quay đầu khi mất line.
- Thử nghiệm, đánh giá và tối ưu hóa hệ thống.

**Mục tiêu cuối cùng:** Xây dựng một robot có khả năng bám line ổn định, xử lý các tình huống trên đường chạy và hoạt động với mức độ tự động ngày càng cao.

---

## 2. Mục tiêu kỹ thuật (Technical Objectives)

### 2.1. Mục tiêu cơ bản

- Điều khiển độc lập tốc độ và chiều quay của hai động cơ.
- Đọc và xử lý chính xác trạng thái của 5 cảm biến hồng ngoại.
- Nhận biết vị trí tương đối của vạch so với robot.
- Điều chỉnh hướng di chuyển theo tín hiệu cảm biến.

### 2.2. Mục tiêu nâng cao

- Ứng dụng điều khiển PID để hạn chế dao động khi bám line.
- Điều chỉnh tốc độ linh hoạt khi đi thẳng và vào cua.
- Xử lý cua gắt và các điểm giao nhau.
- Tự tìm lại line khi robot mất vạch dẫn đường.
- Giảm hiện tượng giật do thay đổi trạng thái động cơ liên tục.

### 2.3. Mục tiêu dài hạn

- Cải thiện độ ổn định ở tốc độ cao.
- Phân biệt chính xác hơn các dạng giao lộ.
- Bổ sung thuật toán ghi nhớ đường đi và giải mê cung.
- Ứng dụng encoder hoặc IMU để cải thiện độ chính xác chuyển động.
- Xây dựng quy trình đo lường, đánh giá hiệu năng có thể lặp lại.

---

## 3. Kiến trúc hệ thống (System Architecture)

Hệ thống gồm ba khối chức năng chính:

**Input – Processing – Output**
<img width="548" height="355" alt="image" src="https://github.com/user-attachments/assets/33f7a22b-7807-4cc1-895b-27f7ec635b73" />

```text
        5 IR LINE SENSORS
       S1  S2  S3  S4  S5
                 |
                 v
        +----------------+
        | ESP32 / Arduino|
        |                |
        | Sensor Reading |
        | Line Detection |
        | PID / Rule Logic|
        | State Machine  |
        +----------------+
                 |
                 v
        +----------------+
        |  L298N DRIVER  |
        +----------------+
             |       |
             v       v
          MOTOR A  MOTOR B
             |       |
             +---+---+
                 |
          ROBOT MOVEMENT
```

### Nguyên lý hoạt động

1. Các cảm biến hồng ngoại thu nhận trạng thái bề mặt dưới robot.
2. Vi điều khiển đọc và chuẩn hóa tín hiệu cảm biến.
3. Thuật toán xác định vị trí tương đối của vạch.
4. Bộ điều khiển lựa chọn tốc độ cho từng bánh xe.
5. L298N cung cấp tín hiệu điều khiển đến hai động cơ.
6. Chu trình lặp lại liên tục để duy trì chuyển động theo line.

---

## 4. Phần cứng sử dụng (Hardware Components)

| Thành phần | Chức năng |
|---|---|
| ESP32 DevKit V1 | Vi điều khiển xử lý tín hiệu và điều khiển robot |
| Arduino Uno | Nền tảng triển khai và mô phỏng phiên bản Arduino |
| L298N | Driver điều khiển hai động cơ DC |
| 2 động cơ DC | Tạo chuyển động cho robot |
| Cảm biến hồng ngoại 5 mắt | Phát hiện vị trí vạch dẫn đường |
| Bánh xe và khung xe | Cơ cấu chuyển động |
| Nguồn điện | Cấp điện cho hệ thống |

**Lưu ý:** ESP32 và Arduino Uno là các nền tảng được sử dụng trong quá trình phát triển, không nhất thiết xuất hiện đồng thời trên một phiên bản robot.

---

## 5. Cấu hình chân ESP32 (Pin Configuration)

### Driver L298N

| L298N | ESP32 GPIO |
|---|---|
| ENA | 14 |
| IN1 | 27 |
| IN2 | 26 |
| IN3 | 25 |
| IN4 | 33 |
| ENB | 32 |

### Cảm biến hồng ngoại

| Cảm biến | ESP32 GPIO |
|---|---|
| S1 – Left Outer | 18 |
| S2 – Left Inner | 19 |
| S3 – Center | 21 |
| S4 – Right Inner | 22 |
| S5 – Right Outer | 23 |

Trạng thái cảm biến phải được kiểm tra theo module thực tế. Trong các phiên bản chương trình hiện tại, thường sử dụng quy ước mức LOW tương ứng với phát hiện vạch đen.

---

## 6. Quá trình phát triển trong 3 tháng (Development Timeline)

### Giai đoạn 1 — Tháng thứ nhất: Nền tảng phần cứng và điều khiển cơ bản

**Mục tiêu:** Hiểu cấu trúc hệ thống và thiết lập khả năng điều khiển động cơ.

Các công việc triển khai:

- Nghiên cứu nguyên lý hoạt động của động cơ DC.
- Tìm hiểu module điều khiển L298N.
- Thiết lập kết nối vi điều khiển với driver động cơ.
- Xây dựng chương trình điều khiển tiến, lùi, rẽ và dừng.
- Làm quen với PWM (Pulse Width Modulation).
- Kiểm tra sự khác biệt giữa tốc độ hai bánh xe.
- Làm quen với Arduino IDE và MicroPython.

**Kiến thức trọng tâm:** GPIO, PWM, H-Bridge, Motor Driver, Digital Output.

**Kết quả của giai đoạn:** Xây dựng nền tảng điều khiển động cơ phục vụ tích hợp cảm biến và thuật toán dò line.

### Giai đoạn 2 — Tháng thứ hai: Tích hợp cảm biến và thuật toán dò line cơ bản

**Mục tiêu:** Robot phản ứng theo vị trí của vạch dẫn đường.

Các công việc triển khai:

- Kết nối hệ thống 5 cảm biến hồng ngoại.
- Đọc và hiển thị tín hiệu cảm biến.
- Phân tích các mẫu tín hiệu từ S1 đến S5.
- Xây dựng bảng điều kiện để nhận biết hướng lệch.
- Lập trình thuật toán điều khiển theo điều kiện.
- Thử nghiệm đi thẳng, rẽ nhẹ và cua gắt.
- Phát hiện các tình huống mất vạch dẫn đường.

Các vấn đề nghiên cứu và khắc phục:

- Cảm biến nhận line không ổn định.
- Robot chuyển đổi liên tục giữa đi thẳng và mất line.
- Động cơ bị giật khi thay đổi lệnh.
- Robot không bắt kịp line ở các khúc cua.
- Khó lựa chọn mức PWM phù hợp cho từng tình huống.

**Kiến thức trọng tâm:** Digital Input, Sensor Calibration, Threshold, Rule-Based Control, Signal Filtering.

**Kết quả của giai đoạn:** Hình thành thuật toán dò line cơ bản và xác định những hạn chế cần cải tiến.

### Giai đoạn 3 — Tháng thứ ba: PID, điều hướng và tối ưu hóa

**Mục tiêu:** Nâng cao khả năng điều khiển và xử lý tình huống.

Các công việc triển khai:

- Nghiên cứu bộ điều khiển PID.
- Xây dựng công thức tính sai lệch từ 5 cảm biến.
- Điều chỉnh tốc độ hai bánh theo sai lệch.
- Nghiên cứu giảm tốc khi vào cua (Adaptive Speed).
- Phát triển cơ chế nhận dạng giao lộ.
- Thử nghiệm quy tắc ưu tiên hướng di chuyển.
- Xây dựng thuật toán tìm lại line khi mất tín hiệu.
- Nghiên cứu cơ chế quay đầu để trở lại đường cũ.
- So sánh phương pháp PID và điều khiển theo điều kiện.
- Tiếp tục điều chỉnh phần mềm theo kết quả chạy thực tế.

**Kiến thức trọng tâm:** PID Control, Feedback Control, State Machine, Junction Detection, Line Recovery, Differential Drive.

**Kết quả của giai đoạn:** Phát triển các phiên bản thuật toán nâng cao; các chức năng vẫn cần kiểm thử và hiệu chỉnh trên phần cứng thực tế.

---

## 7. Thuật toán điều khiển (Control Algorithms)

### 7.1. Điều khiển theo điều kiện — Rule-Based Control

Phiên bản ban đầu sử dụng các câu lệnh `if / else` để xác định hướng di chuyển.

Ví dụ:

| Trạng thái 5 cảm biến | Hành động |
|---|---|
| 00100 | Đi thẳng |
| 01000 | Rẽ trái nhẹ |
| 00010 | Rẽ phải nhẹ |
| 10000 | Rẽ trái gấp |
| 00001 | Rẽ phải gấp |
| 00000 | Kích hoạt xử lý mất line |

Trong bảng này, `1` biểu thị mắt cảm biến phát hiện vạch đen.

**Ưu điểm:** Đơn giản, dễ triển khai và dễ kiểm tra.

**Hạn chế:** Điều khiển theo từng mức rời rạc, dễ gây giật và không tối ưu khi đường cong thay đổi liên tục.

### 7.2. Điều khiển PID — Proportional Integral Derivative

Bộ PID xác định mức hiệu chỉnh tốc độ dựa trên sai lệch vị trí vạch:

\[
u(t)=K_pe(t)+K_i\int e(t)dt+K_d\frac{de(t)}{dt}
\]

Trong đó:

- **Kp:** Proportional Gain — hệ số tỉ lệ.
- **Ki:** Integral Gain — hệ số tích phân.
- **Kd:** Derivative Gain — hệ số vi phân.
- **e(t):** Error — sai lệch vị trí line.
- **u(t):** Control Output — tín hiệu hiệu chỉnh.

Tốc độ hai bánh được điều chỉnh theo sai lệch:

```text
Left Motor  = Base Speed + Correction
Right Motor = Base Speed - Correction
```

Mục tiêu của PID là giảm sai lệch và nâng cao khả năng bám line. Hiệu quả thực tế phụ thuộc vào việc hiệu chỉnh thông số và chất lượng dữ liệu cảm biến.

### 7.3. Điều khiển tốc độ thích nghi — Adaptive Speed

Tốc độ robot được điều chỉnh theo độ lệch của vạch.

- Đường thẳng: Duy trì tốc độ cơ bản.
- Cua nhẹ: Giảm tốc và tăng độ chênh lệch hai bánh.
- Cua gắt: Giảm tốc mạnh hoặc xoay tại chỗ.
- Mất line: Chuyển sang chế độ tìm kiếm và phục hồi.

### 7.4. Xử lý giao lộ — Junction Handling

Các kịch bản được nghiên cứu:

- Ngã ba chữ T.
- Ngã tư chữ thập.
- Nhánh trái.
- Nhánh phải.
- Đường cụt.
- Quay đầu.

Chiến lược lựa chọn hướng thử nghiệm:

**Left → Straight → Right → U-Turn**

Đây là quy tắc ưu tiên đơn giản, chưa phải thuật toán giải mê cung hoàn chỉnh.

### 7.5. Khôi phục khi mất line — Line Recovery

Quy trình xử lý:

```text
LINE FOLLOWING
      |
      v
LINE DETECTED?
      |
      +---- YES ---> CONTINUE
      |
      +---- NO
              |
              v
       CONFIRM LINE LOSS
              |
              v
       SEARCH NEARBY LINE
              |
              +---- FOUND ---> RESUME
              |
              +---- NOT FOUND
                       |
                       v
                  TRY U-TURN
                       |
                       +-- FOUND --> RESUME
                       |
                       +-- FAILED --> STOP
```

Việc quay đầu được ước lượng bằng thời gian và khả năng phát hiện lại vạch. Hệ thống hiện chưa đo trực tiếp góc quay 180°.

---

## 8. Công cụ phát triển (Development Tools)

| Công cụ | Mục đích |
|---|---|
| Arduino IDE | Viết, biên dịch và nạp chương trình C/C++ |
| MicroPython | Lập trình và thử nghiệm ESP32 bằng Python |
| Thonny | Chạy và gỡ lỗi chương trình MicroPython |
| Proteus | Thiết kế sơ đồ và thử nghiệm mô phỏng |
| Serial Monitor | Theo dõi tín hiệu và trạng thái điều khiển |
| GitHub | Quản lý mã nguồn và lịch sử phát triển |

---

## 9. Thử nghiệm và đánh giá (Testing and Evaluation)

Các nội dung kiểm thử được xây dựng để đánh giá:

1. Khả năng nhận diện vạch của từng mắt cảm biến.
2. Chiều quay và tốc độ hai động cơ.
3. Khả năng bám đường thẳng.
4. Khả năng xử lý đường cong và cua 90°.
5. Độ dao động của robot khi điều khiển.
6. Khả năng nhận diện giao lộ.
7. Khả năng tìm lại line khi mất vạch.
8. Độ ổn định khi thay đổi tốc độ.

**Trạng thái:** Đang thử nghiệm và tiếp tục cải thiện. Chưa công bố các chỉ số định lượng như sai lệch RMS, thời gian hoàn thành, tỉ lệ nhận diện giao lộ hoặc tỉ lệ phục hồi line khi chưa có bộ dữ liệu đo kiểm xác thực.

---

## 10. Các vấn đề và bài học kỹ thuật (Engineering Challenges)

Trong quá trình phát triển, dự án tập trung vào những vấn đề thực tế:

**Motor Control:** Nguồn, đấu nối, PWM và chiều quay ảnh hưởng trực tiếp đến khả năng điều khiển.

**Sensor Reliability:** Cảm biến cần được kiểm tra về mức logic, khoảng cách đến mặt sân và ngưỡng phát hiện.

**Control Response:** Tốc độ xe và chu kỳ xử lý phải phù hợp với khả năng phản ứng của hệ thống.

**Sharp Turns:** Robot cần có chiến lược riêng cho đường cong gắt và các đoạn line bị gián đoạn.

**Software Structure:** Việc chia chương trình thành các chức năng riêng biệt giúp dễ kiểm tra, bảo trì và nâng cấp.

**Real-World Testing:** Mô phỏng chỉ hỗ trợ một phần quá trình thiết kế. Kết quả thực nghiệm trên robot thật là cơ sở để đánh giá hiệu năng.

---

## 11. Lộ trình nâng cấp (Future Development Roadmap)

- [ ] Hiệu chỉnh ngưỡng và độ ổn định của 5 cảm biến.
- [ ] Chuẩn hóa phương pháp kiểm thử các mức tốc độ.
- [ ] Tối ưu PID theo dữ liệu thực nghiệm.
- [ ] Xây dựng bộ điều khiển với thời gian lấy mẫu ổn định.
- [ ] Cải thiện khả năng phân biệt cua gắt và giao lộ.
- [ ] Đánh giá độ chính xác của các thao tác quay.
- [ ] Bổ sung encoder cho động cơ.
- [ ] Tích hợp IMU để đo góc quay.
- [ ] Xây dựng thuật toán ghi nhớ đường đi.
- [ ] Nghiên cứu giải mê cung bằng Flood Fill hoặc các thuật toán phù hợp.
- [ ] Tự động lưu và phân tích dữ liệu thử nghiệm.
- [ ] Hoàn thiện tài liệu kỹ thuật và video demo.

---

## 12. Kết luận (Conclusion)

Dự án Line Following Robot là quá trình nghiên cứu và phát triển hệ thống robot di động, kết hợp giữa phần cứng, lập trình nhúng và lý thuyết điều khiển.

Trong 3 tháng phát triển, trọng tâm của dự án đã mở rộng từ điều khiển động cơ cơ bản sang xử lý cảm biến, điều khiển PID, nhận diện các tình huống trên đường chạy và xây dựng khả năng tự phục hồi khi mất line.

Dự án tiếp tục được hoàn thiện thông qua chu trình:

**Design → Implement → Test → Evaluate → Improve**

*Thiết kế → Triển khai → Thử nghiệm → Đánh giá → Cải tiến.*

Mục tiêu không chỉ là tạo ra một robot có thể di chuyển theo vạch, mà còn xây dựng một hệ thống có cấu trúc rõ ràng, dễ nâng cấp và có thể đánh giá bằng các kết quả thực nghiệm.

---

**Project:** Line Following Robot  
**Development Duration:** 3 Months  
**Current Status:** Research & Development  
**Repository:** `xe-do-line`

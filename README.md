# GDKTPL Exam Studio Pro - Hệ Thống Tạo Đề Thi Học Sinh Giỏi Môn GDKT&PL

Ứng dụng chuyên nghiệp phục vụ giáo viên bồi dưỡng và ra đề thi **Học sinh giỏi (HSG) Cấp Trường, Cấp Thành phố** môn **Giáo dục Kinh tế và Pháp luật (GDKT&PL)** theo Chương trình GDPT 2018 (chuẩn năm học 2026 - 2027).

---

## 🌟 Điểm nổi bật của ứng dụng

1. **Chuẩn 100% Ma trận Công văn thi HSG**:
   - Tự động phân bổ đúng ma trận: **Phần I (40 câu TN 4 lựa chọn)** + **Phần II (8 câu tình huống Đúng/Sai gồm 32 ý)**.
   - Kiểm soát chính xác số câu mức độ **Biết (7) - Hiểu (16) - Vận dụng (17)** ở Phần I và **Biết (7) - Hiểu (13) - Vận dụng (12)** ở Phần II.
   - Đầy đủ 3 mạch kiến thức: **Lớp 10** (Pháp luật nước CHXHCN Việt Nam), **Lớp 11** (Bình đẳng, Dân chủ, Tự do), **Lớp 12** (Tăng trưởng KT, Hội nhập KTQT, Bảo hiểm & An sinh xã hội).

2. **Nạp thêm tài liệu bên ngoài linh hoạt**:
   - Tải lên tệp Word (`.docx`), Text (`.txt`) bất kỳ: giáo án, đề thi các tỉnh thành khác. Hệ thống tự động bóc tách và phân loại câu hỏi nạp vào kho.
   - Dán nhanh đoạn câu hỏi hoặc tình huống thời sự.

3. **Tự động lấy ngữ liệu từ Internet & Tích hợp AI**:
   - **Trích xuất từ Web**: Nhập đường link bài báo (Báo Tuổi Trẻ, Báo Lao Động, Cổng TTĐT Chính phủ, Thư viện pháp luật), ứng dụng tự động cào bài viết về làm ngữ liệu đề thi.
   - **Trí tuệ nhân tạo (AI Engine)**: Tự động sáng tạo các câu hỏi tình huống thực tế mới bám sát các vụ án, sự kiện kinh tế xã hội mới nhất.

4. **Tích hợp cập nhật Luật Bảo hiểm xã hội 2024 (Hiệu lực từ 01/07/2025)**:
   - Cập nhật 8 điểm cải cách cốt lõi: Giảm thời gian đóng hưởng lương hưu xuống 15 năm, mở rộng đối tượng đóng BHXH bắt buộc, xử lý trốn đóng BHXH,...
   - Tích hợp bảng định lượng mức phạt vi phạm hành chính (Nghị định 144, 125, 100) và điều khoản Bộ luật Hình sự.

5. **Xuất file Microsoft Word (.docx) chuyên nghiệp**:
   - **Bản Đề thi cho học sinh**: Không đáp án, có khung thông tin thí sinh, phân trang chuẩn.
   - **Bản Hướng dẫn chấm & Đáp án chi tiết**: Bảng tra đáp án nhanh Phần I, bảng ma trận Đúng/Sai Phần II, cùng căn cứ pháp lý và phân tích lời giải chi tiết.
   - **Bản Đặc tả Ma trận**: Phục vụ nộp tổ chuyên môn.
   - **Trộn 4 Mã đề ngẫu nhiên** (Mã 097, 098, 099, 100) với thuật toán xáo trộn câu và phương án khoa học.

---

## 🚀 Hướng dẫn khởi chạy

Chỉ cần **click đúp vào tệp `Start_App.bat`** trong thư mục gốc của dự án:
```bash
d:\Kim-Tuyen-làm đề HSG\Start_App.bat
```
Trình duyệt web sẽ tự động mở giao diện ứng dụng tại địa chỉ: `http://localhost:8088`.

---

## 📁 Cấu trúc thư mục

```
d:\Kim-Tuyen-làm đề HSG\
├── Start_App.bat                   # Tệp bấm đúp để chạy ứng dụng ngay
├── README.md                       # Hướng dẫn sử dụng chi tiết
├── TL làm đề HSG/                  # Thư mục chứa 6 tài liệu gốc tham khảo
├── app/
│   ├── main.py                     # Máy chủ FastAPI & API điều khiển
│   ├── generator.py                # Thuật toán sinh đề chuẩn ma trận & trộn mã đề
│   ├── docx_exporter.py            # Module tạo file Word .docx chuyên nghiệp
│   ├── importer.py                 # Module nạp file docx/txt và lấy bài viết từ Web
│   ├── ai_engine.py                # Module AI sinh câu hỏi tình huống thời sự
│   ├── data/
│   │   ├── question_bank.json      # Ngân hàng câu hỏi chuẩn hóa
│   │   ├── knowledge_base.json     # Kho lý thuyết, Luật BHXH 2024 & bảng mức phạt
│   │   └── user_materials/         # Nơi lưu các tài liệu giáo viên tải lên thêm
│   ├── static/
│   │   ├── index.html              # Giao diện chính của ứng dụng
│   │   ├── style.css               # Thiết kế đồ họa hiện đại (Glassmorphism)
│   │   └── app.js                  # Xử lý tương tác xem trước, đổi câu, xuất file
│   └── output/                     # Nơi lưu các file Word xuất ra
```

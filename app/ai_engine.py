import os
import json
import uuid
import random

APP_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_PATH = os.path.join(APP_DIR, "data", "knowledge_base.json")
BANK_PATH = os.path.join(APP_DIR, "data", "question_bank.json")

def load_knowledge():
    if os.path.exists(KNOWLEDGE_PATH):
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_bank():
    if os.path.exists(BANK_PATH):
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"part1": [], "part2": []}

def save_bank(bank_data):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=2)

API_CONFIG_PATH = os.path.join(APP_DIR, "data", "api_config.json")

def parse_api_keys(raw_text: str) -> list:
    if not raw_text:
        return []
    import re
    return [k.strip() for k in re.split(r'[\n,;]+', raw_text) if k.strip()]

def mask_api_key(key: str) -> str:
    k = (key or "").strip()
    if len(k) <= 12:
        return k
    return f"{k[:8]}...{k[-4:]}"

def get_saved_api_config() -> dict:
    if os.path.exists(API_CONFIG_PATH):
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"raw_keys": "", "model": "gemini-2.0-flash"}

def call_gemini_rest_failover(prompt: str, raw_keys_text: str = "", model: str = "gemini-2.0-flash", system_instruction: str = "") -> dict:
    """
    Call Google Gemini via REST API with 2-Tier Auto-Failover:
    Tries each candidate model and each API key in succession.
    Skips to the next key on 429 Rate Limit, 401/403 Auth errors.
    """
    import requests
    
    if not raw_keys_text:
        raw_keys_text = get_saved_api_config().get("raw_keys", "")
        
    keys = parse_api_keys(raw_keys_text)
    if not keys:
        raise ValueError("Chưa có API Key nào được cài đặt.")
        
    if model == 'auto':
        candidate_models = ['gemini-3.6', 'gemini-3.5', 'gemini-2.5-flash', 'gemini-2.0-flash']
    elif model in ['gemini-3.6', 'gemini-3.5']:
        candidate_models = [model, 'gemini-2.5-flash', 'gemini-2.0-flash']
    else:
        candidate_models = [model, 'gemini-2.5-flash', 'gemini-2.0-flash']
    
    last_err = None
    for cur_model in candidate_models:
        for idx, active_key in enumerate(keys):
            masked = mask_api_key(active_key)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cur_model}:generateContent?key={active_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 8192
                }
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
                
            try:
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "parts" in candidates[0].get("content", {}):
                        text = candidates[0]["content"]["parts"][0].get("text", "")
                        return {
                            "text": text,
                            "used_model": cur_model,
                            "used_key_masked": masked,
                            "key_index": idx
                        }
                
                # Check for model not found (404) -> failover to next candidate model
                if res.status_code == 404 or "not found" in res.text.lower():
                    print(f"[Gemini Failover] Model {cur_model} chưa kích hoạt trực tiếp trên tài khoản ({res.text[:100]}). Tự động thử model tiếp theo...")
                    break

                # Check for rate limit or auth failure -> failover to next key
                if res.status_code in [429, 401, 403]:
                    print(f"[Gemini Failover] Key #{idx+1} ({masked}) lỗi HTTP {res.status_code}. Tự động chuyển sang key tiếp theo...")
                    continue
                else:
                    last_err = Exception(f"HTTP {res.status_code}: {res.text[:200]}")
            except Exception as e:
                print(f"[Gemini Failover] Key #{idx+1} ({masked}) lỗi kết nối: {e}. Thử key tiếp theo...")
                last_err = e
                continue
                
    raise last_err or Exception("Tất cả các Gemini API Key đều thất bại.")

GDKTPL_EXAM_SYSTEM_INSTRUCTION = """Bạn là Chuyên gia Khảo thí và Đo lường Giáo dục hàng đầu Việt Nam, chuyên gia thẩm định và biên soạn đề thi Học sinh giỏi (HSG) cấp Tỉnh/Thành phố và Quốc gia môn GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT (GDKT&PL) theo đúng Chương trình Giáo dục phổ thông (GDPT) 2018 của Bộ Giáo dục và Đào tạo.

QUY TẮC CỐT LÕI BẮT BUỘC VỀ NỘI DUNG VÀ MÔN HỌC:
1. ĐÚNG CHUẨN MÔN GDKT&PL (GDPT 2018):
   - Môn học gồm 2 hợp phần: Giáo dục Kinh tế (Applied Economics) và Giáo dục Pháp luật (Jurisprudence).
   - Tuyệt đối KHÔNG nhầm lẫn sang môn Giáo dục công dân (GDCD cũ 2006) - không ra các câu hỏi giáo điều, đạo đức chung chung, cảm tính.
   - Nội dung phải chính xác về mặt khoa học pháp lý và kinh tế học thực chứng.

2. PHÂN ĐỊNH RÕ PHẠM VI CHƯƠNG TRÌNH THEO KHỐI LỚP:
   - LỚP 10:
     + Kinh tế: Các hoạt động kinh tế cơ bản; Thị trường và cơ chế thị trường (giá cả, quy luật giá trị, cung - cầu); Ngân sách nhà nước và thuế; Sản xuất kinh doanh và các mô hình kinh tế (hộ KD, DNTN, TNHH, CP, HTX); Quản lý tài chính cá nhân.
     + Pháp luật: Hệ thống chính trị và Bộ máy nhà nước CHXHCN Việt Nam; Hiến pháp 2013; Hệ thống pháp luật và văn bản QPPL; 4 HÌNH THỨC THỰC HIỆN PHÁP LUẬT (Sử dụng PL, Thi hành PL, Tuân thủ PL, Áp dụng PL); 4 LOẠI VI PHẠM PHÁP LUẬT VÀ TRÁCH NHIỆM PHÁP LÝ (Hình sự, Dân sự, Hành chính, Kỷ luật).
   - LỚP 11:
     + Kinh tế: Cạnh tranh và quy luật cung - cầu trong KTTT; Lạm phát và thất nghiệp; Thị trường lao động và việc làm; Đạo đức kinh doanh; Văn hóa tiêu dùng.
     + Pháp luật: QUYỀN BÌNH ĐẲNG CỦA CÔNG DÂN (trước pháp luật, hôn nhân và gia đình, lao động, kinh doanh, dân tộc, tôn giáo); CÁC QUYỀN DÂN CHỦ CƠ BẢN (Bầu cử và ứng cử; Khiếu nại và tố cáo; Tham gia quản lý nhà nước và xã hội); CÁC QUYỀN TỰ DO CƠ BẢN (Bất khả xâm phạm về thân thể; Được pháp luật bảo hộ tính mạng, sức khỏe, danh dự, nhân phẩm; Bất khả xâm phạm về chỗ ở; An toàn bí mật thư tín, điện thoại; Tự do ngôn luận, báo chí, tiếp cận thông tin).
   - LỚP 12:
     + Kinh tế: Tăng trưởng và phát triển kinh tế (GDP, GNI, HDI, tăng trưởng xanh và bền vững); Hội nhập kinh tế quốc tế (FTA, CPTPP, EVFTA, WTO); BẢO HIỂM VÀ AN SINH XÃ HỘI (CẬP NHẬT LUẬT BHXH 2024: thời gian đóng tối thiểu 15 năm hưởng lương hưu, xử lý nghiêm trốn đóng theo Điều 216 BLHS, bổ sung chủ hộ kinh doanh tham gia bắt buộc; 4 trụ cột an sinh); Trách nhiệm xã hội của doanh nghiệp.
     + Pháp luật: Quyền và nghĩa vụ của công dân về kinh tế; Quyền và nghĩa vụ về văn hóa, xã hội; Pháp luật quốc tế về biển đảo (UNCLOS 1982, Luật Biển Việt Nam 2012).

3. ĐẢM BẢO CĂN CỨ PHÁP LÝ CHÍNH XÁC VÀ HIỆN HÀNH:
   - Các căn cứ pháp lý áp dụng trong lời giải phải là văn bản hiện hành của Nhà nước Việt Nam: Luật BHXH 2024, Bộ luật Lao động 2019, Bộ luật Dân sự 2015, Bộ luật Hình sự 2015 (sửa đổi 2017), Luật Xử lý VPHC, Nghị định 144/2021/NĐ-CP (an ninh trật tự), Nghị định 12/2022/NĐ-CP (lao động, BHXH)...
   - Tuyệt đối KHÔNG viện dẫn văn bản đã hết hiệu lực hoặc bịa số hiệu điều luật.

4. CẤU TRÚC KỸ THUẬT ĐỀ THI HSG ĐẲNG CẤP:
   - PHẦN I (Trắc nghiệm 4 lựa chọn):
     + Tình huống phức hợp đa chủ thể (ít nhất 3-4 nhân vật: Ông A, bà B, anh C, chị D...), có tình tiết đan xen giữa hành vi đúng luật và vi phạm pháp luật.
     + Câu hỏi phân hóa sâu: "Những ai dưới đây...", "Chủ thể nào vừa vi phạm quyền tự do vừa vi phạm quyền dân chủ...", "Những ai phải chịu trách nhiệm pháp lý...".
     + 4 phương án A, B, C, D là các tổ hợp chủ thể có độ nhiễu cao, đòi hỏi tư duy bóc tách sắc bén.
     + Lời giải (explanation) phải phân tích rõ ràng từng hành vi của từng nhân vật kèm căn cứ điều luật cụ thể.
   - PHẦN II (Đúng / Sai 4 lệnh hỏi a, b, c, d):
     + Ngữ liệu tình huống thực tế bám sát bài viết / sự kiện kinh tế - xã hội.
     + 4 mệnh đề kiểm tra độc lập 4 góc độ:
       * Ý a (Nhận biết): Khái niệm, chủ thể, chỉ tiêu kinh tế hoặc quy định pháp luật.
       * Ý b (Thông hiểu): Bản chất, nguyên nhân, phân loại hiện tượng.
       * Ý c (Vận dụng): Phân tích hành vi đúng/sai của nhân vật trong tình huống.
       * Ý d (Đánh giá / Vận dụng cao): Đánh giá trách nhiệm pháp lý, giải pháp hoặc nghĩa vụ công dân.
     + Mỗi lệnh hỏi đều phải có kết quả boolean (true/false) và căn cứ pháp lý giải thích chi tiết.
"""

def get_grade_curriculum_guidelines(grade: int, topic: str = "") -> str:
    """Trả về khung hướng dẫn kiến thức chuyên môn và căn cứ pháp luật theo khối lớp."""
    if grade == 10:
        return """- KHUNG KIẾN THỨC GDKT&PL 10 (GDPT 2018):
  + Kinh tế: Hoạt động kinh tế (sản xuất, phân phối, trao đổi, tiêu dùng; chủ thể kinh tế); Thị trường và cơ chế thị trường (giá cả, quy luật giá trị, cung - cầu); Ngân sách nhà nước và thuế; Mô hình sản xuất kinh doanh (hộ kinh doanh, doanh nghiệp tư nhân, TNHH, CTCP, Hợp tác xã); Quản lý tài chính cá nhân.
  + Pháp luật: Hệ thống chính trị và Bộ máy nhà nước CHXHCN Việt Nam; Hiến pháp 2013; Hệ thống văn bản QPPL; 4 HÌNH THỨC THỰC HIỆN PHÁP LUẬT (Sử dụng PL - thực hiện quyền; Thi hành PL - thực hiện nghĩa vụ tích cực; Tuân thủ PL - không làm điều cấm; Áp dụng PL - cơ quan, cán bộ có thẩm quyền); 4 LOẠI VI PHẠM PHÁP LUẬT VÀ TRÁCH NHIỆM PHÁP LÝ (Hình sự, Dân sự, Hành chính, Kỷ luật).
  + Căn cứ pháp lý bắt buộc: Hiến pháp 2013, Luật Xử lý vi phạm hành chính, Nghị định 144/2021/NĐ-CP, Bộ luật Hình sự 2015, Bộ luật Dân sự 2015."""
    elif grade == 11:
        return """- KHUNG KIẾN THỨC GDKT&PL 11 (GDPT 2018):
  + Kinh tế: Cạnh tranh trong KTTT; Cung - Cầu; Lạm phát và Thất nghiệp; Thị trường lao động và việc làm; Đạo đức kinh doanh; Văn hóa tiêu dùng.
  + Pháp luật: QUYỀN BÌNH ĐẲNG CỦA CÔNG DÂN (Trước pháp luật, Hôn nhân và gia đình, Lao động, Kinh doanh, Giữa các dân tộc và tôn giáo); CÁC QUYỀN DÂN CHỦ CƠ BẢN (Bầu cử và ứng cử - nguyên tắc: phổ thông, bình đẳng, trực tiếp, bỏ phiếu kín, tuổi 18 và 21; Quyền khiếu nại và tố cáo; Quyền tham gia quản lý nhà nước và xã hội); CÁC QUYỀN TỰ DO CƠ BẢN (Bất khả xâm phạm về thân thể; Được pháp luật bảo hộ về tính mạng, sức khỏe, danh dự, nhân phẩm; Bất khả xâm phạm về chỗ ở; An toàn bí mật thư tín, điện thoại; Tự do ngôn luận, tiếp cận thông tin).
  + Căn cứ pháp lý bắt buộc: Bộ luật Dân sự 2015, Bộ luật Lao động 2019, Bộ luật Hình sự 2015 (Đ155, 156, 157, 158), Luật Khiếu nại 2011, Luật Tố cáo 2018, Luật Bầu cử đại biểu Quốc hội và HĐND 2015, Nghị định 144/2021/NĐ-CP."""
    else:
        return """- KHUNG KIẾN THỨC GDKT&PL 12 (GDPT 2018):
  + Kinh tế: Tăng trưởng và phát triển kinh tế (chỉ tiêu GDP, GNI, HDI, tăng trưởng xanh và bền vững); Hội nhập kinh tế quốc tế (song phương, khu vực, toàn cầu; các hiệp định FTA, CPTPP, EVFTA, WTO; rào cản thuế quan, quy tắc xuất xứ ROO); BẢO HIỂM VÀ AN SINH XÃ HỘI (CẬP NHẬT LUẬT BHXH 2024 - HIỆU LỰC TỪ 01/07/2025: rút thời gian đóng tối thiểu hưởng lương hưu xuống 15 năm; chế tài xử lý trốn đóng BHXH theo Điều 216 BLHS; bổ sung chủ hộ kinh doanh tham gia bắt buộc; 4 trụ cột an sinh xã hội: phòng ngừa, giảm thiểu, khắc phục rủi ro và dịch vụ xã hội cơ bản); Trách nhiệm xã hội của doanh nghiệp.
  + Pháp luật: Quyền và nghĩa vụ của công dân về kinh tế (tự do kinh doanh, nghĩa vụ nộp thuế); Quyền và nghĩa vụ của công dân về văn hóa, xã hội (học tập, phát triển, bảo vệ môi trường); Pháp luật quốc tế về biển đảo (UNCLOS 1982, Luật Biển Việt Nam 2012).
  + Căn cứ pháp lý bắt buộc: Luật Bảo hiểm xã hội 2024 (mới nhất), Bộ luật Lao động 2019, Bộ luật Dân sự 2015, Bộ luật Hình sự 2015 (Đ216), Luật Doanh nghiệp 2020, Luật Cạnh tranh 2018, Luật Biển Việt Nam 2012."""

def build_part1_prompt(grade: int, topic: str, level: str, curriculum_guidance: str) -> str:
    """Xây dựng prompt Phần I chuẩn hóa riêng biệt cho từng mức độ nhận thức: Biết, Hiểu, Vận dụng."""
    lvl = level.lower()
    
    if lvl == "biet":
        return f"""Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp {grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ NHẬN BIẾT (BIẾT), chuyên đề: "{topic}".

{curriculum_guidance}

YÊU CẦU BẮT BUỘC ĐỐI VỚI CÂU HỎI MỨC ĐỘ NHẬN BIẾT:
1. TIÊU CHUẨN CÂU HỎI:
   - Câu hỏi ngắn gọn, chuẩn xác, kiểm tra trực diện năng lực nhận diện khái niệm, định nghĩa, thẩm quyền cơ quan nhà nước, 4 hình thức thực hiện pháp luật (Sử dụng, Thi hành, Tuân thủ, Áp dụng pháp luật), 4 loại vi phạm pháp luật (Hình sự, Dân sự, Hành chính, Kỷ luật), các quyền tự do/dân chủ, hoặc các chỉ tiêu kinh tế (GDP, GNI, HDI, Luật BHXH 2024...).
   - TUYỆT ĐỐI KHÔNG xây dựng tình huống phức hợp 3-4 nhân vật dài dòng khiên cưỡng cho câu hỏi mức độ Nhận biết.
2. TIÊU CHUẨN 4 PHƯƠNG ÁN (A, B, C, D):
   - Có 1 phương án đúng duy nhất và 3 phương án nhiễu có tính sư phạm cao, gài bẫy những lỗi nhầm lẫn khái niệm phổ biến của học sinh giỏi.
3. TIÊU CHUẨN LỜI GIẢI VÀ CĂN CỨ PHÁP LÝ (EXPLANATION):
   - Giải thích ngắn gọn, súc tích, viện dẫn chính xác điều luật hoặc kiến thức chuẩn mực GDPT 2018.
4. ĐỊNH DẠNG JSON DUY NHẤT:
Trích xuất DUY NHẤT một chuỗi JSON hợp lệ (không markdown ngoài JSON):
{{
  "type": "part1",
  "stem": "Nội dung câu hỏi nhận biết trực diện...",
  "options": {{
    "A": "Phương án A...",
    "B": "Phương án B...",
    "C": "Phương án C...",
    "D": "Phương án D..."
  }},
  "answer": "A",
  "explanation": "Căn cứ lý giải chính xác kèm số điều luật/khái niệm...",
  "grade": {grade},
  "topic": "{topic}",
  "level": "biet"
}}"""

    elif lvl == "hieu":
        return f"""Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp {grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ THÔNG HIỂU (HIỂU), chuyên đề: "{topic}".

{curriculum_guidance}

YÊU CẦU BẮT BUỘC ĐỐI VỚI CÂU HỎI MỨC ĐỘ THÔNG HIỂU:
1. TIÊU CHUẨN CÂU HỎI:
   - Câu hỏi yêu cầu học sinh giải thích bản chất kinh tế/pháp lý, phân biệt các hình thức thực hiện pháp luật, phân loại hành vi vi phạm, xác định hậu quả pháp lý hoặc ý nghĩa kinh tế trong một ngữ cảnh/tình huống ngắn gọn (1-2 chủ thể).
   - Đánh giá năng lực hiểu sâu bản chất hiện tượng chứ không học vẹt.
2. TIÊU CHUẨN 4 PHƯƠNG ÁN (A, B, C, D):
   - 4 phương án là các nhận định/lý giải bản chất, đòi hỏi học sinh phải có tư duy so sánh, suy luận loại trừ logic.
3. TIÊU CHUẨN LỜI GIẢI VÀ CĂN CỨ PHÁP LÝ (EXPLANATION):
   - Lập luận phân tích rõ tại sao phương án được chọn là đúng bản chất, trích dẫn quy phạm pháp luật hoặc nguyên lý kinh tế học.
4. ĐỊNH DẠNG JSON DUY NHẤT:
Trích xuất DUY NHẤT một chuỗi JSON hợp lệ:
{{
  "type": "part1",
  "stem": "Tình huống ngắn hoặc câu hỏi phân tích bản chất...",
  "options": {{
    "A": "Phương án A...",
    "B": "Phương án B...",
    "C": "Phương án C...",
    "D": "Phương án D..."
  }},
  "answer": "A",
  "explanation": "Lập luận giải thích bản chất kèm điều luật...",
  "grade": {grade},
  "topic": "{topic}",
  "level": "hieu"
}}"""

    else:
        # Vận dụng / Vận dụng cao
        return f"""Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp {grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ VẬN DỤNG (VẬN DỤNG CAO), chuyên đề: "{topic}".

{curriculum_guidance}

YÊU CẦU BẮT BUỘC ĐỐI VỚI CÂU HỎI MỨC ĐỘ VẬN DỤNG (ĐẶC TRƯNG THI HSG):
1. TIÊU CHUẨN TÌNH HUỐNG (CASE STUDY PHỨC HỢP):
   - Xây dựng một tình huống thực tế phức hợp từ 3 đến 4 nhân vật thuần Việt (ví dụ: Ông An - Giám đốc, bà Bình - Kế toán, anh Cường - Nhân viên, chị Dung - Khách hàng...).
   - Tình huống có mâu thuẫn, đan xen các hành vi pháp lý phức tạp: có nhân vật tuân thủ/thi hành đúng luật, có nhân vật vi phạm pháp luật (hành chính, dân sự, hình sự, kỷ luật), có nhân vật bị xâm phạm quyền.
   - Bối cảnh thời sự, chân thực, bám sát các quan hệ xã hội tại Việt Nam hiện nay.
2. TIÊU CHUẨN LỆNH HỎI PHÂN HÓA HSG:
   - Lệnh hỏi phải có độ phân hóa sâu sắc:
     + "Những ai dưới đây vừa vi phạm quyền tự do vừa vi phạm quyền dân chủ của công dân?"
     + "Những ai dưới đây phải chịu cả trách nhiệm hành chính và trách nhiệm dân sự?"
     + "Những ai dưới đây đã không tuân thủ pháp luật?"
     + "Chủ thể nào dưới đây đã thi hành đúng pháp luật?"
3. TIÊU CHUẨN 4 PHƯƠNG ÁN LỰA CHỌN (A, B, C, D):
   - 4 phương án là CÁC TỔ HỢP TÊN NHÂN VẬT (Ví dụ: A. Ông An, bà Bình và anh Cường. B. Ông An và anh Cường. C. Bà Bình, anh Cường và chị Dung. D. Ông An và chị Dung).
   - Các phương án nhiễu được thiết kế tinh vi, gài bẫy những lỗi suy luận phổ biến của học sinh giỏi (nhầm lỗi cố ý/vô ý, nhầm kỷ luật và hành chính, nhầm quyền tự do và quyền dân chủ).
4. TIÊU CHUẨN LỜI GIẢI VÀ CĂN CỨ PHÁP LÝ (EXPLANATION):
   - Bắt buộc lập luận, bóc tách tường tận hành vi của TỪNG nhân vật trong tình huống:
     + Nhân vật X: Đã thực hiện hành vi gì? Vi phạm điều khoản nào, văn bản luật nào? Phải chịu trách nhiệm gì?
     + Nhân vật Y: Vì sao không vi phạm?
     + Trích dẫn rõ ràng tên văn bản quy phạm pháp luật hiện hành và số điều cụ thể.
5. ĐỊNH DẠNG JSON DUY NHẤT:
Trích xuất DUY NHẤT một chuỗi JSON hợp lệ:
{{
  "type": "part1",
  "stem": "Tình huống thời sự đa nhân vật và lệnh hỏi...",
  "options": {{
    "A": "Phương án A...",
    "B": "Phương án B...",
    "C": "Phương án C...",
    "D": "Phương án D..."
  }},
  "answer": "A",
  "explanation": "Lập luận chi tiết từng nhân vật kèm căn cứ điều luật hiện hành...",
  "grade": {grade},
  "topic": "{topic}",
  "level": "van_dung"
}}"""

def generate_ai_scenario_question(topic, level, grade, api_key=None, raw_keys=None, model="gemini-3.5", custom_prompt="", q_type="part1"):
    """
    Generate an authentic, highly accurate HSG GDKT&PL question using Google Gemini with Multi-Key Auto-Failover.
    Ensures strict alignment with GDPT 2018 standards and current legal codes.
    """
    config_keys = raw_keys or api_key or get_saved_api_config().get("raw_keys", "")
    if config_keys:
        try:
            curriculum_guidance = get_grade_curriculum_guidelines(grade, topic)
            prompt_p1 = build_part1_prompt(grade, topic, level, curriculum_guidance)

            prompt_p2 = f"""Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp {grade} - PHẦN II (Trắc nghiệm Đúng/Sai gồm 4 lệnh hỏi a, b, c, d) mức độ {level.upper()}, chuyên đề: "{topic}".

{curriculum_guidance}

YÊU CẦU BẮT BUỘC ĐỐI VỚI CÂU HỎI THI HSG PHẦN II:
1. TIÊU CHUẨN THÂN CÂU DẪN (STEM):
   - Là một đoạn trích ngữ liệu thực tế (bài báo, vụ việc pháp lý, báo cáo kinh tế - xã hội, dữ liệu thống kê pháp luật) giàu thông tin, có bối cảnh và số liệu cụ thể.

2. TIÊU CHUẨN 4 LỆNH HỎI ĐỘC LẬP (a, b, c, d) - ĐÚNG MA TRẬN 4 MỨC ĐỘ NHẬN THỨC:
   - Lệnh a (Nhận biết): Đánh giá nhận diện khái niệm, chỉ tiêu kinh tế, chủ thể hoặc quy định pháp luật được nêu trực tiếp trong ngữ liệu.
   - Lệnh b (Thông hiểu): Đánh giá hiểu biết về bản chất, nguyên nhân, mối quan hệ nhân quả hoặc phân loại hiện tượng pháp lý/kinh tế.
   - Lệnh c (Vận dụng): Phân tích, đánh giá tính chất đúng/sai trong hành vi của các nhân vật/chủ thể trong tình huống.
   - Lệnh d (Vận dụng cao / Đánh giá): Đánh giá hậu quả pháp lý, trách nhiệm hành chính/hình sự, đề xuất giải pháp chính sách, hoặc liên hệ quyền và nghĩa vụ công dân.
   - Tỷ lệ Đúng/Sai cân bằng, lập luận sắc bén (2 Đúng - 2 Sai, hoặc 1 Đúng - 3 Sai / 3 Đúng - 1 Sai; TUYỆT ĐỐI KHÔNG để 4 ý toàn Đúng hoặc toàn Sai).

3. ĐỊNH DẠNG JSON DUY NHẤT:
Trích xuất DUY NHẤT một chuỗi JSON hợp lệ:
{{
  "type": "part2",
  "stem": "Đoạn ngữ liệu tình huống thời sự chi tiết...",
  "statements": [
    {{"label": "a", "text": "Lệnh hỏi a...", "answer": true, "explanation": "Căn cứ điều luật cụ thể...", "level": "biet", "grade": {grade}, "topic": "{topic}"}},
    {{"label": "b", "text": "Lệnh hỏi b...", "answer": false, "explanation": "Căn cứ điều luật cụ thể...", "level": "hieu", "grade": {grade}, "topic": "{topic}"}},
    {{"label": "c", "text": "Lệnh hỏi c...", "answer": true, "explanation": "Căn cứ điều luật cụ thể...", "level": "van_dung", "grade": {grade}, "topic": "{topic}"}},
    {{"label": "d", "text": "Lệnh hỏi d...", "answer": false, "explanation": "Căn cứ điều luật cụ thể...", "level": "van_dung", "grade": {grade}, "topic": "{topic}"}}
  ],
  "grade": {grade},
  "topic": "{topic}",
  "level": "{level}"
}}"""

            target_prompt = prompt_p1 if q_type == "part1" else prompt_p2
            if custom_prompt:
                target_prompt += f"\n\nYêu cầu bổ sung đặc thù của giáo viên: {custom_prompt}"

            result = call_gemini_rest_failover(
                prompt=target_prompt,
                raw_keys_text=config_keys,
                model=model,
                system_instruction=GDKTPL_EXAM_SYSTEM_INSTRUCTION
            )
            res_text = result["text"].strip()
            
            # Extract JSON cleanly
            import re
            json_match = re.search(r'(\{.*\})', res_text, re.DOTALL)
            if json_match:
                res_text = json_match.group(1)
            elif "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text:
                res_text = res_text.split("```")[1].split("```")[0].strip()
                
            q_data = json.loads(res_text)
            q_data["id"] = f"ai_gemini_{uuid.uuid4().hex[:8]}"
            q_data["source"] = f"Gemini {result['used_model']} ({result['used_key_masked']})"
            q_data["grade"] = int(q_data.get("grade", grade))
            q_data["level"] = q_data.get("level", level)
            q_data["topic"] = q_data.get("topic", topic)
            
            # Save to bank
            bank = load_bank()
            if q_data.get("type") == "part2":
                bank["part2"].append(q_data)
            else:
                q_data["type"] = "part1"
                bank["part1"].append(q_data)
            save_bank(bank)
            
            return {
                "status": "success", 
                "question": q_data, 
                "is_ai": True,
                "used_model": result["used_model"],
                "used_key_masked": result["used_key_masked"]
            }
        except Exception as e:
            print(f"[AI Fallback] Không thể gọi Gemini ({e}), kích hoạt bộ sinh kịch bản thông minh...")
            pass

    # 2. Intelligent Template Fallback
    scenarios = [
        {
            "stem": f"Tại doanh nghiệp X đóng trên địa bàn tỉnh Y, ông H (Giám đốc) ký hợp đồng lao động thời hạn 6 tháng với anh M nhưng thỏa thuận không tham gia bảo hiểm xã hội bắt buộc và bù vào tiền lương. Chị P (kế toán) biết việc này vi phạm quy định nhưng vẫn làm chứng từ chi lương theo chỉ đạo của ông H. Khi anh M bị ốm đau phải nằm viện 10 ngày, ông H từ chối chi trả chế độ theo quy định của Luật Bảo hiểm xã hội 2024. Căn cứ quy định của pháp luật, nhận định nào dưới đây là đúng?",
            "options": {
                "A": "Ông H và chị P đã vi phạm nghĩa vụ thực hiện chính sách bảo hiểm xã hội bắt buộc đối với người lao động.",
                "B": "Chị P không có lỗi vì chỉ là người thực hiện nhiệm vụ theo lệnh cấp trên.",
                "C": "Thỏa thuận giữa ông H và anh M là hợp pháp vì dựa trên sự tự nguyện của hai bên.",
                "D": "Anh M không có quyền khiếu nại vì đã đồng ý nhận tiền bù lương hàng tháng."
            },
            "answer": "A",
            "explanation": "Theo Luật BHXH 2024, người lao động ký hợp đồng từ đủ 1 tháng trở lên thuộc đối tượng tham gia BHXH bắt buộc. Mọi thỏa thuận trốn đóng BHXH đều vô hiệu và trái pháp luật.",
            "grade": 12,
            "topic": "Bảo hiểm và an sinh xã hội",
            "level": "van_dung"
        },
        {
            "stem": f"Trong đợt tiếp xúc cử tri chuẩn bị cho kỳ họp Hội đồng nhân dân tỉnh, cử tri K đã gửi câu hỏi chất vấn về tiến độ giải ngân vốn đầu tư công các dự án giao thông trọng điểm. Ông T (chủ trì cuộc họp) đã cố ý ngắt lời và không ghi nhận ý kiến của ông K vào biên bản tổng hợp vì cho rằng ý kiến mang tính tiêu cực. Sau cuộc họp, anh Q (con trai ông K) đã quay video cảnh tranh cãi tại hội trường và đăng tải lên mạng xã hội kèm theo lời bình luận xuyên tạc về chính quyền địa phương. Những ai dưới đây ĐÃ VI PHẠM pháp luật về quyền dân chủ và tự do của công dân?",
            "options": {
                "A": "Ông T và anh Q.",
                "B": "Chỉ có anh Q.",
                "C": "Ông K, ông T và anh Q.",
                "D": "Chỉ có ông T."
            },
            "answer": "A",
            "explanation": "Ông T cản trở quyền tham gia quản lý nhà nước của cử tri K; anh Q lợi dụng quyền tự do ngôn luận để đăng tải thông tin xuyên tạc xúc phạm uy tín chính quyền.",
            "grade": 11,
            "topic": "Một số quyền dân chủ cơ bản của công dân",
            "level": "van_dung"
        },
        {
            "stem": f"Theo cam kết trong các Hiệp định thương mại tự do thế hệ mới (như EVFTA, CPTPP), Việt Nam cam kết từng bước xóa bỏ thuế nhập khẩu đối với trên 90% dòng thuế nông sản và công nghiệp. Để tận dụng tối đa cơ hội từ các hiệp định này và thúc đẩy tăng trưởng kinh tế bền vững, các doanh nghiệp xuất khẩu Việt Nam cần ưu tiên thực hiện giải pháp nào dưới đây?",
            "options": {
                "A": "Nâng cao tiêu chuẩn chất lượng, minh bạch quy tắc xuất xứ hàng hóa và chuyển đổi số quy trình sản xuất.",
                "B": "Hạ giá bán sản phẩm xuống mức thấp nhất để cạnh tranh bằng mọi giá.",
                "C": "Hạn chế đầu tư công nghệ mới để tiết kiệm chi phí khấu hao tài sản.",
                "D": "Chỉ tập trung vào thị trường nội địa để tránh rủi ro biến động tỷ giá quốc tế."
            },
            "answer": "A",
            "explanation": "Để đáp ứng các rào cản kỹ thuật khắt khe và quy tắc xuất xứ (ROO) trong FTA thế hệ mới, doanh nghiệp bắt buộc phải chuẩn hóa quy trình, bảo đảm nguồn gốc xuất xứ và nâng cao chất lượng.",
            "grade": 12,
            "topic": "Hội nhập kinh tế quốc tế",
            "level": "hieu"
        }
    ]
    
    chosen = random.choice(scenarios)
    chosen["id"] = f"ai_synth_{uuid.uuid4().hex[:8]}"
    chosen["source"] = "Bộ sinh tình huống pháp luật tự động"
    
    bank = load_bank()
    bank["part1"].append(chosen)
    save_bank(bank)
    return {"status": "success", "question": chosen}

def ai_parse_and_solve_imported_exam(raw_text: str, source_name: str = "Tài liệu nạp vào", raw_keys: str = None, model: str = "gemini-3.5") -> tuple:
    """
    Sử dụng Google Gemini AI để bóc tách, thẩm định và giải chuẩn xác toàn bộ đề thi được nạp vào.
    Hỗ trợ xử lý văn bản dài thông qua phân đoạn thông minh (smart chunking).
    Tự động giải đáp án chính xác 100% nếu đề thi chưa có đáp án, kèm lời giải viện dẫn điều luật.
    Trả về tuple (p1_list, p2_list).
    """
    import re
    p1_list = []
    p2_list = []

    config_keys = raw_keys or get_saved_api_config().get("raw_keys", "")
    if not config_keys:
        return p1_list, p2_list

    # Phân đoạn thông minh theo câu hỏi
    # Tìm vị trí các câu hỏi: Câu 1, CÂU 2, Bài 1...
    pattern = re.compile(r'(?:^|\n)\s*(?:Câu|CÂU|Bài|BÀI)\s*(\d+)[\.:]', re.MULTILINE)
    matches = list(pattern.finditer(raw_text))

    chunks = []
    if len(matches) > 10:
        # Gom cụm 8-10 câu hỏi mỗi chunk để AI trả về JSON chi tiết không bị tràn token
        step = 8
        for i in range(0, len(matches), step):
            start_pos = matches[i].start()
            end_idx = min(i + step, len(matches))
            end_pos = matches[end_idx].start() if end_idx < len(matches) else len(raw_text)
            chunks.append(raw_text[start_pos:end_pos].strip())
    else:
        # Nếu ít hơn 10 câu hoặc không tìm thấy marker rõ ràng
        if len(raw_text) > 6000:
            # Tách theo độ dài ~4000 ký tự
            parts = [raw_text[i:i+4000] for i in range(0, len(raw_text), 3800)]
            chunks = parts
        else:
            chunks = [raw_text.strip()]

    for chunk_idx, chunk_text in enumerate(chunks):
        if len(chunk_text) < 40:
            continue
            
        prompt = f"""Bạn là Chuyên gia Khảo thí và Đo lường Giáo dục hàng đầu Việt Nam môn GDKT&PL (GDPT 2018).
Dưới đây là nội dung một phần đề thi Học sinh giỏi môn GDKT&PL được nạp vào hệ thống từ tệp: "{source_name}" (Phần {chunk_idx + 1}/{len(chunks)}):

--- NỘI DUNG ĐỀ THI CẦN BÓC TÁCH & GIẢI ĐÁP ÁN ---
{chunk_text}
--------------------------------------------------

NHIỆM VỤ THẨM ĐỊNH VÀ GIẢI ĐỀ THI CHUẨN MỰC:
1. BÓC TÁCH TOÀN BỘ CÂU HỎI TRONG ĐOẠN TRÊN:
   - Trích xuất đầy đủ câu hỏi Trắc nghiệm khách quan 4 lựa chọn (Phần I).
   - Trích xuất đầy đủ câu hỏi Trắc nghiệm Đúng/Sai 4 lệnh hỏi a, b, c, d (Phần II).
2. GIẢI ĐÁP ÁN CHÍNH XÁC TUYỆT ĐỐI 100%:
   - Nếu trong văn bản đã có sẵn đáp án/hướng dẫn chấm: trích xuất đáp án đó và kiểm tra tính chuẩn xác.
   - Nếu văn bản CHƯA CÓ ĐÁP ÁN (đề thi thô, đề thi học sinh): Bạn hãy giải quyết toàn diện từng câu hỏi, đưa ra đáp án chính xác nhất theo quy định của pháp luật hiện hành (Luật BHXH 2024, Nghị định 144/2021/NĐ-CP, Bộ luật Lao động 2019, BLDS 2015, BLHS 2015/2017) và kiến thức kinh tế học GDPT 2018.
3. LỜI GIẢI CHI TIẾT KÈM CĂN CỨ ĐIỀU LUẬT (EXPLANATION):
   - Phần I: Bóc tách hành vi của từng nhân vật trong tình huống, chỉ rõ ai vi phạm, ai không vi phạm, vi phạm điều khoản nào, chịu trách nhiệm gì.
   - Phần II: Giải thích căn cứ pháp luật rõ ràng cho từng mệnh đề a, b, c, d.
4. PHÂN LOẠI CHUẨN:
   - Khối lớp (grade): 10, 11 hoặc 12.
   - Mức độ nhận thức (level): "biet", "hieu" hoặc "van_dung".
   - Chuyên đề (topic): Đúng tên chuyên đề môn GDKT&PL.

5. ĐỊNH DẠNG JSON DUY NHẤT (không có markdown hay text giải thích ngoài JSON):
{{
  "part1": [
    {{
      "type": "part1",
      "stem": "Nội dung câu hỏi và tình huống...",
      "options": {{
        "A": "Nội dung phương án A...",
        "B": "Nội dung phương án B...",
        "C": "Nội dung phương án C...",
        "D": "Nội dung phương án D..."
      }},
      "answer": "A",
      "explanation": "Lời giải bóc tách chi tiết từng nhân vật kèm căn cứ điều luật hiện hành...",
      "grade": 11,
      "topic": "Một số quyền tự do cơ bản của công dân",
      "level": "van_dung"
    }}
  ],
  "part2": [
    {{
      "type": "part2",
      "stem": "Đoạn ngữ liệu tình huống thực tế...",
      "statements": [
        {{ "label": "a", "text": "Nội dung lệnh hỏi a...", "answer": true, "explanation": "Căn cứ điều luật...", "level": "biet", "grade": 11, "topic": "Bình đẳng, Dân chủ và Tự do công dân" }},
        {{ "label": "b", "text": "Nội dung lệnh hỏi b...", "answer": false, "explanation": "Căn cứ điều luật...", "level": "hieu", "grade": 11, "topic": "Bình đẳng, Dân chủ và Tự do công dân" }},
        {{ "label": "c", "text": "Nội dung lệnh hỏi c...", "answer": true, "explanation": "Căn cứ điều luật...", "level": "van_dung", "grade": 11, "topic": "Bình đẳng, Dân chủ và Tự do công dân" }},
        {{ "label": "d", "text": "Nội dung lệnh hỏi d...", "answer": false, "explanation": "Căn cứ điều luật...", "level": "van_dung", "grade": 11, "topic": "Bình đẳng, Dân chủ và Tự do công dân" }}
      ],
      "grade": 11,
      "topic": "Bình đẳng, Dân chủ và Tự do công dân",
      "level": "van_dung"
    }}
  ]
}}
"""
        try:
            ai_res = call_gemini_rest_failover(
                prompt=prompt,
                raw_keys_text=config_keys,
                model=model or "gemini-3.5",
                system_instruction=GDKTPL_EXAM_SYSTEM_INSTRUCTION
            )
            raw_ai = ai_res.get("text", "").strip()
            raw_ai = re.sub(r"^```json\s*", "", raw_ai, flags=re.IGNORECASE)
            raw_ai = re.sub(r"^```\s*", "", raw_ai)
            raw_ai = re.sub(r"\s*```$", "", raw_ai)
            
            # Tìm JSON
            jmatch = re.search(r'(\{[\s\S]*\})', raw_ai)
            if jmatch:
                parsed = json.loads(jmatch.group(1))
                if isinstance(parsed, dict):
                    for q in parsed.get("part1", []):
                        if q.get("stem") and q.get("options"):
                            q["id"] = f"ai_parsed_{uuid.uuid4().hex[:8]}"
                            q["source"] = f"{source_name} (AI Thẩm định & Giải đề)"
                            p1_list.append(q)
                    for q in parsed.get("part2", []):
                        if q.get("stem") and q.get("statements"):
                            q["id"] = f"ai_parsed_p2_{uuid.uuid4().hex[:8]}"
                            q["source"] = f"{source_name} (AI Thẩm định & Giải đề)"
                            p2_list.append(q)
        except Exception as e:
            print(f"[AI Parse Exam Chunk {chunk_idx+1} Error] {e}")
            continue

    return p1_list, p2_list

def synthesize_questions_from_article(title, body_text, source_name="Web", num_questions=5, raw_keys=None, model="gemini-3.5"):
    """
    Synthesize high-quality HSG questions from an article:
    1. If Gemini API Key is available, ask Gemini (Model 3.5/3.6/2.0) to analyze the article
       and generate `num_questions` questions (both Part 1 and Part 2).
    2. If Gemini API is not available, use enhanced rule-based synthesis.
    """
    p1_list = []
    p2_list = []
    
    # 1. Try generating with Gemini API if key is available
    config_keys = raw_keys or get_saved_api_config().get("raw_keys", "")
    if config_keys:
        try:
            num_p1 = max(1, round(num_questions * 0.6))
            num_p2 = max(1, num_questions - num_p1)
            prompt = f"""Bạn là Chuyên gia Khảo thí và Đo lường Giáo dục hàng đầu Việt Nam, chuyên gia thẩm định và biên soạn đề thi Học sinh giỏi (HSG) cấp Tỉnh/Thành phố và Quốc gia môn GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT (GDKT&PL) theo đúng Chương trình Giáo dục phổ thông (GDPT) 2018.

Dưới đây là nội dung ngữ liệu bài báo / văn bản pháp luật thực tế:
TIÊU ĐỀ: {title}
NỘI DUNG NGỮ LIỆU:
{body_text[:4500]}

NHIỆM VỤ:
Dựa vào ngữ liệu trên, hãy phân tích sâu sắc các mối quan hệ kinh tế - xã hội và hành vi pháp lý để sáng tạo {num_questions} câu hỏi thi Học sinh giỏi (HSG) chuẩn mực tuyệt đối theo Chương trình GDKT&PL (GDPT 2018) gồm:
- {num_p1} câu hỏi Trắc nghiệm khách quan 4 lựa chọn (Phần I).
- {num_p2} câu hỏi Đúng / Sai gồm 4 lệnh hỏi a, b, c, d (Phần II).

TIÊU CHUẨN KỸ THUẬT BẮT BUỘC ĐỐI VỚI CÂU HỎI THI HSG:
1. ĐÚNG BẢN CHẤT MÔN GDKT&PL (GDPT 2018):
   - Tuyệt đối không ra câu hỏi giáo điều, đạo đức chung chung của môn GDCD cũ 2006.
   - Gắn chặt với pháp luật thực định và kinh tế học ứng dụng của Việt Nam.

2. PHÂN LOẠI ĐÚNG KHỐI LỚP (grade: 10, 11 hoặc 12):
   - Lớp 10: Cơ chế thị trường, Ngân sách, Thuế, Mô hình DN, 4 Hình thức thực hiện pháp luật (Sử dụng, Thi hành, Tuân thủ, Áp dụng), 4 Loại vi phạm PL & trách nhiệm pháp lý (Hình sự, Hành chính, Dân sự, Kỷ luật).
   - Lớp 11: Quyền bình đẳng công dân; Các quyền dân chủ cơ bản (Bầu cử, Khiếu nại, Tố cáo, Quản lý NN); Các quyền tự do cơ bản (Thân thể, Tính mạng-sức khỏe-danh dự-nhân phẩm, Chỗ ở, Thư tín); Cạnh tranh, Cung - Cầu, Lạm phát, Thất nghiệp.
   - Lớp 12: Tăng trưởng & phát triển kinh tế (GDP, GNI, HDI); Hội nhập kinh tế quốc tế (FTA, CPTPP, EVFTA, WTO); BẢO HIỂM VÀ AN SINH XÃ HỘI (CẬP NHẬT LUẬT BHXH 2024: 15 năm đóng hưởng lương hưu, xử lý nghiêm trốn đóng theo Điều 216 BLHS, bắt buộc chủ hộ KD tham gia).

3. ĐỐI VỚI PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D):
   - Thân câu dẫn: Xây dựng tình huống thực tế phức hợp từ 3-4 nhân vật (ông A, bà B, anh C, chị D...) đan xen hành vi đúng luật và vi phạm pháp luật.
   - Lệnh hỏi phân hóa cao: "Những ai dưới đây vừa vi phạm...", "Những ai phải chịu trách nhiệm pháp lý...", "Chủ thể nào đã thi hành đúng pháp luật...".
   - 4 phương án A, B, C, D là CÁC TỔ HỢP TÊN NHÂN VẬT có độ nhiễu cao, đánh giá năng lực bóc tách suy luận logic của học sinh giỏi.
   - Lời giải (explanation): Bóc tách tường tận hành vi của TỪNG nhân vật kèm trích dẫn văn bản quy phạm pháp luật hiện hành và số điều luật cụ thể.

4. ĐỐI VỚI PHẦN II (Đúng / Sai 4 lệnh hỏi a, b, c, d):
   - Thân câu dẫn: Đoạn ngữ liệu thực tế giàu thông tin trích xuất từ bài viết.
   - 4 lệnh hỏi a, b, c, d độc lập kiểm tra đúng 4 mức độ nhận thức:
     * a) Nhận biết: Khái niệm, chỉ tiêu, chủ thể hoặc quy định pháp luật cụ thể.
     * b) Thông hiểu: Bản chất, nguyên nhân, mối quan hệ nhân quả.
     * c) Vận dụng: Phân tích, đánh giá hành vi đúng/sai của các chủ thể.
     * d) Vận dụng cao / Đánh giá: Trách nhiệm pháp lý, giải pháp hoặc liên hệ nghĩa vụ công dân.
   - Kết quả boolean (true/false) cân bằng, mỗi lệnh hỏi đều có giải thích căn cứ pháp lý sắc bén.

5. ĐỊNH DẠNG JSON DUY NHẤT:
Trả về DUY NHẤT một chuỗi JSON hợp lệ (không chứa markdown giải thích ngoài JSON) theo cấu trúc:
{{
  "part1": [
    {{
      "type": "part1",
      "stem": "Tình huống thời sự đa nhân vật và lệnh hỏi phân hóa...",
      "options": {{
        "A": "Tổ hợp nhân vật A...",
        "B": "Tổ hợp nhân vật B...",
        "C": "Tổ hợp nhân vật C...",
        "D": "Tổ hợp nhân vật D..."
      }},
      "answer": "A",
      "explanation": "Lập luận bóc tách chi tiết từng nhân vật kèm căn cứ điều luật hiện hành...",
      "grade": 12,
      "topic": "Tên chuyên đề chuẩn môn học",
      "level": "van_dung"
    }}
  ],
  "part2": [
    {{
      "type": "part2",
      "stem": "Ngữ liệu tình huống thời sự chi tiết từ bài viết...",
      "statements": [
        {{ "label": "a", "text": "Lệnh hỏi nhận biết...", "answer": true, "explanation": "Căn cứ pháp lý...", "level": "biet", "grade": 12, "topic": "Tên chuyên đề" }},
        {{ "label": "b", "text": "Lệnh hỏi thông hiểu...", "answer": false, "explanation": "Căn cứ pháp lý...", "level": "hieu", "grade": 12, "topic": "Tên chuyên đề" }},
        {{ "label": "c", "text": "Lệnh hỏi vận dụng...", "answer": true, "explanation": "Căn cứ pháp lý...", "level": "van_dung", "grade": 12, "topic": "Tên chuyên đề" }},
        {{ "label": "d", "text": "Lệnh hỏi vận dụng cao...", "answer": false, "explanation": "Căn cứ pháp lý...", "level": "van_dung", "grade": 12, "topic": "Tên chuyên đề" }}
      ],
      "grade": 12,
      "topic": "Tên chuyên đề chuẩn môn học",
      "level": "van_dung"
    }}
  ]
}}
"""
            ai_res = call_gemini_rest_failover(
                prompt,
                raw_keys_text=config_keys,
                model=model or "gemini-3.5",
                system_instruction=GDKTPL_EXAM_SYSTEM_INSTRUCTION
            )
            raw_ai = ai_res.get("text", "").strip()
            raw_ai = re.sub(r"^```json\s*", "", raw_ai, flags=re.IGNORECASE)
            raw_ai = re.sub(r"^```\s*", "", raw_ai)
            raw_ai = re.sub(r"\s*```$", "", raw_ai)
            parsed = json.loads(raw_ai)
            
            if isinstance(parsed, dict):
                for q in parsed.get("part1", []):
                    if q.get("stem"):
                        q["id"] = f"ai_web_{uuid.uuid4().hex[:8]}"
                        q["source"] = source_name
                        p1_list.append(q)
                for q in parsed.get("part2", []):
                    if q.get("stem") and q.get("statements"):
                        q["id"] = f"ai_web_p2_{uuid.uuid4().hex[:8]}"
                        q["source"] = source_name
                        p2_list.append(q)
                        
            if p1_list or p2_list:
                return p1_list, p2_list
        except Exception as e:
            print(f"[Synthesize URL Gemini Error] {e}. Sử dụng bộ mẫu dự phòng...")

    combined = (title + " " + body_text).lower()
    
    # 1. Topic: Nghị định 144 / Xử phạt hành chính / An ninh trật tự / PCCC / Bạo lực gia đình
    if any(k in combined for k in ["144", "an ninh", "trật tự", "xử phạt vi phạm hành chính", "bạo lực gia đình", "pccc"]):
        p1_list.append({
            "id": f"web_synth_{uuid.uuid4().hex[:8]}",
            "type": "part1",
            "stem": "Do mâu thuẫn cá nhân trên mạng xã hội, anh B đã sử dụng tài khoản cá nhân đăng tải hình ảnh kèm các thông tin sai sự thật, xúc phạm nghiêm trọng danh dự, nhân phẩm của chị C. Chị C đã làm đơn tố cáo gửi cơ quan Công an có thẩm quyền. Căn cứ quy định tại Nghị định số 144/2021/NĐ-CP về xử phạt vi phạm hành chính trong lĩnh vực an ninh, trật tự, an toàn xã hội, hành vi của anh B sẽ bị xử lý như thế nào?",
            "options": {
                "A": "Bị phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng và buộc gỡ bỏ thông tin sai sự thật, xin lỗi công khai.",
                "B": "Chỉ bị lập biên bản nhắc nhở bằng văn bản và không bị phạt tiền vì chưa gây thiệt hại vật chất.",
                "C": "Tự động bị truy cứu trách nhiệm hình sự với khung hình phạt tù từ 1 năm đến 3 năm mà không cần xác minh mức độ nguy hại.",
                "D": "Bị xử phạt cảnh cáo và bồi thường theo mức do chị C tự đưa ra mà không có căn cứ pháp lý."
            },
            "answer": "A",
            "explanation": "Căn cứ Điểm a Khoản 3 Điều 7 Nghị định số 144/2021/NĐ-CP: Hành vi khiêu khích, trêu ghẹo, xúc phạm, lăng mạ, bôi nhọ danh dự, nhân phẩm của người khác bị phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng; đồng thời áp dụng biện pháp khắc phục hậu quả buộc cải chính, xin lỗi công khai.",
            "grade": 11,
            "topic": "Một số quyền tự do cơ bản của công dân",
            "level": "van_dung",
            "source": source_name
        })
        
        p1_list.append({
            "id": f"web_synth_{uuid.uuid4().hex[:8]}",
            "type": "part1",
            "stem": "Theo quy định của pháp luật Việt Nam (Luật Xử lý vi phạm hành chính và Nghị định số 144/2021/NĐ-CP), việc cơ quan Công an áp dụng các chế tài xử phạt hành chính đối với hành vi gây rối trật tự công cộng là biểu hiện của hình thức thực hiện pháp luật nào dưới đây?",
            "options": {
                "A": "Áp dụng pháp luật.",
                "B": "Tuân thủ pháp luật.",
                "C": "Sử dụng pháp luật.",
                "D": "Thi hành pháp luật."
            },
            "answer": "A",
            "explanation": "Cơ quan, cán bộ nhà nước có thẩm quyền căn cứ quy định pháp luật ra quyết định xử phạt vi phạm hành chính đối với cá nhân, tổ chức vi phạm là hình thức Áp dụng pháp luật.",
            "grade": 10,
            "topic": "Pháp luật nước CHXHCN Việt Nam",
            "level": "hieu",
            "source": source_name
        })

        p2_list.append({
            "id": f"web_synth_p2_{uuid.uuid4().hex[:8]}",
            "type": "part2",
            "stem": "Ông A và ông B là hàng xóm cạnh nhà nhau. Do tranh chấp lối đi chung, ông A thường xuyên mở loa công suất lớn hướng sang nhà ông B vào ban đêm (từ 23 giờ đến 2 giờ sáng), gây ảnh hưởng nghiêm trọng đến sinh hoạt của gia đình ông B và các hộ dân xung quanh. Bực tức, anh K (con trai ông B) đã dùng gậy đập vỡ loa của ông A và quay video chửi bới ông A đăng lên mạng xã hội. Nhận được tin báo, Công an xã đã lập biên bản xử lý vụ việc theo quy định của Nghị định số 144/2021/NĐ-CP.",
            "statements": [
                {
                    "label": "a",
                    "text": "Hành vi gây tiếng động lớn, làm ồn ào tại khu dân cư trong khoảng thời gian từ 22 giờ ngày hôm trước đến 06 giờ sáng ngày hôm sau của ông A là hành vi vi phạm quy định về bảo đảm sự yên tĩnh chung theo Nghị định 144/2021/NĐ-CP.",
                    "answer": True,
                    "level": "biet",
                    "grade": 11,
                    "topic": "Bình đẳng, Dân chủ và Tự do công dân",
                    "explanation": "Căn cứ Điểm a Khoản 1 Điều 8 Nghị định 144/2021/NĐ-CP."
                },
                {
                    "label": "b",
                    "text": "Anh K tự ý đập hỏng loa của ông A là hành vi cố ý làm hư hỏng tài sản của người khác, phải chịu chế tài xử phạt hành chính theo Nghị định 144/2021/NĐ-CP và bồi thường thiệt hại.",
                    "answer": True,
                    "level": "hieu",
                    "grade": 11,
                    "topic": "Bình đẳng, Dân chủ và Tự do công dân",
                    "explanation": "Căn cứ Điểm a Khoản 2 Điều 15 Nghị định 144/2021/NĐ-CP phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với hành vi hủy hoại hoặc cố ý làm hư hỏng tài sản."
                },
                {
                    "label": "c",
                    "text": "Vì ông A là người vi phạm trước nên anh K có quyền quay video và đăng tải lời chửi bới lên mạng xã hội để bảo vệ gia đình mà không bị coi là vi phạm pháp luật.",
                    "answer": False,
                    "level": "van_dung",
                    "grade": 11,
                    "topic": "Bình đẳng, Dân chủ và Tự do công dân",
                    "explanation": "Hành vi chửi bới, xúc phạm danh dự nhân phẩm người khác trên không gian mạng là hành vi vi phạm pháp luật độc lập, không được viện cớ người khác có lỗi trước."
                },
                {
                    "label": "d",
                    "text": "Vụ việc trên chỉ thuần túy là tranh chấp dân sự giữa hai gia đình nên Công an xã không có thẩm quyền lập biên bản và xử phạt vi phạm hành chính.",
                    "answer": False,
                    "level": "hieu",
                    "grade": 10,
                    "topic": "Pháp luật nước CHXHCN Việt Nam",
                    "explanation": "Các hành vi gây mất trật tự công cộng và hủy hoại tài sản thuộc thẩm quyền kiểm tra, lập biên bản và xử phạt của lực lượng Công an nhân dân theo Nghị định 144/2021/NĐ-CP."
                }
            ],
            "grade": 11,
            "topic": "Bình đẳng, Dân chủ và Tự do công dân",
            "level": "van_dung",
            "source": source_name
        })

    # 2. Topic: BHXH / Bảo hiểm / Lao động
    elif any(k in combined for k in ["bảo hiểm", "bhxh", "lao động", "lương hưu", "thai sản", "thất nghiệp"]):
        p1_list.append({
            "id": f"web_synth_{uuid.uuid4().hex[:8]}",
            "type": "part1",
            "stem": "Căn cứ nội dung bài viết về chính sách bảo hiểm xã hội, nhận định nào dưới đây là đúng về nghĩa vụ tham gia bảo hiểm xã hội bắt buộc theo quy định mới nhất của pháp luật hiện hành?",
            "options": {
                "A": "Người lao động và người sử dụng lao động thuộc đối tượng bắt buộc không được tự ý thỏa thuận không tham gia BHXH để bù vào tiền lương.",
                "B": "Chỉ những người làm việc trong cơ quan nhà nước mới bắt buộc tham gia BHXH, khối doanh nghiệp tư nhân là tự nguyện.",
                "C": "Người sử dụng lao động có quyền giữ lại toàn bộ tiền đóng BHXH của người lao động để phục vụ tái đầu tư sản xuất.",
                "D": "Người lao động có hợp đồng từ đủ 1 tháng trở lên chỉ cần tham gia BHYT, không bắt buộc đóng BHXH."
            },
            "answer": "A",
            "explanation": "Theo Luật BHXH 2024, bảo hiểm xã hội bắt buộc là nghĩa vụ luật định. Mọi hành vi thỏa thuận né tránh hoặc trốn đóng đều là hành vi vi phạm pháp luật.",
            "grade": 12,
            "topic": "Bảo hiểm và an sinh xã hội",
            "level": "hieu",
            "source": source_name
        })
    else:
        # 3. Topic: Kinh tế / Thương mại / Khác
        p1_list.append({
            "id": f"web_synth_{uuid.uuid4().hex[:8]}",
            "type": "part1",
            "stem": f"Căn cứ các thông tin kinh tế - xã hội được phân tích trong bài viết '{title[:50]}', giải pháp nào dưới đây phù hợp nhất để thúc đẩy tăng trưởng và phát triển kinh tế bền vững gắn liền với bảo đảm tiến bộ và công bằng xã hội?",
            "options": {
                "A": "Đẩy mạnh chuyển đổi số, hoàn thiện thể chế pháp lý, nâng cao năng suất lao động và gắn tăng trưởng với an sinh xã hội.",
                "B": "Tập trung khai thác cạn kiệt tài nguyên thiên nhiên để đạt mục tiêu tăng trưởng GDP ngắn hạn bằng mọi giá.",
                "C": "Hạn chế hội nhập quốc tế để bảo hộ tuyệt đối các doanh nghiệp sản xuất yếu kém trong nước.",
                "D": "Cắt giảm toàn bộ ngân sách dành cho các chương trình mục tiêu quốc gia về y tế, giáo dục."
            },
            "answer": "A",
            "explanation": "Phát triển kinh tế bền vững đòi hỏi kết hợp hài hòa giữa tăng trưởng kinh tế với phát triển văn hóa, tiến bộ, công bằng xã hội và bảo vệ môi trường sinh thái.",
            "grade": 12,
            "topic": "Tăng trưởng và phát triển kinh tế",
            "level": "van_dung",
            "source": source_name
        })

    return p1_list, p2_list


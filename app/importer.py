import os
import re
import json
import uuid
import requests
from bs4 import BeautifulSoup
from docx import Document

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(APP_DIR, "data", "question_bank.json")
USER_MATERIALS_DIR = os.path.join(APP_DIR, "data", "user_materials")
os.makedirs(USER_MATERIALS_DIR, exist_ok=True)

def load_bank():
    if os.path.exists(BANK_PATH):
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"part1": [], "part2": []}

def save_bank(bank_data):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=2)

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_vals:
                full_text.append(" | ".join(row_vals))
    return "\n".join(full_text)

def classify_text(stem, opts_text=""):
    combined = (stem + " " + opts_text).lower()
    
    kt12_kw = ["gdp", "gni", "tăng trưởng", "phát triển kinh tế", "hội nhập", "fta", "cptpp", "evfta", 
               "wto", "asean", "thuế quan", "fdi", "oda", "bảo hiểm", "bhxh", "bhyt", "an sinh", "thất nghiệp", "hưu trí", "thai sản"]
    pl10_kw = ["quy phạm pháp luật", "văn bản luật", "văn bản dưới luật", "ngành luật", "chế định pháp luật",
               "tuân thủ pháp luật", "thi hành pháp luật", "sử dụng pháp luật", "áp dụng pháp luật", 
               "đặc trưng của pháp luật", "tính quy phạm phổ biến", "tính quyền lực", "tính xác định chặt chẽ"]
    
    score_kt12 = sum(1 for kw in kt12_kw if kw in combined)
    score_pl10 = sum(1 for kw in pl10_kw if kw in combined)
    
    if score_kt12 > score_pl10:
        grade = 12
        topic = "Kinh tế và An sinh xã hội 12"
    elif score_pl10 > 0:
        grade = 10
        topic = "Pháp luật nước CHXHCN Việt Nam"
    else:
        grade = 11
        topic = "Bình đẳng, Dân chủ và Tự do công dân"
        
    if any(k in combined for k in ["những ai", "ông a", "bà b", "anh m", "chị n", "xử phạt", "phạt tù", "vi phạm"]) or len(stem) > 250:
        level = "van_dung"
    elif any(k in combined for k in ["vì sao", "nhận định", "ý nghĩa", "phân biệt", "thể hiện"]):
        level = "hieu"
    else:
        level = "biet"
        
    return grade, topic, level

def extract_answer_map(text: str) -> dict:
    """Trích xuất bảng đáp án từ văn bản nếu có (Ví dụ: 1.A, 2-B, Câu 1: C, hoặc bảng đáp án cuối đề)."""
    ans_map = {}
    # Tìm các cụm dạng "1. A", "1-A", "Câu 1: A", "1: A"
    matches = re.finditer(r'(?:(?:Câu|CÂU)\s*)?(\d{1,3})[\.\s:\-_]+([A-D])(?![a-zA-Z0-9])', text)
    for m in matches:
        q_num = int(m.group(1))
        ans = m.group(2).upper()
        if 1 <= q_num <= 120 and q_num not in ans_map:
            ans_map[q_num] = ans
    return ans_map

def parse_questions_from_text(text, source_name="Tài liệu tải lên"):
    p1_items = []
    p2_items = []
    
    ans_map = extract_answer_map(text)

    # Check if text contains Part II indicators (Đúng/Sai with a, b, c, d)
    p2_pattern = re.compile(r'(?:Câu|CÂU|Bài|BÀI)\s*(\d+)[\.:]\s*(.*?)(?=(?:\n(?:Câu|CÂU|Bài|BÀI)\s*\d+[\.:])|$)', re.DOTALL)
    
    for match in p2_pattern.finditer(text):
        q_num = int(match.group(1))
        q_body = match.group(2).strip()
        
        # Check if it has a), b), c), d)
        stmt_matches = list(re.finditer(r'(?:^|\n)\s*([a-d])\)\s*(.*?)(?=(?:\n\s*[a-d]\))|$)', q_body, re.DOTALL))
        if len(stmt_matches) >= 3:
            # This is a Part 2 question
            stem = q_body[:stmt_matches[0].start()].strip()
            grade, topic, level = classify_text(stem)
            statements = []
            for sm in stmt_matches:
                lbl = sm.group(1)
                st_text = sm.group(2).strip()
                s_grade, s_topic, s_level = classify_text(st_text)
                
                # Trích xuất đáp án Đúng/Sai thực tế nếu văn bản có ghi (Ví dụ: "a) ... (Đúng)", "a) ... Đúng", "a) ... [Đ]")
                ans_bool = True if lbl in ['a', 'c'] else False
                st_lower = st_text.lower()
                if re.search(r'[\(\[\s](?:đúng|đ)[\)\]\s\.]*$', st_lower):
                    ans_bool = True
                elif re.search(r'[\(\[\s](?:sai|s)[\)\]\s\.]*$', st_lower):
                    ans_bool = False

                statements.append({
                    "label": lbl,
                    "text": st_text,
                    "answer": ans_bool,
                    "level": s_level,
                    "grade": s_grade,
                    "topic": s_topic,
                    "explanation": f"Căn cứ nội dung chuyên đề {s_topic}."
                })
            p2_items.append({
                "id": f"imported_p2_{uuid.uuid4().hex[:8]}",
                "type": "part2",
                "stem": stem,
                "statements": statements,
                "grade": grade,
                "topic": topic,
                "level": level,
                "source": source_name
            })
        else:
            # Check if it has A., B., C., D. options
            opt_match = re.search(r'(?:^|\s)([A-D])\.\s+', q_body)
            if opt_match:
                stem = q_body[:opt_match.start()].strip()
                opts_str = q_body[opt_match.start():]
                opts = {}
                opt_pattern = re.compile(r'([A-D])\.\s*(.*?)(?=(?:[A-D]\.|$))', re.DOTALL)
                for o_m in opt_pattern.finditer(opts_str):
                    opts[o_m.group(1)] = o_m.group(2).strip()
                    
                grade, topic, level = classify_text(stem, " ".join(opts.values()))
                
                # Tìm đáp án thực tế: từ bảng đáp án ans_map hoặc từ inline text (Ví dụ: "Đáp án: B", "Chọn C")
                ans = ans_map.get(q_num)
                if not ans:
                    inline_match = re.search(r'(?:Đáp án|Chọn|Key|Đ/A)[\s:\.]+([A-D])', q_body, re.IGNORECASE)
                    if inline_match:
                        ans = inline_match.group(1).upper()
                    else:
                        ans = "A" # Mặc định nếu hoàn toàn không có dấu hiệu

                p1_items.append({
                    "id": f"imported_p1_{uuid.uuid4().hex[:8]}",
                    "type": "part1",
                    "stem": stem,
                    "options": opts,
                    "answer": ans,
                    "explanation": f"Căn cứ quy định pháp luật và kiến thức chuyên đề {topic}.",
                    "grade": grade,
                    "topic": topic,
                    "level": level,
                    "source": source_name
                })
                
    return p1_items, p2_items

def import_document_file(filename, file_bytes, raw_keys=None, model="gemini-3.5", use_ai_solver=True):
    save_path = os.path.join(USER_MATERIALS_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(file_bytes)
        
    if filename.lower().endswith(".docx"):
        text = extract_text_from_docx(save_path)
    elif filename.lower().endswith((".txt", ".md", ".json")):
        with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    else:
        text = ""
        
    p1 = []
    p2 = []
    is_synthesized = False
    is_ai_solved = False

    # 1. Nếu cho phép dùng AI Solver và có API Key, ưu tiên dùng AI để bóc tách và giải đề chuẩn xác 100%
    from .ai_engine import get_saved_api_config, ai_parse_and_solve_imported_exam, synthesize_questions_from_article
    config_keys = raw_keys or get_saved_api_config().get("raw_keys", "")

    if use_ai_solver and config_keys and len(text.strip()) > 80:
        try:
            ai_p1, ai_p2 = ai_parse_and_solve_imported_exam(
                raw_text=text,
                source_name=filename,
                raw_keys=config_keys,
                model=model
            )
            if ai_p1 or ai_p2:
                p1 = ai_p1
                p2 = ai_p2
                is_ai_solved = True
        except Exception as e:
            print(f"[Import Document AI Solver Error] {e}. Sử dụng bộ trích xuất nội bộ...")

    # 2. Nếu AI Solver chưa chạy hoặc không có key, dùng bộ trích xuất regex chuẩn hóa
    if not p1 and not p2:
        p1, p2 = parse_questions_from_text(text, source_name=filename)

    # 3. Nếu tài liệu là văn bản/ngữ liệu bài báo (không chứa sẵn câu hỏi trắc nghiệm), tự động sinh câu hỏi HSG từ ngữ liệu
    if not p1 and not p2 and len(text.strip()) > 80:
        p1, p2 = synthesize_questions_from_article(
            filename,
            text,
            source_name=f"Tệp: {filename}",
            num_questions=5,
            raw_keys=config_keys,
            model=model
        )
        is_synthesized = True
    
    # Lưu vào ngân hàng
    if p1 or p2:
        bank = load_bank()
        bank["part1"].extend(p1)
        bank["part2"].extend(p2)
        save_bank(bank)
    
    return {
        "filename": filename,
        "text_length": len(text),
        "imported_part1": len(p1),
        "imported_part2": len(p2),
        "total_imported": len(p1) + len(p2),
        "is_synthesized": is_synthesized,
        "is_ai_solved": is_ai_solved
    }

def import_from_url(url, num_questions=5, raw_keys=None, model="gemini-3.5", use_ai_solver=True):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=12)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Lấy tiêu đề và nội dung bài viết
        title = soup.title.string.strip() if soup.title else url
        paragraphs = soup.find_all('p')
        body_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        
        # Lưu file tài liệu tải về
        filename = f"web_{uuid.uuid4().hex[:6]}.txt"
        save_path = os.path.join(USER_MATERIALS_DIR, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(f"TITLE: {title}\nURL: {url}\n\n{body_text}")
            
        src_name = f"Web: {title[:40]}"
        p1 = []
        p2 = []
        is_synthesized = False
        is_ai_solved = False

        from .ai_engine import get_saved_api_config, ai_parse_and_solve_imported_exam, synthesize_questions_from_article
        config_keys = raw_keys or get_saved_api_config().get("raw_keys", "")

        # Kiểm tra xem web có chứa sẵn đề thi không
        if use_ai_solver and config_keys and ("câu 1" in body_text.lower() or "câu 2" in body_text.lower()):
            try:
                ai_p1, ai_p2 = ai_parse_and_solve_imported_exam(
                    raw_text=body_text,
                    source_name=src_name,
                    raw_keys=config_keys,
                    model=model
                )
                if ai_p1 or ai_p2:
                    p1 = ai_p1
                    p2 = ai_p2
                    is_ai_solved = True
            except Exception as e:
                print(f"[Import URL AI Solver Error] {e}")

        if not p1 and not p2:
            p1, p2 = parse_questions_from_text(body_text, source_name=src_name)
        
        # Nếu là bài báo thông thường, dùng AI tổng hợp câu hỏi chuẩn HSG
        if not p1 and not p2 and len(body_text) > 80:
            p1, p2 = synthesize_questions_from_article(
                title, 
                body_text, 
                source_name=src_name,
                num_questions=num_questions,
                raw_keys=config_keys,
                model=model
            )
            is_synthesized = True

        if p1 or p2:
            bank = load_bank()
            bank["part1"].extend(p1)
            bank["part2"].extend(p2)
            save_bank(bank)
            
        return {
            "status": "success",
            "title": title,
            "url": url,
            "text_length": len(body_text),
            "imported_part1": len(p1),
            "imported_part2": len(p2),
            "total_imported": len(p1) + len(p2),
            "is_synthesized": is_synthesized,
            "is_ai_solved": is_ai_solved,
            "source_name": src_name,
            "raw_text_sample": body_text[:600]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def import_raw_text(text, source_name="Văn bản dán vào", num_questions=5, raw_keys=None, model="gemini-3.5", use_ai_solver=True):
    p1 = []
    p2 = []
    is_synthesized = False
    is_ai_solved = False

    from .ai_engine import get_saved_api_config, ai_parse_and_solve_imported_exam, synthesize_questions_from_article
    config_keys = raw_keys or get_saved_api_config().get("raw_keys", "")

    # 1. Nếu bật AI Solver và có API Key, dùng AI để bóc tách và giải đề
    if use_ai_solver and config_keys and len(text.strip()) > 80:
        try:
            ai_p1, ai_p2 = ai_parse_and_solve_imported_exam(
                raw_text=text,
                source_name=source_name,
                raw_keys=config_keys,
                model=model
            )
            if ai_p1 or ai_p2:
                p1 = ai_p1
                p2 = ai_p2
                is_ai_solved = True
        except Exception as e:
            print(f"[Import Text AI Solver Error] {e}")

    # 2. Fallback regex
    if not p1 and not p2:
        p1, p2 = parse_questions_from_text(text, source_name=source_name)

    # 3. Nếu là đoạn văn bản ngữ liệu bài báo, tổng hợp câu hỏi
    if not p1 and not p2 and len(text.strip()) > 80:
        p1, p2 = synthesize_questions_from_article(
            source_name,
            text,
            source_name=source_name,
            num_questions=num_questions,
            raw_keys=config_keys,
            model=model
        )
        is_synthesized = True

    if p1 or p2:
        bank = load_bank()
        bank["part1"].extend(p1)
        bank["part2"].extend(p2)
        save_bank(bank)

    return {
        "status": "success",
        "imported_part1": len(p1),
        "imported_part2": len(p2),
        "total_imported": len(p1) + len(p2),
        "is_synthesized": is_synthesized,
        "is_ai_solved": is_ai_solved
    }


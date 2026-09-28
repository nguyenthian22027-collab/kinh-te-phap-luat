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
    from .generator import load_bank as gen_load_bank
    return gen_load_bank()

def save_bank(bank_data):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=2)

def extract_text_from_docx(file_path):
    """
    Trích xuất toàn bộ văn bản và bảng số liệu từ tệp docx THEO ĐÚNG THỨ TỰ xuất hiện.
    Bảng số liệu nằm trong câu hỏi nào sẽ được giữ nguyên vị trí trong câu hỏi đó.
    """
    doc = Document(file_path)
    blocks = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith('p'):
            from docx.text.paragraph import Paragraph
            p = Paragraph(child, doc)
            if p.text.strip():
                blocks.append(p.text.strip())
        elif child.tag.endswith('tbl'):
            from docx.table import Table
            t = Table(child, doc)
            tbl_lines = []
            for row in t.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    unique_cells = []
                    for c in cells:
                        if not unique_cells or c != unique_cells[-1]:
                            unique_cells.append(c)
                    tbl_lines.append(" | ".join(unique_cells))
            if tbl_lines:
                blocks.append("[TABLE START]\n" + "\n".join(tbl_lines) + "\n[TABLE END]")
    return "\n".join(blocks)

def classify_text(stem, opts_text=""):
    combined = (stem + " " + opts_text).lower()
    
    # 1. Từ khóa Kinh tế & An sinh xã hội 12
    kt12_kw = [
        "gdp", "gni", "hdi", "tăng trưởng", "phát triển kinh tế", "tăng trưởng xanh", 
        "hội nhập", "hội nhập kinh tế", "fta", "cptpp", "evfta", "wto", "asean", 
        "thuế quan", "fdi", "oda", "xuất khẩu", "nhập khẩu", "quy tắc xuất xứ",
        "bảo hiểm", "bhxh", "bhyt", "bảo hiểm thất nghiệp", "an sinh", "an sinh xã hội",
        "hưu trí", "thai sản", "lương hưu", "luật bảo hiểm xã hội", "trốn đóng",
        "biển đảo", "unclos", "luật biển"
    ]
    
    # 2. Từ khóa Pháp luật & Kinh tế 10
    pl10_kw = [
        "quy phạm pháp luật", "văn bản quy phạm", "văn bản luật", "ngành luật", "hệ thống pháp luật",
        "tuân thủ pháp luật", "thi hành pháp luật", "sử dụng pháp luật", "áp dụng pháp luật", 
        "hình thức thực hiện pháp luật", "đặc trưng của pháp luật", "tính quy phạm phổ biến",
        "tính quyền lực", "tính xác định chặt chẽ", "bộ máy nhà nước", "hệ thống chính trị",
        "hiến pháp 2013", "ngân sách nhà nước", "ngân sách", "thuế", "thuế thu nhập",
        "cơ chế thị trường", "sản xuất kinh doanh", "hộ kinh doanh", "hợp tác xã",
        "doanh nghiệp tư nhân", "tài chính cá nhân"
    ]

    # 3. Từ khóa Quyền công dân & Kinh tế 11
    pl11_kw = [
        "quyền bình đẳng", "bình đẳng", "hôn nhân và gia đình", "lao động",
        "quyền dân chủ", "bầu cử", "ứng cử", "khiếu nại", "tố cáo", "quản lý nhà nước",
        "quyền tự do", "bất khả xâm phạm về thân thể", "tính mạng", "sức khỏe", "danh dự", "nhân phẩm",
        "chỗ ở", "thư tín", "điện thoại", "tự do ngôn luận", "tiếp cận thông tin",
        "lạm phát", "thất nghiệp", "cạnh tranh", "cung cầu", "cung - cầu", "thị trường lao động"
    ]
    
    score_kt12 = sum(1 for kw in kt12_kw if kw in combined)
    score_pl10 = sum(1 for kw in pl10_kw if kw in combined)
    score_pl11 = sum(1 for kw in pl11_kw if kw in combined)
    
    if score_kt12 >= max(score_pl10, score_pl11) and score_kt12 > 0:
        grade = 12
        topic = "Kinh tế và An sinh xã hội 12"
    elif score_pl10 >= max(score_kt12, score_pl11) and score_pl10 > 0:
        grade = 10
        topic = "Pháp luật nước CHXHCN Việt Nam"
    else:
        grade = 11
        topic = "Bình đẳng, Dân chủ và Tự do công dân"
        
    if any(k in combined for k in ["những ai", "ông a", "bà b", "anh m", "chị n", "xử phạt", "phạt tù", "vi phạm", "trách nhiệm pháp lý"]) or len(stem) > 230:
        level = "van_dung"
    elif any(k in combined for k in ["vì sao", "nhận định", "ý nghĩa", "phân biệt", "thể hiện", "bản chất", "nguyên nhân"]):
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

def _clean_passage_bleed(text: str) -> str:
    """Xóa đoạn passage của câu tiếp theo bị dính vào cuối option/stem hiện tại."""
    passage_markers = [
        r'\n\s*Đọc đoạn thông tin',
        r'\n\s*Đọc thông tin',
        r'\n\s*Dựa vào bảng số liệu',
        r'\n\s*Dựa vào thông tin',
        r'\n\s*\[TABLE START\]',
        r'\n\s*Căn cứ Luật',       # passage dạng lý thuyết nối sang câu sau
    ]
    for marker in passage_markers:
        m = re.search(marker, text, re.IGNORECASE)
        if m:
            text = text[:m.start()]
    return text.strip()

def _table_markers_to_html(text: str) -> str:
    """Chuyển [TABLE START]...[TABLE END] thành HTML table."""
    def replace_table(m):
        content = m.group(1).strip()
        rows = [row.strip() for row in content.split('\n') if row.strip()]
        html = '<table class="stem-table">'
        for row in rows:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            # Bỏ ô chỉ chứa số thứ tự đơn độc
            cells = [c for c in cells if not re.match(r'^\d+$', c)]
            if not cells:
                continue
            html += '<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
        html += '</table>'
        return html
    return re.sub(r'\[TABLE START\](.*?)\[TABLE END\]', replace_table, text, flags=re.DOTALL)

def parse_p1_options(opts_str: str) -> dict:
    """
    Trích xuất 4 phương án A, B, C, D chuẩn xác:
    - Hỗ trợ cả nhiều dòng lẫn trên cùng 1 dòng (2 cột hoặc 4 phương án/dòng)
    - Hỗ trợ các ký hiệu: A., A), A:
    - Bảo vệ tuyệt đối không nhận nhầm tên nhân vật (anh A, ông B, chị C, anh C...)
    - Tự động dọn dẹp đoạn text dư thừa (passage bleed) ở phương án cuối
    """
    options = {}
    letters = ['A', 'B', 'C', 'D']
    opts_str = opts_str.strip()
    
    positions = {}
    curr_pos = 0
    for letter in letters:
        p = re.compile(
            rf'(?:^|(?<=\n)\s*|(?<=\t)\s*|(?<=\s\s)\s*|(?<!anh\s)(?<!chị\s)(?<!ông\s)(?<!bà\s)(?<!cô\s)(?<!thầy\s)(?<!bác\s)(?:^|[\s\n])){letter}[\.\:\)]\s+'
        )
        m = p.search(opts_str[curr_pos:])
        if m:
            start_idx = curr_pos + m.start()
            content_idx = curr_pos + m.end()
            positions[letter] = (start_idx, content_idx)
            curr_pos = content_idx

    found_letters = [l for l in letters if l in positions]
    for idx, letter in enumerate(found_letters):
        start = positions[letter][1]
        if idx + 1 < len(found_letters):
            end = positions[found_letters[idx + 1]][0]
            val = opts_str[start:end].strip()
        else:
            val = opts_str[start:].strip()
            
        val = _clean_passage_bleed(val)
        if val:
            options[letter] = val

    # Bổ sung nhãn nếu thiếu
    for l in letters:
        if l not in options:
            options[l] = f"(Phương án {l})"
            
    return options

def find_p1_options_start(text: str):
    """
    Xác định vị trí bắt đầu của khối phương án trắc nghiệm A, B, C, D (chữ in HOA).
    Một câu hỏi được coi là Trắc nghiệm Phần I nếu tìm thấy phương án A và sau đó là B, C
    (hoặc ít nhất A, B, C hoa).
    Trả về vị trí bắt đầu của phương án A nếu hợp lệ, ngược lại trả về None.
    """
    p_a = re.compile(
        r'(?:^|(?<=\n)\s*|(?<=\s\s)\s*|(?<=\t)\s*|(?<!anh\s)(?<!chị\s)(?<!ông\s)(?<!bà\s)(?<!cô\s)(?<!thầy\s)(?<!bác\s)(?:^|[\s\n]))A[\.\:\)]\s+'
    )
    m_a = p_a.search(text)
    if not m_a:
        return None
    
    pos_a = m_a.start()
    after_a = text[m_a.end():]
    
    p_b = re.compile(
        r'(?:^|(?<=\n)\s*|(?<=\s\s)\s*|(?<=\t)\s*|(?<!anh\s)(?<!chị\s)(?<!ông\s)(?<!bà\s)(?<!cô\s)(?<!thầy\s)(?<!bác\s)(?:^|[\s\n]))B[\.\:\)]\s+'
    )
    m_b = p_b.search(after_a)
    if not m_b:
        return None
        
    pos_b = m_a.end() + m_b.end()
    after_b = text[pos_b:]
    
    p_c = re.compile(
        r'(?:^|(?<=\n)\s*|(?<=\s\s)\s*|(?<=\t)\s*|(?<!anh\s)(?<!chị\s)(?<!ông\s)(?<!bà\s)(?<!cô\s)(?<!thầy\s)(?<!bác\s)(?:^|[\s\n]))C[\.\:\)]\s+'
    )
    m_c = p_c.search(after_b)
    if not m_c:
        return None
        
    return pos_a

def detect_text_clusters(text: str):
    """
    Phát hiện các khối câu hỏi chùm trong văn bản:
    Tìm mẫu: (Đọc thông tin / Dựa vào thông tin... câu X đến câu Y)
    Trả về dict: {q_num: {cluster_id, cluster_passage, cluster_header, cluster_order, cluster_size}}
    """
    cluster_map = {}
    pattern = re.compile(
        r'((?:Đọc\s+(?:đoạn\s+)?thông\s+tin|Dựa\s+vào\s+thông\s+tin|Đọc\s+ngữ\s+liệu)[^\n]*?(?:trả\s+lời|cho\s+biết)?[^\n]*?(?:câu|từ\s+câu)\s*(\d+)[\s,vàđến\-]+(?:câu\s*)?(\d+)[^\n]*)\n(.*?)(?=(?:Câu|CÂU|Bài|BÀI)\s*\d+\s*[\.:\)])',
        re.DOTALL | re.IGNORECASE
    )
    for m in pattern.finditer(text):
        header = m.group(1).strip()
        try:
            start_q = int(m.group(2))
            end_q = int(m.group(3))
        except (ValueError, TypeError):
            continue
        passage = m.group(4).strip()
        
        passage = re.sub(r'^[-\s\*\•]+', '', passage).strip()
        if not passage or start_q >= end_q:
            continue
            
        cluster_id = f"cluster_imp_{start_q}_{end_q}_{uuid.uuid4().hex[:6]}"
        size = end_q - start_q + 1
        for idx, q_n in enumerate(range(start_q, end_q + 1), 1):
            cluster_map[q_n] = {
                "cluster_id": cluster_id,
                "cluster_passage": passage,
                "cluster_header": header,
                "cluster_order": idx,
                "cluster_size": size
            }
    return cluster_map

def parse_questions_from_text(text, source_name="Tài liệu tải lên"):
    p1_items = []
    p2_items = []
    
    ans_map = extract_answer_map(text)
    clusters_info = detect_text_clusters(text)

    # Tách ranh giới câu hỏi: "Câu N:" hoặc "Câu N." — lookahead câu tiếp hoặc hết file
    # Thêm lookahead chặn "Đọc thông tin..." không bị ăn vào nội dung câu
    q_pattern = re.compile(
        r'(?:Câu|CÂU|Bài|BÀI)\s*(\d+)\s*[\.:\)]\s*(.*?)(?=(?:\n\s*(?:Câu|CÂU|Bài|BÀI)\s*\d+\s*[\.:\)])|$)',
        re.DOTALL
    )
    
    for match in q_pattern.finditer(text):
        q_num = int(match.group(1))
        q_body = match.group(2).strip()
        
        # Loại bỏ passage "Đọc thông tin..." bị kéo theo nếu chưa có câu mới rõ ràng
        q_body = _clean_passage_bleed(q_body)
        if not q_body:
            continue
        
        # Chuyển bảng số liệu
        q_body = _table_markers_to_html(q_body)

        # 1. ƯU TIÊN KIỂM TRA PHẦN I (TRẮC NGHIỆM 4 PHƯƠNG ÁN A, B, C, D HOA)
        # Bất kể câu hỏi có liệt kê các ý nhỏ a), b), c), d), e), g), h)... trong thân câu hỏi,
        # nếu ở cuối có phương án A, B, C, D thì 100% LÀ PHẦN I (không bao giờ nhầm sang Đúng/Sai).
        p1_opt_start = find_p1_options_start(q_body)

        if p1_opt_start is not None:
            stem = _clean_passage_bleed(q_body[:p1_opt_start].strip())
            opts_str = q_body[p1_opt_start:]
            opts = parse_p1_options(opts_str)
            
            if stem and opts.get("A") and opts.get("A") != "(Phương án A)":
                grade, topic, level = classify_text(stem, " ".join(opts.values()))
                
                needs_review = False
                ans = ans_map.get(q_num)
                if not ans:
                    # Tìm đáp án inline dạng "Đáp án: C", "Key: C", "Chọn C", "Đ/A: C"
                    inline_match = re.search(r'(?:Đáp\s*án|Chọn|Key|Đ/?A|D/?A)[\s:\.\-\(]+([A-D])(?!\w)', q_body, re.IGNORECASE)
                    if inline_match:
                        ans = inline_match.group(1).upper()
                    else:
                        # Kiểm tra option có đánh dấu * (A*. hoặc A* hoặc A.)
                        star_match = re.search(r'([A-D])[\*]\.?', q_body)
                        if star_match:
                            ans = star_match.group(1)
                        else:
                            ans = "A"
                            needs_review = True

                p1_item = {
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
                }
                if needs_review:
                    p1_item["needs_review"] = True
                if q_num in clusters_info:
                    cinfo = clusters_info[q_num]
                    p1_item["cluster_id"] = cinfo["cluster_id"]
                    p1_item["cluster_passage"] = cinfo["cluster_passage"]
                    p1_item["cluster_header"] = cinfo["cluster_header"]
                    p1_item["cluster_order"] = cinfo["cluster_order"]
                    p1_item["cluster_size"] = cinfo["cluster_size"]

                p1_items.append(p1_item)
                continue

        # 2. NẾU KHÔNG CÓ PHƯƠNG ÁN A, B, C, D HOA -> MỚI XÉT ĐẾN CÂU ĐÚNG/SAI (PHẦN II)
        stmt_matches = list(re.finditer(
            r'(?:^|\n)\s*([a-d])\)\s*(.*?)(?=(?:\n\s*[a-d]\))|$)',
            q_body, re.DOTALL
        ))
        if len(stmt_matches) >= 3:
            stem = _clean_passage_bleed(q_body[:stmt_matches[0].start()].strip())
            grade, topic, level = classify_text(stem)
            statements = []
            found_any_answer_marker = False
            for sm in stmt_matches:
                lbl = sm.group(1)
                st_text = _clean_passage_bleed(sm.group(2).strip())
                s_grade, s_topic, s_level = classify_text(st_text)
                
                st_lower = st_text.lower()
                # Ưu tiên: tìm marker đánh dấu đúng/sai trong văn bản
                if re.search(r'[\(\[\s](?:đúng|đ|true|T)[\)\]\s\.]*$', st_lower):
                    ans_bool = True
                    found_any_answer_marker = True
                elif re.search(r'[\(\[\s](?:sai|s|false|F)[\)\]\s\.]*$', st_lower):
                    ans_bool = False
                    found_any_answer_marker = True
                else:
                    # Không có marker → KHÔNG đoán mò, đặt False là placeholder
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
            if stem:
                p2_item = {
                    "id": f"imported_p2_{uuid.uuid4().hex[:8]}",
                    "type": "part2",
                    "stem": stem,
                    "statements": statements,
                    "grade": grade,
                    "topic": topic,
                    "level": level,
                    "source": source_name
                }
                # Gắn cờ cần kiểm tra nếu không phát hiện được marker đúng/sai
                if not found_any_answer_marker:
                    p2_item["needs_review"] = True
                p2_items.append(p2_item)

                
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
    
    # Không ghi đè vào kho gốc hệ thống để bảo vệ tính riêng tư của từng giáo viên
    return {
        "filename": filename,
        "text_length": len(text),
        "imported_part1": len(p1),
        "imported_part2": len(p2),
        "total_imported": len(p1) + len(p2),
        "is_synthesized": is_synthesized,
        "is_ai_solved": is_ai_solved,
        "questions": p1 + p2
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
            "raw_text_sample": body_text[:600],
            "questions": p1 + p2
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

    # Không ghi đè vào kho gốc hệ thống để bảo vệ tính riêng tư của từng giáo viên
    return {
        "status": "success",
        "imported_part1": len(p1),
        "imported_part2": len(p2),
        "total_imported": len(p1) + len(p2),
        "is_synthesized": is_synthesized,
        "is_ai_solved": is_ai_solved,
        "questions": p1 + p2
    }


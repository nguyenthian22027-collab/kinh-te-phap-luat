import json
import random
import copy
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(APP_DIR, "data", "question_bank.json")

# Standard Matrix from 'Cấu trúc MÔN GDKTPL.docx'
STANDARD_MATRIX = {
    "part1": {
        "total": 40,
        "distribution": {
            "pl_10": {"name": "Pháp luật 10", "biet": 2, "hieu": 3, "van_dung": 1, "total": 6},
            "pl_11": {"name": "Pháp luật 11", "biet": 3, "hieu": 7, "van_dung": 7, "total": 17},
            "kt_12": {"name": "Kinh tế 12", "biet": 2, "hieu": 6, "van_dung": 9, "total": 17}
        },
        "levels": {"biet": 7, "hieu": 16, "van_dung": 17}
    },
    "part2": {
        "total_items": 8,  # 8 questions, each with 4 statements = 32 statements
        "distribution": {
            "pl_10": {"name": "Pháp luật 10", "items": 2, "biet": 2, "hieu": 4, "van_dung": 2, "total": 8},
            "pl_11": {"name": "Pháp luật 11", "items": 3, "biet": 3, "hieu": 5, "van_dung": 4, "total": 12},
            "kt_12": {"name": "Kinh tế 12", "items": 3, "biet": 2, "hieu": 4, "van_dung": 6, "total": 12}
        },
        "levels": {"biet": 7, "hieu": 13, "van_dung": 12}
    }
}

def load_bank():
    if os.path.exists(BANK_PATH):
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"part1": [], "part2": []}

def save_bank(bank_data):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=2)

def get_grade_key(grade):
    if grade == 10:
        return "pl_10"
    elif grade == 11:
        return "pl_11"
    else:
        return "kt_12"

def generate_exam(preset="city_hsg", custom_config=None, exam_info=None):
    bank = load_bank()
    p1_pool = copy.deepcopy(bank.get("part1", []))
    p2_pool = copy.deepcopy(bank.get("part2", []))
    
    selected_p1 = []
    selected_p2 = []
    
    if exam_info is None:
        exam_info = {
            "exam_title": "KỲ THI CHỌN HỌC SINH GIỎI CẤP THÀNH PHỐ",
            "school_year": "2026 - 2027",
            "subject": "GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT",
            "duration": "90 phút",
            "code": "097",
            "header_left": "SỞ GIÁO DỤC VÀ ĐÀO TẠO\nTHÀNH PHỐ HẢI PHÒNG",
            "header_right": "ĐỀ THI CHÍNH THỨC\n(Đề thi gồm 48 câu, 8 trang)"
        }
        
    if preset in ["city_hsg", "school_hsg"]:
        # Select Part 1 according to matrix
        dist = STANDARD_MATRIX["part1"]["distribution"]
        for g_key, target in dist.items():
            g_num = 10 if g_key == "pl_10" else (11 if g_key == "pl_11" else 12)
            for lvl in ["biet", "hieu", "van_dung"]:
                target_count = target[lvl]
                # Filter candidates
                candidates = [q for q in p1_pool if q.get("grade") == g_num and q.get("level") == lvl and q not in selected_p1]
                if len(candidates) < target_count:
                    # fallback to any question of same grade
                    candidates += [q for q in p1_pool if q.get("grade") == g_num and q not in selected_p1 and q not in candidates]
                if len(candidates) < target_count:
                    # fallback to any question
                    candidates += [q for q in p1_pool if q not in selected_p1 and q not in candidates]
                    
                chosen = random.sample(candidates, min(target_count, len(candidates)))
                selected_p1.extend(chosen)
                
        # Fill remaining if Part 1 < 40
        while len(selected_p1) < 40 and len(p1_pool) > len(selected_p1):
            avail = [q for q in p1_pool if q not in selected_p1]
            if not avail:
                break
            selected_p1.append(random.choice(avail))
            
        # Select Part 2 according to matrix: 2 items grade 10, 3 items grade 11, 3 items grade 12
        p2_dist = STANDARD_MATRIX["part2"]["distribution"]
        for g_key, target in p2_dist.items():
            g_num = 10 if g_key == "pl_10" else (11 if g_key == "pl_11" else 12)
            target_items = target["items"]
            candidates = [q for q in p2_pool if q.get("grade") == g_num and q not in selected_p2]
            if len(candidates) < target_items:
                candidates += [q for q in p2_pool if q not in selected_p2 and q not in candidates]
            chosen = random.sample(candidates, min(target_items, len(candidates)))
            selected_p2.extend(chosen)
            
        while len(selected_p2) < 8 and len(p2_pool) > len(selected_p2):
            avail = [q for q in p2_pool if q not in selected_p2]
            if not avail:
                break
            selected_p2.append(random.choice(avail))
            
    elif preset.startswith("review_grade_"):
        req_grade = int(preset.split("_")[-1])
        # Filter questions of that grade
        g_p1 = [q for q in p1_pool if q.get("grade") == req_grade]
        g_p2 = [q for q in p2_pool if q.get("grade") == req_grade]
        selected_p1 = random.sample(g_p1, min(len(g_p1), 30))
        selected_p2 = random.sample(g_p2, min(len(g_p2), 5))
        
    elif preset == "custom" and custom_config:
        num_p1 = custom_config.get("num_part1", 40)
        num_p2 = custom_config.get("num_part2", 8)
        selected_p1 = random.sample(p1_pool, min(len(p1_pool), num_p1))
        selected_p2 = random.sample(p2_pool, min(len(p2_pool), num_p2))
    else:
        # Default fallback
        selected_p1 = random.sample(p1_pool, min(len(p1_pool), 40))
        selected_p2 = random.sample(p2_pool, min(len(p2_pool), 8))
        
    # Re-number items in order
    exam_p1 = []
    for idx, q in enumerate(selected_p1, 1):
        item = copy.deepcopy(q)
        item["exam_number"] = idx
        exam_p1.append(item)
        
    exam_p2 = []
    for idx, q in enumerate(selected_p2, 1):
        item = copy.deepcopy(q)
        item["exam_number"] = idx
        exam_p2.append(item)
        
    return {
        "info": exam_info,
        "preset": preset,
        "part1": exam_p1,
        "part2": exam_p2,
        "stats": calculate_stats(exam_p1, exam_p2)
    }

def calculate_stats(p1_list, p2_list):
    stats = {
        "part1_total": len(p1_list),
        "part2_total": len(p2_list),
        "total_questions": len(p1_list) + len(p2_list),
        "by_grade": {10: 0, 11: 0, 12: 0},
        "by_level": {"biet": 0, "hieu": 0, "van_dung": 0}
    }
    for q in p1_list:
        g = q.get("grade", 11)
        stats["by_grade"][g] = stats["by_grade"].get(g, 0) + 1
        lvl = q.get("level", "hieu")
        stats["by_level"][lvl] = stats["by_level"].get(lvl, 0) + 1
        
    for q in p2_list:
        g = q.get("grade", 11)
        stats["by_grade"][g] = stats["by_grade"].get(g, 0) + 1
        lvl = q.get("level", "van_dung")
        stats["by_level"][lvl] = stats["by_level"].get(lvl, 0) + 1
        
    return stats

def get_candidate_replacements(exam, q_id, q_type="part1"):
    bank = load_bank()
    current_ids = {q["id"] for q in exam.get("part1", [])} if q_type == "part1" else {q["id"] for q in exam.get("part2", [])}
    
    target_list = exam.get("part1", []) if q_type == "part1" else exam.get("part2", [])
    current_q = None
    for q in target_list:
        if q["id"] == q_id or str(q.get("exam_number")) == str(q_id):
            current_q = q
            break
            
    if not current_q:
        return {"status": "error", "message": "Không tìm thấy câu hỏi hiện tại trong đề."}
        
    pool = bank.get("part1", []) if q_type == "part1" else bank.get("part2", [])
    
    # 1. Exact match: same grade and level
    exact_matches = [
        q for q in pool 
        if q["id"] not in current_ids and q.get("grade") == current_q.get("grade") and q.get("level") == current_q.get("level")
    ]
    
    # 2. Same grade, other levels
    same_grade_matches = [
        q for q in pool 
        if q["id"] not in current_ids and q.get("grade") == current_q.get("grade") and q.get("level") != current_q.get("level")
    ]
    
    # 3. Other questions in bank of same type
    other_matches = [
        q for q in pool 
        if q["id"] not in current_ids and q.get("grade") != current_q.get("grade")
    ]
    
    return {
        "status": "success",
        "current_question": current_q,
        "exact_matches": exact_matches,
        "same_grade_matches": same_grade_matches,
        "other_matches": other_matches,
        "total_candidates": len(exact_matches) + len(same_grade_matches) + len(other_matches)
    }

def swap_question(exam, q_id, q_type, replacement_q_id):
    bank = load_bank()
    pool = bank.get("part1", []) if q_type == "part1" else bank.get("part2", [])
    target_list = exam.get("part1", []) if q_type == "part1" else exam.get("part2", [])
    
    replacement_q = None
    for q in pool:
        if q["id"] == replacement_q_id:
            replacement_q = q
            break
            
    if not replacement_q:
        return {"status": "error", "message": "Không tìm thấy câu hỏi thay thế trong ngân hàng."}
        
    curr_idx = -1
    current_q = None
    for idx, q in enumerate(target_list):
        if q["id"] == q_id or str(q.get("exam_number")) == str(q_id):
            curr_idx = idx
            current_q = q
            break
            
    if curr_idx == -1 or not current_q:
        return {"status": "error", "message": "Không tìm thấy câu hỏi cần thay thế trong đề thi."}
        
    new_q = copy.deepcopy(replacement_q)
    new_q["exam_number"] = current_q["exam_number"]
    target_list[curr_idx] = new_q
    
    exam["stats"] = calculate_stats(exam.get("part1", []), exam.get("part2", []))
    return {
        "status": "success",
        "new_question": new_q,
        "exam": exam
    }

def delete_question_from_bank(q_id):
    bank = load_bank()
    found = False
    new_p1 = []
    for q in bank.get("part1", []):
        if q["id"] == q_id:
            found = True
        else:
            new_p1.append(q)
            
    new_p2 = []
    for q in bank.get("part2", []):
        if q["id"] == q_id:
            found = True
        else:
            new_p2.append(q)
            
    if found:
        bank["part1"] = new_p1
        bank["part2"] = new_p2
        save_bank(bank)
        return True
    return False

def reroll_question(exam, q_id, q_type="part1"):
    bank = load_bank()
    current_ids = {q["id"] for q in exam["part1"]} if q_type == "part1" else {q["id"] for q in exam["part2"]}
    
    # Find the current question to match attributes
    target_list = exam["part1"] if q_type == "part1" else exam["part2"]
    current_q = None
    curr_idx = -1
    for idx, q in enumerate(target_list):
        if q["id"] == q_id or str(q.get("exam_number")) == str(q_id):
            current_q = q
            curr_idx = idx
            break
            
    if not current_q:
        return None
        
    pool = bank.get("part1", []) if q_type == "part1" else bank.get("part2", [])
    # Candidate search with same grade and level
    cands = [q for q in pool if q["id"] not in current_ids and q.get("grade") == current_q.get("grade") and q.get("level") == current_q.get("level")]
    if not cands:
        cands = [q for q in pool if q["id"] not in current_ids and q.get("grade") == current_q.get("grade")]
    if not cands:
        cands = [q for q in pool if q["id"] not in current_ids]
        
    if not cands:
        return None
        
    new_q = copy.deepcopy(random.choice(cands))
    new_q["exam_number"] = current_q["exam_number"]
    target_list[curr_idx] = new_q
    
    exam["stats"] = calculate_stats(exam["part1"], exam["part2"])
    return new_q

def shuffle_exam(original_exam, num_codes=4):
    codes = ["097", "098", "099", "100"]
    result_exams = []
    
    for i in range(min(num_codes, len(codes))):
        code_str = codes[i]
        new_exam = copy.deepcopy(original_exam)
        new_exam["info"]["code"] = code_str
        
        # Shuffle Part 1 questions
        shuffled_p1 = copy.deepcopy(original_exam["part1"])
        if i > 0:
            random.shuffle(shuffled_p1)
            
        for idx, q in enumerate(shuffled_p1, 1):
            q["exam_number"] = idx
            # Also permute options A, B, C, D if desired
            if i > 0 and "options" in q:
                old_opts = q["options"]
                correct_ans = q.get("answer", "A")
                correct_text = old_opts.get(correct_ans, "")
                
                keys = ["A", "B", "C", "D"]
                texts = [old_opts[k] for k in keys if k in old_opts]
                random.shuffle(texts)
                
                new_opts = {}
                new_ans = "A"
                for k, t in zip(keys, texts):
                    new_opts[k] = t
                    if t == correct_text:
                        new_ans = k
                q["options"] = new_opts
                q["answer"] = new_ans
                
        new_exam["part1"] = shuffled_p1
        
        # For Part 2, keep statements logic intact but we can permute items order
        shuffled_p2 = copy.deepcopy(original_exam["part2"])
        if i > 0:
            random.shuffle(shuffled_p2)
        for idx, q in enumerate(shuffled_p2, 1):
            q["exam_number"] = idx
            
        new_exam["part2"] = shuffled_p2
        result_exams.append(new_exam)
        
    return result_exams

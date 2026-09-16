import json
import random
import copy
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("VERCEL"):
    DATA_DIR = os.path.join("/tmp", "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    BANK_PATH = os.path.join(DATA_DIR, "question_bank.json")
    if not os.path.exists(BANK_PATH):
        orig = os.path.join(APP_DIR, "data", "question_bank.json")
        if os.path.exists(orig):
            try:
                import shutil
                shutil.copy(orig, BANK_PATH)
            except Exception:
                pass
else:
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
    orig = os.path.join(APP_DIR, "data", "question_bank.json")
    if os.environ.get("VERCEL"):
        if os.path.exists(orig):
            if not os.path.exists(BANK_PATH) or os.path.getmtime(orig) > os.path.getmtime(BANK_PATH):
                try:
                    import shutil
                    shutil.copy(orig, BANK_PATH)
                except Exception:
                    pass
    if os.path.exists(BANK_PATH):
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    elif os.path.exists(orig):
        with open(orig, "r", encoding="utf-8") as f:
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

def generate_exam(preset="city_hsg", custom_config=None, exam_info=None, num_clusters=3):
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

    # ---- Helper: select cluster questions atomically ----
    def select_clusters(pool, n_clusters):
        """Pick n_clusters cluster groups atomically (each group = 2 questions).
        Returns list of chosen questions (ordered by cluster_order) and set of used IDs."""
        # Build map of cluster_id -> sorted list of questions
        cluster_map = {}
        for q in pool:
            cid = q.get("cluster_id")
            if cid:
                cluster_map.setdefault(cid, []).append(q)
        # Only keep complete clusters (both sub-questions present)
        complete_clusters = {
            cid: sorted(qs, key=lambda x: x.get("cluster_order", 1))
            for cid, qs in cluster_map.items()
            if len(qs) >= 2
        }
        available = list(complete_clusters.values())
        n_pick = min(n_clusters, len(available))
        chosen_groups = random.sample(available, n_pick)
        chosen_qs = []
        for group in chosen_groups:
            chosen_qs.extend(group[:2])  # take first 2 sub-questions per cluster
        return chosen_qs

    if preset in ["city_hsg", "school_hsg"]:
        # 1. First select clusters atomically
        cluster_qs = select_clusters(p1_pool, num_clusters) if num_clusters > 0 else []
        cluster_ids_used = {q["id"] for q in cluster_qs}
        # Exclude all cluster questions from standalone pool so no cluster question is picked alone
        standalone_pool = [q for q in p1_pool if not q.get("cluster_id")]

        # 2. How many slots remain for standalone questions?
        total_target = 40
        standalone_target = total_target - len(cluster_qs)

        # 3. Select standalone questions per matrix (reduced by cluster contribution)
        dist = STANDARD_MATRIX["part1"]["distribution"]
        # Tally what clusters already contributed by grade/level
        cluster_contrib = {}
        for q in cluster_qs:
            g_key = get_grade_key(q.get("grade", 11))
            lvl = q.get("level", "hieu")
            cluster_contrib.setdefault(g_key, {}).setdefault(lvl, 0)
            cluster_contrib[g_key][lvl] += 1

        selected_standalone = []
        for g_key, target in dist.items():
            g_num = 10 if g_key == "pl_10" else (11 if g_key == "pl_11" else 12)
            for lvl in ["biet", "hieu", "van_dung"]:
                target_count = target[lvl]
                # Subtract cluster contribution for this grade/level
                already = cluster_contrib.get(g_key, {}).get(lvl, 0)
                need = max(0, target_count - already)
                candidates = [
                    q for q in standalone_pool
                    if q.get("grade") == g_num and q.get("level") == lvl
                    and q not in selected_standalone
                ]
                if len(candidates) < need:
                    candidates += [
                        q for q in standalone_pool
                        if q.get("grade") == g_num and q not in selected_standalone and q not in candidates
                    ]
                if len(candidates) < need:
                    candidates += [
                        q for q in standalone_pool
                        if q not in selected_standalone and q not in candidates
                    ]
                chosen = random.sample(candidates, min(need, len(candidates)))
                selected_standalone.extend(chosen)

        # Fill remaining if still under target
        while len(selected_standalone) < standalone_target:
            avail = [q for q in standalone_pool if q not in selected_standalone]
            if not avail:
                break
            selected_standalone.append(random.choice(avail))

        # 4. Merge: place cluster groups together (adjacent), then fill rest
        #    Strategy: insert cluster groups at natural positions, then append standalone
        selected_p1 = cluster_qs + selected_standalone
        random.shuffle(selected_p1)
        # But ensure cluster pairs stay adjacent:
        # Re-sort so that within each cluster_id, order is preserved, and clusters are contiguous blocks
        selected_p1 = _reorder_with_clusters(selected_p1)

        # Select Part 2 (unchanged)
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
        selected_p1 = random.sample(p1_pool, min(len(p1_pool), 40))
        selected_p2 = random.sample(p2_pool, min(len(p2_pool), 8))

    # Re-number items in order
    exam_p1 = []
    for idx, q in enumerate(selected_p1, 1):
        item = copy.deepcopy(q)
        item["exam_number"] = idx
        # Update cluster_header with actual question numbers for cluster q1
        if item.get("cluster_id") and item.get("cluster_order") == 1:
            cluster_size = item.get("cluster_size", 2)
            item["cluster_header_rendered"] = f"Đọc thông tin sau và trả lời câu hỏi từ câu {idx} đến câu {idx + cluster_size - 1}:"
        exam_p1.append(item)

    exam_p2 = []
    for idx, q in enumerate(selected_p2, 1):
        item = copy.deepcopy(q)
        item["exam_number"] = idx
        exam_p2.append(item)

    return {
        "info": exam_info,
        "preset": preset,
        "num_clusters": num_clusters,
        "part1": exam_p1,
        "part2": exam_p2,
        "stats": calculate_stats(exam_p1, exam_p2)
    }


def _reorder_with_clusters(questions):
    """
    Reorder questions so that cluster pairs stay adjacent.
    Non-cluster questions are interspersed randomly between cluster blocks.
    """
    # Separate clusters and standalone
    cluster_map = {}
    standalone = []
    for q in questions:
        cid = q.get("cluster_id")
        if cid:
            cluster_map.setdefault(cid, []).append(q)
        else:
            standalone.append(q)

    # Sort each cluster group by cluster_order
    cluster_blocks = [
        sorted(qs, key=lambda x: x.get("cluster_order", 1))
        for qs in cluster_map.values()
    ]

    # Shuffle cluster blocks and standalone
    random.shuffle(cluster_blocks)
    random.shuffle(standalone)

    # Interleave: place cluster blocks at random insertion points
    result = list(standalone)
    for block in cluster_blocks:
        insert_pos = random.randint(0, len(result))
        for i, q in enumerate(block):
            result.insert(insert_pos + i, q)

    return result



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

import os
import json
import shutil
import uuid
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .generator import (
    generate_exam, reroll_question, shuffle_exam, load_bank, save_bank, STANDARD_MATRIX,
    get_candidate_replacements, swap_question, delete_question_from_bank
)
from .docx_exporter import export_student_docx, export_teacher_docx, export_matrix_docx
from .importer import import_document_file, import_from_url, import_raw_text
from .ai_engine import generate_ai_scenario_question, load_knowledge
from .license_manager import (
    get_user_status, consume_user_quota, activate_user_pro,
    get_firebase_config, save_firebase_config, generate_checksum_key, PLAN_PRICING,
    list_all_users, admin_approve_user, admin_preapprove_email, is_admin_email
)


APP_DIR = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("VERCEL"):
    OUTPUT_DIR = os.path.join("/tmp", "output")
else:
    OUTPUT_DIR = os.path.join(APP_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="GDKTPL Exam Studio Pro", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active session cache for current exam
CURRENT_EXAM = {}

class GenerateRequest(BaseModel):
    preset: str = "city_hsg"
    custom_config: Optional[Dict[str, Any]] = None
    exam_info: Optional[Dict[str, Any]] = None

class RerollRequest(BaseModel):
    exam_id: Optional[str] = None
    q_id: str
    q_type: str = "part1"

class SwapQuestionRequest(BaseModel):
    q_id: str
    q_type: str = "part1"
    replacement_q_id: str

class UpdateQuestionRequest(BaseModel):
    q_id: str
    q_type: str
    stem: str
    grade: Optional[int] = None
    level: Optional[str] = None
    topic: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    statements: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None

class UpdateBankQuestionRequest(BaseModel):
    q_id: str
    q_type: str = "part1"
    stem: str
    grade: int
    level: str
    topic: Optional[str] = "Chuyên đề"
    options: Optional[Dict[str, str]] = None
    statements: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None

class ExportRequest(BaseModel):
    export_type: str = "student" # "student", "teacher", "matrix", "all"
    exam_data: Optional[Dict[str, Any]] = None

class ImportUrlRequest(BaseModel):
    url: str
    num_questions: Optional[int] = 5
    raw_keys: Optional[str] = None
    model: Optional[str] = "gemini-3.5"
    use_ai_solver: Optional[bool] = True

class ImportTextRequest(BaseModel):
    text: str
    source_name: Optional[str] = "Văn bản nhập tay"
    num_questions: Optional[int] = 5
    raw_keys: Optional[str] = None
    model: Optional[str] = "gemini-3.5"
    use_ai_solver: Optional[bool] = True

class AiGenerateRequest(BaseModel):
    topic: str
    level: str = "van_dung"
    grade: int = 12
    api_key: Optional[str] = None
    raw_keys: Optional[str] = None
    model: Optional[str] = "gemini-2.0-flash"
    prompt: Optional[str] = ""
    q_type: Optional[str] = "part1"

class ApiConfigRequest(BaseModel):
    raw_keys: str
    model: Optional[str] = "gemini-2.0-flash"

class SaveGeneratedQuestionRequest(BaseModel):
    question: dict

class UserStatusRequest(BaseModel):
    uid: str
    email: Optional[str] = ""
    display_name: Optional[str] = ""
    photo_url: Optional[str] = ""

class ConsumeQuotaRequest(BaseModel):
    uid: str
    action_name: Optional[str] = "Tác vụ"

class ActivateProRequest(BaseModel):
    uid: str
    license_key: str

class FirebaseConfigRequest(BaseModel):
    config: dict

class AdminApproveRequest(BaseModel):
    uid: str
    action: str
    days: Optional[int] = None
    quota: Optional[int] = None
    admin_email: Optional[str] = None

class AdminPreapproveRequest(BaseModel):
    email: str
    display_name: Optional[str] = "Giáo viên"
    plan: str = "1year"
    days: Optional[int] = None


@app.get("/api/status")
def get_status():
    bank = load_bank()
    p1 = bank.get("part1", [])
    p2 = bank.get("part2", [])
    
    by_grade = {10: 0, 11: 0, 12: 0}
    by_level = {"biet": 0, "hieu": 0, "van_dung": 0}
    
    for q in p1:
        g = q.get("grade", 11)
        by_grade[g] = by_grade.get(g, 0) + 1
        lvl = q.get("level", "hieu")
        by_level[lvl] = by_level.get(lvl, 0) + 1
        
    for q in p2:
        g = q.get("grade", 11)
        by_grade[g] = by_grade.get(g, 0) + 1
        lvl = q.get("level", "van_dung")
        by_level[lvl] = by_level.get(lvl, 0) + 1
        
    return {
        "status": "online",
        "total_part1": len(p1),
        "total_part2": len(p2),
        "total_questions": len(p1) + len(p2),
        "by_grade": by_grade,
        "by_level": by_level,
        "standard_matrix": STANDARD_MATRIX
    }

@app.get("/api/knowledge")
def get_knowledge_data():
    return load_knowledge()

@app.get("/api/question-sources")
def get_question_sources():
    bank = load_bank()
    counts = {}
    for q in bank.get("part1", []) + bank.get("part2", []):
        src = q.get("source", "Tài liệu chưa phân loại")
        counts[src] = counts.get(src, 0) + 1
    
    # Sort descending by count
    sorted_sources = [{"source": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
    return {"sources": sorted_sources}

def match_source_filter(q_src: str, target_src: str) -> bool:
    if not target_src or not target_src.strip():
        return True
    if not q_src:
        return False
    qs = q_src.strip().lower()
    ts = target_src.strip().lower()
    return (qs == ts) or (ts in qs) or (qs in ts)

@app.get("/api/questions")
def get_questions(
    grade: Optional[int] = None, 
    level: Optional[str] = None, 
    q_type: Optional[str] = None, 
    source: Optional[str] = None,
    query: Optional[str] = None,
    q_id: Optional[str] = None
):
    bank = load_bank()
    results = []
    
    if q_type in ["part1", None]:
        for q in bank.get("part1", []):
            if q_id and q.get("id") != q_id:
                continue
            if grade and q.get("grade") != grade:
                continue
            if level and q.get("level") != level:
                continue
            if source and not match_source_filter(q.get("source", ""), source):
                continue
            if query and query.lower() not in (q.get("id", "") + " " + q.get("stem", "") + " " + q.get("topic", "") + " " + q.get("source", "")).lower():
                continue
            results.append(q)
            
    if q_type in ["part2", None]:
        for q in bank.get("part2", []):
            if q_id and q.get("id") != q_id:
                continue
            if grade and q.get("grade") != grade:
                continue
            if level and q.get("level") != level:
                continue
            if source and not match_source_filter(q.get("source", ""), source):
                continue
            if query and query.lower() not in (q.get("id", "") + " " + q.get("stem", "") + " " + q.get("topic", "") + " " + q.get("source", "")).lower():
                continue
            results.append(q)
            
    return {"total": len(results), "questions": results[:500]}

@app.get("/api/question/{q_id}")
def get_single_question(q_id: str):
    bank = load_bank()
    for q in bank.get("part1", []) + bank.get("part2", []):
        if q.get("id") == q_id:
            return {"status": "success", "question": q}
    raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi trong ngân hàng.")

@app.post("/api/update-bank-question")
def handle_update_bank_question(req: UpdateBankQuestionRequest):
    bank = load_bank()
    pool = bank.get("part1", []) if req.q_type == "part1" else bank.get("part2", [])
    found_q = None
    for q in pool:
        if q["id"] == req.q_id:
            q["stem"] = req.stem
            q["grade"] = int(req.grade)
            q["level"] = req.level
            if req.topic:
                q["topic"] = req.topic
            if req.options is not None:
                q["options"] = req.options
            if req.statements is not None:
                q["statements"] = req.statements
            if req.answer is not None:
                q["answer"] = req.answer
            if req.explanation is not None:
                q["explanation"] = req.explanation
            found_q = q
            break
            
    if not found_q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi trong ngân hàng.")
        
    save_bank(bank)
    
    # Also update in CURRENT_EXAM if present
    global CURRENT_EXAM
    if CURRENT_EXAM:
        exam_pool = CURRENT_EXAM.get("part1", []) if req.q_type == "part1" else CURRENT_EXAM.get("part2", [])
        for eq in exam_pool:
            if eq["id"] == req.q_id:
                eq["stem"] = req.stem
                eq["grade"] = int(req.grade)
                eq["level"] = req.level
                eq["topic"] = req.topic or eq.get("topic")
                if req.options is not None:
                    eq["options"] = req.options
                if req.statements is not None:
                    eq["statements"] = req.statements
                if req.answer is not None:
                    eq["answer"] = req.answer
                if req.explanation is not None:
                    eq["explanation"] = req.explanation
                break
                
    return {"status": "success", "question": found_q}

@app.delete("/api/questions/{q_id}")
def handle_delete_question(q_id: str):
    success = delete_question_from_bank(q_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi để xóa.")
    return {"status": "success", "message": f"Đã xóa câu hỏi {q_id} khỏi ngân hàng."}

@app.get("/api/candidate-replacements")
def handle_candidate_replacements(q_id: str, q_type: str = "part1"):
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        raise HTTPException(status_code=400, detail="Chưa có đề thi nào đang hoạt động.")
    return get_candidate_replacements(CURRENT_EXAM, q_id, q_type)

@app.post("/api/swap-question")
def handle_swap_question(req: SwapQuestionRequest):
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        raise HTTPException(status_code=400, detail="Chưa có đề thi nào đang hoạt động.")
    result = swap_question(CURRENT_EXAM, req.q_id, req.q_type, req.replacement_q_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Lỗi khi đổi câu hỏi."))
    CURRENT_EXAM = result["exam"]
    return result

@app.post("/api/generate")
def create_exam(req: GenerateRequest):
    global CURRENT_EXAM
    exam = generate_exam(preset=req.preset, custom_config=req.custom_config, exam_info=req.exam_info)
    CURRENT_EXAM = exam
    return exam

@app.get("/api/current-exam")
def get_current_exam():
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        CURRENT_EXAM = generate_exam(preset="city_hsg")
    return CURRENT_EXAM

@app.post("/api/reroll")
def handle_reroll(req: RerollRequest):
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        raise HTTPException(status_code=400, detail="Chưa có đề thi nào đang hoạt động.")
    new_q = reroll_question(CURRENT_EXAM, req.q_id, req.q_type)
    if not new_q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi phù hợp để thay thế.")
    return {"status": "success", "new_question": new_q, "exam": CURRENT_EXAM}

@app.post("/api/update-question")
def update_question(req: UpdateQuestionRequest):
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        raise HTTPException(status_code=400, detail="Chưa có đề thi nào đang hoạt động.")
        
    target_list = CURRENT_EXAM.get(req.q_type, [])
    found = False
    for q in target_list:
        if q["id"] == req.q_id:
            q["stem"] = req.stem
            if req.options:
                q["options"] = req.options
            if req.statements:
                q["statements"] = req.statements
            if req.answer:
                q["answer"] = req.answer
            if req.explanation:
                q["explanation"] = req.explanation
            found = True
            break
            
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi trong đề thi.")
        
    return {"status": "success", "exam": CURRENT_EXAM}

@app.post("/api/shuffle")
def handle_shuffle():
    global CURRENT_EXAM
    if not CURRENT_EXAM:
        CURRENT_EXAM = generate_exam(preset="city_hsg")
    codes_exams = shuffle_exam(CURRENT_EXAM, num_codes=4)
    return {"status": "success", "codes": codes_exams}

@app.post("/api/export-docx")
def handle_export(req: ExportRequest):
    global CURRENT_EXAM
    exam = req.exam_data or CURRENT_EXAM
    if not exam:
        exam = generate_exam(preset="city_hsg")
        CURRENT_EXAM = exam
        
    code_str = exam.get("info", {}).get("code", "097")
    out_files = {}
    
    if req.export_type in ["student", "all"]:
        fname = f"De_thi_HSG_GDKTPL_Ma_{code_str}_HocSinh.docx"
        fpath = os.path.join(OUTPUT_DIR, fname)
        export_student_docx(exam, fpath)
        out_files["student"] = f"/api/download/{fname}"
        
    if req.export_type in ["teacher", "all"]:
        fname = f"Huong_dan_cham_va_Dap_an_Ma_{code_str}.docx"
        fpath = os.path.join(OUTPUT_DIR, fname)
        export_teacher_docx(exam, fpath)
        out_files["teacher"] = f"/api/download/{fname}"
        
    if req.export_type in ["matrix", "all"]:
        fname = f"Ma_tran_va_Dac_ta_De_HSG_{code_str}.docx"
        fpath = os.path.join(OUTPUT_DIR, fname)
        export_matrix_docx(exam, fpath)
        out_files["matrix"] = f"/api/download/{fname}"
        
    return {"status": "success", "files": out_files}

@app.get("/api/download/{filename}")
def download_file(filename: str):
    fpath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Tệp không tồn tại.")
    return FileResponse(fpath, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)

@app.post("/api/import-file")
async def handle_import_file(
    file: UploadFile = File(...),
    raw_keys: Optional[str] = Form(None),
    model: Optional[str] = Form("gemini-3.5"),
    use_ai_solver: Optional[bool] = Form(True)
):
    bytes_data = await file.read()
    result = import_document_file(
        filename=file.filename,
        file_bytes=bytes_data,
        raw_keys=raw_keys,
        model=model or "gemini-3.5",
        use_ai_solver=use_ai_solver if use_ai_solver is not None else True
    )
    return result

@app.post("/api/import-url")
def handle_import_url(req: ImportUrlRequest):
    return import_from_url(
        req.url,
        num_questions=req.num_questions or 5,
        raw_keys=req.raw_keys,
        model=req.model or "gemini-3.5",
        use_ai_solver=req.use_ai_solver if req.use_ai_solver is not None else True
    )

@app.post("/api/import-text")
def handle_import_text(req: ImportTextRequest):
    return import_raw_text(
        text=req.text,
        source_name=req.source_name,
        num_questions=req.num_questions or 5,
        raw_keys=req.raw_keys,
        model=req.model or "gemini-3.5",
        use_ai_solver=req.use_ai_solver if req.use_ai_solver is not None else True
    )

API_CONFIG_PATH = os.path.join(APP_DIR, "data", "api_config.json")

@app.get("/api/api-config")
def get_api_config():
    if os.path.exists(API_CONFIG_PATH):
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"raw_keys": "", "model": "gemini-2.0-flash"}

@app.post("/api/api-config")
def save_api_config(req: ApiConfigRequest):
    data = {
        "raw_keys": req.raw_keys,
        "model": req.model or "gemini-2.0-flash"
    }
    with open(API_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"status": "success", "message": "Đã lưu cấu hình API thành công."}

@app.post("/api/save-generated-question")
def save_generated_question(req: SaveGeneratedQuestionRequest):
    q = req.question
    if not q or "stem" not in q:
        raise HTTPException(status_code=400, detail="Dữ liệu câu hỏi không hợp lệ.")
    
    if not q.get("id"):
        q["id"] = f"ai_gen_{uuid.uuid4().hex[:8]}"
        
    q_type = q.get("type", "part1")
    bank = load_bank()
    if q_type == "part2":
        bank["part2"].append(q)
    else:
        bank["part1"].append(q)
    save_bank(bank)
    return {"status": "success", "question": q}

@app.post("/api/ai-generate")
def handle_ai_generate(req: AiGenerateRequest):
    return generate_ai_scenario_question(
        topic=req.topic,
        level=req.level,
        grade=req.grade,
        api_key=req.api_key,
        raw_keys=req.raw_keys,
        model=req.model or "gemini-2.0-flash",
        custom_prompt=req.prompt,
        q_type=req.q_type or "part1"
    )

# --- LICENSE & FIREBASE AUTH ENDPOINTS ---

@app.get("/api/user/status")
def handle_get_user_status(uid: str = "guest_local_user", email: str = "", display_name: str = "", photo_url: str = ""):
    return get_user_status(uid=uid, email=email, display_name=display_name, photo_url=photo_url)

@app.post("/api/user/status")
def handle_post_user_status(req: UserStatusRequest):
    return get_user_status(uid=req.uid, email=req.email or "", display_name=req.display_name or "", photo_url=req.photo_url or "")

@app.post("/api/user/consume-quota")
def handle_consume_quota(req: ConsumeQuotaRequest):
    return consume_user_quota(uid=req.uid, action_name=req.action_name or "Tác vụ")

@app.post("/api/user/activate-pro")
def handle_activate_pro(req: ActivateProRequest):
    return activate_user_pro(uid=req.uid, license_key=req.license_key)

@app.get("/api/pricing")
def handle_get_pricing():
    return {"status": "success", "pricing": PLAN_PRICING}

@app.get("/api/firebase-config")
def handle_get_firebase_config():
    return get_firebase_config()

@app.post("/api/firebase-config")
def handle_save_firebase_config(req: FirebaseConfigRequest):
    save_firebase_config(req.config)
    return {"status": "success", "message": "Đã lưu cấu hình Firebase thành công!"}

@app.get("/api/admin/generate-key")
def handle_admin_generate_key(plan: str = "1year", secret: str = ""):
    if secret != "kimtuyen2026":
        raise HTTPException(status_code=403, detail="Mã bảo vệ quản trị viên không chính xác.")
    if plan not in PLAN_PRICING:
        raise HTTPException(status_code=400, detail=f"Gói không hợp lệ. Các gói hợp lệ: {list(PLAN_PRICING.keys())}")
    key = generate_checksum_key(plan)
    return {
        "status": "success",
        "plan": plan,
        "plan_name": PLAN_PRICING[plan]["name"],
        "price": PLAN_PRICING[plan]["price"],
        "license_key": key
    }

@app.get("/api/admin/users")
def handle_admin_get_users(email: Optional[str] = None):
    return list_all_users()

@app.post("/api/admin/approve-user")
def handle_admin_approve_user(req: AdminApproveRequest):
    return admin_approve_user(
        uid=req.uid,
        action=req.action,
        custom_days=req.days,
        custom_quota=req.quota
    )

@app.post("/api/admin/preapprove-user")
def handle_admin_preapprove_user(req: AdminPreapproveRequest):
    return admin_preapprove_email(
        email=req.email,
        display_name=req.display_name or "Giáo viên",
        plan=req.plan,
        custom_days=req.days
    )


# Mount static frontend
static_dir = os.path.join(APP_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
@app.get("/index.html")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_file):
        index_file = os.path.join(os.path.dirname(APP_DIR), "public", "index.html")
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except Exception:
            return FileResponse(index_file)
    return HTMLResponse("<h1>GDKTPL Exam Studio API running.</h1>")

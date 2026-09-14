import os
import json
import time
import uuid
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("VERCEL"):
    DATA_DIR = os.path.join("/tmp", "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    for fname in ["user_licenses.json", "firebase_config.json", "valid_keys.json"]:
        src = os.path.join(APP_DIR, "data", fname)
        dst = os.path.join(DATA_DIR, fname)
        if not os.path.exists(dst) and os.path.exists(src):
            try:
                import shutil
                shutil.copy(src, dst)
            except Exception:
                pass
else:
    DATA_DIR = os.path.join(APP_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)

USER_LICENSES_PATH = os.path.join(DATA_DIR, "user_licenses.json")
FIREBASE_CONFIG_PATH = os.path.join(DATA_DIR, "firebase_config.json")
VALID_KEYS_PATH = os.path.join(DATA_DIR, "valid_keys.json")

SECRET_SALT = "GDKTPL_HSG_PRO_LICENSE_2026_SECURE_SALT"
TRIAL_LIMIT = 10

ADMIN_EMAILS = [
    "nguyenvanthien1812@gmail.com",
    "kimtuyen@gmail.com",
    "admin@gmail.com",
    "nguyenthian22027@gmail.com",
    "hoathinh6966@gmail.com"
]

def is_admin_email(email: str) -> bool:
    if not email:
        return False
    email_clean = email.strip().lower()
    if email_clean in [a.lower() for a in ADMIN_EMAILS]:
        return True
    if "admin" in email_clean:
        return True
    return False


PLAN_PRICING = {
    "1year": {
        "name": "Gói 1 Năm",
        "price": "150.000 VNĐ",
        "days": 365,
        "prefix": "PRO1Y",
        "desc": "Sử dụng đầy đủ tính năng trong 1 năm học (365 ngày)"
    },
    "2year": {
        "name": "Gói 2 Năm",
        "price": "250.000 VNĐ",
        "days": 730,
        "prefix": "PRO2Y",
        "desc": "Sử dụng đầy đủ tính năng trong 2 năm học (730 ngày) - Tiết kiệm 50k"
    },
    "lifetime": {
        "name": "Gói Vĩnh Viễn",
        "price": "599.000 VNĐ",
        "days": None,
        "prefix": "PROLIFE",
        "desc": "Sử dụng trọn đời, cập nhật vĩnh viễn mọi luật mới và đề thi (Khuyên dùng)"
    }
}

def load_json(filepath: str, default: Any) -> Any:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(filepath: str, data: Any):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_default_valid_keys():
    """Khởi tạo một số License Key mẫu nếu tệp valid_keys chưa có."""
    if not os.path.exists(VALID_KEYS_PATH):
        starter_keys = {
            "PRO1Y-DEMO-2026-VIP1": {"plan": "1year", "created_at": "2026-09-14", "used_by": None},
            "PRO2Y-DEMO-2026-VIP2": {"plan": "2year", "created_at": "2026-09-14", "used_by": None},
            "PROLIFE-DEMO-2026-VIP3": {"plan": "lifetime", "created_at": "2026-09-14", "used_by": None},
            "PROLIFE-KIMTUYEN-2026": {"plan": "lifetime", "created_at": "2026-09-14", "used_by": None}
        }
        save_json(VALID_KEYS_PATH, starter_keys)

init_default_valid_keys()

def get_firebase_config() -> dict:
    default_cfg = {
        "apiKey": "AIzaSyAeKfH6_32nI5vYKdI8wONACr17Ryn1QVk",
        "authDomain": "kinh-te-phap-luat-fcd47.firebaseapp.com",
        "projectId": "kinh-te-phap-luat-fcd47",
        "storageBucket": "kinh-te-phap-luat-fcd47.firebasestorage.app",
        "messagingSenderId": "247284686520",
        "appId": "1:247284686520:web:8ec3bc8747bb634494de4d",
        "measurementId": "G-46G1TJMPVZ"
    }
    return load_json(FIREBASE_CONFIG_PATH, default_cfg)

def save_firebase_config(config_data: dict):
    save_json(FIREBASE_CONFIG_PATH, config_data)

def generate_checksum_key(plan: str) -> str:
    """Sinh mã kích hoạt kèm chữ ký số HMAC an toàn."""
    random_part = uuid.uuid4().hex[:8].upper()
    prefix = PLAN_PRICING.get(plan, {}).get("prefix", "PRO1Y")
    data_to_sign = f"{prefix}-{random_part}"
    sig = hmac.new(SECRET_SALT.encode(), data_to_sign.encode(), hashlib.sha256).hexdigest()[:6].upper()
    full_key = f"{prefix}-{random_part[:4]}-{random_part[4:]}-{sig}"
    
    # Lưu vào danh sách valid_keys
    keys_db = load_json(VALID_KEYS_PATH, {})
    keys_db[full_key] = {
        "plan": plan,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "used_by": None
    }
    save_json(VALID_KEYS_PATH, keys_db)
    return full_key

def verify_license_key_validity(key: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Kiểm tra tính hợp lệ của license key:
    Trả về (is_valid, plan_type, reason)
    """
    cleaned_key = (key or "").strip().upper()
    if not cleaned_key:
        return False, None, "Mã kích hoạt không được để trống."

    keys_db = load_json(VALID_KEYS_PATH, {})

    # 1. Kiểm tra trong danh mục keys_db
    if cleaned_key in keys_db:
        key_info = keys_db[cleaned_key]
        if key_info.get("used_by"):
            return False, None, f"Mã kích hoạt này đã được sử dụng bởi tài khoản: {key_info.get('used_by')}."
        return True, key_info.get("plan", "1year"), "Mã hợp lệ."

    # 2. Kiểm tra chữ ký số HMAC
    parts = cleaned_key.split("-")
    if len(parts) == 4:
        prefix, p1, p2, sig = parts
        plan_found = None
        for p_name, p_info in PLAN_PRICING.items():
            if p_info["prefix"] == prefix:
                plan_found = p_name
                break
        if plan_found:
            random_part = f"{p1}{p2}"
            data_to_sign = f"{prefix}-{random_part}"
            expected_sig = hmac.new(SECRET_SALT.encode(), data_to_sign.encode(), hashlib.sha256).hexdigest()[:6].upper()
            if hmac.compare_digest(sig, expected_sig):
                return True, plan_found, "Mã hợp lệ (chữ ký số chuẩn)."

    return False, None, "Mã kích hoạt không hợp lệ hoặc đã hết hạn."

def get_user_status(uid: str, email: str = "", display_name: str = "", photo_url: str = "") -> dict:
    """Lấy hoặc khởi tạo trạng thái của người dùng (Quota dùng thử hoặc PRO)."""
    clean_uid = (uid or "guest_local_user").strip()
    users_db = load_json(USER_LICENSES_PATH, {})
    now = datetime.now()

    user = users_db.get(clean_uid)

    # Nếu chưa có theo clean_uid nhưng có email, kiểm tra xem đã được pre-approve theo email chưa
    if not user and email:
        for ex_uid, ex_u in list(users_db.items()):
            if ex_u.get("email", "").lower() == email.lower():
                # Gán lại sang clean_uid mới
                user = ex_u
                user["uid"] = clean_uid
                if display_name:
                    user["display_name"] = display_name
                if photo_url:
                    user["photo_url"] = photo_url
                users_db[clean_uid] = user
                if ex_uid != clean_uid and ex_uid.startswith("pre_"):
                    del users_db[ex_uid]
                save_json(USER_LICENSES_PATH, users_db)
                break

    if not user:
        is_admin = is_admin_email(email)
        user = {
            "uid": clean_uid,
            "email": email or "",
            "display_name": display_name or "Giáo viên",
            "photo_url": photo_url or "",
            "trial_used": 0,
            "trial_limit": TRIAL_LIMIT,
            "is_pro": False,
            "pro_plan": None,
            "pro_activated_at": None,
            "pro_expires_at": None,
            "status": "active",
            "is_admin": is_admin,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        users_db[clean_uid] = user
        save_json(USER_LICENSES_PATH, users_db)
    else:
        # Cập nhật thông tin profile nếu có
        updated = False
        if email and user.get("email") != email:
            user["email"] = email
            updated = True
        if display_name and user.get("display_name") != display_name:
            user["display_name"] = display_name
            updated = True
        if photo_url and user.get("photo_url") != photo_url:
            user["photo_url"] = photo_url
            updated = True

        # Đảm bảo có trường status
        if "status" not in user:
            user["status"] = "active"
            updated = True

        # Kiểm tra hạn sử dụng nếu là tài khoản PRO có thời hạn
        if user.get("is_pro") and user.get("pro_expires_at"):
            try:
                exp_dt = datetime.strptime(user["pro_expires_at"], "%Y-%m-%d %H:%M:%S")
                if now > exp_dt:
                    user["is_pro"] = False
                    user["pro_expired"] = True
                    updated = True
            except Exception:
                pass

        if updated:
            users_db[clean_uid] = user
            save_json(USER_LICENSES_PATH, users_db)

    user_email = user.get("email", email or "")
    is_admin = is_admin_email(user_email)
    trial_used = user.get("trial_used", 0)
    trial_limit = user.get("trial_limit", TRIAL_LIMIT)
    trial_remaining = max(0, trial_limit - trial_used)
    is_pro = user.get("is_pro", False)
    user_status = user.get("status", "active")
    is_blocked = (user_status == "blocked")

    return {
        "uid": clean_uid,
        "email": user_email,
        "display_name": user.get("display_name", "Giáo viên"),
        "photo_url": user.get("photo_url", ""),
        "is_pro": is_pro and not is_blocked,
        "is_admin": is_admin,
        "status": user_status,
        "is_blocked": is_blocked,
        "pro_plan": user.get("pro_plan"),
        "pro_plan_name": PLAN_PRICING.get(user.get("pro_plan", ""), {}).get("name", "Gói PRO") if is_pro else None,
        "pro_activated_at": user.get("pro_activated_at"),
        "pro_expires_at": user.get("pro_expires_at"),
        "trial_used": trial_used,
        "trial_limit": trial_limit,
        "trial_remaining": 999999 if is_pro else trial_remaining,
        "can_use": (not is_blocked) and (is_pro or trial_remaining > 0),
        "plan_pricing": PLAN_PRICING
    }


def consume_user_quota(uid: str, action_name: str = "Tác vụ") -> dict:
    """Trừ 1 lượt dùng thử của người dùng nếu chưa phải PRO."""
    clean_uid = (uid or "guest_local_user").strip()
    status = get_user_status(clean_uid)

    if status.get("is_pro"):
        return {
            "status": "success",
            "allowed": True,
            "is_pro": True,
            "message": f"Tài khoản PRO - Thực hiện '{action_name}' không giới hạn.",
            "user": status
        }

    trial_used = status.get("trial_used", 0)
    trial_limit = status.get("trial_limit", TRIAL_LIMIT)

    if trial_used >= trial_limit:
        return {
            "status": "quota_exceeded",
            "allowed": False,
            "is_pro": False,
            "message": f"Bạn đã sử dụng hết {trial_limit} lượt dùng thử miễn phí. Vui lòng kích hoạt PRO để tiếp tục!",
            "trial_used": trial_used,
            "trial_remaining": 0,
            "user": status
        }

    # Tăng trial_used lên 1
    users_db = load_json(USER_LICENSES_PATH, {})
    user = users_db.get(clean_uid, {})
    new_used = trial_used + 1
    user["trial_used"] = new_used
    user["last_action"] = f"{action_name} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    users_db[clean_uid] = user
    save_json(USER_LICENSES_PATH, users_db)

    remaining = max(0, trial_limit - new_used)
    status["trial_used"] = new_used
    status["trial_remaining"] = remaining
    status["can_use"] = remaining > 0

    return {
        "status": "success",
        "allowed": True,
        "is_pro": False,
        "trial_used": new_used,
        "trial_remaining": remaining,
        "message": f"Đã sử dụng: {new_used}/{trial_limit} lượt dùng thử miễn phí.",
        "user": status
    }

def activate_user_pro(uid: str, license_key: str) -> dict:
    """Kích hoạt bản quyền PRO bằng mã kích hoạt."""
    clean_uid = (uid or "guest_local_user").strip()
    cleaned_key = (license_key or "").strip().upper()

    is_valid, plan, reason = verify_license_key_validity(cleaned_key)
    if not is_valid:
        return {"status": "error", "message": reason}

    now = datetime.now()
    plan_info = PLAN_PRICING.get(plan, {})
    days = plan_info.get("days")

    if days:
        expires_at = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        expires_at = None # Vĩnh viễn (Lifetime)

    # Cập nhật user
    users_db = load_json(USER_LICENSES_PATH, {})
    user = users_db.get(clean_uid, {})
    user["uid"] = clean_uid
    user["is_pro"] = True
    user["pro_plan"] = plan
    user["pro_key"] = cleaned_key
    user["pro_activated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    user["pro_expires_at"] = expires_at
    users_db[clean_uid] = user
    save_json(USER_LICENSES_PATH, users_db)

    # Đánh dấu key đã sử dụng trong valid_keys_db
    keys_db = load_json(VALID_KEYS_PATH, {})
    if cleaned_key in keys_db:
        keys_db[cleaned_key]["used_by"] = clean_uid
        keys_db[cleaned_key]["used_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    else:
        keys_db[cleaned_key] = {
            "plan": plan,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "used_by": clean_uid,
            "used_at": now.strftime("%Y-%m-%d %H:%M:%S")
        }
    save_json(VALID_KEYS_PATH, keys_db)

    updated_status = get_user_status(clean_uid)
    return {
        "status": "success",
        "message": f"🎉 Chúc mừng! Bạn đã kích hoạt thành công {plan_info.get('name', 'Gói PRO')}!",
        "plan": plan,
        "plan_name": plan_info.get("name"),
        "expires_at": expires_at or "Vĩnh viễn (Trọn đời)",
        "user": updated_status
    }

# --- BẢNG QUẢN TRỊ VIÊN — PHÊ DUYỆT REALTIME CLOUD FUNCTIONS ---

def list_all_users() -> Dict[str, Any]:
    """Lấy danh sách toàn bộ giáo viên cùng số liệu thống kê cho Bảng Quản Trị."""
    users_db = load_json(USER_LICENSES_PATH, {})
    now = datetime.now()

    user_list = []
    total_count = 0
    trial_count = 0
    pro_expiring_count = 0
    pro_lifetime_count = 0
    blocked_count = 0

    for uid, u in users_db.items():
        total_count += 1
        status = u.get("status", "active")
        is_blocked = (status == "blocked")
        is_pro = u.get("is_pro", False) and not is_blocked
        plan = u.get("pro_plan")
        expires_at = u.get("pro_expires_at")
        trial_used = u.get("trial_used", 0)
        trial_limit = u.get("trial_limit", TRIAL_LIMIT)

        # Tính toán ngày còn lại
        days_left = None
        if is_pro and expires_at:
            try:
                exp_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                delta = exp_dt - now
                days_left = max(0, delta.days)
                if delta.total_seconds() <= 0:
                    is_pro = False
            except Exception:
                pass

        if is_blocked:
            blocked_count += 1
        elif is_pro:
            if plan == "lifetime":
                pro_lifetime_count += 1
            else:
                pro_expiring_count += 1
        else:
            trial_count += 1

        user_list.append({
            "uid": uid,
            "email": u.get("email", ""),
            "display_name": u.get("display_name", "Giáo viên"),
            "photo_url": u.get("photo_url", ""),
            "is_pro": is_pro,
            "pro_plan": plan,
            "pro_plan_name": PLAN_PRICING.get(plan, {}).get("name", "Gói PRO") if is_pro else None,
            "pro_expires_at": expires_at,
            "days_left": days_left,
            "trial_used": trial_used,
            "trial_limit": trial_limit,
            "trial_remaining": max(0, trial_limit - trial_used),
            "status": status,
            "created_at": u.get("created_at", now.strftime("%Y-%m-%d %H:%M:%S")),
            "last_action": u.get("last_action", "")
        })

    # Sắp xếp giáo viên mới nhất lên đầu
    user_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {
        "status": "success",
        "stats": {
            "total": total_count,
            "trial": trial_count,
            "pro_expiring": pro_expiring_count,
            "pro_lifetime": pro_lifetime_count,
            "blocked": blocked_count
        },
        "users": user_list
    }

def admin_approve_user(uid: str, action: str, custom_days: Optional[int] = None, custom_quota: Optional[int] = None) -> dict:
    """Xử lý thao tác phê duyệt của Admin: +Lượt, 1 Năm, 2 Năm, Vĩnh Viễn, Khóa."""
    clean_uid = (uid or "").strip()
    users_db = load_json(USER_LICENSES_PATH, {})

    user = users_db.get(clean_uid)
    if not user:
        # Thử tìm theo email nếu uid là email
        found = False
        for k, v in users_db.items():
            if v.get("email", "").lower() == clean_uid.lower():
                clean_uid = k
                user = v
                found = True
                break
        if not found:
            # Tạo mới user
            user = {
                "uid": clean_uid,
                "email": clean_uid if "@" in clean_uid else "",
                "display_name": "Giáo viên",
                "photo_url": "",
                "trial_used": 0,
                "trial_limit": TRIAL_LIMIT,
                "is_pro": False,
                "pro_plan": None,
                "status": "active",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            users_db[clean_uid] = user

    now = datetime.now()
    action_clean = (action or "").strip().lower()

    if action_clean in ["quota_10", "add_quota", "quota_5"]:
        inc = custom_quota or (5 if action_clean == "quota_5" else 10)
        curr_limit = user.get("trial_limit", TRIAL_LIMIT)
        curr_used = user.get("trial_used", 0)
        user["trial_limit"] = max(curr_limit, curr_used) + inc
        user["status"] = "active"
        msg = f"Đã cộng thêm +{inc} lượt dùng thử thành công!"

    elif action_clean == "1year":
        user["is_pro"] = True
        user["pro_plan"] = "1year"
        user["pro_activated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        user["pro_expires_at"] = (now + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        user["status"] = "active"
        msg = "Đã phê duyệt Gói 1 Năm (365 ngày) thành công!"

    elif action_clean == "2year":
        user["is_pro"] = True
        user["pro_plan"] = "2year"
        user["pro_activated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        user["pro_expires_at"] = (now + timedelta(days=730)).strftime("%Y-%m-%d %H:%M:%S")
        user["status"] = "active"
        msg = "Đã phê duyệt Gói 2 Năm (730 ngày) thành công!"

    elif action_clean == "lifetime":
        user["is_pro"] = True
        user["pro_plan"] = "lifetime"
        user["pro_activated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        user["pro_expires_at"] = None
        user["status"] = "active"
        msg = "Đã phê duyệt Gói Vĩnh Viễn (Trọn đời) thành công!"

    elif action_clean == "custom":
        days = custom_days or 30
        user["is_pro"] = True
        user["pro_plan"] = "custom"
        user["pro_activated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        user["pro_expires_at"] = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        user["status"] = "active"
        msg = f"Đã phê duyệt Gói Tùy Chọn ({days} ngày) thành công!"

    elif action_clean in ["toggle_block", "block"]:
        current_status = user.get("status", "active")
        if current_status == "blocked":
            user["status"] = "active"
            msg = "Đã mở khóa tài khoản giáo viên."
        else:
            user["status"] = "blocked"
            msg = "Đã tạm khóa tài khoản giáo viên."

    elif action_clean == "delete":
        if clean_uid in users_db:
            del users_db[clean_uid]
        save_json(USER_LICENSES_PATH, users_db)
        return {"status": "success", "message": "Đã xóa tài khoản khỏi danh sách."}

    else:
        return {"status": "error", "message": f"Hành động không hợp lệ: {action}"}

    users_db[clean_uid] = user
    save_json(USER_LICENSES_PATH, users_db)

    return {
        "status": "success",
        "message": msg,
        "user": get_user_status(clean_uid)
    }

def admin_preapprove_email(email: str, display_name: str, plan: str, custom_days: Optional[int] = None) -> dict:
    """Tạo trước quyền PRO cho một email trước khi giáo viên đăng nhập."""
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        return {"status": "error", "message": "Email không hợp lệ."}

    users_db = load_json(USER_LICENSES_PATH, {})
    # Tìm xem đã có user nào mang email này chưa
    target_uid = None
    for uid, u in users_db.items():
        if u.get("email", "").lower() == clean_email:
            target_uid = uid
            break

    if not target_uid:
        target_uid = f"pre_{uuid.uuid4().hex[:8]}"
        users_db[target_uid] = {
            "uid": target_uid,
            "email": clean_email,
            "display_name": display_name or "Giáo viên",
            "photo_url": "",
            "trial_used": 0,
            "trial_limit": TRIAL_LIMIT,
            "is_pro": False,
            "status": "active",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(USER_LICENSES_PATH, users_db)

    return admin_approve_user(target_uid, plan, custom_days=custom_days)


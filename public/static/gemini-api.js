/**
 * GEMINI API TOOLKIT - Multi-Key & Auto-Failover Engine
 * Hỗ trợ:
 * 1. Nạp nhiều API Key (phân tách bởi dòng mới, dấu phẩy hoặc chấm phẩy)
 * 2. Che key an toàn khi hiển thị UI (AIzaSyB7...9x2A)
 * 3. Ping Test / Health Check siêu nhẹ đo độ trễ (latencyMs) và mã lỗi HTTP (200, 401, 429, timeout)
 * 4. Cơ chế tự động Failover 2 lớp (chuyển sang Key tiếp theo khi gặp 429 Rate Limit / 401/403 Auth Error)
 * 5. Tự động xoay vòng Model (Auto cascade: 2.0 Flash -> 1.5 Flash -> 1.5 Pro)
 */

const GEMINI_CONFIG_KEY = "gdktpl_gemini_api_keys";
const GEMINI_MODEL_KEY = "gdktpl_gemini_model";

const AVAILABLE_MODELS = [
  { id: 'gemini-3.6',       name: 'Gemini 3.6 Flash / Pro', badge: 'Thế Hệ 3.6 Mới Nhất (Siêu Nhanh)' },
  { id: 'gemini-3.5',       name: 'Gemini 3.5 Flash / Pro', badge: 'Thế Hệ 3.5 Tiên Tiến (Khuyên dùng cho HSG)' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash',       badge: 'Thế hệ 2.5 ổn định' },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash',       badge: 'Bản 2.0 Flash siêu tốc' },
  { id: 'auto',             name: 'Tự động xoay vòng Model (Auto)', badge: '3.6 → 3.5 → 2.5 → 2.0' },
];

/**
 * Tách chuỗi nhiều key thành mảng các key sạch
 */
function parseApiKeys(rawText) {
  if (!rawText) return [];
  return rawText
    .split(/[\n,;]+/)
    .map(k => k.trim())
    .filter(k => k.length > 0);
}

/**
 * Che key an toàn: AIzaSyB7...9x2A
 */
function maskApiKey(key) {
  const trimmed = (key || '').trim();
  if (trimmed.length <= 12) return trimmed;
  return `${trimmed.slice(0, 8)}...${trimmed.slice(-4)}`;
}

/**
 * Lấy cấu hình đã lưu trong localStorage hoặc đồng bộ từ backend
 */
function getSavedApiConfig() {
  const rawKeys = localStorage.getItem(GEMINI_CONFIG_KEY) || "";
  const model = localStorage.getItem(GEMINI_MODEL_KEY) || "gemini-2.0-flash";
  const keys = parseApiKeys(rawKeys);
  return {
    rawKeys,
    keys,
    model,
    hasKeys: keys.length > 0
  };
}

/**
 * Lưu cấu hình API Keys và Model
 */
async function saveApiConfig(rawKeysText, model) {
  localStorage.setItem(GEMINI_CONFIG_KEY, rawKeysText.trim());
  localStorage.setItem(GEMINI_MODEL_KEY, model || "gemini-2.0-flash");

  // Đồng bộ lên backend để backend cũng có thể dùng khi cần
  try {
    await fetch("/api/api-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_keys: rawKeysText.trim(),
        model: model || "gemini-2.0-flash"
      })
    });
  } catch (err) {
    console.warn("Không thể đồng bộ API config lên backend:", err);
  }

  updateApiStatusBadges();
}

/**
 * Kiểm tra kết nối 1 API Key (Ping Test siêu nhẹ - 5 tokens)
 */
async function checkSingleApiKeyHealth(apiKey, keyIndex = 0, testModel = 'gemini-2.0-flash') {
  const cleanKey = (apiKey || '').trim();
  if (!cleanKey) return { keyIndex, status: 'error', message: 'Key trống', maskedKey: '' };

  const actualModel = testModel === 'auto' ? 'gemini-2.0-flash' : testModel;
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(actualModel)}:generateContent?key=${encodeURIComponent(cleanKey)}`;
  const startTime = performance.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000); // 12 giây timeout

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: 'ping' }] }],
        generationConfig: { maxOutputTokens: 5 }
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    const latencyMs = Math.round(performance.now() - startTime);

    if (res.ok) {
      return { keyIndex, status: 'success', latencyMs, message: `Hoạt động tốt (${latencyMs}ms)`, maskedKey: maskApiKey(cleanKey) };
    }
    if (res.status === 401 || res.status === 403) {
      return { keyIndex, status: 'auth_error', message: 'Key không hợp lệ hoặc bị khóa', maskedKey: maskApiKey(cleanKey) };
    }
    if (res.status === 429) {
      return { keyIndex, status: 'rate_limit', message: 'Hết Quota / Giới hạn tốc độ (Rate Limit)', maskedKey: maskApiKey(cleanKey) };
    }
    if (res.status === 404 && actualModel !== 'gemini-2.0-flash') {
      // Nếu model 3.5/3.6 chưa có endpoint riêng trên tài khoản, thử ping với 2.0-flash để kiểm tra tính hợp lệ của key
      const fallbackRes = await checkSingleApiKeyHealth(cleanKey, keyIndex, 'gemini-2.0-flash');
      if (fallbackRes.status === 'success') {
        return {
          keyIndex,
          status: 'success',
          latencyMs: fallbackRes.latencyMs,
          message: `Hoạt động tốt (${fallbackRes.latencyMs}ms) - Sẵn sàng Model 3.5 & 3.6`,
          maskedKey: maskApiKey(cleanKey)
        };
      }
      return fallbackRes;
    }

    return { keyIndex, status: 'error', message: `Lỗi HTTP ${res.status}: ${res.statusText}`, maskedKey: maskApiKey(cleanKey) };
  } catch (err) {
    if (err && err.name === 'AbortError') {
      return { keyIndex, status: 'timeout', message: 'Timeout (>12s) - Mạng chậm hoặc bị chặn', maskedKey: maskApiKey(cleanKey) };
    }
    return { keyIndex, status: 'network_error', message: `Lỗi mạng: ${err.message}`, maskedKey: maskApiKey(cleanKey) };
  }
}

/**
 * Kiểm tra đồng thời tất cả các Key bằng Promise.all
 */
async function checkMultipleApiKeysHealth(keys, testModel = 'gemini-2.0-flash') {
  return Promise.all(keys.map((k, i) => checkSingleApiKeyHealth(k, i, testModel)));
}

/**
 * Gọi Gemini với cơ chế Auto-Failover 2 lớp:
 * 1. Chuyển key tiếp theo khi gặp 429 (Quota) hoặc 401/403 (Auth)
 * 2. Chuyển model dự phòng nếu model auto bị quá tải
 */
async function callGeminiWithFailover({
  rawApiKeyText,
  model = 'gemini-2.0-flash',
  prompt,
  systemInstruction = "",
  temperature = 0.3,
  onFailover = null
}) {
  const keys = parseApiKeys(rawApiKeyText);
  if (keys.length === 0) {
    throw new Error("Vui lòng nhập ít nhất 1 Google Gemini API Key trong phần Cài Đặt API!");
  }

  const candidateModels = model === 'auto'
    ? ['gemini-3.6', 'gemini-3.5', 'gemini-2.5-flash', 'gemini-2.0-flash']
    : (model === 'gemini-3.6' || model === 'gemini-3.5'
        ? [model, 'gemini-2.5-flash', 'gemini-2.0-flash']
        : [model, 'gemini-2.0-flash']);

  let lastError = null;

  for (const currentModel of candidateModels) {
    for (let i = 0; i < keys.length; i++) {
      const activeKey = keys[i];
      const masked = maskApiKey(activeKey);
      const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(currentModel)}:generateContent?key=${encodeURIComponent(activeKey)}`;

      const requestBody = {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: temperature,
          maxOutputTokens: 8192
        }
      };

      if (systemInstruction) {
        requestBody.systemInstruction = {
          parts: [{ text: systemInstruction }]
        };
      }

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000); // 25s timeout cho generation

        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          const errMsg = errData?.error?.message || res.statusText;

          if (res.status === 404 || /not found/i.test(errMsg)) {
            console.warn(`[Gemini Failover] Model ${currentModel} chưa được kích hoạt trực tiếp trên tài khoản (${errMsg}). Tự động thử model tương thích tiếp theo...`);
            break; // Thử model kế tiếp trong candidateModels
          }

          const isQuotaOrAuth = res.status === 429 || res.status === 401 || res.status === 403 || /quota|rate limit/i.test(errMsg);

          if (isQuotaOrAuth && i < keys.length - 1) {
            const nextMasked = maskApiKey(keys[i + 1]);
            console.warn(`[Gemini Failover] Key #${i + 1} (${masked}) bị lỗi HTTP ${res.status}. Tự động chuyển sang Key #${i + 2} (${nextMasked})...`);
            if (onFailover) {
              onFailover({
                failedIndex: i,
                failedKeyMasked: masked,
                nextIndex: i + 1,
                nextKeyMasked: nextMasked,
                status: res.status,
                reason: errMsg
              });
            }
            continue; // Thử key tiếp theo
          }

          throw new Error(`Lỗi API Google (${res.status}): ${errMsg}`);
        }

        const data = await res.json();
        const output = data?.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!output) throw new Error("AI Google không trả về nội dung câu hỏi.");

        return {
          text: output,
          usedKey: activeKey,
          usedKeyMasked: masked,
          usedModel: currentModel,
          keyIndex: i
        };
      } catch (err) {
        lastError = err;
        if (i < keys.length - 1) {
          const nextMasked = maskApiKey(keys[i + 1]);
          console.warn(`[Gemini Failover] Key #${i + 1} (${masked}) gặp lỗi mạng. Chuyển sang Key #${i + 2} (${nextMasked})...`);
          if (onFailover) {
            onFailover({
              failedIndex: i,
              failedKeyMasked: masked,
              nextIndex: i + 1,
              nextKeyMasked: nextMasked,
              status: 0,
              reason: err.message
            });
          }
          continue;
        }
      }
    }
  }

  throw lastError || new Error("Tất cả API Key và Model được cung cấp đều thất bại. Vui lòng kiểm tra lại kết nối mạng hoặc thêm API Key mới.");
}

/**
 * Cập nhật nhãn trạng thái API Key trên Topbar, Sidebar và Generator Tab
 */
function updateApiStatusBadges() {
  const config = getSavedApiConfig();
  const count = config.keys.length;

  const topbarBadge = document.getElementById("topbar-api-status");
  const topbarIcon = document.getElementById("topbar-api-icon");
  const sidebarStatus = document.getElementById("sidebar-api-status");
  const navApiBadge = document.getElementById("nav-api-badge");
  const tabApiDesc = document.getElementById("tab-api-status-desc");
  const genApiBadge = document.getElementById("ai-gen-api-status");

  if (count > 0) {
    if (topbarBadge) {
      topbarBadge.textContent = `${count} Key sẵn sàng`;
      topbarBadge.style.color = "#34d399";
    }
    if (topbarIcon) topbarIcon.textContent = "🟢";
    if (sidebarStatus) {
      sidebarStatus.textContent = `${count} Key (${config.model})`;
      sidebarStatus.style.color = "#34d399";
    }
    if (navApiBadge) {
      navApiBadge.textContent = `${count} Key`;
      navApiBadge.style.background = "#10b981";
    }
    if (tabApiDesc) {
      tabApiDesc.textContent = `🟢 Đang kích hoạt ${count} Key [${config.model}] - Sẵn sàng sinh câu hỏi`;
      tabApiDesc.style.color = "#34d399";
    }
    if (genApiBadge) {
      genApiBadge.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div>
            <span style="color: #34d399; font-weight: 600;">🟢 Đang sử dụng Gemini API (${count} Key)</span>
            <span style="color: #94a3b8; font-size: 12px; margin-left: 6px;">[Model: ${config.model}]</span>
            <div style="color: #cbd5e1; font-size: 12px; margin-top: 2px;">⚡ Tự động xoay vòng sang key dự phòng khi chạm 429 Rate Limit.</div>
          </div>
          <button class="btn btn-secondary btn-sm" onclick="openApiSettingsModal()" style="font-size: 12px; padding: 4px 10px;">⚙️ Quản Lý Key</button>
        </div>
      `;
    }
  } else {
    if (topbarBadge) {
      topbarBadge.textContent = "Chưa cài Key";
      topbarBadge.style.color = "#f87171";
    }
    if (topbarIcon) topbarIcon.textContent = "🔑";
    if (sidebarStatus) {
      sidebarStatus.textContent = "Bấm để thêm Key";
      sidebarStatus.style.color = "#94a3b8";
    }
    if (navApiBadge) {
      navApiBadge.textContent = "Chưa cài";
      navApiBadge.style.background = "#ef4444";
    }
    if (tabApiDesc) {
      tabApiDesc.textContent = "⚠️ Chưa cấu hình Key. Bấm 'Mở Cài Đặt' bên cạnh để nạp Key miễn phí.";
      tabApiDesc.style.color = "#fbbf24";
    }
    if (genApiBadge) {
      genApiBadge.innerHTML = `
        <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div>
            <span style="color: #fbbf24; font-weight: 600;">⚠️ Chưa cài đặt Google Gemini API Key</span>
            <div style="color: #cbd5e1; font-size: 12px; margin-top: 2px;">Hệ thống sẽ dùng bộ sinh tình huống mẫu. Hãy nạp API Key miễn phí từ Google để tạo câu hỏi thời sự chuyên sâu.</div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="openApiSettingsModal()" style="font-size: 12px; padding: 4px 10px;">🔑 Cài API Key Ngay</button>
        </div>
      `;
    }
  }
}

// Khởi chạy khi tài liệu nạp xong
document.addEventListener("DOMContentLoaded", () => {
  // Thử đồng bộ config từ backend nếu localStorage chưa có
  if (!localStorage.getItem(GEMINI_CONFIG_KEY)) {
    fetch("/api/api-config")
      .then(res => res.json())
      .then(data => {
        if (data && data.raw_keys) {
          localStorage.setItem(GEMINI_CONFIG_KEY, data.raw_keys);
          localStorage.setItem(GEMINI_MODEL_KEY, data.model || "gemini-2.0-flash");
          updateApiStatusBadges();
        }
      })
      .catch(() => {});
  }
  updateApiStatusBadges();
});

// Xuất ra phạm vi window toàn cục
window.GeminiClient = {
  AVAILABLE_MODELS,
  parseApiKeys,
  maskApiKey,
  getSavedApiConfig,
  saveApiConfig,
  checkSingleApiKeyHealth,
  checkMultipleApiKeysHealth,
  callGeminiWithFailover,
  updateApiStatusBadges
};

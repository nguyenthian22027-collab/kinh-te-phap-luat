// GDKTPL Exam Studio Pro - Frontend Controller

let currentExam = null;
let showAnswers = false;
let currentFilter = 'all';

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initPresetSelection();
  loadStatus();
  loadCurrentExam();
  loadKnowledge();
  initResourceHandlers();
  initExportHandlers();
  initBankExplorer();
});

// TAB NAVIGATION
function initTabs() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Knowledge subtabs
  const pillBtns = document.querySelectorAll(".pill-btn");
  pillBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      pillBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".subtab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetSub = document.getElementById(btn.getAttribute("data-subtab"));
      if (targetSub) targetSub.classList.add("active");
    });
  });

  // Filter chips in preview
  const filterChips = document.querySelectorAll(".btn-chip");
  filterChips.forEach(chip => {
    chip.addEventListener("click", () => {
      filterChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.getAttribute("data-filter");
      renderExam(currentExam);
    });
  });

  // Toggle answers
  const toggleBtn = document.getElementById("btn-toggle-answers");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      showAnswers = !showAnswers;
      const textSpan = document.getElementById("toggle-ans-text");
      textSpan.textContent = showAnswers ? "Ẩn Đáp Án & Lời Giải" : "Hiện Đáp Án & Căn Cứ";
      const container = document.getElementById("exam-render-area");
      if (showAnswers) {
        container.classList.add("show-answers");
      } else {
        container.classList.remove("show-answers");
      }
      renderExam(currentExam);
    });
  }
}

function switchTab(tabId, skipAutoBank = false) {
  document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
  
  const targetNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
  const targetPane = document.getElementById(tabId);
  
  if (targetNav) targetNav.classList.add("active");
  if (targetPane) targetPane.classList.add("active");

  const headingMap = {
    "tab-generator": "Tạo Đề Thi Học Sinh Giỏi",
    "tab-preview": "Xem Trước & Biên Tập Đề Thi",
    "tab-resources": "Quản Lý & Nạp Ngữ Liệu Mới",
    "tab-bank": "Ngân Hàng Câu Hỏi & Ngữ Liệu Đã Nạp",
    "tab-knowledge": "Tra Cứu Chuyên Sâu & Mức Phạt",
    "tab-export": "Trung Tâm Xuất File Word (.docx)"
  };
  const headingEl = document.getElementById("page-heading");
  if (headingEl && headingMap[tabId]) {
    headingEl.textContent = headingMap[tabId];
  }

  if (tabId === 'tab-bank' && !skipAutoBank) {
    loadBankSources();
    loadBankQuestions();
  }
}

function initPresetSelection() {
  const presetLabels = document.querySelectorAll(".preset-option");
  presetLabels.forEach(label => {
    label.addEventListener("click", () => {
      presetLabels.forEach(l => l.classList.remove("active"));
      label.classList.add("active");
      const radio = label.querySelector("input[type='radio']");
      if (radio) radio.checked = true;
    });
  });

  const btnGen = document.getElementById("btn-generate-exam");
  if (btnGen) {
    btnGen.addEventListener("click", async () => {
      if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("Sinh đề thi theo ma trận"))) {
        return;
      }
      const selectedPreset = document.querySelector("input[name='preset-select']:checked").value;
      const examInfo = {
        header_left: document.getElementById("cfg-header-left").value,
        exam_title: document.getElementById("cfg-title").value,
        school_year: document.getElementById("cfg-year").value,
        duration: document.getElementById("cfg-duration").value,
        code: document.getElementById("current-code-display").textContent || "097"
      };

      btnGen.disabled = true;
      btnGen.innerHTML = `<span>⏳</span> ĐANG XỬ LÝ MA TRẬN & SINH ĐỀ...`;

      fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset: selectedPreset, exam_info: examInfo })
      })
      .then(res => res.json())
      .then(data => {
        currentExam = data;
        renderExam(currentExam);
        updateCodeDisplay(currentExam.info?.code || "097");
        switchTab("tab-preview");
      })
      .catch(err => {
        alert("Lỗi khi tạo đề: " + err);
      })
      .finally(() => {
        btnGen.disabled = false;
        btnGen.innerHTML = `<span>✨</span> BẮT ĐẦU SINH ĐỀ THI THEO MA TRẬN`;
      });
    });
  }
}

// STATUS & STATS
function loadStatus() {
  fetch("/api/status")
    .then(res => res.json())
    .then(data => {
      document.getElementById("stat-p1-count").textContent = `${data.total_part1} câu`;
      document.getElementById("stat-p2-count").textContent = `${data.total_part2} câu`;
      document.getElementById("stat-total-count").textContent = `${data.total_questions} câu`;
      const bankNavCount = document.getElementById("bank-nav-count");
      if (bankNavCount) {
        bankNavCount.textContent = data.total_questions;
      }
      const statusTag = document.getElementById("matrix-status-tag");
      if (statusTag) {
        statusTag.textContent = `Ngân hàng đạt chuẩn (${data.total_questions} câu)`;
      }
    })
    .catch(err => console.error("Error loading status:", err));
}

// LOAD ACTIVE EXAM
function loadCurrentExam() {
  fetch("/api/current-exam")
    .then(res => res.json())
    .then(data => {
      currentExam = data;
      renderExam(currentExam);
      updateCodeDisplay(currentExam.info?.code || "097");
    })
    .catch(err => console.error("Error loading exam:", err));
}

function updateCodeDisplay(code) {
  const el = document.getElementById("current-code-display");
  if (el) el.textContent = code;
}

// RENDER EXAM TO PREVIEW
function renderExam(exam) {
  const container = document.getElementById("exam-render-area");
  if (!exam || (!exam.part1 && !exam.part2)) {
    container.innerHTML = `<div class="loading-state"><p>Chưa có câu hỏi nào. Hãy bấm "Tạo Đề Thi".</p></div>`;
    return;
  }

  const badgeCount = document.getElementById("exam-badge-count");
  if (badgeCount) {
    badgeCount.textContent = (exam.part1?.length || 0) + (exam.part2?.length || 0);
  }

  let html = `
    <div class="paper-header">
      <div class="paper-left">
        <div>${(exam.info?.header_left || "SỞ GD&ĐT HẢI PHÒNG").replace(/\n/g, "<br>")}</div>
        <div style="font-size: 12px; margin-top: 4px; font-weight: normal; font-style: italic;">ĐỀ CHÍNH THỨC</div>
      </div>
      <div class="paper-right">
        <div class="paper-title">${exam.info?.exam_title || "KỲ THI CHỌN HỌC SINH GIỎI THÀNH PHỐ"}</div>
        <div>NĂM HỌC: ${exam.info?.school_year || "2026 - 2027"}</div>
        <div>MÔN THI: ${exam.info?.subject || "GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT"}</div>
        <div style="font-size: 12px; font-style: italic;">Thời gian làm bài: ${exam.info?.duration || "90 phút"}</div>
        <div style="font-weight: bold; margin-top: 2px;">MÃ ĐỀ: ${exam.info?.code || "097"}</div>
      </div>
    </div>
    <div class="paper-candidate-bar">
      Họ và tên thí sinh: ................................................................................. Số báo danh: .............................
    </div>
  `;

  // RENDER PART I
  if (currentFilter === 'all' || currentFilter === 'part1') {
    html += `
      <div class="section-divider-title">PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn (6,0 điểm)</div>
      <div class="section-desc">Thí sinh trả lời từ câu 1 đến câu ${exam.part1?.length || 40}. Mỗi câu hỏi thí sinh chỉ chọn một phương án.</div>
    `;

    (exam.part1 || []).forEach((q, idx) => {
      const qNum = q.exam_number || (idx + 1);
      const lvlClass = q.level === 'biet' ? 'q-badge-biet' : (q.level === 'hieu' ? 'q-badge-hieu' : 'q-badge-van-dung');
      const lvlName = q.level === 'biet' ? 'Biết' : (q.level === 'hieu' ? 'Hiểu' : 'Vận dụng');

      html += `
        <div class="question-item" id="q-item-${q.id}">
          <div class="question-header">
            <div class="question-meta">
              <span class="q-badge ${lvlClass}">${lvlName}</span>
              <span class="q-badge q-badge-grade">Lớp ${q.grade || 11}</span>
              <span class="tag">${q.topic || 'GDKT&PL'}</span>
              <span class="source-tag" style="font-size:10px;">📁 ${escapeHtml(q.source || 'Đề gốc')}</span>
            </div>
            <div class="question-tools">
              <button class="btn-tool btn-tool-primary" onclick="openReplacementModal('${q.id}', 'part1')">🎯 Chọn câu thay thế</button>
              <button class="btn-tool btn-tool-reroll" onclick="rerollItem('${q.id}', 'part1')">🎲 Đổi ngẫu nhiên</button>
              <button class="btn-tool" onclick="openEditModal('${q.id}', 'part1')">✏️ Sửa</button>
            </div>
          </div>
          <div class="question-stem"><strong>Câu ${qNum}:</strong> ${escapeHtml(q.stem)}</div>
          <div class="options-grid">
      `;

      const opts = q.options || {};
      ['A', 'B', 'C', 'D'].forEach(optKey => {
        if (opts[optKey]) {
          const isCorrect = (showAnswers && q.answer === optKey);
          html += `
            <div class="option-line ${isCorrect ? 'correct' : ''}">
              <strong>${optKey}.</strong> ${escapeHtml(opts[optKey])}
            </div>
          `;
        }
      });

      html += `
          </div>
          <div class="explanation-card">
            <strong>Đáp án đúng: ${q.answer || 'A'}</strong> | ${escapeHtml(q.explanation || 'Căn cứ quy định chuyên đề.')}
          </div>
        </div>
      `;
    });
  }

  // RENDER PART II
  if (currentFilter === 'all' || currentFilter === 'part2') {
    html += `
      <div class="section-divider-title">PHẦN II. Câu trắc nghiệm đúng sai (4,0 điểm)</div>
      <div class="section-desc">Thí sinh trả lời từ câu 1 đến câu ${exam.part2?.length || 8}. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai.</div>
    `;

    (exam.part2 || []).forEach((q, idx) => {
      const qNum = q.exam_number || (idx + 1);
      html += `
        <div class="question-item" id="q-item-${q.id}">
          <div class="question-header">
            <div class="question-meta">
              <span class="q-badge q-badge-van-dung">Đúng / Sai</span>
              <span class="q-badge q-badge-grade">Lớp ${q.grade || 12}</span>
              <span class="tag">${q.topic || 'Chuyên đề'}</span>
              <span class="source-tag" style="font-size:10px;">📁 ${escapeHtml(q.source || 'Đề gốc')}</span>
            </div>
            <div class="question-tools">
              <button class="btn-tool btn-tool-primary" onclick="openReplacementModal('${q.id}', 'part2')">🎯 Chọn câu thay thế</button>
              <button class="btn-tool btn-tool-reroll" onclick="rerollItem('${q.id}', 'part2')">🎲 Đổi ngẫu nhiên</button>
              <button class="btn-tool" onclick="openEditModal('${q.id}', 'part2')">✏️ Sửa</button>
            </div>
          </div>
          <div class="question-stem"><strong>Câu ${qNum}:</strong> ${escapeHtml(q.stem).replace(/\n/g, "<br>")}</div>
          <div class="statements-list">
      `;

      (q.statements || []).forEach(stmt => {
        const isTrue = stmt.answer === true;
        const tagHtml = showAnswers ? 
          `<span class="stmt-tag ${isTrue ? 'stmt-tag-true' : 'stmt-tag-false'}">${isTrue ? 'ĐÚNG' : 'SAI'}</span>` : '';
          
        html += `
          <div class="statement-row">
            <strong>${stmt.label || 'a'})</strong>
            <span>${escapeHtml(stmt.text)}</span>
            ${tagHtml}
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
}

// REROLL QUESTION
window.rerollItem = function(qId, qType) {
  const itemEl = document.getElementById(`q-item-${qId}`);
  if (itemEl) itemEl.style.opacity = '0.4';

  fetch("/api/reroll", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q_id: qId, q_type: qType })
  })
  .then(res => res.json())
  .then(data => {
    currentExam = data.exam;
    renderExam(currentExam);
  })
  .catch(err => {
    alert("Lỗi khi đổi câu hỏi: " + err);
    if (itemEl) itemEl.style.opacity = '1';
  });
};

// EDIT QUESTION MODAL
window.openEditModal = function(qId, qType) {
  const targetList = qType === 'part1' ? currentExam.part1 : currentExam.part2;
  const q = targetList.find(item => item.id === qId);
  if (!q) return;

  document.getElementById("modal-title").textContent = `Chỉnh Sửa Câu Hỏi Trong Đề Thi (Câu ${q.exam_number || ''})`;
  document.getElementById("edit-q-id").value = q.id;
  document.getElementById("edit-q-type").value = qType;
  document.getElementById("edit-q-mode").value = "exam";
  document.getElementById("edit-q-grade").value = q.grade || 11;
  document.getElementById("edit-q-level").value = q.level || 'hieu';
  document.getElementById("edit-q-stem").value = q.stem || "";
  document.getElementById("edit-q-explanation").value = q.explanation || "";

  if (qType === 'part1') {
    document.getElementById("edit-part1-options").style.display = "block";
    document.getElementById("edit-part2-statements").style.display = "none";
    document.getElementById("edit-opt-A").value = q.options?.A || "";
    document.getElementById("edit-opt-B").value = q.options?.B || "";
    document.getElementById("edit-opt-C").value = q.options?.C || "";
    document.getElementById("edit-opt-D").value = q.options?.D || "";
    document.getElementById("edit-q-ans").value = q.answer || "A";
  } else {
    document.getElementById("edit-part1-options").style.display = "none";
    document.getElementById("edit-part2-statements").style.display = "block";
    const stmtsBox = document.getElementById("p2-statements-editor");
    let stmtsHtml = "";
    (q.statements || []).forEach(s => {
      stmtsHtml += `
        <div class="opt-edit-row" style="margin-bottom: 8px;">
          <strong style="width: 25px;">${s.label})</strong>
          <input type="text" class="form-control edit-stmt-text" data-label="${s.label}" value="${escapeHtml(s.text)}" style="flex:1;">
          <select class="form-control edit-stmt-ans" data-label="${s.label}" style="width: 80px;">
            <option value="true" ${s.answer ? 'selected' : ''}>Đúng</option>
            <option value="false" ${!s.answer ? 'selected' : ''}>Sai</option>
          </select>
        </div>
      `;
    });
    stmtsBox.innerHTML = stmtsHtml;
  }

  document.getElementById("edit-modal").classList.add("active");
};

window.openBankEditModal = function(qId, qType) {
  fetch(`/api/question/${encodeURIComponent(qId)}`)
    .then(res => {
      if (!res.ok) throw new Error("Không tìm thấy câu hỏi");
      return res.json();
    })
    .then(data => {
      const q = data.question;
      if (!q) {
        alert("Không tìm thấy câu hỏi trong ngân hàng.");
        return;
      }
      const actualType = qType || q.type || (q.options ? "part1" : "part2");
      document.getElementById("modal-title").textContent = `Chỉnh Sửa Câu Hỏi & Khối Lớp Trong Ngân Hàng`;
      document.getElementById("edit-q-id").value = q.id;
      document.getElementById("edit-q-type").value = actualType;
      document.getElementById("edit-q-mode").value = "bank";
      document.getElementById("edit-q-grade").value = q.grade || 11;
      document.getElementById("edit-q-level").value = q.level || 'hieu';
      document.getElementById("edit-q-stem").value = q.stem || "";
      document.getElementById("edit-q-explanation").value = q.explanation || "";

      if (actualType === 'part1') {
        document.getElementById("edit-part1-options").style.display = "block";
        document.getElementById("edit-part2-statements").style.display = "none";
        document.getElementById("edit-opt-A").value = q.options?.A || "";
        document.getElementById("edit-opt-B").value = q.options?.B || "";
        document.getElementById("edit-opt-C").value = q.options?.C || "";
        document.getElementById("edit-opt-D").value = q.options?.D || "";
        document.getElementById("edit-q-ans").value = q.answer || "A";
      } else {
        document.getElementById("edit-part1-options").style.display = "none";
        document.getElementById("edit-part2-statements").style.display = "block";
        const stmtsBox = document.getElementById("p2-statements-editor");
        let stmtsHtml = "";
        (q.statements || []).forEach(s => {
          stmtsHtml += `
            <div class="opt-edit-row" style="margin-bottom: 8px;">
              <strong style="width: 25px;">${s.label})</strong>
              <input type="text" class="form-control edit-stmt-text" data-label="${s.label}" value="${escapeHtml(s.text)}" style="flex:1;">
              <select class="form-control edit-stmt-ans" data-label="${s.label}" style="width: 80px;">
                <option value="true" ${s.answer ? 'selected' : ''}>Đúng</option>
                <option value="false" ${!s.answer ? 'selected' : ''}>Sai</option>
              </select>
            </div>
          `;
        });
        stmtsBox.innerHTML = stmtsHtml;
      }

      document.getElementById("edit-modal").classList.add("active");
    })
    .catch(err => alert("Lỗi khi tải thông tin câu hỏi: " + err));
};

window.closeEditModal = function() {
  document.getElementById("edit-modal").classList.remove("active");
};

window.saveQuestionEdit = function() {
  const qId = document.getElementById("edit-q-id").value;
  const qType = document.getElementById("edit-q-type").value;
  const mode = document.getElementById("edit-q-mode").value || "exam";
  const grade = parseInt(document.getElementById("edit-q-grade").value) || 11;
  const level = document.getElementById("edit-q-level").value || "hieu";
  const stem = document.getElementById("edit-q-stem").value;
  const explanation = document.getElementById("edit-q-explanation").value;

  const payload = {
    q_id: qId,
    q_type: qType,
    grade: grade,
    level: level,
    stem: stem,
    explanation: explanation
  };

  if (qType === 'part1') {
    payload.options = {
      A: document.getElementById("edit-opt-A").value,
      B: document.getElementById("edit-opt-B").value,
      C: document.getElementById("edit-opt-C").value,
      D: document.getElementById("edit-opt-D").value
    };
    payload.answer = document.getElementById("edit-q-ans").value;
  } else {
    const stmts = [];
    document.querySelectorAll(".edit-stmt-text").forEach(input => {
      const lbl = input.getAttribute("data-label");
      const ansSelect = document.querySelector(`.edit-stmt-ans[data-label="${lbl}"]`);
      stmts.push({
        label: lbl,
        text: input.value,
        answer: ansSelect.value === 'true'
      });
    });
    payload.statements = stmts;
  }

  const endpoint = (mode === 'bank') ? "/api/update-bank-question" : "/api/update-question";

  fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    if (mode === 'bank') {
      loadBankQuestions();
      loadStatus();
      closeEditModal();
      alert("✅ Đã cập nhật câu hỏi và khối lớp trong Ngân Hàng thành công!");
    } else {
      currentExam = data.exam;
      renderExam(currentExam);
      closeEditModal();
      alert("✅ Đã cập nhật câu hỏi trong đề thi thành công!");
    }
  })
  .catch(err => alert("Lỗi khi lưu: " + err));
};

// RESOURCE HUB HANDLERS
function initResourceHandlers() {
  // Upload file
  const fileInput = document.getElementById("file-input");
  if (fileInput) {
    fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("Thẩm định & Nạp đề thi từ tệp"))) {
        fileInput.value = "";
        return;
      }

      const apiConfig = window.GeminiClient ? window.GeminiClient.getSavedApiConfig() : { rawKeys: "", model: "gemini-3.5" };
      const cbAiSolver = document.getElementById("cb-use-ai-solver");
      const useAiSolver = cbAiSolver ? cbAiSolver.checked : true;

      const formData = new FormData();
      formData.append("file", file);
      if (apiConfig.rawKeys) {
        formData.append("raw_keys", apiConfig.rawKeys);
        formData.append("model", apiConfig.model || "gemini-3.5");
      }
      formData.append("use_ai_solver", useAiSolver);

      const zone = document.getElementById("upload-zone");
      zone.innerHTML = `
        <div class="spinner"></div>
        <p>${useAiSolver && apiConfig.rawKeys ? '🤖 AI đang đọc hiểu, thẩm định & giải chi tiết đáp án toàn bộ đề thi...' : 'Đang bóc tách và phân tích ngữ liệu từ tệp...'}</p>
        <small style="color: #94a3b8;">Quá trình có thể mất từ 5 - 15 giây đối với đề thi dài.</small>
      `;

      fetch("/api/import-file", {
        method: "POST",
        body: formData
      })
      .then(res => res.json())
      .then(res => {
        const solvedNote = res.is_ai_solved ? "\n🤖 (Đã được AI thẩm định và giải chi tiết đáp án 100%!)" : "";
        alert(`✅ Nạp thành công tệp: ${res.filename}!\nBổ sung thêm: ${res.total_imported} câu hỏi (${res.imported_part1} câu TN, ${res.imported_part2} câu Đúng/Sai).${solvedNote}`);
        loadStatus();
        zone.innerHTML = `
          <div class="dropzone-icon">✅</div>
          <h4>Đã nạp thành công: ${escapeHtml(res.filename)}</h4>
          <p>Tìm thấy ${res.total_imported} câu hỏi mới được đưa vào ngân hàng.</p>
          ${res.is_ai_solved ? '<div style="color: #34d399; font-weight: 600; margin: 6px 0; font-size: 13px;">✨ Toàn bộ câu hỏi đã được AI giải chính xác & viện dẫn điều luật!</div>' : ''}
          <div style="display: flex; gap: 10px; justify-content: center; margin-top: 14px; flex-wrap: wrap;">
            <button class="btn btn-primary" onclick="viewSourceInBank('${escapeHtml(res.filename)}')">👁️ Xem ${res.total_imported} câu vừa nạp trong Ngân Hàng</button>
            <button class="btn btn-secondary" onclick="document.getElementById('file-input').click()">Tải thêm tệp khác</button>
          </div>
        `;
      })
      .catch(err => {
        alert("Lỗi tải tệp: " + err);
        loadStatus();
      });
    });
  }

  // Paste text
  const btnPaste = document.getElementById("btn-import-paste");
  if (btnPaste) {
    btnPaste.addEventListener("click", async () => {
      const text = document.getElementById("paste-text-area").value.trim();
      if (!text) {
        alert("Vui lòng dán nội dung văn bản câu hỏi.");
        return;
      }

      if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("Thẩm định & Nạp đề từ văn bản"))) {
        return;
      }

      const apiConfig = window.GeminiClient ? window.GeminiClient.getSavedApiConfig() : { rawKeys: "", model: "gemini-3.5" };
      const cbAiSolver = document.getElementById("cb-use-ai-solver");
      const useAiSolver = cbAiSolver ? cbAiSolver.checked : true;

      btnPaste.disabled = true;
      btnPaste.innerHTML = `<span>⏳</span> Đang phân tích & thẩm định...`;

      fetch("/api/import-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          source_name: "Dán trực tiếp",
          raw_keys: apiConfig.rawKeys,
          model: apiConfig.model || "gemini-3.5",
          use_ai_solver: useAiSolver
        })
      })
      .then(res => res.json())
      .then(res => {
        btnPaste.disabled = false;
        btnPaste.innerHTML = `<span>➕</span> Nhận Diện & Nạp Vào Ngân Hàng`;
        const solvedNote = res.is_ai_solved ? "\n🤖 (Đã được AI thẩm định và giải chi tiết đáp án 100%!)" : "";
        alert(`✅ Nạp thành công!\nPhần I: ${res.imported_part1} câu, Phần II: ${res.imported_part2} câu.${solvedNote}`);
        document.getElementById("paste-text-area").value = "";
        loadStatus();
        viewSourceInBank("Dán trực tiếp");
      })
      .catch(err => {
        btnPaste.disabled = false;
        btnPaste.innerHTML = `<span>➕</span> Nhận Diện & Nạp Vào Ngân Hàng`;
        alert("Lỗi khi nạp văn bản: " + err);
      });
    });
  }

  // Fetch URL
  const btnUrl = document.getElementById("btn-fetch-url");
  if (btnUrl) {
    btnUrl.addEventListener("click", async () => {
      const url = document.getElementById("input-web-url").value.trim();
      if (!url) {
        alert("Vui lòng nhập đường link URL.");
        return;
      }

      if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("Bóc tách đề thi từ web"))) {
        return;
      }
      const numQuestionsSelect = document.getElementById("url-num-questions");
      const numQ = numQuestionsSelect ? parseInt(numQuestionsSelect.value) || 5 : 5;
      const apiConfig = window.GeminiClient ? window.GeminiClient.getSavedApiConfig() : { rawKeys: "", model: "gemini-3.5" };

      resBox.innerHTML = `<div class="spinner"></div><span>Đang kết nối trang web, bóc tách bài viết & AI đang phân tích sinh ${numQ} câu hỏi...</span>`;

      fetch("/api/import-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: url,
          num_questions: numQ,
          raw_keys: apiConfig.rawKeys,
          model: apiConfig.model || "gemini-3.5"
        })
      })
      .then(res => res.json())
      .then(res => {
        if (res.status === 'success') {
          const total = res.total_imported || 0;
          const srcName = res.source_name || `Web: ${res.title.substring(0, 35)}`;
          let resultMsg = "";
          
          if (total > 0) {
            resultMsg = `
              <strong>✅ Đã thu thập bài viết & tạo câu hỏi thành công!</strong><br>
              <strong>Tiêu đề:</strong> ${escapeHtml(res.title)}<br>
              <span style="color: #34d399; font-weight: 600;">✨ Đã tự động tạo & nạp ${total} câu hỏi mới (${res.imported_part1} câu Phần I, ${res.imported_part2} câu Phần II) vào Ngân Hàng!</span>
              <div style="margin-top: 10px;">
                <button class="btn btn-primary btn-sm" onclick="viewSourceInBank('${escapeHtml(srcName)}')">👁️ Xem ngay ${total} câu hỏi vừa tạo trong Ngân Hàng</button>
              </div>
            `;
          } else {
            resultMsg = `
              <strong>✅ Đã thu thập bài viết:</strong> ${escapeHtml(res.title)}<br>
              <small>Nội dung (${res.text_length} ký tự) đã được lưu vào kho ngữ liệu tham khảo.</small>
            `;
          }
          
          resBox.innerHTML = `
            <div style="background: rgba(16, 185, 129, 0.1); padding: 12px; border-radius: 6px; border: 1px solid #10b981; color: #a7f3d0;">
              ${resultMsg}
            </div>
          `;
          loadStatus();
        } else {
          resBox.innerHTML = `<span style="color: #ef4444;">❌ Lỗi: ${res.message}</span>`;
        }
      })
      .catch(err => {
        resBox.innerHTML = `<span style="color: #ef4444;">❌ Lỗi: ${err}</span>`;
      });
    });
  }

  // AI Generator
  const btnAi = document.getElementById("btn-ai-generate");
  if (btnAi) {
    btnAi.addEventListener("click", async () => {
      if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("AI sinh câu hỏi tình huống"))) {
        return;
      }
      const topic = document.getElementById("ai-topic-select").value;
      const level = document.getElementById("ai-level-select").value;
      const grade = parseInt(document.getElementById("ai-grade-select")?.value || "12");
      const qType = document.getElementById("ai-type-select")?.value || "part1";
      const customPrompt = document.getElementById("ai-custom-prompt").value.trim();
      const resBox = document.getElementById("ai-gen-result");

      const apiConfig = window.GeminiClient ? window.GeminiClient.getSavedApiConfig() : { hasKeys: false, rawKeys: "", model: "gemini-2.0-flash" };
      const hasKeys = apiConfig.hasKeys;

      resBox.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #38bdf8; border-radius: 8px; padding: 14px; margin-top: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="spinner"></div>
            <span id="ai-gen-live-status" style="color: #bae6fd; font-size: 13.5px;">
              ${hasKeys ? `🤖 Đang kết nối Gemini (${apiConfig.model}) và biên soạn câu hỏi theo chuẩn HSG GDPT 2018...` : `Đang kích hoạt bộ sinh kịch bản tình huống pháp luật...`}
            </span>
          </div>
        </div>
      `;

      // 1. If keys are present, use frontend multi-key auto-failover engine
      if (hasKeys && window.GeminiClient) {
        try {
          const systemInstruction = `Bạn là Chuyên gia Khảo thí và Đo lường Giáo dục hàng đầu Việt Nam, chuyên gia thẩm định và biên soạn đề thi Học sinh giỏi (HSG) cấp Tỉnh/Thành phố và Quốc gia môn GIÁO DỤC KINH TẾ VÀ PHÁP LUẬT (GDKT&PL) theo đúng Chương trình Giáo dục phổ thông (GDPT) 2018 của Bộ Giáo dục và Đào tạo.

QUY TẮC CỐT LÕI BẮT BUỘC:
1. ĐÚNG BẢN CHẤT MÔN GDKT&PL (GDPT 2018):
   - Môn học gồm 2 hợp phần khoa học: Giáo dục Kinh tế (Applied Economics) và Giáo dục Pháp luật (Jurisprudence).
   - Tuyệt đối KHÔNG nhầm sang GDCD cũ (không ra câu hỏi đạo đức giáo điều, cảm tính).
   - Nội dung phải chính xác tuyệt đối về thuật ngữ kinh tế và pháp luật thực định Việt Nam.

2. PHÂN ĐỊNH RÕ PHẠM VI CHƯƠNG TRÌNH VÀ CĂN CỨ PHÁP LÝ THEO KHỐI LỚP:
   - Lớp 10: 4 hình thức thực hiện PL (Sử dụng PL - thực hiện quyền; Thi hành PL - làm điều luật bắt buộc; Tuân thủ PL - không làm điều cấm; Áp dụng PL - cơ quan có thẩm quyền); 4 loại vi phạm PL & trách nhiệm pháp lý (Hình sự, Hành chính, Dân sự, Kỷ luật); Hệ thống chính trị & Bộ máy nhà nước; Hoạt động kinh tế, ngân sách, thuế, mô hình SXKD. (Căn cứ: Hiến pháp 2013, Luật Xử lý VPHC, Nghị định 144/2021/NĐ-CP, BLHS 2015, BLDS 2015).
   - Lớp 11: Quyền bình đẳng của công dân (Trước PL, Hôn nhân - GĐ, Lao động, Kinh doanh); Các quyền dân chủ cơ bản (Bầu cử - ứng cử: 18 và 21 tuổi; Khiếu nại - tố cáo; Quản lý nhà nước); Các quyền tự do cơ bản (Thân thể, Tính mạng-sức khỏe-danh dự-nhân phẩm, Chỗ ở, Thư tín, Ngôn luận); Cạnh tranh, Cung - Cầu, Lạm phát, Thất nghiệp. (Căn cứ: BLDS 2015, BLLĐ 2019, BLHS 2015 Đ155-158, Luật Khiếu nại 2011, Luật Tố cáo 2018, Nghị định 144/2021/NĐ-CP).
   - Lớp 12: Tăng trưởng & Phát triển kinh tế (GDP, GNI, HDI, tăng trưởng xanh); Hội nhập kinh tế quốc tế (FTA, CPTPP, EVFTA, WTO); BẢO HIỂM & AN SINH XÃ HỘI (CẬP NHẬT LUẬT BHXH 2024 - HIỆU LỰC TỪ 01/07/2025: giảm thời gian đóng tối thiểu hưởng lương hưu xuống 15 năm, xử lý hình sự hành vi trốn đóng theo Điều 216 BLHS, chủ hộ kinh doanh bắt buộc tham gia; 4 trụ cột an sinh xã hội); Quyền công dân về kinh tế, văn hóa, xã hội; Pháp luật biển đảo. (Căn cứ: Luật BHXH 2024, BLLĐ 2019, BLDS 2015, BLHS 2015 Đ216, Luật Doanh nghiệp 2020, Luật Biển VN 2012).

3. ĐẢM BẢO CĂN CỨ PHÁP LÝ HIỆN HÀNH: Trích dẫn chính xác điều khoản, tên văn bản luật hiện hành. Tuyệt đối không bịa điều luật hoặc dùng văn bản hết hiệu lực.

4. CẤU TRÚC PHÂN HÓA HSG:
   - Mức Biết: Trực diện, chuẩn xác về định nghĩa, khái niệm, hình thức, thẩm quyền. Không gượng ép tình huống 4 người.
   - Mức Hiểu: Tình huống ngắn hoặc phân tích bản chất, phân biệt loại vi phạm, nhận diện hậu quả pháp lý.
   - Mức Vận dụng: Tình huống phức hợp 3-4 nhân vật, đan xen đúng/sai, lệnh hỏi tổ hợp ("Những ai dưới đây..."), 4 phương án là tổ hợp tên nhân vật gây nhiễu sâu sắc. Lời giải bóc tách chi tiết từng nhân vật kèm điều luật cụ thể.`;

          // Xây dựng prompt Phần I chuẩn hóa riêng theo mức độ nhận thức
          let promptP1 = "";
          if (level === "biet") {
            promptP1 = `Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp ${grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ NHẬN BIẾT (BIẾT), chuyên đề: "${topic}".
YÊU CẦU:
1. Câu hỏi ngắn gọn, chuẩn xác, kiểm tra trực diện nhận diện định nghĩa, khái niệm, thẩm quyền cơ quan nhà nước, 4 hình thức thực hiện pháp luật (Sử dụng, Thi hành, Tuân thủ, Áp dụng), 4 loại vi phạm pháp luật, chỉ tiêu kinh tế (GDP, GNI, Luật BHXH 2024...).
2. TUYỆT ĐỐI KHÔNG xây dựng tình huống phức hợp 3-4 nhân vật dài dòng khiên cưỡng cho câu hỏi mức độ Nhận biết.
3. 4 phương án rõ ràng: 1 phương án đúng và 3 phương án nhiễu phản ánh sai lầm phổ biến của học sinh.
4. Lời giải (explanation) giải thích chuẩn xác kèm điều luật hoặc kiến thức GDPT 2018.
5. Trả về DUY NHẤT một chuỗi JSON hợp lệ:
{
  "type": "part1",
  "stem": "Câu hỏi nhận biết trực diện...",
  "options": {
    "A": "Phương án A...",
    "B": "Phương án B...",
    "C": "Phương án C...",
    "D": "Phương án D..."
  },
  "answer": "A",
  "explanation": "Căn cứ lý giải chính xác kèm điều luật/khái niệm...",
  "grade": ${grade},
  "topic": "${topic}",
  "level": "biet"
}`;
          } else if (level === "hieu") {
            promptP1 = `Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp ${grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ THÔNG HIỂU (HIỂU), chuyên đề: "${topic}".
YÊU CẦU:
1. Câu hỏi yêu cầu phân tích bản chất kinh tế/pháp lý, phân biệt các hình thức thực hiện pháp luật, phân loại hành vi vi phạm, xác định hậu quả pháp lý trong một ngữ cảnh/tình huống ngắn gọn (1-2 chủ thể).
2. 4 phương án là các nhận định giải thích bản chất, đòi hỏi tư duy so sánh, loại trừ logic.
3. Lời giải (explanation) phân tích rõ bản chất và viện dẫn căn cứ pháp lý/kinh tế.
4. Trả về DUY NHẤT một chuỗi JSON hợp lệ:
{
  "type": "part1",
  "stem": "Tình huống ngắn hoặc câu hỏi phân tích bản chất...",
  "options": {
    "A": "Phương án A...",
    "B": "Phương án B...",
    "C": "Phương án C...",
    "D": "Phương án D..."
  },
  "answer": "A",
  "explanation": "Lập luận giải thích bản chất kèm điều luật...",
  "grade": ${grade},
  "topic": "${topic}",
  "level": "hieu"
}`;
          } else {
            promptP1 = `Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp ${grade} - PHẦN I (Trắc nghiệm 4 lựa chọn A, B, C, D) mức độ VẬN DỤNG (VẬN DỤNG CAO), chuyên đề: "${topic}".
YÊU CẦU ĐẶC TRƯNG THI HSG:
1. Tình huống phức hợp từ 3 - 4 nhân vật thuần Việt (ông A, bà B, anh C, chị D...) đan xen nhiều quan hệ pháp lý và hành vi đúng/sai.
2. Lệnh hỏi phân hóa cao chuẩn HSG: "Những ai dưới đây vừa vi phạm... vừa vi phạm...", "Những ai dưới đây phải chịu trách nhiệm pháp lý...", "Những ai dưới đây đã không tuân thủ pháp luật?".
3. 4 phương án A, B, C, D là CÁC TỔ HỢP TÊN NHÂN VẬT có độ nhiễu sâu sắc.
4. Lời giải (explanation) bắt buộc bóc tách tường tận hành vi của TỪNG nhân vật kèm điều luật cụ thể.
5. Trả về DUY NHẤT một chuỗi JSON hợp lệ:
{
  "type": "part1",
  "stem": "Tình huống thời sự đa nhân vật và lệnh hỏi phân hóa...",
  "options": {
    "A": "Tổ hợp nhân vật A...",
    "B": "Tổ hợp nhân vật B...",
    "C": "Tổ hợp nhân vật C...",
    "D": "Tổ hợp nhân vật D..."
  },
  "answer": "A",
  "explanation": "Lập luận bóc tách chi tiết từng nhân vật kèm căn cứ điều luật hiện hành...",
  "grade": ${grade},
  "topic": "${topic}",
  "level": "van_dung"
}`;
          }

          const promptP2 = `Tạo 01 câu hỏi thi Học sinh giỏi (HSG) môn GDKT&PL lớp ${grade} - PHẦN II (Trắc nghiệm Đúng/Sai 4 lệnh hỏi a, b, c, d) mức độ ${level.toUpperCase()}, chuyên đề: "${topic}".
YÊU CẦU CHUẨN MỰC HSG:
1. Thân câu dẫn là một đoạn ngữ liệu thực tế/thời sự (bài báo, vụ việc pháp lý, dữ liệu kinh tế) giàu thông tin và bối cảnh cụ thể.
2. 4 lệnh hỏi a, b, c, d độc lập kiểm tra đúng 4 mức độ nhận thức:
   - a (Nhận biết): Khái niệm, chỉ tiêu, chủ thể hoặc quy định pháp luật được nêu trực tiếp trong ngữ liệu.
   - b (Thông hiểu): Bản chất kinh tế/pháp lý, nguyên nhân hoặc phân loại hiện tượng.
   - c (Vận dụng): Phân tích, đánh giá tính đúng/sai trong hành vi của các chủ thể trong tình huống.
   - d (Vận dụng cao / Đánh giá): Đánh giá trách nhiệm pháp lý, xử phạt, giải pháp hoặc nghĩa vụ công dân.
3. Tỷ lệ Đúng/Sai cân bằng, lập luận sắc bén (2 Đúng - 2 Sai, hoặc 1 Đúng - 3 Sai / 3 Đúng - 1 Sai; TUYỆT ĐỐI KHÔNG để 4 ý toàn Đúng hoặc toàn Sai).
4. Mỗi lệnh hỏi đều phải có kết quả boolean (true/false) và căn cứ pháp lý giải thích chi tiết.
5. Trả về DUY NHẤT một chuỗi JSON hợp lệ:
{
  "type": "part2",
  "stem": "Đoạn tình huống thời sự chi tiết...",
  "statements": [
    {"label": "a", "text": "Lệnh hỏi nhận biết...", "answer": true, "explanation": "Căn cứ điều luật...", "level": "biet", "grade": ${grade}, "topic": "${topic}"},
    {"label": "b", "text": "Lệnh hỏi thông hiểu...", "answer": false, "explanation": "Căn cứ điều luật...", "level": "hieu", "grade": ${grade}, "topic": "${topic}"},
    {"label": "c", "text": "Lệnh hỏi vận dụng...", "answer": true, "explanation": "Căn cứ điều luật...", "level": "van_dung", "grade": ${grade}, "topic": "${topic}"},
    {"label": "d", "text": "Lệnh hỏi vận dụng cao...", "answer": false, "explanation": "Căn cứ điều luật...", "level": "van_dung", "grade": ${grade}, "topic": "${topic}"}
  ],
  "grade": ${grade},
  "topic": "${topic}",
  "level": "${level}"
}`;

          let targetPrompt = qType === 'part1' ? promptP1 : promptP2;
          if (customPrompt) {
            targetPrompt += `\n\nYêu cầu bổ sung đặc thù của giáo viên: ${customPrompt}`;
          }

          const geminiRes = await window.GeminiClient.callGeminiWithFailover({
            rawApiKeyText: apiConfig.rawKeys,
            model: apiConfig.model,
            prompt: targetPrompt,
            systemInstruction: systemInstruction,
            onFailover: (info) => {
              const liveStatus = document.getElementById("ai-gen-live-status");
              if (liveStatus) {
                liveStatus.innerHTML = `⚠️ Key #${info.failedIndex + 1} (${info.failedKeyMasked}) chạm giới hạn. <strong style="color: #38bdf8;">Đang tự động chuyển sang Key #${info.nextIndex + 1} (${info.nextKeyMasked})...</strong>`;
              }
            }
          });

          // Parse JSON
          let resText = geminiRes.text.trim();
          const jsonMatch = resText.match(/\{[\s\S]*\}/);
          if (jsonMatch) resText = jsonMatch[0];

          const qData = JSON.parse(resText);
          qData.source = `AI Gemini ${geminiRes.usedModel} (${geminiRes.usedKeyMasked})`;
          qData.grade = parseInt(qData.grade) || grade;
          qData.level = qData.level || level;
          qData.topic = qData.topic || topic;
          qData.type = qType;

          // Save to backend bank
          const saveRes = await fetch("/api/save-generated-question", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: qData })
          }).then(r => r.json());

          const finalQ = saveRes.question || qData;
          resBox.innerHTML = `
            <div style="background: rgba(56, 189, 248, 0.1); padding: 14px; border-radius: 8px; border: 1px solid #38bdf8; color: #bae6fd; margin-top: 10px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
                <strong style="color: #38bdf8;">✨ Gemini AI đã tạo xong câu hỏi mới thành công!</strong>
                <span class="badge-tag" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">${geminiRes.usedModel} (${geminiRes.usedKeyMasked})</span>
              </div>
              <div style="font-size: 13.5px; color: #f8fafc; line-height: 1.5; margin: 8px 0;">
                <em>${escapeHtml(finalQ.stem).substring(0, 180)}...</em>
              </div>
              <div style="display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap;">
                <span style="color: #10b981; font-weight: 600; font-size: 13px;">✅ Đã lưu trực tiếp vào Ngân Hàng Đề Thi!</span>
                <button class="btn btn-primary btn-sm" onclick="viewSourceInBank('${escapeHtml(finalQ.source)}')">👁️ Xem ngay câu hỏi vừa tạo trong Ngân Hàng</button>
              </div>
            </div>
          `;
          loadStatus();
          return;
        } catch (err) {
          console.warn("Lỗi khi gọi Gemini trực tiếp, kích hoạt fallback backend:", err);
        }
      }

      // 2. Fallback to backend /api/ai-generate
      fetch("/api/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic,
          level: level,
          grade: grade,
          prompt: customPrompt,
          q_type: qType,
          raw_keys: apiConfig.rawKeys,
          model: apiConfig.model
        })
      })
      .then(res => res.json())
      .then(res => {
        if (res.status === 'success') {
          const q = res.question;
          const qSource = q.source || 'Bộ sinh tình huống pháp luật tự động';
          resBox.innerHTML = `
            <div style="background: rgba(56, 189, 248, 0.1); padding: 14px; border-radius: 8px; border: 1px solid #38bdf8; color: #bae6fd; margin-top: 10px;">
              <strong style="color: #38bdf8;">✨ Đã tạo xong câu hỏi mới:</strong><br>
              <div style="font-size: 13.5px; color: #f8fafc; line-height: 1.5; margin: 8px 0;">
                <em>${escapeHtml(q.stem).substring(0, 180)}...</em>
              </div>
              <div style="display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap;">
                <span style="color: #10b981; font-weight: 600; font-size: 13px;">Đã lưu tự động vào ngân hàng đề thi!</span>
                <button class="btn btn-primary btn-sm" onclick="viewSourceInBank('${escapeHtml(qSource)}')">👁️ Xem ngay câu hỏi vừa tạo trong Ngân Hàng</button>
              </div>
            </div>
          `;
          loadStatus();
        } else {
          resBox.innerHTML = `<span style="color: #ef4444;">❌ Lỗi tạo câu hỏi: ${res.message || 'Không thể tạo'}</span>`;
        }
      })
      .catch(err => {
        resBox.innerHTML = `<span style="color: #ef4444;">❌ Lỗi: ${err}</span>`;
      });
    });
  }
}

// KNOWLEDGE BASE POPULATION
function loadKnowledge() {
  fetch("/api/knowledge")
    .then(res => res.json())
    .then(data => {
      // 1. BHXH 2024
      const bhxhList = document.getElementById("bhxh-points-list");
      if (bhxhList && data.bhxh_2024_new_points) {
        let html = "";
        data.bhxh_2024_new_points.forEach(pt => {
          const parts = pt.split(":");
          html += `
            <div class="point-card">
              <strong>${parts[0]}</strong>
              ${parts.slice(1).join(":")}
            </div>
          `;
        });
        bhxhList.innerHTML = html;
      }

      // 2. Penalties Table
      const penTableBody = document.querySelector("#penalties-table tbody");
      if (penTableBody && data.penalties_reference) {
        let html = "";
        data.penalties_reference.forEach(p => {
          html += `
            <tr>
              <td><strong>${p.category}</strong></td>
              <td><span class="badge-tag">${p.law}</span></td>
              <td style="text-align: left;">${p.violation}</td>
              <td style="text-align: left; color: #f59e0b; font-weight: 500;">${p.fine}</td>
            </tr>
          `;
        });
        penTableBody.innerHTML = html;
      }

      // 3. Theory topics
      const theoryContainer = document.getElementById("theory-topics-container");
      if (theoryContainer && data.topics) {
        let html = "";
        data.topics.forEach(t => {
          html += `<h4 style="color: #38bdf8; margin: 18px 0 10px 0; font-size: 15px;">📘 ${t.name}</h4>`;
          (t.core_concepts || []).forEach(c => {
            html += `
              <div class="point-card" style="margin-bottom: 10px;">
                <strong>${c.title}</strong>
                ${c.content.replace(/\n/g, "<br>")}
              </div>
            `;
          });
        });
        theoryContainer.innerHTML = html;
      }
    })
    .catch(err => console.error("Error loading knowledge:", err));
}

// EXPORT HANDLERS
function initExportHandlers() {
  const quickExportBtn = document.getElementById("btn-quick-export");
  if (quickExportBtn) {
    quickExportBtn.addEventListener("click", () => {
      switchTab("tab-export");
    });
  }

  const previewExportBtn = document.getElementById("btn-export-from-preview");
  if (previewExportBtn) {
    previewExportBtn.addEventListener("click", () => {
      switchTab("tab-export");
    });
  }

  const shuffleBtn = document.getElementById("btn-shuffle-codes");
  if (shuffleBtn) {
    shuffleBtn.addEventListener("click", () => {
      shuffleBtn.disabled = true;
      shuffleBtn.innerHTML = `<span>⏳</span> Đang tạo 4 mã đề...`;
      fetch("/api/shuffle", { method: "POST" })
        .then(res => res.json())
        .then(res => {
          alert("✅ Đã tạo thành công 4 mã đề: 097, 098, 099, 100 với thuật toán xáo trộn câu và phương án khoa học!");
          switchTab("tab-export");
        })
        .finally(() => {
          shuffleBtn.disabled = false;
          shuffleBtn.innerHTML = `<span>🔀</span> Trộn 4 Mã Đề`;
        });
    });
  }

  const btnExportAll = document.getElementById("btn-export-all-codes");
  if (btnExportAll) {
    btnExportAll.addEventListener("click", () => {
      triggerExport("all");
    });
  }
}

window.triggerExport = async function(type) {
  if (window.AuthManager && !(await window.AuthManager.checkAndConsumeQuota("Xuất file Word chuẩn"))) {
    return;
  }
  fetch("/api/export-docx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ export_type: type, exam_data: currentExam })
  })
  .then(res => res.json())
  .then(data => {
    const container = document.getElementById("export-download-links");
    const list = document.getElementById("download-buttons-list");
    container.style.display = "block";
    list.innerHTML = "";

    const labels = {
      student: "📄 Tải Đề Thi Cho Học Sinh (.docx)",
      teacher: "📑 Tải Đáp Án & Hướng Dẫn Chấm (.docx)",
      matrix: "📊 Tải Ma Trận & Bản Đặc Tả (.docx)"
    };

    for (const [key, url] of Object.entries(data.files || {})) {
      const a = document.createElement("a");
      a.href = url;
      a.className = "btn btn-primary";
      a.innerHTML = labels[key] || `Tải tệp ${key}`;
      a.download = "";
      list.appendChild(a);

      // Auto trigger download for single export
      if (type !== 'all' && key === type) {
        window.location.href = url;
      }
    }
  })
  .catch(err => alert("Lỗi khi xuất file: " + err));
};

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// REPLACEMENT SELECTION MODAL LOGIC
let currentCandidatesData = null;
let currentTargetQId = null;
let currentTargetQType = 'part1';
let activeCandidateTab = 'exact';
let currentCandidateList = [];

window.openReplacementModal = function(qId, qType) {
  currentTargetQId = qId;
  currentTargetQType = qType;
  activeCandidateTab = 'exact';
  
  const modal = document.getElementById("replace-modal");
  const banner = document.getElementById("replace-current-q-box");
  const candidatesContainer = document.getElementById("replace-candidates-list");
  
  candidatesContainer.innerHTML = `<div class="spinner"></div><p style="text-align:center;">Đang tải danh sách câu hỏi phù hợp từ ngân hàng...</p>`;
  modal.classList.add("active");

  fetch(`/api/candidate-replacements?q_id=${encodeURIComponent(qId)}&q_type=${encodeURIComponent(qType)}`)
    .then(res => res.json())
    .then(data => {
      if (data.status !== 'success') {
        candidatesContainer.innerHTML = `<p style="color:#ef4444; padding:20px;">Lỗi: ${data.message || 'Không thể tải câu hỏi.'}</p>`;
        return;
      }
      currentCandidatesData = data;
      const curQ = data.current_question;
      const lvlName = curQ.level === 'biet' ? 'Biết' : (curQ.level === 'hieu' ? 'Hiểu' : 'Vận dụng');
      const qNum = curQ.exam_number || '';
      
      banner.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 6px; flex-wrap:wrap; gap:8px;">
          <div>
            <strong style="color: #38bdf8; font-size: 14px;">🎯 Đang thay thế cho: Câu ${qNum}</strong>
            <span class="q-badge q-badge-grade" style="margin-left:6px;">Lớp ${curQ.grade || 11}</span>
            <span class="q-badge ${curQ.level === 'biet' ? 'q-badge-biet' : (curQ.level === 'hieu' ? 'q-badge-hieu' : 'q-badge-van-dung')}">${lvlName}</span>
            <span class="tag" style="margin-left:4px;">${curQ.topic || 'Chuyên đề'}</span>
          </div>
          <span class="source-tag" style="font-size:11px;">Nguồn: ${escapeHtml(curQ.source || 'Đề gốc')}</span>
        </div>
        <div style="font-size: 13px; color: #cbd5e1; line-height: 1.5; font-style: italic; background: rgba(0,0,0,0.2); padding: 8px 10px; border-radius: 4px;">
          "${escapeHtml(curQ.stem.substring(0, 180))}..."
        </div>
      `;
      
      // Update tab counts
      document.getElementById("pill-exact-matches").textContent = `✨ Chuẩn Ma Trận (${data.exact_matches.length} câu)`;
      document.getElementById("pill-same-grade").textContent = `📚 Cùng Khối Lớp (${data.same_grade_matches.length} câu)`;
      document.getElementById("pill-all-cands").textContent = `🌐 Tất Cả Khác (${data.other_matches.length} câu)`;
      
      // Clear search input
      const searchInput = document.getElementById("replace-search-input");
      if (searchInput) searchInput.value = "";

      // Default tab
      if (data.exact_matches.length > 0) {
        switchCandidateTab('exact');
      } else if (data.same_grade_matches.length > 0) {
        switchCandidateTab('same_grade');
      } else {
        switchCandidateTab('all');
      }
    })
    .catch(err => {
      candidatesContainer.innerHTML = `<p style="color:#ef4444; padding:20px;">Lỗi kết nối: ${err}</p>`;
    });
};

window.closeReplacementModal = function() {
  const modal = document.getElementById("replace-modal");
  if (modal) modal.classList.remove("active");
};

window.switchCandidateTab = function(tabKey) {
  activeCandidateTab = tabKey;
  document.querySelectorAll("#replace-modal .pill-btn").forEach(btn => btn.classList.remove("active"));
  
  if (tabKey === 'exact') document.getElementById("pill-exact-matches").classList.add("active");
  else if (tabKey === 'same_grade') document.getElementById("pill-same-grade").classList.add("active");
  else document.getElementById("pill-all-cands").classList.add("active");

  filterCandidateList();
};

window.filterCandidateList = function() {
  if (!currentCandidatesData) return;
  
  let pool = [];
  if (activeCandidateTab === 'exact') pool = currentCandidatesData.exact_matches || [];
  else if (activeCandidateTab === 'same_grade') pool = currentCandidatesData.same_grade_matches || [];
  else pool = currentCandidatesData.other_matches || [];
  
  const searchInput = document.getElementById("replace-search-input");
  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
  
  if (query) {
    pool = pool.filter(q => (q.stem + " " + (q.topic || "") + " " + (q.source || "")).toLowerCase().includes(query));
  }
  
  currentCandidateList = pool;
  renderCandidateList(pool);
};

window.renderCandidateList = function(list) {
  const container = document.getElementById("replace-candidates-list");
  if (!list || list.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding: 30px; color: #94a3b8;">
        <p style="font-size: 14px; font-weight: 500;">Không có câu hỏi nào trong nhóm này.</p>
        <small>Thầy/cô có thể chuyển sang tab "Cùng Khối Lớp" hoặc "Tất Cả Khác" phía trên để chọn.</small>
      </div>
    `;
    return;
  }
  
  let html = "";
  list.forEach(q => {
    const lvlName = q.level === 'biet' ? 'Biết' : (q.level === 'hieu' ? 'Hiểu' : 'Vận dụng');
    const lvlClass = q.level === 'biet' ? 'q-badge-biet' : (q.level === 'hieu' ? 'q-badge-hieu' : 'q-badge-van-dung');
    const isAi = (q.source || "").toLowerCase().includes("ai") || (q.source || "").toLowerCase().includes("tự động");
    
    html += `
      <div class="candidate-card">
        <div class="candidate-header">
          <div class="bank-q-meta">
            <span class="source-tag ${isAi ? 'source-tag-ai' : ''}">📁 ${escapeHtml(q.source || 'Ngân hàng')}</span>
            <span class="q-badge q-badge-grade">Lớp ${q.grade || 11}</span>
            <span class="q-badge ${lvlClass}">${lvlName}</span>
            <span class="tag">${escapeHtml(q.topic || 'GDKT&PL')}</span>
          </div>
          <button class="btn-choose-replacement" onclick="selectReplacement('${q.id}')">
            <span>✅</span> Chọn câu này
          </button>
        </div>
        <div class="candidate-stem">${escapeHtml(q.stem)}</div>
    `;
    
    if (q.options) {
      html += `<div class="bank-q-options">`;
      ['A', 'B', 'C', 'D'].forEach(k => {
        if (q.options[k]) {
          const isCorrect = (q.answer === k);
          html += `
            <div class="bank-opt-item ${isCorrect ? 'is-correct' : ''}">
              <strong>${k}.</strong> ${escapeHtml(q.options[k])} ${isCorrect ? '✓' : ''}
            </div>
          `;
        }
      });
      html += `</div>`;
    } else if (q.statements) {
      html += `<div style="margin-bottom: 8px;">`;
      q.statements.forEach(s => {
        html += `
          <div style="font-size: 13px; margin-bottom: 4px; display: flex; gap: 6px;">
            <strong>${s.label})</strong>
            <span style="flex:1;">${escapeHtml(s.text)}</span>
            <span class="stmt-tag ${s.answer ? 'stmt-tag-true' : 'stmt-tag-false'}">${s.answer ? 'Đúng' : 'Sai'}</span>
          </div>
        `;
      });
      html += `</div>`;
    }
    
    if (q.explanation) {
      html += `
        <div class="bank-q-explanation">
          <strong>Căn cứ:</strong> ${escapeHtml(q.explanation)}
        </div>
      `;
    }
    
    html += `</div>`;
  });
  
  container.innerHTML = html;
};

window.selectReplacement = function(replacementQId) {
  fetch("/api/swap-question", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      q_id: currentTargetQId,
      q_type: currentTargetQType,
      replacement_q_id: replacementQId
    })
  })
  .then(res => res.json())
  .then(data => {
    currentExam = data.exam;
    renderExam(currentExam);
    closeReplacementModal();
    alert("✅ Đã thay thế thành công câu hỏi vào đề thi!");
  })
  .catch(err => {
    alert("Lỗi khi thay thế câu hỏi: " + err);
  });
};

window.rerollItemFromModal = function() {
  rerollItem(currentTargetQId, currentTargetQType);
  closeReplacementModal();
};

// BANK EXPLORER LOGIC
function initBankExplorer() {
  const btnRefresh = document.getElementById("btn-refresh-bank");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadBankSources();
      loadBankQuestions();
    });
  }

  const btnSearch = document.getElementById("btn-search-bank");
  if (btnSearch) {
    btnSearch.addEventListener("click", () => loadBankQuestions());
  }

  const searchInput = document.getElementById("bank-search-query");
  if (searchInput) {
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === 'Enter') loadBankQuestions();
    });
  }

  const btnReset = document.getElementById("btn-reset-bank-filter");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      document.getElementById("bank-filter-source").value = "";
      document.getElementById("bank-filter-grade").value = "";
      document.getElementById("bank-filter-type").value = "";
      document.getElementById("bank-filter-level").value = "";
      document.getElementById("bank-search-query").value = "";
      loadBankQuestions();
    });
  }

  ['bank-filter-source', 'bank-filter-grade', 'bank-filter-type', 'bank-filter-level'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", () => loadBankQuestions());
    }
  });
}

function loadBankSources(preselectSource) {
  return fetch("/api/question-sources")
    .then(res => res.json())
    .then(data => {
      const select = document.getElementById("bank-filter-source");
      if (!select) return "";
      
      const sources = data.sources || [];
      const totalCount = sources.reduce((a, c) => a + c.count, 0);
      
      let matchedSourceValue = "";
      if (preselectSource) {
        const ps = preselectSource.trim().toLowerCase();
        // 1. Exact match (case insensitive)
        const exact = sources.find(s => s.source.trim().toLowerCase() === ps);
        if (exact) {
          matchedSourceValue = exact.source;
        } else {
          // 2. Substring match
          const sub = sources.find(s => {
            const ss = s.source.trim().toLowerCase();
            return ss.includes(ps) || ps.includes(ss);
          });
          if (sub) {
            matchedSourceValue = sub.source;
          } else {
            matchedSourceValue = preselectSource;
          }
        }
      } else if (select.value) {
        matchedSourceValue = select.value;
      }

      let html = `<option value="">-- Tất cả nguồn tài liệu (${totalCount} câu) --</option>`;
      let hasSelected = false;
      sources.forEach(s => {
        const isMatch = matchedSourceValue && s.source === matchedSourceValue;
        if (isMatch && !hasSelected) {
          html += `<option value="${escapeHtml(s.source)}" selected>${escapeHtml(s.source)} (${s.count} câu)</option>`;
          hasSelected = true;
        } else {
          html += `<option value="${escapeHtml(s.source)}">${escapeHtml(s.source)} (${s.count} câu)</option>`;
        }
      });
      select.innerHTML = html;

      if (matchedSourceValue) {
        select.value = matchedSourceValue;
      }
      return select.value;
    })
    .catch(err => {
      console.error("Error loading sources:", err);
      return "";
    });
}

function loadBankQuestions() {
  const container = document.getElementById("bank-questions-list");
  const countBadge = document.getElementById("bank-view-count");
  if (!container) return;

  container.innerHTML = `<div class="spinner"></div><p style="text-align:center;">Đang tải danh sách câu hỏi...</p>`;

  const source = document.getElementById("bank-filter-source")?.value || "";
  const grade = document.getElementById("bank-filter-grade")?.value || "";
  const qType = document.getElementById("bank-filter-type")?.value || "";
  const level = document.getElementById("bank-filter-level")?.value || "";
  const query = document.getElementById("bank-search-query")?.value.trim() || "";

  let url = `/api/questions?`;
  const params = [];
  if (source) params.push(`source=${encodeURIComponent(source)}`);
  if (grade) params.push(`grade=${encodeURIComponent(grade)}`);
  if (qType) params.push(`q_type=${encodeURIComponent(qType)}`);
  if (level) params.push(`level=${encodeURIComponent(level)}`);
  if (query) params.push(`query=${encodeURIComponent(query)}`);
  url += params.join("&");

  fetch(url)
    .then(res => res.json())
    .then(data => {
      const questions = data.questions || [];
      if (countBadge) {
        if (source) {
          countBadge.innerHTML = `Đang lọc nguồn: <strong style="color: #38bdf8;">${escapeHtml(source)}</strong> (${questions.length} / ${data.total} câu) <button onclick="clearBankSourceFilter()" style="margin-left: 8px; background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 4px; padding: 2px 8px; cursor: pointer; font-size: 11px;">✕ Xem tất cả</button>`;
        } else {
          countBadge.textContent = `Hiển thị ${questions.length} / ${data.total} câu`;
        }
      }

      if (questions.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding: 40px; color: #94a3b8;">
            <h4>Không tìm thấy câu hỏi nào phù hợp với bộ lọc</h4>
            <p style="margin-top: 6px;">Hãy thử chọn "-- Tất cả nguồn tài liệu --" hoặc bấm nút xem tất cả bên trên.</p>
          </div>
        `;
        return;
      }

      let html = "";
      questions.forEach((q, idx) => {
        const lvlName = q.level === 'biet' ? 'Nhận biết' : (q.level === 'hieu' ? 'Thông hiểu' : 'Vận dụng');
        const lvlClass = q.level === 'biet' ? 'q-badge-biet' : (q.level === 'hieu' ? 'q-badge-hieu' : 'q-badge-van-dung');
        const isAi = (q.source || "").toLowerCase().includes("ai") || (q.source || "").toLowerCase().includes("tự động");
        const typeName = q.type === 'part1' ? 'Phần I (Trắc nghiệm)' : 'Phần II (Đúng/Sai)';

        html += `
          <div class="bank-question-card" id="bank-q-${q.id}">
            <div class="bank-q-header">
              <div class="bank-q-meta">
                <span class="source-tag ${isAi ? 'source-tag-ai' : ''}">📁 ${escapeHtml(q.source || 'Tài liệu nạp')}</span>
                <span class="q-badge" style="font-weight: 700; font-size: 12px; background: rgba(59, 130, 246, 0.25); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.5); padding: 2px 8px; border-radius: 4px;">🎓 Lớp ${q.grade || 11}</span>
                <span class="q-badge ${lvlClass}" style="font-weight: 600; padding: 2px 8px; border-radius: 4px;">🎯 ${lvlName}</span>
                <span class="badge-info" style="font-size: 11px; padding: 2px 8px; border-radius: 4px;">${typeName}</span>
                <span class="tag" style="font-size: 11px; padding: 2px 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.05); color: #cbd5e1;">📌 ${escapeHtml(q.topic || 'Chuyên đề')}</span>
              </div>
              <div style="display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-secondary btn-sm" onclick="openBankEditModal('${q.id}', '${q.type}')" title="Sửa nội dung hoặc đổi Khối Lớp (10, 11, 12), Mức độ nhận thức" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4);">✏️ Sửa / Đổi Lớp</button>
                <button class="btn btn-secondary btn-sm" onclick="deleteBankQuestion('${q.id}')" title="Xóa khỏi ngân hàng" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);">🗑️ Xóa</button>
              </div>
            </div>
            <div class="bank-q-stem"><strong>#${idx + 1}:</strong> ${escapeHtml(q.stem)}</div>
        `;

        if (q.options) {
          html += `<div class="bank-q-options">`;
          ['A', 'B', 'C', 'D'].forEach(k => {
            if (q.options[k]) {
              const isCorrect = (q.answer === k);
              html += `
                <div class="bank-opt-item ${isCorrect ? 'is-correct' : ''}">
                  <strong>${k}.</strong> ${escapeHtml(q.options[k])} ${isCorrect ? '✓' : ''}
                </div>
              `;
            }
          });
          html += `</div>`;
        } else if (q.statements) {
          html += `<div style="margin-bottom: 8px;">`;
          q.statements.forEach(s => {
            html += `
              <div style="font-size: 13px; margin-bottom: 4px; display: flex; gap: 6px;">
                <strong>${s.label})</strong>
                <span style="flex:1;">${escapeHtml(s.text)}</span>
                <span class="stmt-tag ${s.answer ? 'stmt-tag-true' : 'stmt-tag-false'}">${s.answer ? 'Đúng' : 'Sai'}</span>
              </div>
            `;
          });
          html += `</div>`;
        }

        if (q.explanation) {
          html += `
            <div class="bank-q-explanation">
              <strong>Căn cứ & Lời giải:</strong> ${escapeHtml(q.explanation)}
            </div>
          `;
        }

        html += `</div>`;
      });

      container.innerHTML = html;
    })
    .catch(err => {
      container.innerHTML = `<p style="color:#ef4444; padding:20px;">Lỗi tải câu hỏi: ${err}</p>`;
    });
}

window.clearBankSourceFilter = function() {
  const sel = document.getElementById("bank-filter-source");
  if (sel) sel.value = "";
  loadBankQuestions();
};

window.deleteBankQuestion = function(qId) {
  if (!confirm("Thầy/cô có chắc chắn muốn xóa câu hỏi này khỏi Ngân Hàng Câu Hỏi?")) return;

  fetch(`/api/questions/${qId}`, { method: "DELETE" })
    .then(res => res.json())
    .then(res => {
      loadBankQuestions();
      loadBankSources();
      loadStatus();
    })
    .catch(err => alert("Lỗi khi xóa: " + err));
};

window.viewSourceInBank = function(sourceName) {
  // Clear other filters so they don't inadvertently hide matching questions
  const gradeSel = document.getElementById("bank-filter-grade");
  const typeSel = document.getElementById("bank-filter-type");
  const levelSel = document.getElementById("bank-filter-level");
  const searchInp = document.getElementById("bank-search-query");
  if (gradeSel) gradeSel.value = "";
  if (typeSel) typeSel.value = "";
  if (levelSel) levelSel.value = "";
  if (searchInp) searchInp.value = "";

  // Switch to tab-bank without triggering auto-loading that would wipe preselect
  switchTab("tab-bank", true);

  loadBankSources(sourceName).then(() => {
    loadBankQuestions();
    const bankEl = document.getElementById("tab-bank");
    if (bankEl) {
      bankEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
};

// ==========================================
// GEMINI API SETTINGS MODAL LOGIC
// ==========================================

window.openApiSettingsModal = function() {
  const modal = document.getElementById("api-settings-modal");
  if (!modal) return;

  const config = window.GeminiClient ? window.GeminiClient.getSavedApiConfig() : { rawKeys: "", model: "gemini-2.0-flash", keys: [] };

  const textarea = document.getElementById("api-modal-keys-textarea");
  const modelSelect = document.getElementById("api-modal-model-select");
  const counter = document.getElementById("api-key-detected-count");
  const resultsContainer = document.getElementById("api-keys-health-list");
  const summaryEl = document.getElementById("ping-test-summary");

  if (textarea) textarea.value = config.rawKeys;
  if (modelSelect) modelSelect.value = config.model || "gemini-2.0-flash";
  if (counter) counter.textContent = `${config.keys.length} Key được nhận diện`;
  if (summaryEl) summaryEl.textContent = "";

  // Render initial list of keys with masked previews
  if (resultsContainer) {
    if (config.keys.length === 0) {
      resultsContainer.innerHTML = `
        <div style="text-align: center; color: #94a3b8; font-size: 13px; padding: 20px;">
          Chưa có Key nào. Hãy dán danh sách Key vào ô trên rồi bấm "Kiểm Tra Kết Nối".
        </div>
      `;
    } else {
      let initialHtml = "";
      config.keys.forEach((k, i) => {
        initialHtml += `
          <div class="key-health-card" id="key-card-${i}">
            <div class="key-health-meta">
              <span style="font-weight: 600; color: #94a3b8;">#${i + 1}</span>
              <span class="key-masked-code">${window.GeminiClient ? window.GeminiClient.maskApiKey(k) : k.slice(0, 8)}</span>
            </div>
            <span class="key-status-badge" style="background: rgba(100, 116, 139, 0.2); color: #94a3b8;">
              Chưa kiểm tra (Bấm Ping Test)
            </span>
          </div>
        `;
      });
      resultsContainer.innerHTML = initialHtml;
    }
  }

  modal.classList.add("active");
};

window.closeApiSettingsModal = function() {
  const modal = document.getElementById("api-settings-modal");
  if (modal) modal.classList.remove("active");
};

window.onKeysTextareaInput = function() {
  const textarea = document.getElementById("api-modal-keys-textarea");
  const counter = document.getElementById("api-key-detected-count");
  if (!textarea || !counter) return;

  const keys = window.GeminiClient ? window.GeminiClient.parseApiKeys(textarea.value) : [];
  counter.textContent = `${keys.length} Key được nhận diện`;
  counter.style.background = keys.length > 0 ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)";
  counter.style.color = keys.length > 0 ? "#34d399" : "#fca5a5";
};

window.onModelSelectChange = function() {
  const select = document.getElementById("api-modal-model-select");
  const badge = document.getElementById("model-desc-badge");
  if (!select || !badge) return;

  const m = select.value;
  if (m === 'gemini-3.6') {
    badge.textContent = "Thế hệ 3.6: Mới nhất & Siêu nhanh";
    badge.style.color = "#38bdf8";
  } else if (m === 'gemini-3.5') {
    badge.textContent = "Thế hệ 3.5: Tư duy sâu & Chuẩn HSG";
    badge.style.color = "#34d399";
  } else if (m === 'gemini-2.5-flash') {
    badge.textContent = "Thế hệ 2.5: Bản Flash ổn định";
    badge.style.color = "#a78bfa";
  } else if (m === 'gemini-2.0-flash') {
    badge.textContent = "Bản 2.0 Flash: Siêu tốc";
    badge.style.color = "#f59e0b";
  } else if (m === 'auto') {
    badge.textContent = "Tự động xoay vòng: 3.6 → 3.5 → 2.5 → 2.0";
    badge.style.color = "#c084fc";
  } else {
    badge.textContent = m;
    badge.style.color = "#cbd5e1";
  }
};

window.clearAllApiKeys = function() {
  if (!confirm("Thầy/cô có chắc muốn xóa tất cả API Key trong ô nhập?")) return;
  const textarea = document.getElementById("api-modal-keys-textarea");
  if (textarea) {
    textarea.value = "";
    window.onKeysTextareaInput();
  }
  const resultsContainer = document.getElementById("api-keys-health-list");
  if (resultsContainer) resultsContainer.innerHTML = "";
};

window.runPingTestAllKeys = async function() {
  const textarea = document.getElementById("api-modal-keys-textarea");
  const modelSelect = document.getElementById("api-modal-model-select");
  const resultsContainer = document.getElementById("api-keys-health-list");
  const summaryEl = document.getElementById("ping-test-summary");
  const pingBtn = document.getElementById("btn-ping-test-keys");

  if (!textarea || !resultsContainer || !window.GeminiClient) return;

  const keys = window.GeminiClient.parseApiKeys(textarea.value);
  if (keys.length === 0) {
    alert("Vui lòng dán ít nhất 1 Google Gemini API Key vào ô nhập.");
    textarea.focus();
    return;
  }

  const model = modelSelect ? modelSelect.value : "gemini-2.0-flash";

  pingBtn.disabled = true;
  pingBtn.innerHTML = `<span class="spinner" style="width: 14px; height: 14px; display: inline-block;"></span> Đang kiểm tra ${keys.length} Key...`;
  if (summaryEl) summaryEl.innerHTML = `<span style="color: #38bdf8;">Đang gửi gói tin ping siêu nhẹ (5 tokens) tới máy chủ Google...</span>`;

  // Render cards in testing state
  let testingHtml = "";
  keys.forEach((k, i) => {
    testingHtml += `
      <div class="key-health-card" id="key-card-${i}">
        <div class="key-health-meta">
          <span style="font-weight: 600; color: #94a3b8;">#${i + 1}</span>
          <span class="key-masked-code">${window.GeminiClient.maskApiKey(k)}</span>
        </div>
        <span class="key-status-badge key-status-testing">
          <span class="spinner" style="width: 10px; height: 10px; display: inline-block;"></span> Đang đo độ trễ...
        </span>
      </div>
    `;
  });
  resultsContainer.innerHTML = testingHtml;

  try {
    const results = await window.GeminiClient.checkMultipleApiKeysHealth(keys, model);

    let successCount = 0;
    let rateLimitCount = 0;
    let authErrorCount = 0;

    let finalHtml = "";
    results.forEach(res => {
      let badgeClass = "key-status-auth-error";
      let icon = "❌";

      if (res.status === 'success') {
        badgeClass = "key-status-success";
        icon = "🟢";
        successCount++;
      } else if (res.status === 'rate_limit') {
        badgeClass = "key-status-rate-limit";
        icon = "🟡";
        rateLimitCount++;
      } else if (res.status === 'auth_error') {
        badgeClass = "key-status-auth-error";
        icon = "🔴";
        authErrorCount++;
      } else if (res.status === 'timeout') {
        badgeClass = "key-status-timeout";
        icon = "⏱️";
      }

      finalHtml += `
        <div class="key-health-card">
          <div class="key-health-meta">
            <span style="font-weight: 600; color: #94a3b8;">#${res.keyIndex + 1}</span>
            <span class="key-masked-code">${escapeHtml(res.maskedKey)}</span>
          </div>
          <span class="key-status-badge ${badgeClass}">
            ${icon} ${escapeHtml(res.message)}
          </span>
        </div>
      `;
    });
    resultsContainer.innerHTML = finalHtml;

    if (summaryEl) {
      summaryEl.innerHTML = `
        <span style="color: #34d399; font-weight: 600;">✓ ${successCount}/${keys.length} Key hoạt động</span>
        ${rateLimitCount > 0 ? `<span style="color: #fbbf24; margin-left: 6px;">(${rateLimitCount} Key hết hạn mức)</span>` : ''}
        ${authErrorCount > 0 ? `<span style="color: #f87171; margin-left: 6px;">(${authErrorCount} Key sai/khóa)</span>` : ''}
      `;
    }
  } catch (err) {
    alert("Lỗi khi chạy Ping Test: " + err);
  } finally {
    pingBtn.disabled = false;
    pingBtn.innerHTML = `<span>⚡</span> Kiểm Tra Kết Nối (Ping Test Tất Cả Key)`;
  }
};

window.saveApiSettingsFromModal = async function() {
  const textarea = document.getElementById("api-modal-keys-textarea");
  const modelSelect = document.getElementById("api-modal-model-select");

  if (!textarea || !window.GeminiClient) return;

  const rawKeys = textarea.value.trim();
  const model = modelSelect ? modelSelect.value : "gemini-2.0-flash";
  const keys = window.GeminiClient.parseApiKeys(rawKeys);

  await window.GeminiClient.saveApiConfig(rawKeys, model);

  alert(`✅ Đã lưu thành công cấu hình!\n- Số lượng: ${keys.length} API Key\n- Model mặc định: ${model}\n\nHệ thống đã sẵn sàng tạo câu hỏi bằng AI với cơ chế tự động xoay vòng.`);
  window.closeApiSettingsModal();
};


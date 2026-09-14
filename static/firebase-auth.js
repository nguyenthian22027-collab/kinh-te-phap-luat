// GDKTPL Exam Studio Pro - Firebase Authentication & License Quota Manager
// Supports Google Sign-In, 10-use Free Trial Quota, and Pro Activation (150k, 250k, 599k)

(function() {
  const AuthManager = {
    user: null,
    status: null,
    firebaseInitialized: false,
    selectedPlan: 'lifetime',

    async init() {
      const defaultFirebaseConfig = {
        apiKey: "AIzaSyAeKfH6_32nI5vYKdI8wONACr17Ryn1QVk",
        authDomain: "kinh-te-phap-luat-fcd47.firebaseapp.com",
        projectId: "kinh-te-phap-luat-fcd47",
        storageBucket: "kinh-te-phap-luat-fcd47.firebasestorage.app",
        messagingSenderId: "247284686520",
        appId: "1:247284686520:web:8ec3bc8747bb634494de4d",
        measurementId: "G-46G1TJMPVZ"
      };

      // 1. Try to load Firebase configuration from backend
      try {
        const res = await fetch("/api/firebase-config");
        let config = await res.json();
        if (!config || !config.apiKey) config = defaultFirebaseConfig;
        if (config && config.apiKey && config.apiKey.length > 5 && typeof firebase !== "undefined") {
          if (!firebase.apps.length) {
            firebase.initializeApp(config);
          }
          this.firebaseInitialized = true;
          this.setupFirebaseListener();
        } else {
          this.initLocalGuestSession();
        }
      } catch (e) {
        console.warn("Firebase config fetch error, using default config:", e);
        if (typeof firebase !== "undefined") {
          if (!firebase.apps.length) {
            firebase.initializeApp(defaultFirebaseConfig);
          }
          this.firebaseInitialized = true;
          this.setupFirebaseListener();
        }
      }

      // 2. Fetch current user status
      await this.refreshUserStatus();

      // 3. Render UI components
      this.renderTopbarAuth();
      this.updateSidebarLicenseInfo();
    },

    setupFirebaseListener() {
      if (!this.firebaseInitialized || typeof firebase === "undefined") return;
      firebase.auth().onAuthStateChanged(async (firebaseUser) => {
        if (firebaseUser) {
          this.user = {
            uid: firebaseUser.uid,
            email: firebaseUser.email || "",
            displayName: firebaseUser.displayName || "Giáo viên",
            photoURL: firebaseUser.photoURL || ""
          };
          localStorage.setItem("gdktpl_auth_user", JSON.stringify(this.user));
        } else {
          this.initLocalGuestSession();
        }
        await this.refreshUserStatus();
        this.renderTopbarAuth();
        this.updateSidebarLicenseInfo();
      });
    },

    initLocalGuestSession() {
      const saved = localStorage.getItem("gdktpl_auth_user");
      if (saved) {
        try {
          this.user = JSON.parse(saved);
        } catch (e) {
          this.user = null;
        }
      }
      if (!this.user) {
        let guestId = localStorage.getItem("gdktpl_guest_uid");
        if (!guestId) {
          guestId = "guest_" + Math.random().toString(36).substring(2, 10);
          localStorage.setItem("gdktpl_guest_uid", guestId);
        }
        this.user = {
          uid: guestId,
          email: "",
          displayName: "Khách dùng thử",
          photoURL: "",
          isGuest: true
        };
      }
    },

    async refreshUserStatus() {
      if (!this.user) this.initLocalGuestSession();
      try {
        const res = await fetch("/api/user/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: this.user.uid,
            email: this.user.email || "",
            display_name: this.user.displayName || "Giáo viên",
            photo_url: this.user.photoURL || ""
          })
        });
        this.status = await res.json();
      } catch (e) {
        console.error("Error fetching user status:", e);
        this.status = {
          uid: this.user.uid,
          is_pro: false,
          trial_used: 0,
          trial_limit: 10,
          trial_remaining: 10,
          can_use: true
        };
      }
      return this.status;
    },

    async checkAndConsumeQuota(actionName = "Tác vụ") {
      await this.refreshUserStatus();

      // Nếu đã là tài khoản PRO -> Không bao giờ bị giới hạn
      if (this.status && this.status.is_pro) {
        return true;
      }

      // Kiểm tra còn lượt dùng thử không
      const remaining = this.status ? this.status.trial_remaining : 0;
      if (remaining <= 0) {
        this.showQuotaExceededAlert(actionName);
        this.openProModal();
        return false;
      }

      // Còn lượt dùng thử -> Thực hiện trừ 1 lượt trên backend
      try {
        const res = await fetch("/api/user/consume-quota", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: this.user.uid,
            action_name: actionName
          })
        });
        const data = await res.json();

        if (data.allowed) {
          this.status = data.user || this.status;
          this.renderTopbarAuth();
          this.updateSidebarLicenseInfo();
          this.showTrialToast(actionName, data.trial_remaining, data.trial_used);
          return true;
        } else {
          this.showQuotaExceededAlert(actionName);
          this.openProModal();
          return false;
        }
      } catch (e) {
        console.error("Quota consumption error:", e);
        // Fallback cho phép nếu lỗi mạng nội bộ
        return true;
      }
    },

    showTrialToast(actionName, remaining, used) {
      const existingToast = document.getElementById("trial-quota-toast");
      if (existingToast) existingToast.remove();

      const toast = document.createElement("div");
      toast.id = "trial-quota-toast";
      toast.className = "trial-toast";
      toast.innerHTML = `
        <div class="toast-icon">⚡</div>
        <div class="toast-body">
          <div class="toast-title">Đã dùng 1 lượt [${actionName}]</div>
          <div class="toast-desc">Còn lại <strong>${remaining}/10</strong> lượt dùng thử miễn phí.</div>
        </div>
        <button class="toast-upgrade-btn" onclick="window.AuthManager.openProModal()">Nâng cấp PRO ⭐</button>
      `;
      document.body.appendChild(toast);

      setTimeout(() => {
        toast.classList.add("show");
      }, 50);

      setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 400);
      }, 4500);
    },

    showQuotaExceededAlert(actionName) {
      console.warn(`Hết lượt dùng thử cho: ${actionName}`);
    },

    async signInWithGoogle() {
      if (this.firebaseInitialized && typeof firebase !== "undefined") {
        try {
          const provider = new firebase.auth.GoogleAuthProvider();
          provider.setCustomParameters({ prompt: 'select_account' });
          const result = await firebase.auth().signInWithPopup(provider);
          const fbUser = result.user;
          this.user = {
            uid: fbUser.uid,
            email: fbUser.email,
            displayName: fbUser.displayName,
            photoURL: fbUser.photoURL
          };
          localStorage.setItem("gdktpl_auth_user", JSON.stringify(this.user));
          await this.refreshUserStatus();
          this.renderTopbarAuth();
          this.updateSidebarLicenseInfo();
          alert(`🎉 Xin chào quý thầy/cô ${fbUser.displayName}!\nĐăng nhập Google thành công.`);
        } catch (error) {
          console.error("Google Sign-In Error:", error);
          if (error.code === 'auth/popup-closed-by-user') return;
          if (error.code === 'auth/unauthorized-domain') {
            alert("⚠️ Lỗi tên miền: Thầy/cô cần vào Firebase Console > Authentication > Settings > Authorized domains > Bấm 'Add domain' và thêm 'localhost' để Google cấp phép đăng nhập.");
            return;
          }
          if (error.code === 'auth/operation-not-allowed') {
            alert("⚠️ Lỗi phương thức: Thầy/cô cần vào Firebase Console > Authentication > Sign-in method > Bấm chọn 'Google' và gạt sang 'Enable' (Bật).");
            return;
          }
          alert("Lỗi đăng nhập Google: " + (error.message || error));
        }
      } else {
        // Chưa có cấu hình Firebase -> Mở cửa sổ nạp cấu hình Firebase
        this.openFirebaseConfigModal();
      }
    },

    async signOut() {
      if (confirm("Thầy/Cô có chắc chắn muốn đăng xuất tài khoản?")) {
        if (this.firebaseInitialized && typeof firebase !== "undefined") {
          try {
            await firebase.auth().signOut();
          } catch (e) {}
        }
        localStorage.removeItem("gdktpl_auth_user");
        this.user = null;
        this.initLocalGuestSession();
        await this.refreshUserStatus();
        this.renderTopbarAuth();
        this.updateSidebarLicenseInfo();
        alert("Đã đăng xuất tài khoản thành công.");
      }
    },

    renderTopbarAuth() {
      const topbarRight = document.querySelector(".topbar-right");
      if (!topbarRight) return;

      let authContainer = document.getElementById("topbar-auth-container");
      if (!authContainer) {
        authContainer = document.createElement("div");
        authContainer.id = "topbar-auth-container";
        authContainer.className = "topbar-auth-pill";
        topbarRight.insertBefore(authContainer, topbarRight.firstChild);
      }

      const isPro = this.status && this.status.is_pro;
      const remaining = this.status ? this.status.trial_remaining : 10;
      const userName = (this.user && this.user.displayName) ? this.user.displayName : "Khách";
      const userPhoto = (this.user && this.user.photoURL) ? this.user.photoURL : "";

      if (isPro) {
        const planName = this.status.pro_plan_name || "Bản Quyền PRO";
        authContainer.innerHTML = `
          <div class="user-profile-badge pro-active" onclick="window.AuthManager.openProModal()" title="Nhấn để xem thông tin bản quyền">
            ${userPhoto ? `<img src="${userPhoto}" class="user-avatar" alt="Avatar">` : `<span class="avatar-icon">👑</span>`}
            <div class="user-meta">
              <span class="user-name">${escapeHtml(userName)}</span>
              <span class="pro-tag">⭐ ${escapeHtml(planName)}</span>
            </div>
          </div>
          <button class="btn-auth-logout" onclick="window.AuthManager.signOut()" title="Đăng xuất">↪</button>
        `;
      } else {
        authContainer.innerHTML = `
          <div class="user-profile-badge trial-active" onclick="window.AuthManager.openProModal()" title="Nhấn để nâng cấp bản quyền">
            ${userPhoto ? `<img src="${userPhoto}" class="user-avatar" alt="Avatar">` : `<span class="avatar-icon">👤</span>`}
            <div class="user-meta">
              <span class="user-name">${escapeHtml(userName)}</span>
              <span class="trial-tag">🎁 Dùng thử: <strong>${remaining}/10</strong></span>
            </div>
          </div>
          <button class="btn-upgrade-pro-pulse" onclick="window.AuthManager.openProModal()" title="Nâng cấp gói bản quyền">
            <span>⭐ NÂNG CẤP PRO</span>
          </button>
          ${this.user && !this.user.isGuest ? `
            <button class="btn-auth-logout" onclick="window.AuthManager.signOut()" title="Đăng xuất">↪</button>
          ` : `
            <button class="btn-google-login-mini" onclick="window.AuthManager.signInWithGoogle()" title="Đăng nhập bằng Google">
              <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="14" height="14" alt="G">
              <span>Đăng nhập</span>
            </button>
          `}
        `;
      }
    },

    updateSidebarLicenseInfo() {
      const statsCard = document.querySelector(".bank-stats-card");
      if (!statsCard) return;

      let licenseInfoEl = document.getElementById("sidebar-license-box");
      if (!licenseInfoEl) {
        licenseInfoEl = document.createElement("div");
        licenseInfoEl.id = "sidebar-license-box";
        licenseInfoEl.className = "sidebar-license-card";
        statsCard.parentNode.insertBefore(licenseInfoEl, statsCard.nextSibling);
      }

      const isPro = this.status && this.status.is_pro;
      const remaining = this.status ? this.status.trial_remaining : 10;
      const used = this.status ? this.status.trial_used : 0;

      if (isPro) {
        const planName = this.status.pro_plan_name || "Gói PRO Trọn Đời";
        const exp = this.status.pro_expires_at || "Vĩnh viễn không thời hạn";
        licenseInfoEl.innerHTML = `
          <div class="license-box-inner pro-box">
            <div class="license-head">
              <span class="pro-crown">👑</span>
              <strong>BẢN QUYỀN PRO</strong>
            </div>
            <div class="license-desc">${escapeHtml(planName)}</div>
            <div class="license-expiry">Hạn dùng: <span>${escapeHtml(exp)}</span></div>
            <div class="license-badge-unlimited">⚡ Không giới hạn tính năng</div>
          </div>
        `;
      } else {
        const percent = Math.min(100, Math.round((used / 10) * 100));
        licenseInfoEl.innerHTML = `
          <div class="license-box-inner trial-box">
            <div class="license-head">
              <span class="gift-icon">🎁</span>
              <strong>DÙNG THỬ MIỄN PHÍ</strong>
            </div>
            <div class="trial-counter-row">
              <span>Lượt đã dùng:</span>
              <strong>${used}/10 lượt</strong>
            </div>
            <div class="trial-progress-bar">
              <div class="trial-progress-fill" style="width: ${percent}%;"></div>
            </div>
            <div class="trial-rem-text">Còn <strong>${remaining}</strong> lượt miễn phí</div>
            <button class="btn-sidebar-upgrade" onclick="window.AuthManager.openProModal()">
              <span>⭐</span> Nâng Cấp Bản Quyền
            </button>
          </div>
        `;
      }
    },

    openProModal(defaultPlan = 'lifetime') {
      this.selectedPlan = defaultPlan;
      const modal = document.getElementById("pro-license-modal");
      if (modal) {
        modal.classList.add("active");
        this.renderPricingCards();
        this.updatePaymentDetails();
      }
    },

    closeProModal() {
      const modal = document.getElementById("pro-license-modal");
      if (modal) {
        modal.classList.remove("active");
      }
    },

    selectPlan(planKey) {
      this.selectedPlan = planKey;
      this.renderPricingCards();
      this.updatePaymentDetails();
    },

    renderPricingCards() {
      const cards = document.querySelectorAll(".pricing-card");
      cards.forEach(card => {
        const pKey = card.getAttribute("data-plan");
        if (pKey === this.selectedPlan) {
          card.classList.add("selected");
        } else {
          card.classList.remove("selected");
        }
      });
    },

    updatePaymentDetails() {
      const planInfo = {
        '1year': { name: 'Gói 1 Năm', price: '150.000 VNĐ', amount: 150000, prefix: 'PRO1Y' },
        '2year': { name: 'Gói 2 Năm', price: '250.000 VNĐ', amount: 250000, prefix: 'PRO2Y' },
        'lifetime': { name: 'Gói Vĩnh Viễn', price: '599.000 VNĐ', amount: 599000, prefix: 'PROLIFE' }
      }[this.selectedPlan] || { name: 'Gói Vĩnh Viễn', price: '599.000 VNĐ', amount: 599000, prefix: 'PROLIFE' };

      const userUid = this.user ? this.user.uid : 'GUEST';
      const cleanUid = userUid.substring(0, 10).toUpperCase();
      const transferContent = `GDKTPL ${planInfo.prefix} ${cleanUid}`;

      const paymentPlanName = document.getElementById("pay-plan-name");
      const paymentAmount = document.getElementById("pay-plan-amount");
      const paymentContent = document.getElementById("pay-plan-content");
      const qrImg = document.getElementById("pay-qr-code");

      if (paymentPlanName) paymentPlanName.textContent = planInfo.name;
      if (paymentAmount) paymentAmount.textContent = planInfo.price;
      if (paymentContent) paymentContent.textContent = transferContent;

      if (qrImg) {
        // Sử dụng VietQR chuẩn MBBank (Ngân hàng Quân Đội)
        const qrUrl = `https://img.vietqr.io/image/970422-0969888999-compact2.png?amount=${planInfo.amount}&addInfo=${encodeURIComponent(transferContent)}&accountName=GDKTPL%20EXAM%20STUDIO`;
        qrImg.src = qrUrl;
      }
    },

    async activateLicenseKey() {
      const inputEl = document.getElementById("input-license-key");
      if (!inputEl) return;
      const key = inputEl.value.trim().toUpperCase();
      if (!key) {
        alert("Vui lòng nhập Mã kích hoạt bản quyền.");
        inputEl.focus();
        return;
      }

      const btn = document.getElementById("btn-submit-activate-key");
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳</span> Đang xác thực mã...`;
      }

      try {
        const res = await fetch("/api/user/activate-pro", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: this.user.uid,
            license_key: key
          })
        });
        const data = await res.json();

        if (data.status === "success") {
          alert(`🎉 CHÚC MỪNG QUÝ THẦY/CÔ!\n${data.message}\n\nTài khoản của thầy/cô đã được nâng cấp lên bản quyền PRO.\nChúc thầy/cô ra đề và bồi dưỡng HSG đạt kết quả cao nhất!`);
          inputEl.value = "";
          this.closeProModal();
          await this.refreshUserStatus();
          this.renderTopbarAuth();
          this.updateSidebarLicenseInfo();
        } else {
          alert(`❌ Kích hoạt không thành công:\n${data.message}`);
        }
      } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<span>🚀</span> Kích Hoạt Ngay`;
        }
      }
    },

    openFirebaseConfigModal() {
      fetch("/api/firebase-config")
        .then(res => res.json())
        .then(cfg => {
          const ta = document.getElementById("firebase-config-json");
          if (ta && cfg && cfg.apiKey) {
            ta.value = JSON.stringify(cfg, null, 2);
          }
          const m = document.getElementById("firebase-config-modal");
          if (m) m.classList.add("active");
        });
    },

    closeFirebaseConfigModal() {
      const m = document.getElementById("firebase-config-modal");
      if (m) m.classList.remove("active");
    },

    async saveFirebaseConfigAndLogin() {
      const ta = document.getElementById("firebase-config-json");
      if (!ta) return;
      let text = ta.value.trim();
      if (!text) {
        alert("Vui lòng dán đoạn mã cấu hình Firebase.");
        ta.focus();
        return;
      }
      try {
        if (text.includes("=") && text.includes("{")) {
          text = text.substring(text.indexOf("{"), text.lastIndexOf("}") + 1);
        }
        let json;
        try {
          json = JSON.parse(text);
        } catch(e) {
          json = (new Function(`return (${text});`))();
        }

        if (!json.apiKey || json.apiKey.length < 5) {
          throw new Error("Không tìm thấy trường apiKey hợp lệ trong cấu hình.");
        }

        // 1. Lưu cấu hình vào backend
        const res = await fetch("/api/firebase-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ config: json })
        });
        await res.json();

        // 2. Khởi tạo Firebase SDK ngay lập tức
        if (typeof firebase !== "undefined") {
          if (!firebase.apps.length) {
            firebase.initializeApp(json);
          }
          this.firebaseInitialized = true;
          this.setupFirebaseListener();
        }

        this.closeFirebaseConfigModal();
        alert("✅ Đã lưu cấu hình Firebase thành công!\nCửa sổ đăng nhập Google chính thức của Google sẽ mở ra ngay bây giờ.");

        // 3. Mở ngay cửa sổ Google Sign-In thật
        await this.signInWithGoogle();

      } catch (e) {
        alert("Định dạng cấu hình Firebase không hợp lệ. Vui lòng kiểm tra lại: " + e.message);
      }
    },

    fillDemoKey(key) {
      const input = document.getElementById("input-license-key");
      if (input) {
        input.value = key;
        input.focus();
      }
    }
  };

  function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  window.AuthManager = AuthManager;

  document.addEventListener("DOMContentLoaded", () => {
    AuthManager.init();
  });
})();

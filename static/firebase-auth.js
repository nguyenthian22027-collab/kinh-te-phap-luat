// GDKTPL Exam Studio Pro - Firebase Authentication & Realtime Cloud License Manager
// Supports Google Sign-In, 10-use Free Trial Quota, Pro Plans (150k, 250k, 599k), and Realtime Admin Approval Dashboard

(function() {
  const ADMIN_EMAILS = [
    "nguyenvanthien1812@gmail.com",
    "kimtuyen@gmail.com",
    "admin@gmail.com",
    "nguyenthian22027@gmail.com",
    "hoathinh6966@gmail.com"
  ];

  function checkIsAdmin(email) {
    if (!email) return false;
    const clean = email.trim().toLowerCase();
    return ADMIN_EMAILS.some(a => a.toLowerCase() === clean) || clean.includes("admin");
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  const defaultFirebaseConfig = {
    apiKey: "AIzaSyAeKfH6_32nI5vYKdI8wONACr17Ryn1QVk",
    authDomain: "kinh-te-phap-luat-fcd47.firebaseapp.com",
    projectId: "kinh-te-phap-luat-fcd47",
    storageBucket: "kinh-te-phap-luat-fcd47.firebasestorage.app",
    messagingSenderId: "247284686520",
    appId: "1:247284686520:web:8ec3bc8747bb634494de4d",
    measurementId: "G-46G1TJMPVZ"
  };

  const AuthManager = {
    user: null,
    status: null,
    firebaseInitialized: false,
    selectedPlan: 'lifetime',
    db: null,
    userDocUnsubscribe: null,

    async init() {
      // 1. Khởi tạo Firebase SDK (Auth + Firestore Realtime)
      if (typeof firebase !== "undefined") {
        try {
          if (!firebase.apps.length) {
            firebase.initializeApp(defaultFirebaseConfig);
          }
          this.firebaseInitialized = true;
          try {
            this.db = firebase.firestore();
          } catch(e) {
            console.warn("Firestore init warning:", e);
          }
          this.setupFirebaseListener();
        } catch (e) {
          console.error("Firebase init error:", e);
          this.initLocalGuestSession();
        }
      } else {
        this.initLocalGuestSession();
      }

      // 2. Tải trạng thái người dùng hiện tại từ Backend
      await this.refreshUserStatus();

      // 3. Render giao diện Auth & Sidebar
      this.renderTopbarAuth();
      this.updateSidebarLicenseInfo();

      // 4. Lắng nghe phím tắt mở nhanh Bảng Quản Trị (Ctrl+Alt+A)
      document.addEventListener("keydown", (e) => {
        if (e.ctrlKey && e.altKey && (e.key === 'a' || e.key === 'A')) {
          e.preventDefault();
          window.AdminManager.openModal();
        }
      });
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

          // Đồng bộ User sang Firestore Cloud Realtime
          if (this.db) {
            try {
              this.db.collection("users").doc(firebaseUser.uid).set({
                uid: firebaseUser.uid,
                email: firebaseUser.email || "",
                display_name: firebaseUser.displayName || "Giáo viên",
                photo_url: firebaseUser.photoURL || "",
                last_login: new Date().toISOString()
              }, { merge: true }).catch(() => {});

              // Lắng nghe thay đổi quyền Realtime từ Admin
              if (this.userDocUnsubscribe) this.userDocUnsubscribe();
              this.userDocUnsubscribe = this.db.collection("users").doc(firebaseUser.uid).onSnapshot((doc) => {
                if (doc.exists) {
                  const cloudData = doc.data();
                  if (cloudData.is_pro !== undefined || cloudData.status !== undefined) {
                    this.refreshUserStatus();
                  }
                }
              }, () => {});
            } catch(e) {}
          }
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
          can_use: true,
          is_admin: checkIsAdmin(this.user ? this.user.email : "")
        };
      }
      return this.status;
    },

    async checkAndConsumeQuota(actionName = "Tác vụ") {
      await this.refreshUserStatus();

      // Kiểm tra tài khoản có bị khóa không
      if (this.status && (this.status.is_blocked || this.status.status === "blocked")) {
        alert("⚠️ Tài khoản của thầy/cô đang tạm thời bị khóa. Vui lòng liên hệ Admin (0969.888.999) để được mở lại.");
        return false;
      }

      // Nếu đã là tài khoản PRO -> Không bao giờ bị giới hạn
      if (this.status && this.status.is_pro) {
        return true;
      }

      // Kiểm tra còn lượt dùng thử không
      const remaining = this.status ? this.status.trial_remaining : 0;
      if (remaining <= 0) {
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
          this.openProModal();
          return false;
        }
      } catch (e) {
        console.error("Quota consumption error:", e);
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

      setTimeout(() => { toast.classList.add("show"); }, 50);
      setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 400);
      }, 4500);
    },

    async signInWithGoogle() {
      if (typeof firebase === "undefined") {
        alert("Đang tải thư viện Google, vui lòng thử lại sau 2 giây...");
        return;
      }

      if (!firebase.apps.length) {
        firebase.initializeApp(defaultFirebaseConfig);
        this.firebaseInitialized = true;
      }

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
        alert(`🎉 Xin chào quý thầy/cô ${fbUser.displayName}!
Đăng nhập Google thành công.`);
      } catch (error) {
        console.error("Google Sign-In Error:", error);
        if (error.code === 'auth/popup-closed-by-user') return;
        if (error.code === 'auth/unauthorized-domain') {
          alert("⚠️ Lỗi tên miền: Thầy/cô cần vào Firebase Console > Authentication > Settings > Authorized domains > Thêm tên miền web vào danh sách.");
          return;
        }
        alert("Lỗi đăng nhập Google: " + (error.message || error));
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
      const userEmail = (this.user && this.user.email) ? this.user.email : "";
      const isAdmin = checkIsAdmin(userEmail) || (this.status && this.status.is_admin);

      let adminBtnHtml = "";
      if (isAdmin) {
        adminBtnHtml = `
          <button class="btn-admin-panel-topbar" onclick="window.AdminManager.openModal()" title="Mở Bảng Quản Trị Viên Phê Duyệt">
            <span>🛡️ Phê Duyệt Realtime</span>
          </button>
        `;
      }

      if (isPro) {
        const planName = this.status.pro_plan_name || "Bản Quyền PRO";
        authContainer.innerHTML = `
          ${adminBtnHtml}
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
          ${adminBtnHtml}
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

      // Thêm nút Quản trị trên Sidebar nếu là Admin
      this.renderSidebarAdminButton(isAdmin);
    },

    renderSidebarAdminButton(isAdmin) {
      const navGroup = document.querySelector(".nav-group");
      if (!navGroup) return;

      let adminNavBtn = document.getElementById("nav-item-admin-approval-btn");
      if (isAdmin) {
        if (!adminNavBtn) {
          adminNavBtn = document.createElement("button");
          adminNavBtn.id = "nav-item-admin-approval-btn";
          adminNavBtn.className = "nav-item";
          adminNavBtn.style.background = "rgba(124, 58, 237, 0.12)";
          adminNavBtn.style.border = "1px solid rgba(124, 58, 237, 0.4)";
          adminNavBtn.style.marginTop = "6px";
          adminNavBtn.innerHTML = `
            <span class="nav-icon" style="color: #c084fc;">🛡️</span>
            <span style="font-weight: 700; color: #e9d5ff;">Phê Duyệt Realtime</span>
          `;
          adminNavBtn.onclick = () => window.AdminManager.openModal();
          navGroup.appendChild(adminNavBtn);
        }
      } else {
        if (adminNavBtn) adminNavBtn.remove();
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

      const userEmail = (this.user && this.user.email) ? this.user.email : "";
      const userUid = (this.user && this.user.uid) ? this.user.uid : "GUEST";
      const cleanUid = userUid.substring(0, 10).toUpperCase();
      const transferContent = `GDKTPL ${planInfo.prefix} ${cleanUid}`;

      const paymentPlanName = document.getElementById("pay-plan-name");
      const paymentAmount = document.getElementById("pay-plan-amount");
      const paymentContent = document.getElementById("pay-plan-content");
      const paymentUserEmail = document.getElementById("pay-user-email");
      const qrImg = document.getElementById("pay-qr-code");

      if (paymentPlanName) paymentPlanName.textContent = planInfo.name;
      if (paymentAmount) paymentAmount.textContent = planInfo.price;
      if (paymentContent) paymentContent.textContent = transferContent;
      if (paymentUserEmail) {
        paymentUserEmail.textContent = userEmail || "Chưa đăng nhập (Vui lòng bấm 'Đăng nhập Google' phía trên)";
      }

      if (qrImg) {
        const qrUrl = `https://img.vietqr.io/image/970422-0969888999-compact2.png?amount=${planInfo.amount}&addInfo=${encodeURIComponent(transferContent)}&accountName=GDKTPL%20EXAM%20STUDIO`;
        qrImg.src = qrUrl;
      }
    }
  };

  // ============================================================
  // ADMIN MANAGER — BẢNG QUẢN TRỊ VIÊN PHÊ DUYỆT REALTIME CLOUD
  // ============================================================
  const AdminManager = {
    users: [],
    filteredUsers: [],
    currentFilter: 'all',
    searchQuery: '',
    stats: { total: 0, trial: 0, pro_expiring: 0, pro_lifetime: 0, blocked: 0 },
    firestoreUnsubscribe: null,

    async openModal() {
      const modal = document.getElementById("admin-approval-modal");
      if (modal) {
        modal.classList.add("active");
        await this.loadUsers();
        this.setupFirestoreListener();
      }
    },

    closeModal() {
      const modal = document.getElementById("admin-approval-modal");
      if (modal) modal.classList.remove("active");
      if (this.firestoreUnsubscribe) {
        this.firestoreUnsubscribe();
        this.firestoreUnsubscribe = null;
      }
    },

    setupFirestoreListener() {
      if (typeof firebase !== "undefined" && firebase.firestore) {
        try {
          const db = firebase.firestore();
          if (this.firestoreUnsubscribe) this.firestoreUnsubscribe();
          this.firestoreUnsubscribe = db.collection("users").onSnapshot(() => {
            // Khi có thay đổi trên Firestore, tự động refresh danh sách
            this.loadUsers();
          }, (err) => {
            console.log("Firestore admin listener notice:", err);
          });
        } catch(e) {
          console.warn("Firestore listener setup error:", e);
        }
      }
    },

    async loadUsers() {
      try {
        const res = await fetch("/api/admin/users");
        const data = await res.json();
        if (data && data.users) {
          this.users = data.users;
          this.stats = data.stats || this.stats;
          this.renderStats();
          this.filterUsers();
        }
      } catch (e) {
        console.error("Lỗi nạp danh sách giáo viên Admin:", e);
      }
    },

    renderStats() {
      const elTotal = document.getElementById("stat-total-users");
      const elTrial = document.getElementById("stat-trial-users");
      const elPro = document.getElementById("stat-pro-users");
      const elLifetime = document.getElementById("stat-lifetime-users");

      if (elTotal) elTotal.textContent = this.stats.total || 0;
      if (elTrial) elTrial.textContent = this.stats.trial || 0;
      if (elPro) elPro.textContent = this.stats.pro_expiring || 0;
      if (elLifetime) elLifetime.textContent = this.stats.pro_lifetime || 0;
    },

    setFilter(filter) {
      this.currentFilter = filter;
      document.querySelectorAll(".admin-filter-tabs .filter-tab").forEach(tab => {
        if (tab.getAttribute("data-filter") === filter) {
          tab.classList.add("active");
        } else {
          tab.classList.remove("active");
        }
      });
      this.filterUsers();
    },

    filterUsers() {
      const q = (document.getElementById("admin-search-input")?.value || "").trim().toLowerCase();
      this.filteredUsers = this.users.filter(u => {
        // Lọc theo Tab trạng thái
        if (this.currentFilter === 'trial') {
          if (u.is_pro || u.status === 'blocked') return false;
        } else if (this.currentFilter === 'pro') {
          if (!u.is_pro || u.pro_plan === 'lifetime' || u.status === 'blocked') return false;
        } else if (this.currentFilter === 'lifetime') {
          if (!u.is_pro || u.pro_plan !== 'lifetime' || u.status === 'blocked') return false;
        } else if (this.currentFilter === 'blocked') {
          if (u.status !== 'blocked') return false;
        }

        // Tìm kiếm theo Email hoặc Tên
        if (q) {
          const name = (u.display_name || "").toLowerCase();
          const email = (u.email || "").toLowerCase();
          const uid = (u.uid || "").toLowerCase();
          return name.includes(q) || email.includes(q) || uid.includes(q);
        }
        return true;
      });

      this.renderTable();
    },

    renderTable() {
      const tbody = document.getElementById("admin-users-table-body");
      if (!tbody) return;

      if (this.filteredUsers.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="5" class="admin-empty-state">
              <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
              <div>Không tìm thấy giáo viên nào phù hợp với bộ lọc.</div>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = this.filteredUsers.map(u => {
        const isBlocked = (u.status === 'blocked');
        const isPro = u.is_pro && !isBlocked;
        const isLife = isPro && (u.pro_plan === 'lifetime');

        let planBadge = '';
        if (isBlocked) {
          planBadge = `<span class="badge-plan badge-plan-blocked">🚫 Đã Khóa</span>`;
        } else if (isLife) {
          planBadge = `<span class="badge-plan badge-plan-lifetime">👑 Vĩnh Viễn</span>`;
        } else if (isPro) {
          const pName = u.pro_plan_name || (u.pro_plan === '2year' ? 'Gói 2 Năm' : 'Gói 1 Năm');
          planBadge = `<span class="badge-plan badge-plan-pro">📅 ${escapeHtml(pName)}</span>`;
        } else {
          planBadge = `<span class="badge-plan badge-plan-trial">⏰ Dùng Thử</span>`;
        }

        let quotaText = '';
        if (isBlocked) {
          quotaText = `<span style="color: #dc2626; font-weight: 600;">Tài khoản bị tạm khóa</span>`;
        } else if (isLife) {
          quotaText = `<strong style="color: #7e22ce;">Không giới hạn (Trọn đời)</strong>`;
        } else if (isPro) {
          const expDate = u.pro_expires_at ? u.pro_expires_at.split(" ")[0].split("-").reverse().join("/") : "Không rõ";
          const days = (u.days_left !== undefined && u.days_left !== null) ? u.days_left : "...";
          quotaText = `<strong>Hạn: ${expDate}</strong><br><small style="color: #64748b;">(Còn ${days} ngày)</small>`;
        } else {
          const used = u.trial_used || 0;
          const limit = u.trial_limit || 10;
          quotaText = `<strong>${used} / ${limit} lượt</strong> tạo & tải`;
        }

        const joinDate = u.created_at ? u.created_at.split(" ")[0].split("-").reverse().join("/") : "Hôm nay";
        const avatarHtml = u.photo_url 
          ? `<img src="${u.photo_url}" class="user-avatar-circle" alt="Avatar">`
          : `<div class="user-avatar-fallback">${escapeHtml((u.display_name || u.email || 'G')[0].toUpperCase())}</div>`;

        return `
          <tr>
            <td>
              <div class="user-cell">
                ${avatarHtml}
                <div>
                  <div class="user-name-text">${escapeHtml(u.display_name || 'Giáo viên')}</div>
                  <div class="user-email-text">${escapeHtml(u.email || u.uid)}</div>
                </div>
              </div>
            </td>
            <td>${planBadge}</td>
            <td>${quotaText}</td>
            <td><span style="color: #64748b; font-size: 12.5px;">${joinDate}</span></td>
            <td>
              <div class="admin-actions-cell">
                <button class="btn-action-pill btn-action-quota" onclick="window.AdminManager.approveUser('${u.uid}', 'quota_10')" title="Cộng thêm 10 lượt dùng thử">+10 Lượt</button>
                <button class="btn-action-pill btn-action-1y" onclick="window.AdminManager.approveUser('${u.uid}', '1year')" title="Duyệt Gói 1 Năm (365 ngày)">1 Năm</button>
                <button class="btn-action-pill btn-action-2y" onclick="window.AdminManager.approveUser('${u.uid}', '2year')" title="Duyệt Gói 2 Năm (730 ngày)">2 Năm</button>
                <button class="btn-action-pill btn-action-life" onclick="window.AdminManager.approveUser('${u.uid}', 'lifetime')" title="Duyệt Gói Vĩnh Viễn Trọn Đời">Vĩnh Viễn</button>
                <button class="btn-action-pill btn-action-custom" onclick="window.AdminManager.promptCustomDays('${u.uid}')" title="Cấp theo số ngày tùy chọn">Tùy Chọn</button>
                <button class="btn-action-block" onclick="window.AdminManager.toggleBlockUser('${u.uid}')" title="${isBlocked ? 'Mở khóa tài khoản' : 'Khóa tài khoản'}">
                  ${isBlocked ? '🔓' : '🚫'}
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    },

    async approveUser(uid, action, customDays, customQuota) {
      try {
        const res = await fetch("/api/admin/approve-user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: uid,
            action: action,
            days: customDays,
            quota: customQuota
          })
        });
        const data = await res.json();
        if (data.status === "success") {
          // Đồng bộ sang Firestore Realtime Cloud
          if (typeof firebase !== "undefined" && firebase.firestore) {
            try {
              const db = firebase.firestore();
              const updateObj = { last_admin_update: new Date().toISOString() };
              if (action === '1year') {
                updateObj.is_pro = true;
                updateObj.pro_plan = '1year';
                updateObj.pro_plan_name = 'Gói 1 Năm';
                updateObj.status = 'active';
              } else if (action === '2year') {
                updateObj.is_pro = true;
                updateObj.pro_plan = '2year';
                updateObj.pro_plan_name = 'Gói 2 Năm';
                updateObj.status = 'active';
              } else if (action === 'lifetime') {
                updateObj.is_pro = true;
                updateObj.pro_plan = 'lifetime';
                updateObj.pro_plan_name = 'Gói Vĩnh Viễn';
                updateObj.status = 'active';
              } else if (action === 'toggle_block') {
                updateObj.status = data.user?.status || 'blocked';
              } else if (action.includes('quota')) {
                updateObj.trial_limit = data.user?.trial_limit || 20;
              }
              db.collection("users").doc(uid).set(updateObj, { merge: true }).catch(() => {});
            } catch (e) {}
          }

          alert(`✅ ${data.message}`);
          await this.loadUsers();
        } else {
          alert(`❌ Lỗi phê duyệt: ${data.message}`);
        }
      } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e);
      }
    },

    promptCustomDays(uid) {
      const daysStr = prompt("Nhập số ngày muốn cấp quyền PRO cho giáo viên (ví dụ: 30, 60, 90, 180):", "30");
      if (!daysStr) return;
      const days = parseInt(daysStr);
      if (isNaN(days) || days <= 0) {
        alert("Số ngày không hợp lệ.");
        return;
      }
      this.approveUser(uid, 'custom', days);
    },

    toggleBlockUser(uid) {
      const u = this.users.find(x => x.uid === uid);
      const isBlocked = u && u.status === 'blocked';
      const msg = isBlocked 
        ? `Thầy/Cô có chắc muốn MỞ KHÓA cho tài khoản: ${u.email || u.display_name}?`
        : `Thầy/Cô có chắc muốn KHÓA tài khoản: ${u.email || u.display_name}?`;
      if (confirm(msg)) {
        this.approveUser(uid, 'toggle_block');
      }
    },

    promptPreapproveEmail() {
      const email = prompt("Nhập địa chỉ Gmail của giáo viên cần kích hoạt trước:");
      if (!email || !email.includes("@")) {
        if (email) alert("Email không hợp lệ.");
        return;
      }
      const plan = prompt(`Chọn gói kích hoạt:\n1: Gói 1 Năm (150k)\n2: Gói 2 Năm (250k)\n3: Gói Vĩnh Viễn (599k)`, "3");
      let planKey = "lifetime";
      if (plan === "1") planKey = "1year";
      else if (plan === "2") planKey = "2year";

      fetch("/api/admin/preapprove-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), plan: planKey })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === "success") {
          alert(`✅ Đã kích hoạt trước thành công cho Gmail: ${email}
Khi giáo viên đăng nhập bằng Gmail này sẽ có ngay bản quyền PRO!`);
          this.loadUsers();
        } else {
          alert("Lỗi: " + data.message);
        }
      })
      .catch(err => alert("Lỗi kết nối: " + err));
    }
  };

  window.AuthManager = AuthManager;
  window.AdminManager = AdminManager;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => AuthManager.init());
  } else {
    AuthManager.init();
  }
})();

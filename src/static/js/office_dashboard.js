/* ============================================
   PlantMind AI — Office Dashboard Controller
   ============================================ */
(function () {
  "use strict";

  /* ---------- State ---------- */
  const state = {
    allOrders: [],
    emailLogs: [],
    autoRefreshTimer: null,
    darkMode: localStorage.getItem("pm_dark") === "1",
    searchTimer: null,
    processing: false,
  };

  /* ---------- Helpers ---------- */
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  function esc(v) {
    if (v == null) return "";
    return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }

  function relTime(iso) {
    if (!iso) return "Never";
    const d = new Date(iso), mins = Math.max(0, Math.floor((Date.now() - d) / 60000));
    const rel = mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins/60)}h ago`;
    return `${d.toLocaleString()} (${rel})`;
  }

  function statusBadge(s) {
    const m = {
      new:           { cls: "badge-new",        label: "New" },
      needs_review:  { cls: "badge-review",     label: "Needs Review" },
      scheduled:     { cls: "badge-scheduled",  label: "Scheduled" },
      in_production: { cls: "badge-production", label: "In Production" },
      completed:     { cls: "badge-completed",  label: "Completed" },
      dispatched:    { cls: "badge-dispatched", label: "Dispatched" },
    };
    const k = String(s || "").toLowerCase();
    return m[k] || { cls: "badge-skip", label: esc(s || "Unknown") };
  }

  function emailBadge(s) {
    const m = {
      success: { cls: "badge-success",  label: "Success" },
      error:   { cls: "badge-error",    label: "Error" },
      flagged: { cls: "badge-flagged",  label: "Flagged" },
      skipped: { cls: "badge-skip",     label: "Skipped" },
    };
    const k = String(s || "").toLowerCase();
    return m[k] || { cls: "badge-skip", label: esc(s) };
  }

  /* ---------- Toast Notifications (Enhanced) ---------- */
  function toast(msg, type = "success", duration = 5000) {
    const c = $(".toast-container") || document.getElementById("toastContainer");
    if (!c) return;
    
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span>${type === "success" ? "✓" : type === "error" ? "✗" : type === "warning" ? "⚠" : "ℹ"}</span>
        <span>${esc(msg)}</span>
      </div>
    `;
    c.appendChild(el);
    
    // Auto remove with animation
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateX(100%)";
      el.style.transition = "all 0.3s ease";
      setTimeout(() => el.remove(), 300);
    }, duration);
  }
  
  /* ---------- Loading Overlay ---------- */
  function showLoading(message = "Loading...") {
    const overlay = $(".loading-overlay") || document.getElementById("loadingOverlay");
    if (overlay) {
      overlay.classList.add("active");
    }
  }
  
  function hideLoading() {
    const overlay = $(".loading-overlay") || document.getElementById("loadingOverlay");
    if (overlay) {
      overlay.classList.remove("active");
    }
  }
  
  /* ---------- Smooth Data Refresh ---------- */
  async function refreshAll(showToast = false) {
    showLoading();
    try {
      await Promise.all([
        loadSummary(),
        loadCustomerStats(),
        loadFlagged(),
        loadOrders(),
        loadEmails()
      ]);
      updateLastRefreshTime();
      if (showToast) toast("Data refreshed", "success", 2000);
    } catch (e) {
      console.error("Refresh failed:", e);
    } finally {
      hideLoading();
    }
  }
  
  function updateLastRefreshTime() {
    const el = $("#lastCheckTime");
    if (el) {
      el.textContent = "Last updated: " + new Date().toLocaleTimeString();
    }
  }

  /* ---------- Dark Mode ---------- */
  function applyTheme() {
    document.documentElement.setAttribute("data-theme", state.darkMode ? "dark" : "light");
    const btn = $("#themeToggle");
    if (btn) btn.textContent = state.darkMode ? "☀️ Light" : "🌙 Dark";
    localStorage.setItem("pm_dark", state.darkMode ? "1" : "0");
  }

  /* ---------- API (Enhanced with retry) ---------- */
  async function api(url, opts = {}, retries = 1) {
    try {
      const r = await fetch(url, opts);
      if (r.status === 401) { 
        window.location.href = "/login"; 
        return null; 
      }
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      }
      return await r.json();
    } catch (e) {
      if (retries > 0) {
        await new Promise(r => setTimeout(r, 1000));
        return api(url, opts, retries - 1);
      }
      throw e;
    }
  }

  /* ---------- Load Functions ---------- */
  async function loadSummary() {
    const d = await api("/processing-summary");
    if (!d || !d.success) return;
    const s = d.summary;
    const el = $("#lastProcessed");
    if (el) el.textContent = relTime(s.last_processed);
    const ne = $("#statNew");     if (ne) ne.textContent = s.orders.new;
    const rv = $("#statReview");  if (rv) rv.textContent = s.orders.needs_review;
    const to = $("#statTotal");   if (to) to.textContent = s.orders.total;
  }

  async function loadCustomerStats() {
    const d = await api("/customer-stats");
    if (!d || !d.success) return;
    const el = $("#statCustomers"); if (el) el.textContent = d.stats.total_customers;
  }

  async function loadFlagged() {
    const d = await api("/orders/flagged");
    if (!d || !d.success) return;
    const list = d.flagged_orders || [];
    const body = $("#flaggedBody");
    const empty = $("#flaggedEmpty");
    const count = $("#flaggedCount");
    if (count) count.textContent = list.length;
    if (!list.length) {
      if (body) body.innerHTML = "";
      if (empty) empty.classList.remove("hidden");
      return;
    }
    if (empty) empty.classList.add("hidden");
    if (body) body.innerHTML = list.map(o => {
      const sb = statusBadge(o.status);
      return `<tr>
        <td><strong>ORD-${String(o.order_id).padStart(3,"0")}</strong></td>
        <td>${esc(o.customer_name)}</td>
        <td>${esc(o.product_name)}</td>
        <td>${o.quantity || 0}</td>
        <td>${esc(o.required_delivery_date || "—")}</td>
        <td><span class="badge ${sb.cls}">${sb.label}</span></td>
        <td><button class="btn btn-primary" onclick="window._openReview(${o.order_id})">Review</button></td>
      </tr>`;
    }).join("");
  }

  async function loadOrders() {
    const d = await api("/orders");
    if (!d || !d.success) return;
    state.allOrders = d.orders || [];
    const ct = $("#orderCount"); if (ct) ct.textContent = state.allOrders.length;
    renderOrders();
  }

  function renderOrders() {
    const body = $("#ordersBody");
    if (!body) return;
    const q = ($("#searchInput") || {}).value || "";
    const ql = q.toLowerCase().trim();
    const list = state.allOrders.filter(o => {
      if (!ql) return true;
      return [o.customer_name, o.product_name, o.required_delivery_date, o.status, o.special_instructions]
        .join(" ").toLowerCase().includes(ql);
    });
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="8" class="table-empty">No orders match your search.</td></tr>`;
      return;
    }
    body.innerHTML = list.map(o => {
      const sb = statusBadge(o.status);
      return `<tr>
        <td><strong>ORD-${String(o.order_id).padStart(3,"0")}</strong></td>
        <td>${esc(o.customer_name)}</td>
        <td>${esc(o.product_name)}</td>
        <td>${o.quantity || 0}</td>
        <td>${esc(o.required_delivery_date || "—")}</td>
        <td class="truncate">${esc(o.special_instructions || "—")}</td>
        <td><span class="badge ${sb.cls}">${sb.label}</span></td>
        <td>${o.created_at ? new Date(o.created_at).toLocaleDateString() : "—"}</td>
      </tr>`;
    }).join("");
  }

  async function loadEmails() {
    const d = await api("/email-log");
    if (!d || !d.success) return;
    state.emailLogs = d.email_logs || [];
    const body = $("#emailBody");
    if (!body) return;
    if (!state.emailLogs.length) {
      body.innerHTML = `<tr><td colspan="4" class="table-empty">No emails processed yet.</td></tr>`;
      return;
    }
    body.innerHTML = state.emailLogs.map((l, i) => {
      const eb = emailBadge(l.processing_status);
      return `<tr class="clickable" onclick="window._previewEmail(${i})">
        <td>${l.processed_at ? new Date(l.processed_at).toLocaleString() : "—"}</td>
        <td>${esc(l.from_address || "—")}</td>
        <td>${esc(l.subject || "—")}</td>
        <td><span class="badge ${eb.cls}">${eb.label}</span></td>
      </tr>`;
    }).join("");
  }

  function refreshAll() {
    loadSummary(); loadCustomerStats(); loadFlagged(); loadOrders(); loadEmails();
  }

  /* ---------- Process Emails (Enhanced) ---------- */
  async function processEmails() {
    if (state.processing) {
      toast("Already processing...", "warning");
      return;
    }
    state.processing = true;
    
    const btn = $("#processBtn");
    const indicator = $("#processIndicator");
    const result = $("#processResult");

    // UI Updates
    if (btn) { 
      btn.disabled = true; 
      btn.innerHTML = '<span class="spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px;"></span> Processing…'; 
    }
    if (indicator) indicator.classList.remove("hidden");
    if (result) result.classList.add("hidden");
    
    toast("Starting email processing...", "info", 3000);

    try {
      const d = await api("/check-emails", { 
        method: "POST", 
        headers: { "Content-Type": "application/json" } 
      });

      if (d && d.success) {
        const r = d.result || {};
        const msg = `Processed ${r.total_emails || 0} emails → ${r.orders_created || 0} orders created`;
        
        if (result) {
          result.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; padding: 16px; background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; color: #166534;">
              <span style="font-size: 24px;">✅</span>
              <div>
                <div style="font-weight: 600;">Processing Complete</div>
                <div style="font-size: 0.875rem; color: #15803d;">${esc(msg)}</div>
              </div>
            </div>
          `;
          result.classList.remove("hidden");
        }
        
        toast(msg, "success");
        
        // Refresh data after short delay
        setTimeout(() => refreshAll(false), 500);
        
        // Update last check time
        updateLastRefreshTime();
        
      } else {
        const err = (d && d.error) || "Unknown error";
        if (result) {
          result.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; padding: 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b;">
              <span style="font-size: 24px;">❌</span>
              <div>
                <div style="font-weight: 600;">Processing Failed</div>
                <div style="font-size: 0.875rem;">${esc(err)}</div>
              </div>
            </div>
          `;
          result.classList.remove("hidden");
        }
        toast("Processing failed: " + err, "error", 8000);
      }
    } catch (e) {
      console.error("Email processing error:", e);
      if (result) {
        result.innerHTML = `
          <div style="display: flex; align-items: center; gap: 12px; padding: 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b;">
            <span style="font-size: 24px;">❌</span>
            <div>
              <div style="font-weight: 600;">Connection Error</div>
              <div style="font-size: 0.875rem;">Please check if the server is running.</div>
            </div>
          </div>
        `;
        result.classList.remove("hidden");
      }
      toast("Connection error - please try again", "error", 8000);
    } finally {
      state.processing = false;
      if (btn) { 
        btn.disabled = false; 
        btn.innerHTML = "<span>📧</span><span>Check New Emails</span>"; 
      }
      if (indicator) indicator.classList.add("hidden");
    }
  }

  /* ---------- Email Preview Modal ---------- */
  window._previewEmail = function (idx) {
    const log = state.emailLogs[idx];
    if (!log) return;
    $("#mFrom").textContent = log.from_address || "—";
    $("#mSubject").textContent = log.subject || "—";
    const eb = emailBadge(log.processing_status);
    $("#mStatus").innerHTML = `<span class="badge ${eb.cls}">${eb.label}</span>`;
    $("#mBody").textContent = log.body_summary || log.error_details || "No content saved.";
    $("#emailModal").classList.add("active");
  };

  /* ---------- Review Modal ---------- */
  window._openReview = function (id) {
    $("#rvOrderId").value = id;
    $("#rvProduct").value = "";
    $("#rvQty").value = "";
    $("#rvDate").value = "";
    $("#reviewModal").classList.add("active");
  };

  async function submitReview(e) {
    e.preventDefault();
    const id = $("#rvOrderId").value;
    if (!id) return;
    const fd = new FormData();
    const p = ($("#rvProduct") || {}).value; if (p) fd.append("product_name", p);
    const q = ($("#rvQty") || {}).value;     if (q) fd.append("quantity", q);
    const d = ($("#rvDate") || {}).value;    if (d) fd.append("delivery_date", d);
    try {
      const r = await api(`/orders/${id}/complete-review`, { method: "POST", body: fd });
      if (r && r.success) {
        toast("Order reviewed successfully", "success");
        closeModal("reviewModal");
        loadFlagged(); loadOrders();
      } else {
        toast("Error: " + ((r && (r.error || r.detail)) || "Unknown"), "error");
      }
    } catch { toast("Network error", "error"); }
  }

  function closeModal(id) { const m = $("#" + id); if (m) m.classList.remove("active"); }

  /* ---------- Auto Refresh ---------- */
  function toggleAutoRefresh() {
    const btn = $("#autoRefresh");
    if (state.autoRefreshTimer) {
      clearInterval(state.autoRefreshTimer);
      state.autoRefreshTimer = null;
      if (btn) btn.textContent = "Auto-refresh: OFF";
    } else {
      state.autoRefreshTimer = setInterval(refreshAll, 300000);
      if (btn) btn.textContent = "Auto-refresh: ON";
    }
  }

  /* ---------- Manual Order Creation ---------- */
  async function submitCreateOrder(e) {
    e.preventDefault();
    const btn = $("#coSubmitBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Creating…"; }

    const fd = new FormData();
    fd.append("customer_name", ($("#coName") || {}).value || "");
    fd.append("customer_email", ($("#coEmail") || {}).value || "");
    fd.append("product_name", ($("#coProduct") || {}).value || "");
    fd.append("quantity", ($("#coQty") || {}).value || "0");
    fd.append("delivery_date", ($("#coDate") || {}).value || "");
    fd.append("special_instructions", ($("#coInstructions") || {}).value || "");

    try {
      const resp = await fetch("/orders/create", { method: "POST", body: fd });
      const r = await resp.json();
      if (r && r.success) {
        toast("Order ORD-" + String(r.order_id).padStart(3, "0") + " created!", "success");
        closeModal("createOrderModal");
        e.target.reset();
        refreshAll();
      } else {
        toast("Error: " + ((r && (r.error || r.detail)) || "Unknown"), "error");
      }
    } catch { toast("Network error", "error"); }
    finally {
      if (btn) { btn.disabled = false; btn.textContent = "Create Order"; }
    }
  }

  /* ---------- AI Health Check ---------- */
  async function checkAiHealth() {
    const el = $("#aiStatus");
    if (!el) return;
    el.textContent = "🤖 Checking AI…";
    el.className = "ai-status ai-checking";
    try {
      const r = await fetch("/health/ai");
      const d = await r.json();
      if (d.status === "online") {
        el.textContent = "🟢 AI Online (" + (d.model || "ready") + ")";
        el.className = "ai-status ai-online";
      } else {
        el.textContent = "🔴 AI Offline";
        el.className = "ai-status ai-offline";
        el.title = d.message || "Ollama is not responding";
      }
    } catch {
      el.textContent = "🔴 AI Offline";
      el.className = "ai-status ai-offline";
      el.title = "Cannot reach AI health endpoint";
    }
  }

  /* ---------- Keyboard Shortcuts ---------- */
  document.addEventListener("keydown", (e) => {
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (e.ctrlKey && e.key === "f") { e.preventDefault(); const s = $("#searchInput"); if (s) s.focus(); return; }
    if (e.key === "r" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); refreshAll(); toast("Refreshed", "info"); }
    if (e.key === "p" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); processEmails(); }
    if (e.key === "n" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); const m = $("#createOrderModal"); if (m) m.classList.add("active"); }
  });

  /* ---------- Enhanced Auto Refresh ---------- */
  function toggleAutoRefresh() {
    const btn = $("#autoRefresh");
    const text = $("#autoRefreshText");
    
    if (state.autoRefreshTimer) {
      clearInterval(state.autoRefreshTimer);
      state.autoRefreshTimer = null;
      if (text) text.textContent = "Auto: OFF";
      if (btn) btn.classList.remove("active");
      toast("Auto-refresh disabled", "info", 2000);
    } else {
      state.autoRefreshTimer = setInterval(() => refreshAll(false), 60000); // Every minute
      if (text) text.textContent = "Auto: ON";
      if (btn) btn.classList.add("active");
      toast("Auto-refresh enabled (60s)", "success", 2000);
    }
  }
  
  /* ---------- Refresh Button ---------- */
  function setupRefreshButton() {
    const btn = $("#refreshBtn");
    if (btn) {
      btn.addEventListener("click", () => {
        // Add spin animation
        btn.style.transform = "rotate(360deg)";
        btn.style.transition = "transform 0.5s ease";
        setTimeout(() => btn.style.transform = "", 500);
        refreshAll(true);
      });
    }
  }

  /* ---------- Init (Enhanced) ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme();
    refreshAll(false);
    checkAiHealth();
    setupRefreshButton();

    // Process button
    const pb = $("#processBtn"); if (pb) pb.addEventListener("click", processEmails);

    // Create order button
    const co = $("#createOrderBtn"); if (co) co.addEventListener("click", () => {
      const m = $("#createOrderModal"); if (m) m.classList.add("active");
    });

    // Theme toggle
    const tb = $("#themeToggle"); if (tb) tb.addEventListener("click", () => { 
      state.darkMode = !state.darkMode; 
      applyTheme(); 
      toast(state.darkMode ? "Dark mode enabled" : "Light mode enabled", "info", 2000);
    });

    // Auto refresh
    const ar = $("#autoRefresh"); if (ar) ar.addEventListener("click", toggleAutoRefresh);

    // Search with debounce
    const si = $("#searchInput"); 
    if (si) {
      si.addEventListener("input", () => {
        clearTimeout(state.searchTimer);
        state.searchTimer = setTimeout(renderOrders, 200);
      });
      // Clear search on Escape
      si.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          si.value = "";
          renderOrders();
          si.blur();
        }
      });
    }

    // Export
    const ex = $("#exportBtn"); if (ex) ex.addEventListener("click", () => { 
      toast("Exporting orders...", "info", 2000);
      window.location.href = "/orders/export"; 
    });

    // Modal closes
    document.querySelectorAll("[data-close-modal]").forEach(btn => {
      btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
    });
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.classList.remove("active"); });
    });
    
    // Close modals on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document.querySelectorAll(".modal-overlay.active").forEach(m => m.classList.remove("active"));
      }
    });

    // Review form
    const rf = $("#reviewForm"); if (rf) rf.addEventListener("submit", submitReview);

    // Create order form
    const cf = $("#createOrderForm"); if (cf) cf.addEventListener("submit", submitCreateOrder);

    // Check AI health periodically (every 2 minutes)
    setInterval(checkAiHealth, 120000);
    
    // Welcome toast
    setTimeout(() => {
      toast(`Welcome back, ${esc(document.querySelector(".navbar-user strong")?.textContent || "User")}!`, "success", 3000);
    }, 1000);
  });
})();

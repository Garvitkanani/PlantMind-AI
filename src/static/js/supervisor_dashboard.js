/* ============================================
   PlantMind AI — Supervisor Dashboard Controller
   ============================================ */
(function () {
  "use strict";

  /* ---------- State ---------- */
  const state = {
    schedules: [],
    machines: [],
    autoRefreshTimer: null,
    darkMode: localStorage.getItem("pm_dark") === "1",
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
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString();
  }

  function statusBadge(s) {
    const m = {
      scheduled: { cls: "badge-scheduled", label: "Scheduled" },
      in_production: { cls: "badge-production", label: "In Production" },
      completed: { cls: "badge-completed", label: "Completed" },
      cancelled: { cls: "badge-skip", label: "Cancelled" },
      delayed: { cls: "badge-error", label: "Delayed" },
    };
    const k = String(s || "").toLowerCase();
    return m[k] || { cls: "badge-skip", label: esc(s || "Unknown") };
  }

  /* ---------- Toast Notifications ---------- */
  function toast(msg, type = "success", duration = 5000) {
    const c = $(".toast-container") || document.getElementById("toastContainer");
    if (!c) return;
    
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span>${type === "success" ? "✓" : type === "error" ? "✗" : type === "warning" ? "⚠" : "ℹ"}</span> <span>${esc(msg)}</span>`;
    c.appendChild(el);
    
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateX(100%)";
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  /* ---------- API ---------- */
  async function api(url, opts = {}) {
    try {
      const r = await fetch(url, opts);
      if (r.status === 401) { 
        window.location.href = "/login"; 
        return null; 
      }
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      return await r.json();
    } catch (e) {
      toast("Error: " + e.message, "error");
      throw e;
    }
  }

  /* ---------- Load Data ---------- */
  async function loadProductionSchedule() {
    const d = await api("/api/v2/production-schedule");
    if (!d || !d.success) return;
    state.schedules = d.schedules || [];
    renderSchedules();
  }

  async function loadMachines() {
    const d = await api("/api/v2/machines");
    if (!d || !d.success) return;
    state.machines = d.machines || [];
    renderMachines();
  }

  /* ---------- Render ---------- */
  function renderSchedules() {
    const body = $("#schedulesBody");
    if (!body) return;
    
    if (!state.schedules.length) {
      body.innerHTML = `<tr><td colspan="9" class="table-empty">No production schedules yet.</td></tr>`;
      return;
    }
    
    body.innerHTML = state.schedules.map(s => {
      const sb = statusBadge(s.status);
      const isDelayed = s.is_delayed;
      const eta = s.new_eta ? new Date(s.new_eta).toLocaleDateString() : (s.estimated_end ? new Date(s.estimated_end).toLocaleDateString() : "—");
      
      return `<tr>
        <td><strong>ORD-${String(s.order_id).padStart(3,"0")}</strong></td>
        <td>${esc(s.product_name || "—")}</td>
        <td>${esc(s.customer_name || "—")}</td>
        <td>${esc(s.machine_name || "—")}</td>
        <td>${s.quantity || 0}</td>
        <td>${s.pieces_completed || 0} / ${s.quantity || 0}</td>
        <td>
          <div style="width: 100px; background: #e5e7eb; height: 8px; border-radius: 4px; overflow: hidden;">
            <div style="width: ${s.completion_percentage || 0}%; background: ${isDelayed ? '#dc2626' : '#4f46e5'}; height: 100%;"></div>
          </div>
          <small>${Math.round(s.completion_percentage || 0)}%</small>
        </td>
        <td class="${isDelayed ? 'text-red-600 font-bold' : ''}">${eta}</td>
        <td><span class="badge ${sb.cls}">${sb.label}</span></td>
        <td>
          ${s.status === 'scheduled' ? `<button class="btn btn-primary btn-sm" onclick="startProduction(${s.schedule_id})">Start</button>` : ''}
          ${s.status === 'in_production' ? `<button class="btn btn-primary btn-sm" onclick="openProgressModal(${s.schedule_id})">Update</button>` : ''}
        </td>
      </tr>`;
    }).join("");
  }

  function renderMachines() {
    const body = $("#machinesBody");
    if (!body) return;
    
    if (!state.machines.length) {
      body.innerHTML = `<tr><td colspan="6" class="table-empty">No machines configured.</td></tr>`;
      return;
    }
    
    const statusColors = {
      available: "#22c55e",
      running: "#4f46e5",
      maintenance: "#f59e0b",
      offline: "#dc2626"
    };
    
    body.innerHTML = state.machines.map(m => `
      <tr>
        <td><strong>${esc(m.name)}</strong></td>
        <td>${esc(m.model || "—")}</td>
        <td><span style="color: ${statusColors[m.status] || '#666'}">●</span> ${esc(m.status || "unknown")}</td>
        <td>${m.current_order_id ? `<a href="#" onclick="return false;">ORD-${String(m.current_order_id).padStart(3,"0")}</a>` : "—"}</td>
        <td>${m.total_runtime_hours ? Math.round(m.total_runtime_hours) + ' hrs' : "—"}</td>
        <td>${m.needs_maintenance ? '<span class="badge badge-warning">Maintenance Due</span>' : '<span class="badge badge-success">OK</span>'}</td>
      </tr>
    `).join("");
  }

  /* ---------- Actions ---------- */
  window.startProduction = async function(scheduleId) {
    try {
      const d = await api(`/api/v2/production-schedule/${scheduleId}/start`, { method: "POST" });
      if (d.success) {
        toast("Production started successfully", "success");
        loadProductionSchedule();
      }
    } catch {}
  };

  window.openProgressModal = function(scheduleId) {
    $("#progressScheduleId").value = scheduleId;
    $("#progressPieces").value = "";
    $("#progressNotes").value = "";
    $("#progressModal").classList.add("active");
  };

  async function submitProgress(e) {
    e.preventDefault();
    const scheduleId = $("#progressScheduleId").value;
    const pieces = $("#progressPieces").value;
    const notes = $("#progressNotes").value;
    
    if (!pieces || pieces <= 0) {
      toast("Please enter valid piece count", "error");
      return;
    }
    
    try {
      const d = await api(`/api/v2/production-schedule/${scheduleId}/progress`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ pieces_completed: parseInt(pieces), notes: notes })
      });
      
      if (d.success) {
        toast("Progress updated successfully", "success");
        closeModal("progressModal");
        loadProductionSchedule();
        
        if (d.is_complete) {
          toast("Production completed! 🎉", "success");
        }
        if (d.delay_alert_triggered) {
          toast("Delay alert sent to owner", "warning");
        }
      }
    } catch {}
  }

  window.markComplete = async function(scheduleId) {
    if (!confirm("Mark this production as complete?")) return;
    
    try {
      const d = await api(`/api/v2/production-schedule/${scheduleId}/complete`, { method: "POST" });
      if (d.success) {
        toast("Production marked as complete", "success");
        loadProductionSchedule();
      }
    } catch {}
  };

  function closeModal(id) { 
    const m = $("#" + id); 
    if (m) m.classList.remove("active"); 
  }

  /* ---------- Init ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    loadProductionSchedule();
    loadMachines();

    // Modal closes
    document.querySelectorAll("[data-close-modal]").forEach(btn => {
      btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
    });
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.classList.remove("active"); });
    });

    // Progress form
    const pf = $("#progressForm"); 
    if (pf) pf.addEventListener("submit", submitProgress);

    // Refresh button
    const rb = $("#refreshBtn");
    if (rb) rb.addEventListener("click", () => { loadProductionSchedule(); loadMachines(); toast("Refreshed", "info"); });

    // Auto refresh every 30 seconds
    state.autoRefreshTimer = setInterval(() => { loadProductionSchedule(); loadMachines(); }, 30000);
  });
})();
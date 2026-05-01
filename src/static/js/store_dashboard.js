/* ============================================
   PlantMind AI — Store Dashboard Controller
   ============================================ */
(function () {
  "use strict";

  /* ---------- State ---------- */
  const state = {
    materials: [],
    reorders: [],
    suppliers: [],
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
    return d.toLocaleDateString();
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
  async function loadMaterials() {
    const d = await api("/api/v2/materials");
    if (!d || !d.success) return;
    state.materials = d.materials || [];
    renderMaterials();
  }

  async function loadReorders() {
    const d = await api("/api/v2/reorders");
    if (!d || !d.success) return;
    state.reorders = d.reorders || [];
    renderReorders();
  }

  async function loadSuppliers() {
    const d = await api("/api/v2/suppliers");
    if (!d || !d.success) return;
    state.suppliers = d.suppliers || [];
  }

  /* ---------- Render ---------- */
  function getStockStatus(material) {
    const current = material.current_stock_kg;
    const reorder = material.reorder_level_kg;
    const ratio = current / reorder;
    
    if (ratio <= 1) return { cls: "badge-critical", label: "Critical", color: "#dc2626" };
    if (ratio <= 2) return { cls: "badge-warning", label: "Low", color: "#f59e0b" };
    return { cls: "badge-success", label: "Good", color: "#22c55e" };
  }

  function renderMaterials() {
    const body = $("#materialsBody");
    if (!body) return;
    
    if (!state.materials.length) {
      body.innerHTML = `<tr><td colspan="7" class="table-empty">No materials in inventory.</td></tr>`;
      return;
    }
    
    body.innerHTML = state.materials.map(m => {
      const status = getStockStatus(m);
      return `<tr>
        <td><strong>${esc(m.name)}</strong></td>
        <td>${esc(m.type || "—")}</td>
        <td style="color: ${status.color}; font-weight: bold;">${m.current_stock_kg.toFixed(1)} kg</td>
        <td>${m.reorder_level_kg.toFixed(1)} kg</td>
        <td><span class="badge ${status.cls}">${status.label}</span></td>
        <td>${esc(m.supplier_name || "—")}</td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="openStockModal(${m.material_id}, '${esc(m.name)}', ${m.current_stock_kg})">
            Update Stock
          </button>
          ${m.needs_reorder ? `<button class="btn btn-warning btn-sm" onclick="openReorderModal(${m.material_id}, '${esc(m.name)}')">Reorder</button>` : ''}
        </td>
      </tr>`;
    }).join("");
    
    // Update summary stats
    const critical = state.materials.filter(m => m.current_stock_kg <= m.reorder_level_kg).length;
    const low = state.materials.filter(m => m.current_stock_kg <= m.reorder_level_kg * 2 && m.current_stock_kg > m.reorder_level_kg).length;
    
    const ce = $("#criticalCount"); if (ce) ce.textContent = critical;
    const le = $("#lowCount"); if (le) le.textContent = low;
  }

  function renderReorders() {
    const body = $("#reordersBody");
    if (!body) return;
    
    if (!state.reorders.length) {
      body.innerHTML = `<tr><td colspan="7" class="table-empty">No reorders yet.</td></tr>`;
      return;
    }
    
    const statusColors = {
      pending: "#f59e0b",
      ordered: "#4f46e5",
      confirmed: "#8b5cf6",
      shipped: "#06b6d4",
      delivered: "#22c55e",
      cancelled: "#dc2626"
    };
    
    body.innerHTML = state.reorders.map(r => `
      <tr>
        <td>${r.reorder_id}</td>
        <td>${esc(r.material_name || "—")}</td>
        <td>${r.quantity_kg.toFixed(1)} kg</td>
        <td>${esc(r.supplier_name || "—")}</td>
        <td><span style="color: ${statusColors[r.status] || "#666"}">●</span> ${esc(r.status || "unknown")}</td>
        <td>${relTime(r.created_at)}</td>
        <td>${r.expected_delivery ? relTime(r.expected_delivery) : "—"}</td>
      </tr>
    `).join("");
  }

  /* ---------- Actions ---------- */
  window.openStockModal = function(materialId, materialName, currentStock) {
    $("#stockMaterialId").value = materialId;
    $("#stockMaterialName").textContent = materialName;
    $("#stockCurrent").textContent = currentStock.toFixed(1) + " kg";
    $("#stockNew").value = currentStock.toFixed(1);
    $("#stockNotes").value = "";
    $("#stockModal").classList.add("active");
  };

  window.openReorderModal = function(materialId, materialName) {
    $("#reorderMaterialId").value = materialId;
    $("#reorderMaterialName").textContent = materialName;
    $("#reorderQuantity").value = "";
    $("#reorderModal").classList.add("active");
  };

  async function submitStockUpdate(e) {
    e.preventDefault();
    const materialId = $("#stockMaterialId").value;
    const newStock = $("#stockNew").value;
    const notes = $("#stockNotes").value;
    
    try {
      const d = await api(`/api/v2/materials/${materialId}/stock`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ new_stock_kg: parseFloat(newStock), notes: notes })
      });
      
      if (d.success) {
        toast("Stock updated successfully", "success");
        closeModal("stockModal");
        loadMaterials();
        
        if (d.orders_scheduled > 0) {
          toast(`${d.orders_scheduled} order(s) now ready for scheduling!`, "success");
        }
      }
    } catch {}
  }

  async function submitReorder(e) {
    e.preventDefault();
    const materialId = $("#reorderMaterialId").value;
    const quantity = $("#reorderQuantity").value;
    
    if (!quantity || quantity <= 0) {
      toast("Please enter valid quantity", "error");
      return;
    }
    
    try {
      const d = await api("/api/v2/reorders", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          material_id: parseInt(materialId),
          supplier_id: 1,
          quantity_kg: parseFloat(quantity),
          triggered_by: "manual_store"
        })
      });
      
      if (d.success) {
        toast("Reorder created successfully", "success");
        closeModal("reorderModal");
        loadReorders();
      }
    } catch {}
  }

  function closeModal(id) { 
    const m = $("#" + id); 
    if (m) m.classList.remove("active"); 
  }

  /* ---------- Init ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    loadMaterials();
    loadReorders();
    loadSuppliers();

    // Modal closes
    document.querySelectorAll("[data-close-modal]").forEach(btn => {
      btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
    });
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.classList.remove("active"); });
    });

    // Stock update form
    const sf = $("#stockForm"); 
    if (sf) sf.addEventListener("submit", submitStockUpdate);

    // Reorder form
    const rf = $("#reorderForm"); 
    if (rf) rf.addEventListener("submit", submitReorder);

    // Refresh button
    const rb = $("#refreshBtn");
    if (rb) rb.addEventListener("click", () => { loadMaterials(); loadReorders(); toast("Refreshed", "info"); });

    // Auto refresh every 30 seconds
    state.autoRefreshTimer = setInterval(() => { loadMaterials(); loadReorders(); }, 30000);
  });
})();
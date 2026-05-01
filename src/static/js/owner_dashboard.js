/**
 * PlantMind AI — Owner Dashboard JavaScript
 * Factory Command Center: real-time production monitoring, dispatch tracking, MIS reporting.
 *
 * Fetches data from /api/v3/owner/dashboard-data and renders:
 *   1. Health cards (5 KPI metrics)
 *   2. Live orders table with progress bars
 *   3. Activity feed (recent emails in/out)
 *   4. Machine status board (visual cards)
 *   5. Inventory & stock level bars
 *   6. Dispatch history
 *   7. MIS report history with "View Report" modal
 *   8. Quick action buttons (email check, dispatch, MIS)
 */

'use strict';

const OWNER_API = '/api/v3/owner/dashboard-data';
const REFRESH_INTERVAL_MS = 30000; // 30 seconds

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    setInterval(loadDashboardData, REFRESH_INTERVAL_MS);
});

async function loadDashboardData() {
    try {
        const res = await fetch(OWNER_API);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.success) {
            console.error('Dashboard API returned failure:', data);
            return;
        }

        renderHealthCards(data.overview || {});
        renderOrdersTable(data.orders || []);
        renderActivityFeed(data.activity || []);
        renderMachineGrid(data.machines || []);
        renderInventoryList(data.materials || []);
        renderDispatchHistory(data.dispatch_history || []);
        renderMisHistory(data.mis_history || []);

    } catch (err) {
        console.error('Failed to load owner dashboard data:', err);
    }
}

// ============================================================
// 1. Health Cards
// ============================================================

function renderHealthCards(overview) {
    setText('activeOrders', overview.active_orders ?? 0);
    setText('inProduction', overview.in_production ?? 0);
    setText('completedTotal', overview.completed_total ?? 0);
    setText('dispatchedTotal', overview.dispatched_total ?? 0);

    const overdue = overview.overdue ?? 0;
    setText('overdueCount', overdue);

    // Delay status badge
    const delayEl = document.getElementById('delayStatus');
    if (delayEl) {
        if (overdue > 0) {
            delayEl.className = 'status-indicator status-critical';
            delayEl.textContent = `⚠ ${overdue} delayed`;
        } else {
            delayEl.className = 'status-indicator status-healthy';
            delayEl.textContent = '● None';
        }
    }

    // Active orders status badge
    const activeEl = document.getElementById('activeStatus');
    if (activeEl) {
        if (overdue > 0) {
            activeEl.className = 'status-indicator status-warning';
            activeEl.textContent = `⚠ ${overdue} delayed`;
        } else {
            activeEl.className = 'status-indicator status-healthy';
            activeEl.textContent = '● On Track';
        }
    }
}

// ============================================================
// 2. Live Orders Table
// ============================================================

function renderOrdersTable(orders) {
    const tbody = document.getElementById('ordersBody');
    if (!tbody) return;

    if (!orders.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:2rem;color:#6b7280;">No orders found</td></tr>';
        return;
    }

    const statusColors = {
        new: '#3b82f6',
        needs_review: '#f59e0b',
        scheduled: '#6366f1',
        in_production: '#8b5cf6',
        awaiting_material: '#f97316',
        completed: '#10b981',
        dispatched: '#059669',
    };

    const statusIcons = {
        new: '🆕', needs_review: '⚠️', scheduled: '📅',
        in_production: '⚙️', awaiting_material: '📦',
        completed: '✅', dispatched: '🚚',
    };

    tbody.innerHTML = orders.slice(0, 50).map(o => {
        const pct = o.completion_percentage ?? 0;
        const color = statusColors[o.status] || '#6b7280';
        const icon = statusIcons[o.status] || '';
        const barColor = o.status === 'dispatched' ? '#059669' : (pct >= 100 ? '#10b981' : '#6366f1');

        return `
            <tr style="border-bottom:1px solid #f3f4f6;">
                <td style="padding:0.6rem;font-weight:600;">#${o.order_id}</td>
                <td style="padding:0.6rem;">${esc(o.customer_name || 'Unknown')}</td>
                <td style="padding:0.6rem;">${esc(o.product_name || '')}</td>
                <td style="padding:0.6rem;">${(o.quantity ?? 0).toLocaleString()}</td>
                <td style="padding:0.6rem;">
                    <span style="color:${color};font-weight:500;font-size:0.85rem;">
                        ${icon} ${(o.status || '').replace(/_/g, ' ')}
                    </span>
                </td>
                <td style="padding:0.6rem;color:#6b7280;font-size:0.85rem;">${esc(o.machine_name || '—')}</td>
                <td style="padding:0.6rem;">
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <div style="width:60px;height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden;">
                            <div style="width:${Math.min(pct, 100)}%;height:100%;background:${barColor};border-radius:3px;transition:width 0.5s;"></div>
                        </div>
                        <span style="font-size:0.8rem;color:#6b7280;">${pct.toFixed(0)}%</span>
                    </div>
                </td>
            </tr>`;
    }).join('');
}

// ============================================================
// 3. Recent Activity Feed
// ============================================================

function renderActivityFeed(activities) {
    const container = document.getElementById('activityList');
    if (!container) return;

    if (!activities.length) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#6b7280;">No recent activity</p>';
        return;
    }

    container.innerHTML = activities.slice(0, 15).map(a => {
        const isIn = a.direction === 'in';
        const iconClass = a.processing_status === 'error' ? 'error' : (isIn ? 'inbound' : 'outbound');
        const icon = a.processing_status === 'error' ? '❌' : (isIn ? '📥' : '📤');
        const timeStr = formatTime(a.processed_at);
        const statusBadge = a.processing_status === 'success'
            ? '<span style="color:#059669;font-size:0.7rem;">✓</span>'
            : (a.processing_status === 'error'
                ? '<span style="color:#ef4444;font-size:0.7rem;">✗</span>'
                : '');

        return `
            <div class="activity-item">
                <div class="activity-icon ${iconClass}">${icon}</div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:0.85rem;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                        ${esc(a.subject || 'No subject')} ${statusBadge}
                    </div>
                    <div style="font-size:0.75rem;color:#9ca3af;margin-top:2px;">
                        ${isIn ? 'From' : 'To'}: ${esc(isIn ? (a.from_address || '') : (a.to_address || ''))}
                        &nbsp;·&nbsp; ${timeStr}
                    </div>
                </div>
            </div>`;
    }).join('');
}

// ============================================================
// 4. Machine Status Board
// ============================================================

function renderMachineGrid(machines) {
    const grid = document.getElementById('machineGrid');
    if (!grid) return;

    if (!machines.length) {
        grid.innerHTML = '<p style="text-align:center;padding:2rem;color:#6b7280;grid-column:1/-1;">No machines configured</p>';
        return;
    }

    grid.innerHTML = machines.map(m => {
        const status = m.status || 'available';
        const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);
        const badgeClass = status === 'running' ? 'status-healthy'
            : status === 'maintenance' ? 'status-warning'
            : status === 'offline' ? 'status-critical'
            : 'status-healthy';

        const runtime = m.total_runtime_hours ? `${parseFloat(m.total_runtime_hours).toFixed(0)}h runtime` : '';
        const maint = m.next_scheduled_maintenance ? `Next maint: ${m.next_scheduled_maintenance}` : '';
        const details = [runtime, maint].filter(Boolean).join(' · ');

        return `
            <div class="machine-card ${status}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                    <strong>${esc(m.name)}</strong>
                    <span class="status-indicator ${badgeClass}">● ${statusLabel}</span>
                </div>
                <div style="font-size:0.8rem;color:#6b7280;">
                    ${m.model ? esc(m.model) : ''}
                    ${m.current_order_id ? ` · Order #${m.current_order_id}` : ''}
                </div>
                ${details ? `<div style="font-size:0.75rem;color:#9ca3af;margin-top:0.3rem;">${details}</div>` : ''}
            </div>`;
    }).join('');
}

// ============================================================
// 5. Inventory & Stock Levels
// ============================================================

function renderInventoryList(materials) {
    const container = document.getElementById('inventoryList');
    if (!container) return;

    if (!materials.length) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#6b7280;">No materials configured</p>';
        return;
    }

    container.innerHTML = materials.map(m => {
        const current = parseFloat(m.current_stock_kg) || 0;
        const reorder = parseFloat(m.reorder_level_kg) || 1;
        const ratio = current / reorder;
        const pct = Math.min(ratio * 100, 100);
        const barClass = ratio <= 0.5 ? 'critical' : ratio <= 1.0 ? 'warning' : 'healthy';
        const label = ratio <= 0.5 ? '⚠️ Critical' : ratio <= 1.0 ? '⚡ Low' : '✅ OK';

        return `
            <div style="padding:0.75rem 0;border-bottom:1px solid #f3f4f6;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong style="font-size:0.9rem;">${esc(m.name)}</strong>
                    <span style="font-size:0.8rem;color:${barClass === 'critical' ? '#ef4444' : barClass === 'warning' ? '#d97706' : '#059669'};font-weight:500;">
                        ${current.toFixed(0)} / ${reorder.toFixed(0)} kg ${label}
                    </span>
                </div>
                <div class="stock-bar">
                    <div class="stock-fill ${barClass}" style="width:${pct}%"></div>
                </div>
            </div>`;
    }).join('');
}

// ============================================================
// 6. Dispatch History
// ============================================================

function renderDispatchHistory(dispatches) {
    const container = document.getElementById('dispatchList');
    if (!container) return;

    if (!dispatches.length) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#6b7280;">No dispatches yet</p>';
        return;
    }

    container.innerHTML = dispatches.slice(0, 10).map(d => {
        const isSent = d.send_status === 'sent';
        const icon = isSent ? '✅' : '❌';
        const timeStr = formatTime(d.created_at);

        return `
            <div class="dispatch-item">
                <div style="min-width:0;">
                    <div style="font-size:0.85rem;font-weight:500;">
                        ${icon} Order #${d.order_id} — ${esc(d.product_name || '')}
                    </div>
                    <div style="font-size:0.75rem;color:#9ca3af;">
                        To: ${esc(d.customer_email || '—')} · ${timeStr}
                    </div>
                </div>
                <span style="padding:0.2rem 0.5rem;border-radius:9999px;font-size:0.7rem;font-weight:600;
                    background:${isSent ? '#d1fae5' : '#fee2e2'};color:${isSent ? '#065f46' : '#991b1b'};">
                    ${d.send_status}
                </span>
            </div>`;
    }).join('');
}

// ============================================================
// 7. MIS Report History
// ============================================================

function renderMisHistory(reports) {
    const tbody = document.getElementById('misBody');
    if (!tbody) return;

    if (!reports.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;color:#6b7280;">No MIS reports generated yet</td></tr>';
        return;
    }

    tbody.innerHTML = reports.map(r => {
        const isSent = r.send_status === 'sent';
        const date = r.report_date || '—';
        const hasBody = r.report_body && r.report_body.trim().length > 0;

        return `
            <tr style="border-bottom:1px solid #f3f4f6;">
                <td style="padding:0.65rem;font-weight:500;">${date}</td>
                <td style="padding:0.65rem;font-size:0.85rem;">${esc(r.email_subject || '—')}</td>
                <td style="padding:0.65rem;font-size:0.85rem;color:#6b7280;">${esc(r.owner_email || '—')}</td>
                <td style="padding:0.65rem;">
                    <span style="padding:0.2rem 0.5rem;border-radius:9999px;font-size:0.7rem;font-weight:600;
                        background:${isSent ? '#d1fae5' : '#fee2e2'};color:${isSent ? '#065f46' : '#991b1b'};">
                        ${r.send_status || 'unknown'}
                    </span>
                </td>
                <td style="padding:0.65rem;">
                    ${hasBody
                        ? `<button onclick="openMisModal('${esc(r.email_subject || 'MIS Report')}', ${r.mis_report_log_id})"
                             style="padding:0.3rem 0.6rem;background:#eef2ff;color:#4f46e5;border:none;border-radius:6px;cursor:pointer;font-size:0.8rem;font-weight:500;">
                             View Report
                           </button>`
                        : '<span style="color:#9ca3af;font-size:0.8rem;">—</span>'}
                </td>
            </tr>`;
    }).join('');
}

// Store report bodies for modal viewing
let _misReportCache = {};

function openMisModal(title, reportId) {
    const modal = document.getElementById('misModal');
    const titleEl = document.getElementById('misModalTitle');
    const bodyEl = document.getElementById('misModalBody');

    titleEl.textContent = title;

    // Find the report body from the last loaded data
    if (_misReportCache[reportId]) {
        bodyEl.textContent = _misReportCache[reportId];
    } else {
        bodyEl.textContent = 'Report body not available. Try refreshing the page.';
    }

    modal.classList.add('active');
}

function closeMisModal() {
    document.getElementById('misModal').classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.id === 'misModal') closeMisModal();
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMisModal();
});

// Override loadDashboardData to also cache MIS report bodies
const _originalLoad = loadDashboardData;
loadDashboardData = async function() {
    try {
        const res = await fetch(OWNER_API);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.success) {
            console.error('Dashboard API returned failure:', data);
            return;
        }

        // Cache MIS report bodies for modal
        (data.mis_history || []).forEach(r => {
            if (r.report_body && r.mis_report_log_id) {
                _misReportCache[r.mis_report_log_id] = r.report_body;
            }
        });

        renderHealthCards(data.overview || {});
        renderOrdersTable(data.orders || []);
        renderActivityFeed(data.activity || []);
        renderMachineGrid(data.machines || []);
        renderInventoryList(data.materials || []);
        renderDispatchHistory(data.dispatch_history || []);
        renderMisHistory(data.mis_history || []);

    } catch (err) {
        console.error('Failed to load owner dashboard data:', err);
    }
};

// ============================================================
// 8. Quick Action Buttons
// ============================================================

async function triggerAction(url, loadingText, button) {
    const originalText = button.textContent;
    button.textContent = loadingText;
    button.disabled = true;

    try {
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            button.textContent = '✅ Done!';
            // Refresh dashboard data
            setTimeout(() => loadDashboardData(), 1000);
        } else {
            button.textContent = '❌ Failed';
            console.error('Action failed:', data.error || data.detail || data);
        }
    } catch (err) {
        button.textContent = '❌ Error';
        console.error('Action error:', err);
    }

    setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;
    }, 3000);
}

// ============================================================
// Utility Functions
// ============================================================

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        const now = new Date();
        const diffMs = now - d;
        const diffMin = Math.floor(diffMs / 60000);
        const diffHr = Math.floor(diffMs / 3600000);

        if (diffMin < 1) return 'Just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        if (diffHr < 24) return `${diffHr}h ago`;

        return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch {
        return isoStr;
    }
}

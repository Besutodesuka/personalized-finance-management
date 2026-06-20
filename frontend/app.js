'use strict';

const API = 'http://localhost:8000/api';

const state = {
  wallets: [],
  categories: [],
  subscriptions: [],
  expenses: [],
  dashboard: null,
  currentMonth: new Date().toISOString().slice(0, 7),
  activeTab: 'dashboard',
  chatHistory: [],
  charts: {},
};

// ---- API ----

const api = {
  async get(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(API + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async del(path) {
    const r = await fetch(API + path, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

async function loadData() {
  try {
    [state.wallets, state.categories, state.subscriptions, state.dashboard] = await Promise.all([
      api.get('/wallets'),
      api.get('/categories'),
      api.get('/subscriptions'),
      api.get(`/dashboard?month=${state.currentMonth}`),
    ]);
    state.expenses = await api.get(`/expenses?month=${state.currentMonth}`);
  } catch (e) {
    console.error('Load error:', e);
  }
}

// ---- Navigation ----

function navigate(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  destroyCharts();
  renderView();
}

function destroyCharts() {
  Object.values(state.charts).forEach(c => c.destroy());
  state.charts = {};
}

function renderView() {
  const main = document.getElementById('main-content');
  switch (state.activeTab) {
    case 'dashboard':     main.innerHTML = buildDashboard();     afterDashboard(); break;
    case 'expenses':      main.innerHTML = buildExpenses();      break;
    case 'wallets':       main.innerHTML = buildWallets();       break;
    case 'subscriptions': main.innerHTML = buildSubscriptions(); break;
    case 'categories':    main.innerHTML = buildCategories();    break;
    case 'chat':          main.innerHTML = buildChat();          afterChat(); break;
  }
}

async function changeMonth(val) {
  state.currentMonth = val;
  await loadData();
  renderView();
}

// ---- Helpers ----

const fmt = n => (n || 0).toLocaleString('th-TH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const pct = (spent, budget) => budget ? Math.min(100, Math.round(spent / budget * 100)) : 0;
const walletOf = id => state.wallets.find(w => w.id === id);
const catOf = id => state.categories.find(c => c.id === id);

function walletTag(wallet) {
  if (!wallet) return '';
  return `<span class="wallet-tag" style="background:${wallet.color}22;color:${wallet.color}">${wallet.icon} ${wallet.name}</span>`;
}

// ---- Dashboard ----

function buildDashboard() {
  const d = state.dashboard;
  if (!d) return '<p class="loading">Loading…</p>';
  const today = new Date().toISOString().slice(0, 10);

  return `
    <div class="today-card">
      <div class="today-card-info">
        <h2>Today · ${today}</h2>
        <div class="today-amount">฿${fmt(d.today_spent)}</div>
        <div class="today-sub">${d.today_count} transaction${d.today_count !== 1 ? 's' : ''} today</div>
      </div>
      <div class="today-actions">
        <button class="btn" onclick="showAddExpense('planned')">+ Planned</button>
        <button class="btn" onclick="showAddExpense('unexpected')">⚡ Unexpected</button>
      </div>
    </div>

    <div class="page-header">
      <h1>Dashboard</h1>
      <input type="month" value="${state.currentMonth}" onchange="changeMonth(this.value)" class="month-picker">
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Budget</div>
        <div class="stat-value">฿${fmt(d.total_budget)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Spent</div>
        <div class="stat-value danger">฿${fmt(d.total_spent)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Remaining</div>
        <div class="stat-value ${d.total_remaining >= 0 ? 'success' : 'danger'}">฿${fmt(d.total_remaining)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Daily Avg</div>
        <div class="stat-value">฿${fmt(d.daily_average)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Subscriptions</div>
        <div class="stat-value warning">฿${fmt(d.subscription_total)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Unexpected</div>
        <div class="stat-value">${d.unexpected_count} events</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Wallet Progress</h2>
        ${d.wallet_breakdown.map(wb => `
          <div class="wallet-progress">
            <div class="wallet-progress-header">
              <span>${wb.wallet.icon} ${wb.wallet.name}</span>
              <span>฿${fmt(wb.spent)} / ฿${fmt(wb.budget)}</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" style="width:${pct(wb.spent, wb.budget)}%; background:${wb.wallet.color}"></div>
            </div>
            <div class="wallet-progress-footer">
              <span class="${wb.remaining >= 0 ? 'success' : 'danger'}">฿${fmt(wb.remaining)} left</span>
              <span>${pct(wb.spent, wb.budget)}%</span>
            </div>
          </div>
        `).join('')}
      </div>

      <div class="card">
        <h2>Spending by Wallet</h2>
        <canvas id="walletChart"></canvas>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Daily Spending <span class="badge">${state.currentMonth}</span></h2>
        <canvas id="dailyChart"></canvas>
      </div>

      <div class="card">
        <h2>Active Subscriptions <span class="badge">฿${fmt(d.subscription_total)}/mo</span></h2>
        ${d.active_subscriptions.length ? d.active_subscriptions.map(s => {
          const w = walletOf(s.wallet_id);
          return `
          <div class="list-item">
            <div>
              <div class="item-name">${s.name}</div>
              <div class="item-sub">Day ${s.billing_day} · ${walletTag(w)}</div>
            </div>
            <div class="item-amount">฿${fmt(s.amount)}</div>
          </div>`;
        }).join('') : '<p class="empty">No subscriptions</p>'}
      </div>
    </div>

    <div class="card">
      <h2>Recent Expenses</h2>
      ${d.recent_expenses.length ? d.recent_expenses.map(e => {
        const cat = catOf(e.category_id);
        const w = walletOf(e.wallet_id);
        return `
        <div class="list-item">
          <div>
            <div class="item-name">${e.description} ${e.type === 'unexpected' ? '<span class="tag-unexpected">⚡ unexpected</span>' : ''}</div>
            <div class="item-sub">${e.date} · ${cat?.name || '—'} · ${walletTag(w)}</div>
          </div>
          <div class="item-amount">฿${fmt(e.amount)}</div>
        </div>`;
      }).join('') : '<p class="empty">No expenses this month</p>'}
    </div>
  `;
}

function afterDashboard() {
  const d = state.dashboard;
  if (!d || !window.Chart) return;

  const walletCtx = document.getElementById('walletChart');
  if (walletCtx) {
    const hasData = d.wallet_breakdown.some(wb => wb.spent > 0);
    state.charts.wallet = new Chart(walletCtx, {
      type: 'doughnut',
      data: {
        labels: d.wallet_breakdown.map(wb => wb.wallet.name),
        datasets: [{
          data: hasData ? d.wallet_breakdown.map(wb => wb.spent) : d.wallet_breakdown.map(wb => wb.budget),
          backgroundColor: d.wallet_breakdown.map(wb => wb.wallet.color + (hasData ? 'dd' : '44')),
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom', labels: { font: { size: 12 } } } },
      },
    });
  }

  const dailyCtx = document.getElementById('dailyChart');
  if (dailyCtx && d.daily_chart.length) {
    state.charts.daily = new Chart(dailyCtx, {
      type: 'bar',
      data: {
        labels: d.daily_chart.map(x => x.date.slice(8)),
        datasets: [{
          label: 'Daily Spend (฿)',
          data: d.daily_chart.map(x => x.amount),
          backgroundColor: '#6366f144',
          borderColor: '#6366f1',
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => '฿' + v.toLocaleString() } },
        },
      },
    });
  }
}

// ---- Expenses ----

function buildExpenses() {
  const sorted = [...state.expenses].sort((a, b) => b.date.localeCompare(a.date));
  return `
    <div class="page-header">
      <h1>Expenses</h1>
      <div class="header-actions">
        <input type="month" value="${state.currentMonth}" onchange="changeMonth(this.value)" class="month-picker">
        <button class="btn btn-secondary" onclick="showAddExpense('planned')">+ Planned</button>
        <button class="btn btn-primary" onclick="showAddExpense('unexpected')">⚡ Unexpected</button>
      </div>
    </div>
    <div class="card" style="overflow-x:auto">
      <table class="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Category</th>
            <th>Wallet</th>
            <th>Type</th>
            <th style="text-align:right">Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${sorted.length === 0 ? '<tr><td colspan="7" class="empty">No expenses this month</td></tr>' :
            sorted.map(e => {
              const cat = catOf(e.category_id);
              const w = walletOf(e.wallet_id);
              return `
              <tr>
                <td>${e.date}</td>
                <td>${e.description}</td>
                <td>${cat?.name || '—'}</td>
                <td>${walletTag(w)}</td>
                <td><span class="type-tag type-${e.type}">${e.type}</span></td>
                <td class="amount">฿${fmt(e.amount)}</td>
                <td>
                  <button class="btn-icon" title="Edit" onclick="editExpense('${e.id}')">✏️</button>
                  <button class="btn-icon" title="Delete" onclick="deleteExpense('${e.id}')">🗑️</button>
                </td>
              </tr>`;
            }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function showAddExpense(type) {
  const walletOpts = state.wallets.map(w =>
    `<option value="${w.id}">${w.icon} ${w.name}</option>`).join('');
  const catOpts = buildCatOptions();
  const today = new Date().toISOString().slice(0, 10);

  showModal(`
    <h2>${type === 'unexpected' ? '⚡ Unexpected Activity' : '+ Add Planned Expense'}</h2>
    <form id="expense-form" onsubmit="submitExpense(event, null, '${type}')">
      <div class="form-group">
        <label>Date</label>
        <input type="date" name="date" value="${today}" required>
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" name="description" placeholder="e.g. Starbucks latte" required autofocus>
      </div>
      <div class="form-group">
        <label>Amount (฿)</label>
        <input type="number" name="amount" placeholder="0" min="0" step="1" required>
      </div>
      <div class="form-group">
        <label>Wallet</label>
        <select name="wallet_id" required onchange="onWalletChange(this)">
          <option value="">— Select wallet —</option>
          ${walletOpts}
        </select>
      </div>
      <div class="form-group">
        <label>Category</label>
        <select name="category_id" id="cat-select" required>
          <option value="">— Select category —</option>
          ${catOpts}
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  `);
}

function onWalletChange(sel) {
  const walletId = sel.value;
  const catSel = document.getElementById('cat-select');
  if (!catSel) return;
  catSel.innerHTML = '<option value="">— Select category —</option>' + buildCatOptions(walletId);
}

function buildCatOptions(walletId) {
  return state.categories
    .filter(c => !walletId || c.wallet_id === walletId)
    .map(c => {
      const w = walletOf(c.wallet_id);
      const suffix = walletId ? '' : ` (${w?.name || ''})`;
      return `<option value="${c.id}">${c.name}${suffix}</option>`;
    }).join('');
}

async function submitExpense(event, id, type) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  data.amount = parseFloat(data.amount);
  if (!type) type = 'planned';
  data.type = type;
  try {
    if (id) {
      await api.put(`/expenses/${id}`, data);
    } else {
      await api.post('/expenses', data);
    }
    closeModal();
    await loadData();
    renderView();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

function editExpense(id) {
  const e = state.expenses.find(x => x.id === id);
  if (!e) return;
  const walletOpts = state.wallets.map(w =>
    `<option value="${w.id}" ${w.id === e.wallet_id ? 'selected' : ''}>${w.icon} ${w.name}</option>`).join('');
  const catOpts = state.categories.map(c => {
    const w = walletOf(c.wallet_id);
    return `<option value="${c.id}" ${c.id === e.category_id ? 'selected' : ''}>${c.name} (${w?.name || ''})</option>`;
  }).join('');

  showModal(`
    <h2>Edit Expense</h2>
    <form id="expense-form" onsubmit="submitExpense(event, '${id}', '${e.type}')">
      <div class="form-group">
        <label>Date</label>
        <input type="date" name="date" value="${e.date}" required>
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" name="description" value="${e.description}" required autofocus>
      </div>
      <div class="form-group">
        <label>Amount (฿)</label>
        <input type="number" name="amount" value="${e.amount}" min="0" step="1" required>
      </div>
      <div class="form-group">
        <label>Wallet</label>
        <select name="wallet_id" required>${walletOpts}</select>
      </div>
      <div class="form-group">
        <label>Category</label>
        <select name="category_id" required>${catOpts}</select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Update</button>
      </div>
    </form>
  `);
}

async function deleteExpense(id) {
  if (!confirm('Delete this expense?')) return;
  await api.del(`/expenses/${id}`);
  await loadData();
  renderView();
}

// ---- Wallets ----

function buildWallets() {
  return `
    <div class="page-header">
      <h1>Wallets</h1>
      <div class="header-actions">
        <input type="month" value="${state.currentMonth}" onchange="changeMonth(this.value)" class="month-picker">
        <button class="btn btn-primary" onclick="showWalletForm()">+ Add Wallet</button>
      </div>
    </div>
    <div class="wallet-grid">
      ${state.wallets.map(w => {
        const wb = state.dashboard?.wallet_breakdown?.find(x => x.wallet.id === w.id);
        const spent = wb?.spent || 0;
        const p = pct(spent, w.budget);
        return `
        <div class="wallet-card" style="border-top:4px solid ${w.color}">
          <div class="wallet-card-header">
            <span class="wallet-icon">${w.icon}</span>
            <div class="wallet-card-actions">
              <button class="btn-icon" onclick="showWalletForm('${w.id}')">✏️</button>
              <button class="btn-icon" onclick="deleteWallet('${w.id}')">🗑️</button>
            </div>
          </div>
          <h3>${w.name}</h3>
          <div class="wallet-budget">Monthly Budget: ฿${fmt(w.budget)}</div>
          <div class="progress-bar mt-1">
            <div class="progress-fill" style="width:${p}%; background:${w.color}"></div>
          </div>
          <div class="wallet-stats">
            <span>Spent ฿${fmt(spent)}</span>
            <span class="${wb?.remaining >= 0 ? 'success' : 'danger'}">฿${fmt(wb?.remaining || w.budget)} left</span>
          </div>
        </div>`;
      }).join('')}
    </div>
  `;
}

function showWalletForm(id) {
  const w = id ? state.wallets.find(x => x.id === id) : null;
  showModal(`
    <h2>${w ? 'Edit Wallet' : 'Add Wallet'}</h2>
    <form id="wallet-form" onsubmit="submitWallet(event, ${id ? `'${id}'` : 'null'})">
      <div class="form-group">
        <label>Name</label>
        <input type="text" name="name" value="${w?.name || ''}" placeholder="e.g. Food & Dining" required autofocus>
      </div>
      <div class="form-group">
        <label>Monthly Budget (฿)</label>
        <input type="number" name="budget" value="${w?.budget || ''}" placeholder="5000" min="0" step="100" required>
      </div>
      <div class="form-group">
        <label>Icon (emoji)</label>
        <input type="text" name="icon" value="${w?.icon || '💰'}" maxlength="4">
      </div>
      <div class="form-group">
        <label>Color</label>
        <input type="color" name="color" value="${w?.color || '#6366f1'}">
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">${w ? 'Update' : 'Create'}</button>
      </div>
    </form>
  `);
}

async function submitWallet(event, id) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  data.budget = parseFloat(data.budget);
  try {
    if (id) await api.put(`/wallets/${id}`, data);
    else await api.post('/wallets', data);
    closeModal();
    await loadData();
    renderView();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function deleteWallet(id) {
  if (!confirm('Delete wallet? Expenses assigned to it will remain.')) return;
  await api.del(`/wallets/${id}`);
  await loadData();
  renderView();
}

// ---- Subscriptions ----

function buildSubscriptions() {
  const active = state.subscriptions.filter(s => s.active);
  const monthly = active.reduce((a, s) => a + s.amount, 0);
  return `
    <div class="page-header">
      <h1>Subscriptions</h1>
      <button class="btn btn-primary" onclick="showSubForm()">+ Add Subscription</button>
    </div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Monthly</div>
        <div class="stat-value warning">฿${fmt(monthly)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Annual</div>
        <div class="stat-value">฿${fmt(monthly * 12)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Active</div>
        <div class="stat-value">${active.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Paused</div>
        <div class="stat-value">${state.subscriptions.length - active.length}</div>
      </div>
    </div>
    <div class="card">
      ${state.subscriptions.length ? state.subscriptions.map(s => {
        const w = walletOf(s.wallet_id);
        return `
        <div class="list-item ${!s.active ? 'inactive' : ''}">
          <div>
            <div class="item-name">${s.name} ${!s.active ? '<span class="tag-inactive">paused</span>' : ''}</div>
            <div class="item-sub">Bills day ${s.billing_day} · ${walletTag(w)}</div>
          </div>
          <div class="item-right">
            <span class="item-amount">฿${fmt(s.amount)}/mo</span>
            <button class="btn-icon" title="${s.active ? 'Pause' : 'Resume'}" onclick="toggleSub('${s.id}', ${!s.active})">${s.active ? '⏸️' : '▶️'}</button>
            <button class="btn-icon" onclick="showSubForm('${s.id}')">✏️</button>
            <button class="btn-icon" onclick="deleteSub('${s.id}')">🗑️</button>
          </div>
        </div>`;
      }).join('') : '<p class="empty">No subscriptions yet</p>'}
    </div>
  `;
}

function showSubForm(id) {
  const s = id ? state.subscriptions.find(x => x.id === id) : null;
  const walletOpts = state.wallets.map(w =>
    `<option value="${w.id}" ${s?.wallet_id === w.id ? 'selected' : ''}>${w.icon} ${w.name}</option>`).join('');
  showModal(`
    <h2>${s ? 'Edit Subscription' : 'Add Subscription'}</h2>
    <form id="sub-form" onsubmit="submitSub(event, ${id ? `'${id}'` : 'null'})">
      <div class="form-group">
        <label>Service Name</label>
        <input type="text" name="name" value="${s?.name || ''}" placeholder="Netflix, Spotify…" required autofocus>
      </div>
      <div class="form-group">
        <label>Amount (฿/month)</label>
        <input type="number" name="amount" value="${s?.amount || ''}" placeholder="199" min="0" step="1" required>
      </div>
      <div class="form-group">
        <label>Billing Day (1–31)</label>
        <input type="number" name="billing_day" value="${s?.billing_day || 1}" min="1" max="31" required>
      </div>
      <div class="form-group">
        <label>Wallet</label>
        <select name="wallet_id" required>
          <option value="">— Select wallet —</option>
          ${walletOpts}
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">${s ? 'Update' : 'Add'}</button>
      </div>
    </form>
  `);
}

async function submitSub(event, id) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  data.amount = parseFloat(data.amount);
  data.billing_day = parseInt(data.billing_day);
  data.active = id ? (state.subscriptions.find(s => s.id === id)?.active ?? true) : true;
  try {
    if (id) await api.put(`/subscriptions/${id}`, data);
    else await api.post('/subscriptions', data);
    closeModal();
    await loadData();
    renderView();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function toggleSub(id, active) {
  const s = state.subscriptions.find(x => x.id === id);
  if (!s) return;
  await api.put(`/subscriptions/${id}`, { ...s, active });
  await loadData();
  renderView();
}

async function deleteSub(id) {
  if (!confirm('Delete subscription?')) return;
  await api.del(`/subscriptions/${id}`);
  await loadData();
  renderView();
}

// ---- Categories ----

function buildCategories() {
  const typeColor = { daily: '#10b981', subscription: '#6366f1', unexpected: '#f59e0b' };
  return `
    <div class="page-header">
      <h1>Categories</h1>
      <button class="btn btn-primary" onclick="showCatForm()">+ Add Category</button>
    </div>
    <div class="card">
      ${state.categories.length ? state.categories.map(c => {
        const w = walletOf(c.wallet_id);
        const tc = typeColor[c.type] || '#888';
        return `
        <div class="list-item">
          <div>
            <div class="item-name">${c.name}</div>
            <div class="item-sub">
              ${walletTag(w)}
              <span class="type-tag" style="background:${tc}22;color:${tc}">${c.type}</span>
            </div>
          </div>
          <div>
            <button class="btn-icon" onclick="showCatForm('${c.id}')">✏️</button>
            <button class="btn-icon" onclick="deleteCat('${c.id}')">🗑️</button>
          </div>
        </div>`;
      }).join('') : '<p class="empty">No categories yet</p>'}
    </div>
  `;
}

function showCatForm(id) {
  const c = id ? state.categories.find(x => x.id === id) : null;
  const walletOpts = state.wallets.map(w =>
    `<option value="${w.id}" ${c?.wallet_id === w.id ? 'selected' : ''}>${w.icon} ${w.name}</option>`).join('');
  showModal(`
    <h2>${c ? 'Edit Category' : 'Add Category'}</h2>
    <form id="cat-form" onsubmit="submitCat(event, ${id ? `'${id}'` : 'null'})">
      <div class="form-group">
        <label>Name</label>
        <input type="text" name="name" value="${c?.name || ''}" placeholder="e.g. Cafe, Taxi, Gym" required autofocus>
      </div>
      <div class="form-group">
        <label>Default Wallet</label>
        <select name="wallet_id" required>
          <option value="">— Select wallet —</option>
          ${walletOpts}
        </select>
      </div>
      <div class="form-group">
        <label>Type</label>
        <select name="type">
          <option value="daily" ${c?.type === 'daily' ? 'selected' : ''}>Daily</option>
          <option value="subscription" ${c?.type === 'subscription' ? 'selected' : ''}>Subscription</option>
          <option value="unexpected" ${c?.type === 'unexpected' ? 'selected' : ''}>Unexpected</option>
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">${c ? 'Update' : 'Add'}</button>
      </div>
    </form>
  `);
}

async function submitCat(event, id) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    if (id) await api.put(`/categories/${id}`, data);
    else await api.post('/categories', data);
    closeModal();
    await loadData();
    renderView();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function deleteCat(id) {
  if (!confirm('Delete category?')) return;
  await api.del(`/categories/${id}`);
  await loadData();
  renderView();
}

// ---- Chat ----

function buildChat() {
  return `
    <div class="page-header">
      <h1>AI Assistant</h1>
      <span class="badge">Qwen 7B via vLLM</span>
    </div>
    <div class="chat-container">
      <div class="chat-messages" id="chat-messages">
        <div class="chat-message assistant">
          <div class="message-bubble">Hi! I'm your finance assistant. Ask me about your spending, budgets, or tips to save money. (Requires vLLM running with <code>--profile ai</code>)</div>
        </div>
      </div>
      <div class="chat-input-area">
        <input type="text" id="chat-input" class="chat-input" placeholder="How much did I spend this month?">
        <button class="btn btn-primary" onclick="sendChat()">Send</button>
      </div>
    </div>
  `;
}

function afterChat() {
  const input = document.getElementById('chat-input');
  if (input) {
    input.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
  }
  const container = document.getElementById('chat-messages');
  if (container && state.chatHistory.length) {
    state.chatHistory.forEach(({ role, content }) => {
      container.appendChild(makeMsgEl(role, content));
    });
    container.scrollTop = container.scrollHeight;
  }
}

function makeMsgEl(role, content) {
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = content;
  div.appendChild(bubble);
  return div;
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input?.value?.trim();
  if (!msg) return;
  input.value = '';

  const container = document.getElementById('chat-messages');
  container.appendChild(makeMsgEl('user', msg));
  state.chatHistory.push({ role: 'user', content: msg });

  const loadingEl = makeMsgEl('assistant', '…');
  container.appendChild(loadingEl);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await api.post('/chat', { message: msg });
    loadingEl.querySelector('.message-bubble').textContent = res.reply;
    state.chatHistory.push({ role: 'assistant', content: res.reply });
  } catch (e) {
    loadingEl.querySelector('.message-bubble').textContent = 'Connection error. Is vLLM running?';
  }
  container.scrollTop = container.scrollHeight;
}

// ---- Modal ----

function showModal(html) {
  document.getElementById('modal-body').innerHTML = html;
  document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

function handleModalClick(e) {
  if (e.target === e.currentTarget) closeModal();
}

// ---- Init ----

document.addEventListener('DOMContentLoaded', async () => {
  await loadData();
  navigate('dashboard');
});

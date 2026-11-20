'use strict';
/* Admin dashboard pages: dashboard, menu, orders, customers, reports. */

const ADMIN_NAV = [
  ['admin-dashboard', 'dashboard.html', '📊', 'Dashboard'],
  ['admin-menu', 'manage-menu.html', '🍽️', 'Menu'],
  ['admin-orders', 'manage-orders.html', '📦', 'Orders'],
  ['admin-users', 'manage-users.html', '👥', 'Customers'],
  ['admin-reports', 'reports.html', '📈', 'Reports'],
];
const TITLES = { 'admin-dashboard': 'Dashboard', 'admin-menu': 'Menu Management', 'admin-orders': 'Order Management', 'admin-users': 'Customer Management', 'admin-reports': 'Reports' };

async function adminShell() {
  const user = await Auth.me();
  if (!user || user.role !== 'admin') {
    window.location.replace(ROOT + 'admin/login.html');
    return new Promise(() => {});
  }
  $('#admin-sidebar').className = 'admin-sidebar';
  $('#admin-sidebar').innerHTML = '<a class="brand" href="dashboard.html"><img src="' + ROOT + 'assets/images/logo.svg" alt=""><span>Smart <b>Canteen</b></span></a><nav>' +
    ADMIN_NAV.map(n => '<a href="' + n[1] + '" class="' + (PAGE === n[0] ? 'active' : '') + '"><span>' + n[2] + '</span>' + n[3] + '</a>').join('') + '</nav>' +
    '<div class="side-foot"><a class="side-btn" href="' + ROOT + 'index.html" style="display:flex;gap:.75rem;padding:.75rem .9rem;color:#c9cfdd">🌐 View website</a><button class="side-btn" id="admin-logout">🚪 Logout</button></div>';
  $('#admin-topbar').className = 'admin-topbar';
  $('#admin-topbar').innerHTML = '<div style="display:flex;align-items:center;gap:.8rem"><button class="icon-btn side-toggle" id="side-toggle" aria-label="Menu">☰</button><h1>' + esc(TITLES[PAGE]) + '</h1></div>' +
    '<div class="who"><span class="avatar">' + initial(user.name) + '</span><span>' + esc(user.name) + '</span></div>';
  document.body.insertAdjacentHTML('beforeend', '<div class="admin-scrim" id="admin-scrim"></div>');
  $('#side-toggle').addEventListener('click', () => document.body.classList.toggle('sidebar-open'));
  $('#admin-scrim').addEventListener('click', () => document.body.classList.remove('sidebar-open'));
  $('#admin-logout').addEventListener('click', () => Auth.logout());
  return user;
}
function adminPage(name, fn) { onPage(name, async () => { await adminShell(); await fn(); }); }
function fieldHTML(label, name, inner, hint) {
  return '<div class="form-group"><label for="f-' + name + '">' + label + '</label>' + inner + (hint ? '<div class="form-hint">' + hint + '</div>' : '') + '<div class="field-error" data-error-for="' + name + '"></div></div>';
}

/* ============================== dashboard ============================== */
adminPage('admin-dashboard', async () => {
  const kpis = $('#kpis'), recent = $('#recent-orders'), pop = $('#popular'), bars = $('#status-bars');
  kpis.innerHTML = loadingHTML();
  async function load() {
    try {
      const d = await Api.get('/admin/dashboard'), s = d.stats;
      const cards = [
        ['kpi-orange', '🧾', s.total_orders, 'Total orders'], ['kpi-green', '💰', money2(s.total_revenue), 'Total revenue'],
        ['kpi-blue', '👥', s.total_customers, 'Total customers'], ['kpi-purple', '🍽️', s.total_menu_items, 'Menu items'],
        ['kpi-yellow', '⏳', s.pending_orders, 'Pending orders'], ['kpi-teal', '✅', s.completed_orders, 'Completed orders'],
      ];
      kpis.innerHTML = cards.map(c => '<div class="card kpi ' + c[0] + '"><div class="stat-icon">' + c[1] + '</div><div><div class="stat-value">' + esc(c[2]) + '</div><div class="stat-label">' + c[3] + '</div></div></div>').join('');
      recent.innerHTML = d.recent_orders.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Order</th><th>Customer</th><th>Items</th><th class="num">Total</th><th>Status</th></tr></thead><tbody>' +
        d.recent_orders.map(o => '<tr><td><strong>' + esc(o.order_number) + '</strong><br><span class="muted">' + esc(fmtDateTime(o.created_at)) + '</span></td><td>' + esc(o.customer_name) + '</td><td>' + o.items.reduce((n, i) => n + i.quantity, 0) + '</td><td class="num">' + money2(o.total) + '</td><td>' + statusBadge(o.status) + '</td></tr>').join('') + '</tbody></table></div>'
        : emptyHTML('📭', 'No orders yet', 'Orders will appear here as customers place them.');
      const max = Math.max(1, ...d.popular_items.map(p => p.quantity));
      pop.innerHTML = d.popular_items.length ? '<ul class="rank-list">' + d.popular_items.map((p, i) =>
        '<li><span class="rank-no">' + (i + 1) + '</span><div><strong>' + esc(p.name) + '</strong><div class="rank-bar"><span style="width:' + (p.quantity / max * 100) + '%"></span></div></div><span class="muted">' + p.quantity + ' sold</span></li>').join('') + '</ul>'
        : emptyHTML('🍽️', 'No sales yet', '');
      const total = Math.max(1, s.total_orders);
      bars.innerHTML = Object.keys(d.status_breakdown).map(k => '<div class="row"><span>' + esc(k) + '</span><div class="track"><span style="width:' + (d.status_breakdown[k] / total * 100) + '%"></span></div><strong>' + d.status_breakdown[k] + '</strong></div>').join('');
      $('#today-line').textContent = 'Today: ' + s.today_orders + ' orders · ' + money2(s.today_revenue) + ' revenue';
    } catch (err) { kpis.innerHTML = errorHTML(err, 'retry-dash'); $('#retry-dash').addEventListener('click', load); }
  }
  await load();
});

/* ============================ menu management ============================ */
adminPage('admin-menu', async () => {
  const table = $('#menu-table'), search = $('#menu-search'), catFilter = $('#menu-cat-filter');
  let items = [], categories = [];

  async function loadCategories() {
    categories = (await Api.get('/categories')).categories;
    catFilter.innerHTML = '<option value="">All categories</option>' + categories.map(c => '<option value="' + c.id + '">' + esc(c.name) + '</option>').join('');
  }
  function render() {
    const q = search.value.trim().toLowerCase(), cat = catFilter.value;
    const shown = items.filter(i => (!cat || String(i.category_id) === cat) && (!q || (i.name + ' ' + i.category).toLowerCase().includes(q)));
    if (!shown.length) { table.innerHTML = emptyHTML('🍽️', items.length ? 'No items match' : 'No menu items yet', items.length ? 'Try a different search.' : 'Click "Add item" to create the first dish.'); return; }
    table.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr><th>Item</th><th>Category</th><th>Type</th><th class="num">Price</th><th>Available</th><th>Actions</th></tr></thead><tbody>' +
      shown.map(i => '<tr data-id="' + i.id + '"><td><div class="cell-main"><img class="thumb" src="' + esc(imgSrc(i.image_url)) + '" alt=""><div><strong>' + esc(i.name) + '</strong>' + (i.is_popular ? '<span class="badge badge-muted">🔥 popular</span>' : '') + '</div></div></td>' +
        '<td>' + esc(i.category) + '</td><td>' + (i.is_veg ? '<span class="badge badge-ok">Veg</span>' : '<span class="badge badge-no">Non-veg</span>') + '</td>' +
        '<td class="num"><strong>' + money(i.price) + '</strong></td>' +
        '<td><label class="switch"><input type="checkbox" data-toggle ' + (i.is_available ? 'checked' : '') + '><span class="track"></span></label></td>' +
        '<td><div class="actions"><button class="btn btn-outline btn-sm" data-edit>Edit</button><button class="btn btn-danger-outline btn-sm" data-delete>Delete</button></div></td></tr>').join('') + '</tbody></table></div>';
  }
  async function load() {
    table.innerHTML = loadingHTML();
    try { await loadCategories(); items = (await Api.get('/menu')).items; render(); }
    catch (err) { table.innerHTML = errorHTML(err, 'retry-menu'); $('#retry-menu').addEventListener('click', load); }
  }

  function itemForm(item) {
    const isNew = !item; item = item || { is_veg: true, is_available: true, is_popular: false, prep_time: 10 };
    const form = '<form id="item-form" novalidate><div class="form-alert hidden"></div>' +
      fieldHTML('Name', 'name', '<input class="input" id="f-name" name="name" maxlength="80" value="' + esc(item.name || '') + '" required>') +
      fieldHTML('Description', 'description', '<textarea class="input" id="f-description" name="description" maxlength="300">' + esc(item.description || '') + '</textarea>') +
      '<div class="form-row">' + fieldHTML('Price (₹)', 'price', '<input class="input" id="f-price" name="price" type="number" step="0.01" min="0.01" max="10000" value="' + (item.price !== undefined ? item.price : '') + '" required>') +
      fieldHTML('Category', 'category_id', '<select class="input" id="f-category_id" name="category_id">' + categories.map(c => '<option value="' + c.id + '" ' + (c.id === item.category_id ? 'selected' : '') + '>' + esc(c.name) + '</option>').join('') + '</select>') + '</div>' +
      '<div class="form-row">' + fieldHTML('Preparation time (min)', 'prep_time', '<input class="input" id="f-prep_time" name="prep_time" type="number" min="1" max="120" value="' + item.prep_time + '">') +
      fieldHTML('Type', 'is_veg', '<select class="input" id="f-is_veg" name="is_veg"><option value="1" ' + (item.is_veg ? 'selected' : '') + '>Vegetarian</option><option value="0" ' + (!item.is_veg ? 'selected' : '') + '>Non-vegetarian</option></select>') + '</div>' +
      '<div class="check-row"><label class="switch"><input type="checkbox" name="is_available" ' + (item.is_available ? 'checked' : '') + '><span class="track"></span> Available</label>' +
      '<label class="switch"><input type="checkbox" name="is_popular" ' + (item.is_popular ? 'checked' : '') + '><span class="track"></span> Mark as popular</label></div>' +
      fieldHTML('Food image', 'image', '<input class="input" id="f-image" name="image" type="file" accept="image/png,image/jpeg,image/gif,image/webp">', 'PNG, JPG, GIF or WEBP, max 2 MB.') +
      '<img class="image-preview" id="img-preview" alt="Preview" src="' + esc(imgSrc(item.image_url)) + '">' +
      (!isNew && item.image_url && item.image_url.indexOf('/uploads/') === 0 ? '<label class="switch" style="margin-top:.6rem"><input type="checkbox" name="remove_image"><span class="track"></span> Remove current image</label>' : '') +
      '</form>';
    const m = openModal({ title: isNew ? 'Add menu item' : 'Edit menu item', body: form, footer: '<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="save-item">' + (isNew ? 'Add item' : 'Save changes') + '</button>' });
    const f = $('#item-form', m.el);
    f.elements.image.addEventListener('change', () => { const file = f.elements.image.files[0]; if (file) $('#img-preview', m.el).src = URL.createObjectURL(file); });
    const submit = async () => {
      clearFieldErrors(f);
      const fd = new FormData();
      ['name', 'description', 'price', 'category_id', 'prep_time', 'is_veg'].forEach(k => fd.append(k, f.elements[k].value));
      fd.append('is_available', f.elements.is_available.checked ? '1' : '0');
      fd.append('is_popular', f.elements.is_popular.checked ? '1' : '0');
      if (f.elements.remove_image && f.elements.remove_image.checked) fd.append('remove_image', '1');
      if (f.elements.image.files[0]) fd.append('image', f.elements.image.files[0]);
      const btn = $('#save-item', m.el);
      setLoading(btn, true, 'Saving…');
      try {
        await (isNew ? Api.post('/menu', fd) : Api.put('/menu/' + item.id, fd));
        m.close(); toast(isNew ? 'Menu item added.' : 'Menu item updated.', 'success'); load();
      } catch (err) { setLoading(btn, false); showFieldErrors(f, err); }
    };
    $('#save-item', m.el).addEventListener('click', submit);
    f.addEventListener('submit', e => { e.preventDefault(); submit(); });
  }

  function categoryManager() {
    const m = openModal({ title: 'Manage categories', body: '<div id="cat-body"></div>' });
    const body = $('#cat-body', m.el);
    function draw() {
      body.innerHTML = '<div class="cat-list">' + categories.map(c => '<div class="cat-row" data-id="' + c.id + '"><input class="input" value="' + esc(c.name) + '" maxlength="40" aria-label="Category name"><span class="muted" style="min-width:60px">' + c.item_count + ' items</span><button class="btn btn-outline btn-sm" data-save>Save</button><button class="btn btn-danger-outline btn-sm" data-del>Delete</button></div>').join('') + '</div>' +
        '<hr style="border:0;border-top:1px solid var(--border);margin:1.2rem 0"><div class="cat-row"><input class="input" id="new-cat" placeholder="New category name" maxlength="40"><button class="btn btn-primary btn-sm" id="add-cat">Add</button></div>';
    }
    draw();
    body.addEventListener('click', async e => {
      const row = e.target.closest('.cat-row[data-id]');
      try {
        if (e.target.id === 'add-cat') {
          const name = $('#new-cat', body).value.trim(); if (!name) return toast('Enter a category name.', 'error');
          await Api.post('/categories', { name: name }); toast('Category added.', 'success');
        } else if (e.target.matches('[data-save]')) {
          await Api.put('/categories/' + row.dataset.id, { name: $('input', row).value.trim() }); toast('Category renamed.', 'success');
        } else if (e.target.matches('[data-del]')) {
          if (!await confirmDialog('Delete category', 'Delete this category? It must not contain any items.', 'Delete', true)) return;
          await Api.del('/categories/' + row.dataset.id); toast('Category deleted.', 'success');
        } else return;
        await loadCategories(); items = (await Api.get('/menu')).items; draw(); render();
      } catch (err) { toast(err.message, 'error'); }
    });
  }

  table.addEventListener('click', async e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr) return;
    const item = items.find(i => i.id === Number(tr.dataset.id));
    if (e.target.matches('[data-edit]')) itemForm(item);
    if (e.target.matches('[data-delete]')) {
      if (!await confirmDialog('Delete item', 'Delete "' + item.name + '"? Past orders keep their history.', 'Delete', true)) return;
      try { await Api.del('/menu/' + item.id); toast('Item deleted.', 'success'); load(); } catch (err) { toast(err.message, 'error'); }
    }
  });
  table.addEventListener('change', async e => {
    if (!e.target.matches('[data-toggle]')) return;
    const item = items.find(i => i.id === Number(e.target.closest('tr').dataset.id));
    try { await Api.put('/menu/' + item.id, { is_available: e.target.checked }); item.is_available = e.target.checked; toast(item.name + (item.is_available ? ' is now available' : ' marked unavailable'), 'success'); }
    catch (err) { e.target.checked = !e.target.checked; toast(err.message, 'error'); }
  });
  search.addEventListener('input', debounce(render, 150));
  catFilter.addEventListener('change', render);
  $('#add-item').addEventListener('click', () => categories.length ? itemForm(null) : toast('Create a category first.', 'error'));
  $('#manage-cats').addEventListener('click', categoryManager);
  await load();
});

/* =========================== order management =========================== */
adminPage('admin-orders', async () => {
  const table = $('#orders-table'), search = $('#order-search'), statusSel = $('#order-status');
  const STATUSES = ['Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Completed', 'Cancelled'];
  statusSel.innerHTML = '<option value="">All statuses</option>' + STATUSES.map(s => '<option>' + s + '</option>').join('');
  let orders = [], modal = null;

  async function load(silent) {
    if (!silent) table.innerHTML = loadingHTML();
    const qs = new URLSearchParams();
    if (search.value.trim()) qs.set('q', search.value.trim());
    if (statusSel.value) qs.set('status', statusSel.value);
    try {
      orders = (await Api.get('/orders?' + qs.toString())).orders;
      $('#order-count').textContent = orders.length + (orders.length === 1 ? ' order' : ' orders');
      if (!orders.length) { table.innerHTML = emptyHTML('📭', 'No orders found', 'Try changing the search or status filter.'); return; }
      table.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr><th>Order</th><th>Customer</th><th>Items</th><th class="num">Total</th><th>Payment</th><th>Status</th><th>Actions</th></tr></thead><tbody>' +
        orders.map(o => '<tr data-id="' + o.id + '"><td><strong>' + esc(o.order_number) + '</strong><br><span class="muted">' + esc(fmtDateTime(o.created_at)) + '</span></td>' +
          '<td>' + esc(o.customer_name) + '<br><span class="muted">' + esc(o.student_id) + ' · ' + esc(o.order_type) + '</span></td>' +
          '<td>' + o.items.map(i => esc(i.quantity + '× ' + i.name)).join('<br>') + '</td><td class="num"><strong>' + money2(o.total) + '</strong></td>' +
          '<td>' + esc(o.payment_method) + '<br><span class="muted">' + esc(o.payment_status) + '</span></td><td>' + statusBadge(o.status) + '</td>' +
          '<td><button class="btn btn-outline btn-sm" data-view>View / Update</button></td></tr>').join('') + '</tbody></table></div>';
    } catch (err) { if (!silent) { table.innerHTML = errorHTML(err, 'retry-orders'); $('#retry-orders').addEventListener('click', () => load()); } }
  }

  async function showOrder(id) {
    let o;
    try { o = (await Api.get('/orders/' + id)).order; } catch (err) { return toast(err.message, 'error'); }
    const options = o.next_statuses.filter(s => s !== 'Cancelled');
    const controls = o.next_statuses.length
      ? '<div class="toolbar" style="margin:1.2rem 0 0"><select class="input" id="new-status" aria-label="New status">' + o.next_statuses.map(s => '<option>' + s + '</option>').join('') + '</select>' +
        '<button class="btn btn-primary" id="apply-status">Update status</button>' +
        (o.next_statuses.includes('Cancelled') ? '<button class="btn btn-danger-outline" id="cancel-order">Cancel order</button>' : '') + '</div>'
      : '<p class="muted" style="margin-top:1rem">This order is ' + esc(o.status.toLowerCase()) + ' and can no longer be changed.</p>';
    if (modal) modal.close();
    modal = openModal({ title: 'Order ' + o.order_number, wide: true, body: orderDetailHTML(o) + controls, onClose: () => { modal = null; } });
    // default to the next "forward" step instead of Cancelled
    const sel = $('#new-status', modal.el); if (sel && options.length) sel.value = options[0];
    const apply = async status => {
      try { await Api.put('/orders/' + o.id + '/status', { status: status }); toast('Order ' + o.order_number + ' → ' + status, 'success'); await load(true); showOrder(o.id); }
      catch (err) { toast(err.message, 'error'); }
    };
    if (sel) {
      $('#apply-status', modal.el).addEventListener('click', () => apply(sel.value));
      const c = $('#cancel-order', modal.el);
      if (c) c.addEventListener('click', async () => { if (await confirmDialog('Cancel order', 'Cancel ' + o.order_number + '? The customer will see it as cancelled.', 'Cancel order', true)) apply('Cancelled'); });
    }
  }
  table.addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr && e.target.matches('[data-view]')) showOrder(Number(tr.dataset.id)); });
  search.addEventListener('input', debounce(() => load(), 300));
  statusSel.addEventListener('change', () => load());
  $('#refresh-orders').addEventListener('click', () => load());
  await load();
  setInterval(() => { if (!document.hidden && !modal) load(true); }, 20000);
});

/* ========================== customer management ========================== */
adminPage('admin-users', async () => {
  const table = $('#users-table'), search = $('#user-search');
  let users = [];
  async function load(silent) {
    if (!silent) table.innerHTML = loadingHTML();
    try {
      users = (await Api.get('/admin/customers?q=' + encodeURIComponent(search.value.trim()))).customers;
      $('#user-count').textContent = users.length + (users.length === 1 ? ' customer' : ' customers');
      if (!users.length) { table.innerHTML = emptyHTML('👥', 'No customers found', 'Registered customers will appear here.'); return; }
      table.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr><th>Customer</th><th>Student ID</th><th>Phone</th><th class="num">Orders</th><th class="num">Spent</th><th>Joined</th><th>Status</th><th>Actions</th></tr></thead><tbody>' +
        users.map(u => '<tr data-id="' + u.id + '"><td><div class="cell-main"><span class="avatar">' + initial(u.name) + '</span><div><strong>' + esc(u.name) + '</strong><span class="muted">' + esc(u.email) + '</span></div></div></td>' +
          '<td>' + esc(u.student_id || '—') + '</td><td>' + esc(u.phone || '—') + '</td><td class="num">' + u.order_count + '</td><td class="num">' + money2(u.total_spent) + '</td><td>' + esc(fmtDate(u.created_at)) + '</td>' +
          '<td>' + (u.is_active ? '<span class="badge badge-ok">Active</span>' : '<span class="badge badge-no">Disabled</span>') + '</td>' +
          '<td><div class="actions"><button class="btn btn-outline btn-sm" data-view>View</button><button class="btn btn-ghost btn-sm" data-toggle>' + (u.is_active ? 'Disable' : 'Enable') + '</button><button class="btn btn-danger-outline btn-sm" data-delete>Delete</button></div></td></tr>').join('') + '</tbody></table></div>';
    } catch (err) { if (!silent) { table.innerHTML = errorHTML(err, 'retry-users'); $('#retry-users').addEventListener('click', () => load()); } }
  }
  async function view(id) {
    try {
      const d = await Api.get('/admin/customers/' + id), c = d.customer;
      openModal({ title: c.name, wide: true, body:
        '<dl class="detail-grid"><div><dt>Email</dt><dd>' + esc(c.email) + '</dd></div><div><dt>Phone</dt><dd>' + esc(c.phone || '—') + '</dd></div>' +
        '<div><dt>Student ID</dt><dd>' + esc(c.student_id || '—') + '</dd></div><div><dt>Joined</dt><dd>' + esc(fmtDate(c.created_at)) + '</dd></div>' +
        '<div><dt>Account</dt><dd>' + (c.is_active ? 'Active' : 'Disabled') + '</dd></div><div><dt>Total spent</dt><dd>' + money2(d.total_spent) + '</dd></div></dl>' +
        '<h4>Order history (' + d.orders.length + ')</h4>' + (d.orders.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Order</th><th>Items</th><th class="num">Total</th><th>Status</th></tr></thead><tbody>' +
          d.orders.map(o => '<tr><td><strong>' + esc(o.order_number) + '</strong><br><span class="muted">' + esc(fmtDateTime(o.created_at)) + '</span></td><td>' + o.items.map(i => esc(i.quantity + '× ' + i.name)).join(', ') + '</td><td class="num">' + money2(o.total) + '</td><td>' + statusBadge(o.status) + '</td></tr>').join('') + '</tbody></table></div>' : '<p class="muted">No orders yet.</p>') });
    } catch (err) { toast(err.message, 'error'); }
  }
  table.addEventListener('click', async e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr) return;
    const u = users.find(x => x.id === Number(tr.dataset.id));
    if (e.target.matches('[data-view]')) view(u.id);
    if (e.target.matches('[data-toggle]')) {
      const enable = !u.is_active;
      if (!await confirmDialog(enable ? 'Enable account' : 'Disable account', (enable ? 'Allow ' : 'Block ') + u.name + (enable ? ' to sign in again?' : ' from signing in? They will be logged out.'), enable ? 'Enable' : 'Disable', !enable)) return;
      try { await Api.put('/admin/customers/' + u.id, { is_active: enable }); toast('Account ' + (enable ? 'enabled' : 'disabled') + '.', 'success'); load(true); } catch (err) { toast(err.message, 'error'); }
    }
    if (e.target.matches('[data-delete]')) {
      if (!await confirmDialog('Delete customer', 'Permanently delete ' + u.name + '? Customers with orders cannot be deleted.', 'Delete', true)) return;
      try { await Api.del('/admin/customers/' + u.id); toast('Customer deleted.', 'success'); load(true); } catch (err) { toast(err.message, 'error'); }
    }
  });
  search.addEventListener('input', debounce(() => load(), 300));
  await load();
});

/* ================================= reports ================================= */
adminPage('admin-reports', async () => {
  const kpis = $('#report-kpis'), chart = $('#chart'), pop = $('#report-popular');
  let data = null, mode = 'daily';
  function drawChart() {
    const rows = data[mode], max = Math.max(1, ...rows.map(r => r.revenue));
    chart.innerHTML = '<div class="bar-chart">' + rows.map(r => '<div class="bar-col" title="' + esc(r.label) + ': ' + money2(r.revenue) + ' (' + r.orders + ' orders)"><span class="val">' + (r.revenue ? money(Math.round(r.revenue)) : '') + '</span><div class="bar" style="height:' + (r.revenue / max * 78) + '%"></div></div>').join('') + '</div>' +
      '<div class="bar-labels">' + rows.map(r => '<span>' + esc(r.label) + '</span>').join('') + '</div>';
    const sum = rows.reduce((a, r) => ({ rev: a.rev + r.revenue, ord: a.ord + r.orders }), { rev: 0, ord: 0 });
    $('#chart-summary').textContent = 'Last ' + rows.length + ' ' + (mode === 'daily' ? 'days' : mode === 'weekly' ? 'weeks' : 'months') + ': ' + money2(sum.rev) + ' from ' + sum.ord + ' orders';
    $$('#chart-tabs button').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  }
  async function load() {
    kpis.innerHTML = loadingHTML();
    try {
      data = await Api.get('/admin/reports');
      const t = data.total_sales;
      kpis.innerHTML = [['kpi-green', '💰', money2(t.revenue), 'Total sales'], ['kpi-orange', '🧾', t.orders, 'Orders (not cancelled)'], ['kpi-blue', '🍽️', t.items_sold, 'Items sold'],
        ['kpi-yellow', '📅', money2(t.revenue_today), 'Revenue today'], ['kpi-purple', '🗓️', money2(t.revenue_this_week), 'Revenue this week'], ['kpi-teal', '📆', money2(t.revenue_this_month), 'Revenue this month']]
        .map(c => '<div class="card kpi ' + c[0] + '"><div class="stat-icon">' + c[1] + '</div><div><div class="stat-value">' + esc(c[2]) + '</div><div class="stat-label">' + c[3] + '</div></div></div>').join('');
      $('#report-note').textContent = data.revenue_definition + ' Average order value: ' + money2(t.average_order_value) + ' · Cancelled orders: ' + t.cancelled_orders + '.';
      drawChart();
      const max = Math.max(1, ...data.popular_items.map(p => p.quantity));
      pop.innerHTML = data.popular_items.length ? '<ul class="rank-list">' + data.popular_items.map((p, i) => '<li><span class="rank-no">' + (i + 1) + '</span><div><strong>' + esc(p.name) + '</strong><div class="rank-bar"><span style="width:' + (p.quantity / max * 100) + '%"></span></div></div><span class="muted">' + p.quantity + ' sold · ' + money(p.revenue) + '</span></li>').join('') + '</ul>' : emptyHTML('📊', 'No sales data yet', 'Popular items will appear after the first orders.');
    } catch (err) { kpis.innerHTML = errorHTML(err, 'retry-rep'); $('#retry-rep').addEventListener('click', load); }
  }
  $('#chart-tabs').addEventListener('click', e => { const b = e.target.closest('button'); if (b && data) { mode = b.dataset.mode; drawChart(); } });
  await load();
});

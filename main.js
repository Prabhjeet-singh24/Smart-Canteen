'use strict';
/* Smart Canteen - shared helpers: API client, auth state, cart, header/footer, toasts, modals. */

const ROOT = document.body.dataset.root || '';
const API_BASE = window.CANTEEN_API_BASE || '';
const PAGE = document.body.dataset.page || '';

/* ------------------------------------------------------------------ utils */
function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, ch =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}
function money(n) { return '₹' + (Number(n) || 0).toFixed(2).replace(/\.00$/, ''); }
function money2(n) { return '₹' + (Number(n) || 0).toFixed(2); }
function parseDate(s) { return s ? new Date(String(s).replace(' ', 'T')) : null; }
function fmtDateTime(s) {
  const d = parseDate(s);
  if (!d || isNaN(d)) return '—';
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtDate(s) {
  const d = parseDate(s);
  if (!d || isNaN(d)) return '—';
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function imgSrc(url) {
  if (!url) return ROOT + 'assets/images/placeholder.svg';
  if (url.indexOf('/uploads/') === 0) return API_BASE + url;
  return ROOT + url.replace(/^\/+/, '');
}
function statusClass(s) { return 'status-' + String(s).toLowerCase().replace(/\s+/g, '-'); }
function statusBadge(s) { return '<span class="status ' + statusClass(s) + '">' + esc(s) + '</span>'; }
function initial(name) { return esc((name || '?').trim().charAt(0).toUpperCase()); }
function debounce(fn, ms) { let t; return function () { const a = arguments; clearTimeout(t); t = setTimeout(() => fn.apply(null, a), ms); }; }
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
function safeNext(next) {
  // only allow simple relative page names (prevents open redirects)
  return /^[A-Za-z0-9_\-\/]+\.html(\?[A-Za-z0-9_=&\-]*)?$/.test(next || '') ? next : '';
}
const CATEGORY_EMOJI = { breakfast: '🥞', meals: '🍛', snacks: '🥟', 'fast food': '🍔', beverages: '☕', desserts: '🍨' };
function categoryEmoji(name) { return CATEGORY_EMOJI[String(name).toLowerCase()] || '🍽️'; }

document.addEventListener('error', function (e) {      // broken image -> placeholder
  const el = e.target;
  if (el && el.tagName === 'IMG' && !el.dataset.fallback) {
    el.dataset.fallback = '1';
    el.src = ROOT + 'assets/images/placeholder.svg';
  }
}, true);

/* -------------------------------------------------------------------- API */
class ApiError extends Error {
  constructor(message, status, details) { super(message); this.status = status; this.details = details || {}; }
}
async function api(method, path, body) {
  const opts = { method: method, credentials: 'include', headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(API_BASE + '/api' + path, opts); }
  catch (err) { throw new ApiError('Cannot reach the server. Please make sure the backend is running.', 0); }
  let data = null;
  try { data = await res.json(); } catch (err) { /* non-JSON body */ }
  if (!res.ok) throw new ApiError((data && data.error) || 'Request failed (' + res.status + ').', res.status, data && data.details);
  return data;
}
const Api = {
  get: p => api('GET', p),
  post: (p, b) => api('POST', p, b === undefined ? {} : b),
  put: (p, b) => api('PUT', p, b === undefined ? {} : b),
  del: p => api('DELETE', p),
};

/* ------------------------------------------------------------- UI helpers */
function toast(message, type) {
  const root = $('#toast-root');
  if (!root) return;
  const el = document.createElement('div');
  el.className = 'toast ' + (type || 'info');
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => { el.classList.add('leaving'); setTimeout(() => el.remove(), 260); }, type === 'error' ? 5500 : 3200);
}
function loadingHTML(text) { return '<div class="loading-block"><div class="spinner"></div>' + esc(text || 'Loading…') + '</div>'; }
function emptyHTML(icon, title, text, actionHtml) {
  return '<div class="empty-state"><div class="big">' + icon + '</div><h3>' + esc(title) + '</h3><p>' + esc(text || '') + '</p>' + (actionHtml || '') + '</div>';
}
function errorHTML(err, retryId) {
  return '<div class="empty-state"><div class="big">⚠️</div><h3>Something went wrong</h3><p>' + esc(err.message) + '</p>' +
    (retryId ? '<button class="btn btn-outline" id="' + retryId + '">Try again</button>' : '') + '</div>';
}
function setLoading(btn, on, label) {
  if (!btn) return;
  if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> ' + esc(label || 'Please wait…'); }
  else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
}
function clearFieldErrors(form) {
  $$('.field-error', form).forEach(e => { e.textContent = ''; });
  $$('.input.invalid', form).forEach(e => e.classList.remove('invalid'));
  const alert = $('.form-alert', form); if (alert) alert.classList.add('hidden');
}
function showFieldErrors(form, err) {
  const details = (err && err.details) || {};
  let shown = false;
  Object.keys(details).forEach(name => {
    const slot = $('[data-error-for="' + name + '"]', form), input = form.elements[name];
    if (slot) { slot.textContent = details[name]; shown = true; }
    if (input && input.classList) input.classList.add('invalid');
  });
  const alert = $('.form-alert', form);
  if (alert) {
    alert.textContent = err.message; alert.className = 'form-alert error';
  } else if (!shown) toast(err.message, 'error');
}
function formValues(form) {
  const out = {};
  Array.from(form.elements).forEach(el => {
    if (!el.name || el.disabled) return;
    if ((el.type === 'radio') && !el.checked) return;
    out[el.name] = el.type === 'checkbox' ? el.checked : el.value;
  });
  return out;
}
function openModal(opts) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = '<div class="modal ' + (opts.wide ? 'wide' : '') + '" role="dialog" aria-modal="true" aria-label="' + esc(opts.title) + '">' +
    '<div class="modal-head"><h3>' + esc(opts.title) + '</h3><button class="icon-btn" data-close aria-label="Close">✕</button></div>' +
    '<div class="modal-body">' + (opts.body || '') + '</div>' + (opts.footer ? '<div class="modal-foot">' + opts.footer + '</div>' : '') + '</div>';
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  const onKey = e => { if (e.key === 'Escape') close(); };
  function close() {
    document.removeEventListener('keydown', onKey);
    overlay.remove();
    if (!$('.modal-overlay')) document.body.style.overflow = '';
    if (opts.onClose) opts.onClose();
  }
  overlay.addEventListener('mousedown', e => { if (e.target === overlay) close(); });
  overlay.addEventListener('click', e => { if (e.target.closest('[data-close]')) close(); });
  document.addEventListener('keydown', onKey);
  const first = $('input:not([type=hidden]), select, textarea, button.btn', overlay); if (first) first.focus();
  return { el: overlay, close: close, body: $('.modal-body', overlay) };
}
function confirmDialog(title, message, confirmLabel, danger) {
  return new Promise(resolve => {
    let done = false;
    const m = openModal({
      title: title, body: '<p>' + esc(message) + '</p>',
      footer: '<button class="btn btn-ghost" data-close>Cancel</button><button class="btn ' + (danger ? 'btn-danger' : 'btn-primary') + '" id="cd-ok">' + esc(confirmLabel || 'Confirm') + '</button>',
      onClose: () => { if (!done) resolve(false); },
    });
    $('#cd-ok', m.el).addEventListener('click', () => { done = true; m.close(); resolve(true); });
  });
}

/* ------------------------------------------------------------------- Auth */
const Auth = {
  user: undefined, offline: false,
  async me(force) {
    if (this.user !== undefined && !force) return this.user;
    try { this.user = (await Api.get('/profile')).user; this.offline = false; }
    catch (err) { this.user = null; this.offline = err.status === 0; }
    return this.user;
  },
  async logout() {
    try { await Api.post('/logout'); } catch (e) { /* ignore */ }
    this.user = null; Cart.clear();
    window.location.href = ROOT + (PAGE.indexOf('admin') === 0 ? 'admin/login.html' : 'login.html');
  },
};
async function requireLogin() {
  const user = await Auth.me();
  if (!user) {
    const here = window.location.pathname.split('/').pop() + window.location.search;
    window.location.replace(ROOT + 'login.html?next=' + encodeURIComponent(here));
    return new Promise(() => {});          // stop the page from continuing
  }
  if (user.role === 'admin') { window.location.replace(ROOT + 'admin/dashboard.html'); return new Promise(() => {}); }
  return user;
}

/* ------------------------------------------------------------------- Cart */
const Cart = {
  KEY: 'smart_canteen_cart',
  read() {
    try { const v = JSON.parse(localStorage.getItem(this.KEY) || '[]'); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  },
  write(items) { try { localStorage.setItem(this.KEY, JSON.stringify(items)); } catch (e) { /* storage disabled */ } this.updateBadge(); },
  count() { return this.read().reduce((n, i) => n + i.qty, 0); },
  qty(id) { const it = this.read().find(i => i.id === id); return it ? it.qty : 0; },
  add(item, qty) {
    const items = this.read(), found = items.find(i => i.id === item.id);
    if (found) found.qty = Math.min(20, found.qty + (qty || 1));
    else items.push({ id: item.id, name: item.name, price: item.price, image_url: item.image_url, is_veg: item.is_veg, qty: Math.min(20, qty || 1) });
    this.write(items);
  },
  setQty(id, qty) {
    let items = this.read();
    if (qty <= 0) items = items.filter(i => i.id !== id);
    else items.forEach(i => { if (i.id === id) i.qty = Math.min(20, qty); });
    this.write(items);
  },
  remove(id) { this.write(this.read().filter(i => i.id !== id)); },
  clear() { this.write([]); },
  totals(items, taxRate) {
    const subtotal = Math.round(items.reduce((s, i) => s + i.price * i.qty, 0) * 100) / 100;
    const tax = Math.round(subtotal * taxRate * 100) / 100;
    return { subtotal: subtotal, tax: tax, total: Math.round((subtotal + tax) * 100) / 100 };
  },
  updateBadge() {
    const n = this.count();
    $$('.cart-badge').forEach(b => { b.textContent = n; b.classList.toggle('empty', n === 0); });
  },
};

/* --------------------------------------------------------- header / footer */
function renderHeader(user) {
  const host = $('#site-header');
  if (!host) return;
  const isAdmin = user && user.role === 'admin';
  const link = (page, href, label) => '<li><a class="nav-link ' + (PAGE === page ? 'active' : '') + '" href="' + ROOT + href + '">' + label + '</a></li>';
  let links = link('home', 'index.html', 'Home') + link('menu', 'menu.html', 'Menu');
  if (!isAdmin) links += link('orders', 'orders.html', 'My Orders');
  if (!isAdmin) links += '<li><a class="nav-link ' + (PAGE === 'cart' ? 'active' : '') + '" href="' + ROOT + 'cart.html">🛒 Cart <span class="cart-badge empty">0</span></a></li>';
  let actions;
  if (user) {
    actions = '<div class="user-menu"><button class="user-btn" id="user-btn" aria-haspopup="true" aria-expanded="false"><span class="avatar">' + initial(user.name) + '</span><span class="uname">' + esc(user.name.split(' ')[0]) + '</span> ▾</button>' +
      '<div class="dropdown" id="user-dd"><div class="dd-head"><strong>' + esc(user.name) + '</strong>' + esc(user.email) + '</div>' +
      (isAdmin ? '<a href="' + ROOT + 'admin/dashboard.html">⚙️ Admin Dashboard</a>' : '<a href="' + ROOT + 'profile.html">👤 My Profile</a><a href="' + ROOT + 'orders.html">📦 My Orders</a>') +
      '<button id="logout-btn">🚪 Logout</button></div></div>';
  } else {
    actions = '<a class="btn btn-ghost btn-sm" href="' + ROOT + 'login.html">Login</a><a class="btn btn-primary btn-sm" href="' + ROOT + 'register.html">Sign up</a>';
  }
  host.className = 'site-header';
  host.innerHTML = (Auth.offline ? '<div class="offline-banner">⚠️ Cannot reach the server. Start the backend with <code>python run.py</code> and reload this page.</div>' : '') +
    '<div class="container nav"><a class="brand" href="' + ROOT + 'index.html"><img src="' + ROOT + 'assets/images/logo.svg" alt=""><span>Smart <b>Canteen</b></span></a>' +
    '<ul class="nav-links">' + links + '</ul><div class="nav-actions">' + actions +
    '<button class="icon-btn menu-toggle" id="menu-toggle" aria-label="Toggle navigation">☰</button></div></div>';
  Cart.updateBadge();
  $('#menu-toggle').addEventListener('click', () => host.classList.toggle('nav-open'));
  const btn = $('#user-btn'), dd = $('#user-dd');
  if (btn) {
    btn.addEventListener('click', e => { e.stopPropagation(); const open = dd.classList.toggle('open'); btn.setAttribute('aria-expanded', open); });
    document.addEventListener('click', () => dd.classList.remove('open'));
    $('#logout-btn').addEventListener('click', () => Auth.logout());
  }
}
function renderFooter() {
  const host = $('#site-footer');
  if (!host) return;
  host.className = 'site-footer';
  host.innerHTML = '<div class="container"><div class="footer-grid">' +
    '<div><a class="brand" href="' + ROOT + 'index.html"><img src="' + ROOT + 'assets/images/logo.svg" alt=""><span>Smart <b>Canteen</b></span></a><p style="margin-top:.8rem">Fresh, fast and hassle-free canteen ordering for students and staff.</p></div>' +
    '<div><h4>Quick links</h4><ul><li><a href="' + ROOT + 'menu.html">Menu</a></li><li><a href="' + ROOT + 'orders.html">My Orders</a></li><li><a href="' + ROOT + 'cart.html">Cart</a></li><li><a href="' + ROOT + 'profile.html">Profile</a></li></ul></div>' +
    '<div><h4>Opening hours</h4><ul><li>Mon – Fri: 8:00 AM – 7:00 PM</li><li>Saturday: 8:00 AM – 3:00 PM</li><li>Sunday: Closed</li></ul></div>' +
    '<div><h4>Contact</h4><ul><li>📍 Main Building, Ground Floor</li><li>📞 +91 00000 00000</li><li>✉️ canteen@example.edu</li></ul></div>' +
    '</div><div class="footer-bottom">© ' + new Date().getFullYear() + ' Smart Canteen · Payments in this project are simulated (demo only).</div></div>';
}

/* --------------------------------------------------------------- bootstrap */
const pageHandlers = {};
function onPage(name, fn) { (pageHandlers[name] = pageHandlers[name] || []).push(fn); }

document.addEventListener('DOMContentLoaded', async function () {
  if (!$('#toast-root')) { const t = document.createElement('div'); t.id = 'toast-root'; document.body.appendChild(t); }
  if (PAGE.indexOf('admin') !== 0) {
    const user = await Auth.me();
    renderHeader(user);
    renderFooter();
  }
  const handlers = pageHandlers[PAGE] || [];
  for (const fn of handlers) {
    try { await fn(); } catch (err) { console.error(err); toast(err.message || 'Unexpected error', 'error'); }
  }
});

/* ---------------------------------------------------- shared order details */
const FLOW = ['Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Completed'];
function timelineHTML(status) {
  if (status === 'Cancelled') return '<div class="form-alert error" style="margin:1rem 0">This order was cancelled.</div>';
  const idx = FLOW.indexOf(status);
  return '<div class="timeline">' + FLOW.map((s, i) =>
    '<div class="tl-step ' + (i < idx ? 'done' : i === idx ? 'current' : '') + '"><div class="tl-dot">' + (i < idx ? '✓' : i + 1) + '</div><span>' + esc(s) + '</span></div>').join('') + '</div>';
}
function orderDetailHTML(o, opts) {
  opts = opts || {};
  const rows = o.items.map(i => '<tr><td>' + esc(i.name) + '</td><td>' + i.quantity + '</td><td>' + money2(i.unit_price) + '</td><td>' + money2(i.line_total) + '</td></tr>').join('');
  return timelineHTML(o.status) +
    '<dl class="detail-grid">' +
    '<div><dt>Order ID</dt><dd>' + esc(o.order_number) + '</dd></div>' +
    '<div><dt>Placed on</dt><dd>' + esc(fmtDateTime(o.created_at)) + '</dd></div>' +
    '<div><dt>Status</dt><dd>' + statusBadge(o.status) + '</dd></div>' +
    '<div><dt>Order type</dt><dd>' + esc(o.order_type) + '</dd></div>' +
    '<div><dt>Customer</dt><dd>' + esc(o.customer_name) + '</dd></div>' +
    '<div><dt>Student ID / Phone</dt><dd>' + esc(o.student_id) + ' · ' + esc(o.phone) + '</dd></div>' +
    '<div><dt>Payment</dt><dd>' + esc(o.payment_method) + ' — ' + esc(o.payment_status) + '</dd></div>' +
    '<div><dt>Payment reference</dt><dd>' + esc(o.payment_ref || '—') + '</dd></div>' +
    (o.notes ? '<div style="grid-column:1/-1"><dt>Notes</dt><dd>' + esc(o.notes) + '</dd></div>' : '') +
    '</dl>' +
    '<table class="items-table"><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead><tbody>' + rows + '</tbody></table>' +
    '<div style="margin-top:1rem"><div class="summary-row"><span>Subtotal</span><span>' + money2(o.subtotal) + '</span></div>' +
    '<div class="summary-row"><span>Tax</span><span>' + money2(o.tax) + '</span></div>' +
    '<div class="summary-row total"><span>Total</span><span>' + money2(o.total) + '</span></div></div>';
}

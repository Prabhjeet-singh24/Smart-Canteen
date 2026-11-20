'use strict';
/* Customer order history and order details. */

onPage('orders', async () => {
  const user = await requireLogin();
  const list = $('#order-list'), tabs = $('#status-tabs');
  const STATUSES = ['All', 'Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Completed', 'Cancelled'];
  let orders = [], filter = 'All', modal = null, detailId = null;

  tabs.innerHTML = STATUSES.map(s => '<button class="chip" data-s="' + s + '">' + s + '</button>').join('');
  const syncTabs = () => $$('.chip', tabs).forEach(c => c.classList.toggle('active', c.dataset.s === filter));
  tabs.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; filter = b.dataset.s; syncTabs(); render(); });

  function render() {
    const shown = orders.filter(o => filter === 'All' || o.status === filter);
    if (!orders.length) { list.innerHTML = '<div class="card">' + emptyHTML('📦', 'No orders yet', 'When you place an order it will show up here.', '<a class="btn btn-primary" href="menu.html">Browse the menu</a>') + '</div>'; return; }
    if (!shown.length) { list.innerHTML = '<div class="card">' + emptyHTML('🔎', 'No ' + filter + ' orders', 'Try another status filter.') + '</div>'; return; }
    list.innerHTML = shown.map(o =>
      '<article class="card order-card"><div class="order-top"><div><div class="order-id">' + esc(o.order_number) + '</div><span class="muted">' + esc(fmtDateTime(o.created_at)) + ' · ' + esc(o.order_type) + '</span></div>' + statusBadge(o.status) + '</div>' +
      '<div class="order-items-line">' + o.items.map(i => esc(i.quantity + '× ' + i.name)).join(', ') + '</div>' +
      '<div class="order-bottom"><span class="price">' + money2(o.total) + '</span><button class="btn btn-outline btn-sm" data-view="' + o.id + '">View details</button></div></article>').join('');
  }

  async function load(silent) {
    if (!silent) list.innerHTML = loadingHTML('Loading your orders…');
    try { orders = (await Api.get('/orders')).orders; render(); if (detailId && modal) refreshDetail(); }
    catch (err) { if (!silent) { list.innerHTML = errorHTML(err, 'retry-orders'); $('#retry-orders').addEventListener('click', () => load()); } }
  }

  async function showDetail(id) {
    detailId = id;
    modal = openModal({ title: 'Order details', wide: true, body: loadingHTML(), onClose: () => { modal = null; detailId = null; } });
    refreshDetail();
  }
  async function refreshDetail() {
    if (!modal) return;
    let o;
    try { o = (await Api.get('/orders/' + detailId)).order; }
    catch (err) { if (modal) modal.body.innerHTML = errorHTML(err); return; }
    if (!modal) return;
    let extra = '';
    if (o.status === 'Pending') extra = '<div style="margin-top:1.2rem"><button class="btn btn-danger-outline" id="cancel-order">Cancel this order</button></div>';
    if (o.status === 'Completed') {
      extra = o.rating
        ? '<div style="margin-top:1.2rem">Your rating: <span class="stars-static">' + '★'.repeat(o.rating) + '☆'.repeat(5 - o.rating) + '</span></div>'
        : '<div style="margin-top:1.2rem"><strong>How was your order?</strong><div class="stars" id="stars">' + [1, 2, 3, 4, 5].map(n => '<button data-n="' + n + '" aria-label="' + n + ' stars">★</button>').join('') + '</div><button class="btn btn-primary btn-sm" id="submit-rating" disabled>Submit rating</button></div>';
    }
    modal.body.innerHTML = orderDetailHTML(o) + extra;
    const cancel = $('#cancel-order', modal.el);
    if (cancel) cancel.addEventListener('click', async () => {
      if (!await confirmDialog('Cancel order', 'Cancel order ' + o.order_number + '? This cannot be undone.', 'Yes, cancel it', true)) return;
      try { await Api.put('/orders/' + o.id + '/status', { status: 'Cancelled' }); toast('Order cancelled.', 'success'); await load(true); refreshDetail(); }
      catch (err) { toast(err.message, 'error'); }
    });
    const stars = $('#stars', modal.el);
    if (stars) {
      let chosen = 0;
      stars.addEventListener('click', e => {
        const b = e.target.closest('button'); if (!b) return;
        chosen = Number(b.dataset.n);
        $$('button', stars).forEach(x => x.classList.toggle('on', Number(x.dataset.n) <= chosen));
        $('#submit-rating', modal.el).disabled = false;
      });
      $('#submit-rating', modal.el).addEventListener('click', async () => {
        try { await Api.post('/orders/' + o.id + '/rating', { rating: chosen }); toast('Thanks for your feedback! ⭐', 'success'); await load(true); refreshDetail(); }
        catch (err) { toast(err.message, 'error'); }
      });
    }
  }

  list.addEventListener('click', e => { const b = e.target.closest('[data-view]'); if (b) showDetail(Number(b.dataset.view)); });
  syncTabs();
  await load();
  const wanted = Number(new URLSearchParams(window.location.search).get('order'));
  if (wanted) showDetail(wanted);
  setInterval(() => { if (!document.hidden) load(true); }, 20000);   // pick up status changes from the kitchen
});

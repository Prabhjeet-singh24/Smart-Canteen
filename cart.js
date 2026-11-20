'use strict';
/* Shopping cart page and checkout page. */

/* Refresh cart lines with current prices / availability from the server. */
async function syncCart() {
  const data = await Api.get('/menu');
  const byId = {};
  data.items.forEach(i => { byId[i.id] = i; });
  const notes = [];
  const lines = [];
  Cart.read().forEach(line => {
    const live = byId[line.id];
    if (!live) { notes.push(line.name + ' is no longer on the menu and was removed.'); return; }
    if (live.price !== line.price) notes.push('Price of ' + live.name + ' changed to ' + money(live.price) + '.');
    lines.push({ id: live.id, name: live.name, price: live.price, image_url: live.image_url, is_veg: live.is_veg, qty: line.qty, available: live.is_available });
  });
  Cart.write(lines.map(l => ({ id: l.id, name: l.name, price: l.price, image_url: l.image_url, is_veg: l.is_veg, qty: l.qty })));
  return { lines: lines, taxRate: data.tax_rate, notes: notes };
}

/* ---------------- cart page ---------------- */
onPage('cart', async () => {
  const box = $('#cart-box');
  let state = null;

  function render() {
    const lines = state.lines;
    if (!lines.length) {
      box.className = '';
      box.innerHTML = '<div class="card">' + emptyHTML('🛒', 'Your cart is empty', 'Browse the menu and add something delicious.', '<a class="btn btn-primary" href="menu.html">View Menu</a>') + '</div>';
      return;
    }
    const sel = lines.filter(l => l.available);
    const t = Cart.totals(sel, state.taxRate);
    const blocked = lines.some(l => !l.available);
    const isAdmin = Auth.user && Auth.user.role === 'admin';
    box.className = 'cart-layout';
    box.innerHTML =
      '<div class="card cart-list" id="cart-list">' + lines.map(l =>
        '<div class="cart-item" data-id="' + l.id + '"><img src="' + esc(imgSrc(l.image_url)) + '" alt="' + esc(l.name) + '">' +
        '<div><h4>' + esc(l.name) + '</h4><span class="muted">' + money(l.price) + ' each</span>' + (l.available ? '' : '<div class="warn-line">Currently unavailable — remove to continue</div>') + '</div>' +
        '<div class="stepper"><button data-act="dec" aria-label="Decrease quantity">−</button><span>' + l.qty + '</span><button data-act="inc" aria-label="Increase quantity">+</button></div>' +
        '<div class="line-total">' + money2(l.price * l.qty) + '<br><button class="btn btn-sm btn-danger-outline" data-act="remove" style="margin-top:.3rem">Remove</button></div></div>').join('') + '</div>' +
      '<aside class="card summary-card"><h3>Order summary</h3>' +
      '<div class="summary-row"><span>Subtotal</span><span>' + money2(t.subtotal) + '</span></div>' +
      '<div class="summary-row"><span>Tax (' + Math.round(state.taxRate * 1000) / 10 + '%)</span><span>' + money2(t.tax) + '</span></div>' +
      '<div class="summary-row total"><span>Total</span><span>' + money2(t.total) + '</span></div>' +
      (blocked ? '<p class="warn-line">Remove unavailable items to continue.</p>' : '') +
      (isAdmin ? '<p class="muted">Admin accounts cannot place orders.</p>' : '') +
      '<a id="checkout-btn" class="btn btn-primary btn-block" href="' + (Auth.user ? 'checkout.html' : 'login.html?next=checkout.html') + '" ' + ((blocked || isAdmin) ? 'aria-disabled="true"' : '') + '>' + (Auth.user ? 'Proceed to Checkout →' : 'Login to Checkout →') + '</a>' +
      '<button class="btn btn-ghost btn-block" id="clear-cart" style="margin-top:.7rem">Clear cart</button>' +
      '<a class="btn btn-ghost btn-block" href="menu.html" style="margin-top:.7rem">+ Add more items</a></aside>';
    const cb = $('#checkout-btn');
    if (blocked || isAdmin) cb.addEventListener('click', e => e.preventDefault());
    $('#clear-cart').addEventListener('click', async () => { if (await confirmDialog('Clear cart', 'Remove all items from your cart?', 'Clear cart', true)) { Cart.clear(); state.lines = []; render(); } });
  }

  box.addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (!btn || !btn.closest('.cart-item')) return;
    const id = Number(btn.closest('.cart-item').dataset.id), line = state.lines.find(l => l.id === id);
    if (btn.dataset.act === 'inc') { if (line.qty >= 20) return toast('Maximum 20 per item.', 'error'); line.qty++; Cart.setQty(id, line.qty); }
    if (btn.dataset.act === 'dec') { line.qty--; Cart.setQty(id, line.qty); if (line.qty <= 0) state.lines = state.lines.filter(l => l.id !== id); }
    if (btn.dataset.act === 'remove') { Cart.remove(id); state.lines = state.lines.filter(l => l.id !== id); toast(line.name + ' removed', 'info'); }
    render();
  });

  async function load() {
    box.className = ''; box.innerHTML = loadingHTML('Loading your cart…');
    try {
      state = await syncCart();
      state.notes.forEach(n => toast(n, 'info'));
      render();
    } catch (err) { box.innerHTML = errorHTML(err, 'retry-cart'); $('#retry-cart').addEventListener('click', load); }
  }
  await load();
});

/* ---------------- checkout page ---------------- */
onPage('checkout', async () => {
  const user = await requireLogin();
  const box = $('#checkout-box');
  if (!Cart.read().length) { window.location.replace('cart.html'); return; }
  let state;
  try { state = await syncCart(); } catch (err) { box.innerHTML = errorHTML(err); return; }
  state.notes.forEach(n => toast(n, 'info'));
  if (!state.lines.length) { window.location.replace('cart.html'); return; }
  const bad = state.lines.filter(l => !l.available);
  if (bad.length) { toast(bad.map(b => b.name).join(', ') + ' unavailable. Please update your cart.', 'error'); window.location.replace('cart.html'); return; }
  const t = Cart.totals(state.lines, state.taxRate);

  box.className = 'cart-layout';
  box.innerHTML =
    '<form class="card card-pad" id="checkout-form" novalidate><div class="form-alert hidden"></div>' +
    '<h3>Customer details</h3>' +
    '<div class="form-row"><div class="form-group"><label for="customer_name">Full name</label><input class="input" id="customer_name" name="customer_name" value="' + esc(user.name) + '" maxlength="60" required><div class="field-error" data-error-for="customer_name"></div></div>' +
    '<div class="form-group"><label for="student_id">Student ID / Registration no.</label><input class="input" id="student_id" name="student_id" value="' + esc(user.student_id || '') + '" maxlength="20" required><div class="field-error" data-error-for="student_id"></div></div></div>' +
    '<div class="form-group"><label for="phone">Contact number</label><input class="input" id="phone" name="phone" type="tel" value="' + esc(user.phone || '') + '" maxlength="20" required><div class="field-error" data-error-for="phone"></div></div>' +
    '<h3 style="margin-top:1.4rem">Order type</h3><div class="option-cards" style="margin-bottom:1.2rem">' +
    '<div class="option-card"><input type="radio" name="order_type" id="ot1" value="Dine-in" checked><label for="ot1"><span class="oc-emoji">🍽️</span><span>Dine-in<small>Eat at the canteen</small></span></label></div>' +
    '<div class="option-card"><input type="radio" name="order_type" id="ot2" value="Takeaway"><label for="ot2"><span class="oc-emoji">🥡</span><span>Takeaway<small>Pick up &amp; go</small></span></label></div></div>' +
    '<h3>Payment method</h3><div class="option-cards">' +
    '<div class="option-card"><input type="radio" name="payment_method" id="pm1" value="Cash" checked><label for="pm1"><span class="oc-emoji">💵</span><span>Cash<small>Pay at the counter</small></span></label></div>' +
    '<div class="option-card"><input type="radio" name="payment_method" id="pm2" value="Demo UPI"><label for="pm2"><span class="oc-emoji">📲</span><span>Demo UPI<small>Simulated payment</small></span></label></div></div>' +
    '<div class="demo-box hidden" id="upi-box"><strong>Demo UPI payment</strong><p class="muted" style="margin:.3rem 0 .8rem">This is a simulation. No real money is charged and no real payment service is contacted.</p>' +
    '<div class="form-group" style="margin:0"><label for="upi_id">Demo UPI ID</label><input class="input" id="upi_id" name="upi_id" placeholder="yourname@upi" maxlength="60" autocomplete="off"><div class="field-error" data-error-for="upi_id"></div></div></div>' +
    '<div class="form-group" style="margin-top:1.2rem"><label for="notes">Special instructions (optional)</label><textarea class="input" id="notes" name="notes" maxlength="200" placeholder="E.g. less spicy"></textarea><div class="field-error" data-error-for="notes"></div></div>' +
    '</form>' +
    '<aside class="card summary-card"><h3>Order summary</h3><div class="summary-items">' + state.lines.map(l =>
      '<div class="summary-row"><span>' + l.qty + ' × ' + esc(l.name) + '</span><span>' + money2(l.price * l.qty) + '</span></div>').join('') + '</div>' +
    '<div class="summary-row"><span>Subtotal</span><span>' + money2(t.subtotal) + '</span></div>' +
    '<div class="summary-row"><span>Tax (' + Math.round(state.taxRate * 1000) / 10 + '%)</span><span>' + money2(t.tax) + '</span></div>' +
    '<div class="summary-row total"><span>Total</span><span>' + money2(t.total) + '</span></div>' +
    '<button class="btn btn-primary btn-block" id="place-order" type="submit" form="checkout-form">Place Order</button>' +
    '<a class="btn btn-ghost btn-block" href="cart.html" style="margin-top:.7rem">← Back to cart</a></aside>';

  const form = $('#checkout-form');
  const upiToggle = () => $('#upi-box').classList.toggle('hidden', formValues(form).payment_method !== 'Demo UPI');
  $$('input[name=payment_method]', form).forEach(r => r.addEventListener('change', upiToggle));

  form.addEventListener('submit', async e => {
    e.preventDefault(); clearFieldErrors(form);
    const v = formValues(form), btn = $('#place-order'), details = {};
    if (v.customer_name.trim().length < 2) details.customer_name = 'Enter your name.';
    if (!/^[A-Za-z0-9][A-Za-z0-9\-\/]{2,19}$/.test(v.student_id.trim())) details.student_id = 'Enter a valid Student ID / registration number.';
    if (!/^\+?\d{10,13}$/.test(v.phone.replace(/[\s\-()]/g, ''))) details.phone = 'Enter a valid contact number.';
    if (v.payment_method === 'Demo UPI' && !/^[A-Za-z0-9._\-]{2,}@[A-Za-z]{2,}$/.test(v.upi_id.trim())) details.upi_id = 'Enter a demo UPI ID like name@upi.';
    if (Object.keys(details).length) return showFieldErrors(form, { message: 'Please fix the highlighted fields.', details: details });
    setLoading(btn, true, 'Placing order…');
    try {
      const res = await Api.post('/orders', {
        items: state.lines.map(l => ({ menu_item_id: l.id, quantity: l.qty })),
        order_type: v.order_type, payment_method: v.payment_method, customer_name: v.customer_name.trim(),
        student_id: v.student_id.trim(), phone: v.phone, upi_id: v.upi_id.trim(), notes: v.notes.trim(),
      });
      Cart.clear();
      const o = res.order;
      const m = openModal({
        title: 'Order placed!', body: '<div class="success-burst"><div class="big">🎉</div><h3>Thank you, ' + esc(o.customer_name.split(' ')[0]) + '!</h3>' +
          '<p>Your order <strong>' + esc(o.order_number) + '</strong> has been received.</p>' +
          '<p class="muted">Total ' + money2(o.total) + ' · ' + esc(o.payment_method) + ' (' + esc(o.payment_status) + ')' + (o.payment_ref ? '<br>Demo reference: ' + esc(o.payment_ref) : '') + '</p></div>',
        footer: '<a class="btn btn-ghost" href="menu.html">Order more</a><a class="btn btn-primary" href="orders.html?order=' + o.id + '">View my order</a>',
        onClose: () => { window.location.href = 'orders.html?order=' + o.id; },
      });
    } catch (err) {
      setLoading(btn, false);
      showFieldErrors(form, err);
      if (err.status === 409) toast('Some items changed. Please review your cart.', 'error');
    }
  });
});

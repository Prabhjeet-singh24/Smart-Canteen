'use strict';
/* Home page and menu page (food cards, filters). */

const itemsById = {};
function foodActionsHTML(item) {
  if (Auth.user && Auth.user.role === 'admin') return '<span class="badge badge-muted">Admin view</span>';
  if (!item.is_available) return '<button class="btn btn-ghost btn-block" disabled>Currently unavailable</button>';
  const q = Cart.qty(item.id);
  if (q) return '<div class="stepper" role="group" aria-label="Quantity"><button data-act="dec" aria-label="Decrease">−</button><span>' + q + '</span><button data-act="inc" aria-label="Increase">+</button></div>';
  return '<button class="btn btn-primary btn-block" data-act="add">🛒 Add to Cart</button>';
}
function foodCardHTML(item) {
  itemsById[item.id] = item;
  return '<article class="card food-card ' + (item.is_available ? '' : 'unavailable') + '" data-id="' + item.id + '">' +
    '<div class="food-img"><img src="' + esc(imgSrc(item.image_url)) + '" alt="' + esc(item.name) + '" loading="lazy">' +
    '<span class="veg-mark ' + (item.is_veg ? '' : 'nonveg') + '" title="' + (item.is_veg ? 'Vegetarian' : 'Non-vegetarian') + '"></span>' +
    (item.is_popular ? '<span class="pop-tag">🔥 Popular</span>' : '') + '</div>' +
    '<div class="food-body"><span class="food-cat">' + esc(item.category) + '</span><h3>' + esc(item.name) + '</h3>' +
    '<p class="food-desc">' + esc(item.description) + '</p>' +
    '<div class="food-meta"><span class="price">' + money(item.price) + '</span>' +
    '<span class="badge ' + (item.is_available ? 'badge-ok' : 'badge-no') + '">' + (item.is_available ? '● Available' : '● Unavailable') + '</span></div>' +
    '<div class="food-actions">' + foodActionsHTML(item) + '</div></div></article>';
}
function bindFoodGrid(grid) {
  grid.addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const card = btn.closest('.food-card'), item = itemsById[card.dataset.id];
    if (!item) return;
    const act = btn.dataset.act;
    if (act === 'add') { Cart.add(item, 1); toast(item.name + ' added to cart', 'success'); }
    else if (act === 'inc') Cart.setQty(item.id, Cart.qty(item.id) + 1);
    else if (act === 'dec') Cart.setQty(item.id, Cart.qty(item.id) - 1);
    $('.food-actions', card).innerHTML = foodActionsHTML(item);
  });
}

/* ---------------- home ---------------- */
onPage('home', async () => {
  const user = Auth.user;
  $('#greeting').textContent = user ? 'Welcome back, ' + user.name.split(' ')[0] + '! 👋' : 'Welcome to Smart Canteen! 👋';
  $('#greeting-sub').textContent = user && user.role === 'admin'
    ? 'You are signed in as an administrator. Open the dashboard to manage the canteen.'
    : 'Skip the queue. Order your favourite meals in a few taps and pick them up fresh.';
  if (user && user.role === 'admin') {
    $('#my-orders-btn').textContent = '⚙️ Admin Dashboard'; $('#my-orders-btn').href = ROOT + 'admin/dashboard.html';
  }

  const statsEl = $('#stats'), catEl = $('#categories'), popEl = $('#popular');
  catEl.innerHTML = loadingHTML(); popEl.innerHTML = loadingHTML();
  try {
    const s = await Api.get('/stats');
    const cards = [
      ['👨‍🍳', s.chefs, 'Expert chefs'],
      ['🍽️', s.menu_items, 'Menu items'],
      ['⭐', s.rating !== null ? s.rating.toFixed(1) + ' / 5' : 'New', s.rating !== null ? 'Customer rating (' + s.rating_count + ')' : 'No ratings yet'],
      ['⏱️', s.avg_minutes ? '~' + s.avg_minutes + ' min' : '—', 'Avg. preparation time'],
    ];
    statsEl.innerHTML = cards.map(c => '<div class="card stat-card"><div class="stat-icon">' + c[0] + '</div><div><div class="stat-value">' + esc(c[1]) + '</div><div class="stat-label">' + esc(c[2]) + '</div></div></div>').join('');
  } catch (err) { statsEl.innerHTML = ''; }
  try {
    const cats = (await Api.get('/categories')).categories;
    catEl.innerHTML = cats.length ? cats.map(c => '<a class="card category-card" href="menu.html?category=' + c.id + '"><span class="emoji">' + categoryEmoji(c.name) + '</span><strong>' + esc(c.name) + '</strong><small>' + c.item_count + ' items</small></a>').join('')
      : emptyHTML('🗂️', 'No categories yet', 'The canteen has not added any categories.');
    catEl.className = cats.length ? 'category-grid' : '';
  } catch (err) { catEl.innerHTML = errorHTML(err); }
  try {
    const items = (await Api.get('/menu?popular=1&available=1&limit=8')).items;
    popEl.innerHTML = items.length ? items.map(foodCardHTML).join('') : emptyHTML('🍽️', 'Nothing popular yet', 'Check the full menu for all dishes.');
    popEl.className = items.length ? 'food-grid' : '';
    bindFoodGrid(popEl);
  } catch (err) { popEl.innerHTML = errorHTML(err); }
});

/* ---------------- menu ---------------- */
onPage('menu', async () => {
  const grid = $('#menu-grid'), count = $('#result-count'), chipsEl = $('#category-chips');
  const params = new URLSearchParams(window.location.search);
  const state = { q: '', category: params.get('category') || '', veg: '', available: false, sort: 'name' };
  bindFoodGrid(grid);

  async function load() {
    grid.className = ''; grid.innerHTML = loadingHTML('Loading menu…');
    const qs = new URLSearchParams();
    if (state.q) qs.set('q', state.q);
    if (state.category) qs.set('category', state.category);
    if (state.veg) qs.set('veg', state.veg);
    if (state.available) qs.set('available', '1');
    qs.set('sort', state.sort);
    try {
      const data = await Api.get('/menu?' + qs.toString());
      count.textContent = data.count + (data.count === 1 ? ' dish found' : ' dishes found');
      if (!data.items.length) {
        grid.innerHTML = emptyHTML('🔎', 'No dishes match your filters', 'Try a different search term or clear the filters.', '<button class="btn btn-outline" id="clear-filters">Clear filters</button>');
        $('#clear-filters').addEventListener('click', resetFilters);
        return;
      }
      grid.className = 'food-grid';
      grid.innerHTML = data.items.map(foodCardHTML).join('');
    } catch (err) {
      count.textContent = '';
      grid.innerHTML = errorHTML(err, 'retry-menu');
      $('#retry-menu').addEventListener('click', load);
    }
  }
  function syncControls() {
    $$('#category-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.cat === String(state.category)));
    $$('#veg-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.veg === state.veg));
    $('#search').value = state.q; $('#only-available').checked = state.available; $('#sort').value = state.sort;
  }
  function resetFilters() { Object.assign(state, { q: '', category: '', veg: '', available: false, sort: 'name' }); syncControls(); load(); }

  try {
    const cats = (await Api.get('/categories')).categories;
    chipsEl.innerHTML = '<button class="chip" data-cat="">All</button>' + cats.map(c => '<button class="chip" data-cat="' + c.id + '">' + categoryEmoji(c.name) + ' ' + esc(c.name) + '</button>').join('');
  } catch (err) { chipsEl.innerHTML = ''; }
  chipsEl.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; state.category = b.dataset.cat; syncControls(); load(); });
  $('#veg-chips').addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; state.veg = b.dataset.veg; syncControls(); load(); });
  $('#search').addEventListener('input', debounce(e => { state.q = e.target.value.trim(); load(); }, 300));
  $('#only-available').addEventListener('change', e => { state.available = e.target.checked; load(); });
  $('#sort').addEventListener('change', e => { state.sort = e.target.value; load(); });
  $('#reset-filters').addEventListener('click', resetFilters);
  syncControls();
  await load();
});

'use strict';
/* Login, registration, admin login and profile pages. */

function initPasswordToggles(scope) {
  $$('.pw-toggle', scope).forEach(btn => btn.addEventListener('click', () => {
    const input = $('input', btn.parentElement);
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.textContent = show ? '🙈' : '👁️';
    btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  }));
}
function passwordProblem(pw) {
  if (pw.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return 'Password must contain a letter and a digit.';
  return '';
}
const RE = { email: /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/, phone: /^\+?\d{10,13}$/, sid: /^[A-Za-z0-9][A-Za-z0-9\-\/]{2,19}$/ };
function clientErrors(form, v, rules) {
  const details = {};
  if ('name' in rules && (v.name || '').trim().length < 2) details.name = 'Enter your full name.';
  if ('email' in rules && !RE.email.test((v.email || '').trim())) details.email = 'Enter a valid email address.';
  if ('phone' in rules && !RE.phone.test((v.phone || '').replace(/[\s\-()]/g, ''))) details.phone = 'Enter a valid phone number (10 to 13 digits).';
  if ('student_id' in rules && !RE.sid.test((v.student_id || '').trim())) details.student_id = 'Student ID must be 3-20 letters, digits, "-" or "/".';
  return details;
}

/* ---------------- login (customer) & admin login ---------------- */
async function setupLogin(role) {
  const form = $('#login-form');
  initPasswordToggles(form);
  const user = await Auth.me();
  if (user && (role === 'customer' || user.role === 'admin')) { window.location.replace(ROOT + (user.role === 'admin' ? 'admin/dashboard.html' : 'index.html')); return; }
  const params = new URLSearchParams(window.location.search);
  if (params.get('registered')) { const a = $('.form-alert', form); a.textContent = 'Account created. Please sign in.'; a.className = 'form-alert success'; }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    clearFieldErrors(form);
    const v = formValues(form), btn = $('button[type=submit]', form);
    const details = {};
    if (!RE.email.test(v.email.trim())) details.email = 'Enter a valid email address.';
    if (!v.password) details.password = 'Enter your password.';
    if (Object.keys(details).length) return showFieldErrors(form, { message: 'Please fix the highlighted fields.', details: details });
    setLoading(btn, true, 'Signing in…');
    try {
      const res = await Api.post('/login', { email: v.email.trim(), password: v.password, role: role });
      const next = safeNext(params.get('next'));
      window.location.href = role === 'admin' ? ROOT + 'admin/dashboard.html' : (res.user.role === 'admin' ? ROOT + 'admin/dashboard.html' : ROOT + (next || 'index.html'));
    } catch (err) { setLoading(btn, false); showFieldErrors(form, err); }
  });
}
onPage('login', () => setupLogin('customer'));
onPage('admin-login', () => setupLogin('admin'));

/* ---------------- register ---------------- */
onPage('register', async () => {
  const form = $('#register-form');
  initPasswordToggles(form);
  if (await Auth.me()) { window.location.replace(ROOT + 'index.html'); return; }
  const meter = $('.pw-meter span', form);
  form.elements.password.addEventListener('input', e => {
    const p = e.target.value;
    let score = 0;
    if (p.length >= 8) score++; if (/[A-Z]/.test(p) && /[a-z]/.test(p)) score++; if (/\d/.test(p)) score++; if (/[^A-Za-z0-9]/.test(p)) score++;
    meter.style.width = (score * 25) + '%';
    meter.style.background = ['#d93a3a', '#d93a3a', '#e59a0b', '#7bb83d', '#1e9e5a'][score];
  });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    clearFieldErrors(form);
    const v = formValues(form), btn = $('button[type=submit]', form);
    const details = clientErrors(form, v, { name: 1, email: 1, phone: 1, student_id: 1 });
    const pwProblem = passwordProblem(v.password || '');
    if (pwProblem) details.password = pwProblem;
    if (v.password !== v.confirm_password) details.confirm_password = 'Passwords do not match.';
    if (Object.keys(details).length) return showFieldErrors(form, { message: 'Please fix the highlighted fields.', details: details });
    setLoading(btn, true, 'Creating account…');
    try {
      await Api.post('/register', { name: v.name.trim(), email: v.email.trim(), phone: v.phone, student_id: v.student_id.trim(), password: v.password, confirm_password: v.confirm_password });
      toast('Welcome to Smart Canteen! 🎉', 'success');
      window.location.href = ROOT + 'index.html';
    } catch (err) { setLoading(btn, false); showFieldErrors(form, err); }
  });
});

/* ---------------- profile ---------------- */
onPage('profile', async () => {
  const user = await requireLogin();
  const view = $('#profile-view'), form = $('#profile-form'), pwForm = $('#password-form');
  function renderView(u) {
    $('#profile-avatar').textContent = (u.name || '?').trim().charAt(0).toUpperCase();
    $('#profile-name').textContent = u.name;
    $('#profile-facts').innerHTML =
      '<div><span>Email</span><span>' + esc(u.email) + '</span></div>' +
      '<div><span>Phone</span><span>' + esc(u.phone || '—') + '</span></div>' +
      '<div><span>Student ID</span><span>' + esc(u.student_id || '—') + '</span></div>' +
      '<div><span>Member since</span><span>' + esc(fmtDate(u.created_at)) + '</span></div>';
    ['name', 'email', 'phone', 'student_id'].forEach(k => { form.elements[k].value = u[k] || ''; });
  }
  renderView(user);
  initPasswordToggles(pwForm);
  const editBtn = $('#edit-profile-btn');
  const toggleEdit = on => { form.classList.toggle('hidden', !on); view.classList.toggle('hidden', on); clearFieldErrors(form); };
  editBtn.addEventListener('click', () => toggleEdit(true));
  $('#cancel-edit').addEventListener('click', () => { renderView(Auth.user); toggleEdit(false); });
  form.addEventListener('submit', async e => {
    e.preventDefault(); clearFieldErrors(form);
    const v = formValues(form), btn = $('button[type=submit]', form);
    const details = clientErrors(form, v, { name: 1, email: 1, phone: 1, student_id: 1 });
    if (Object.keys(details).length) return showFieldErrors(form, { message: 'Please fix the highlighted fields.', details: details });
    setLoading(btn, true, 'Saving…');
    try {
      const res = await Api.put('/profile', { name: v.name.trim(), email: v.email.trim(), phone: v.phone, student_id: v.student_id.trim() });
      Auth.user = res.user; renderView(res.user); toggleEdit(false); renderHeader(res.user);
      toast('Profile updated.', 'success');
    } catch (err) { showFieldErrors(form, err); } finally { setLoading(btn, false); }
  });
  pwForm.addEventListener('submit', async e => {
    e.preventDefault(); clearFieldErrors(pwForm);
    const v = formValues(pwForm), btn = $('button[type=submit]', pwForm), details = {};
    if (!v.current_password) details.current_password = 'Enter your current password.';
    const p = passwordProblem(v.new_password || ''); if (p) details.new_password = p;
    if (v.new_password !== v.confirm_password) details.confirm_password = 'Passwords do not match.';
    if (Object.keys(details).length) return showFieldErrors(pwForm, { message: 'Please fix the highlighted fields.', details: details });
    setLoading(btn, true, 'Updating…');
    try { await Api.post('/change-password', v); pwForm.reset(); toast('Password changed successfully.', 'success'); }
    catch (err) { showFieldErrors(pwForm, err); } finally { setLoading(btn, false); }
  });
  $('#profile-logout').addEventListener('click', () => Auth.logout());
});

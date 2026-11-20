/* API location.
 * - Opened through the Flask server (http://localhost:5000/...)  -> same origin, nothing to configure.
 * - Frontend served separately (e.g. `python -m http.server 5500`) -> API is expected on port 5000
 *   of the same host name. If your backend runs elsewhere, put its full URL in FIXED_API_BASE. */
window.CANTEEN_API_BASE = (function () {
  var FIXED_API_BASE = '';              // e.g. 'http://localhost:8000'
  if (FIXED_API_BASE) return FIXED_API_BASE.replace(/\/+$/, '');
  var loc = window.location;
  if (loc.protocol === 'file:') return 'http://localhost:5000';   // note: login cookies need http://, see README
  if (loc.port === '5000') return '';
  return 'http://' + loc.hostname + ':5000';
})();

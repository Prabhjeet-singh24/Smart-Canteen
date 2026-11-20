# Smart Canteen – Frontend

Static HTML/CSS/vanilla JS site. It needs the Smart Canteen backend API (see `smart-canteen-backend.zip`).

* Easiest: copy this folder to `smart-canteen/frontend/` next to the backend and run `python run.py` – Flask serves it at http://127.0.0.1:5000/.
* Separate hosting: `python -m http.server 5500` inside this folder, open http://localhost:5500/ . The API address is set in `js/config.js` (default `http://<same host>:5000`).
* Do not open the files via `file://` (login cookies do not work there).

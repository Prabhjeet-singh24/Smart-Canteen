"""Start the Smart Canteen server:  python run.py"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _load_init_db():
    spec = importlib.util.spec_from_file_location("init_db", os.path.join(ROOT, "database", "init_db.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    _load_init_db().init_database(app.config["DATABASE"], demo="--demo" in sys.argv)
    host, port = app.config["HOST"], app.config["PORT"]
    print("\nSmart Canteen is running:")
    if os.path.isdir(app.config["FRONTEND_DIR"]) and app.config["SERVE_FRONTEND"]:
        print("  Customer site : http://%s:%d/" % (host, port))
        print("  Admin login   : http://%s:%d/admin/login.html" % (host, port))
    else:
        print("  (backend only - serve the frontend folder separately, see README)")
    print("  API health    : http://%s:%d/api/health\n" % (host, port))
    app.run(host=host, port=port, debug=app.config["DEBUG"])

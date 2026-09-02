import sys, traceback
from pathlib import Path

webapp_dir = Path(__file__).parent.parent / "webapp"
sys.path.insert(0, str(webapp_dir))

_import_error = None
try:
    from app import app
except Exception as e:
    _import_error = traceback.format_exc()
    from flask import Flask, Response
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return Response(f"<pre>IMPORT ERROR:\n{_import_error}</pre>", status=500,
                        mimetype="text/html")

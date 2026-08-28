import sys
from pathlib import Path

# Agregar webapp/ al path para que Vercel encuentre app.py y evaluator.py
webapp_dir = Path(__file__).parent.parent / "webapp"
sys.path.insert(0, str(webapp_dir))

from app import app

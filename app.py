"""Render entry point.

Render runs gunicorn from the repo root as `app:app`, but the real Flask
app and its `ml` sibling package live under webapp/. Both must be on
sys.path, and the real app is loaded under a different module name so it
doesn't collide with this file (also named app.py) in sys.modules.
"""
import importlib.util
import os
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_WEBAPP_DIR = os.path.join(_BASE_DIR, "webapp")

if _WEBAPP_DIR not in sys.path:
    sys.path.insert(0, _WEBAPP_DIR)

_spec = importlib.util.spec_from_file_location("webapp_app", os.path.join(_WEBAPP_DIR, "app.py"))
_webapp_app = importlib.util.module_from_spec(_spec)
sys.modules["webapp_app"] = _webapp_app
_spec.loader.exec_module(_webapp_app)

app = _webapp_app.app

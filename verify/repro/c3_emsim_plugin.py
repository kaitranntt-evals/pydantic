"""pytest plugin: fake sys.platform='emscripten' before test modules import, so skipif(sys.platform == 'emscripten') evaluates as on Pyodide. Use: python -m pytest -p emsim ..."""
import sys

def pytest_configure(config):
    sys.platform = 'emscripten'

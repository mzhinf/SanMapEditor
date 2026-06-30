from __future__ import annotations

try:
    from ._legacy_wrapper import load_module
except ImportError:
    from _legacy_wrapper import load_module

_module = load_module("san_tools.map.apply_editor_patch")
globals().update({name: getattr(_module, name) for name in dir(_module) if not name.startswith("__")})

if __name__ == "__main__" and hasattr(_module, "main"):
    raise SystemExit(_module.main())

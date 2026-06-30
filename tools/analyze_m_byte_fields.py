"""兼容旧入口，转发到 `.m` byte 字段分析命令。"""

from __future__ import annotations

try:
    from ._legacy_wrapper import load_module
except ImportError:
    from _legacy_wrapper import load_module

_module = load_module('san_tools.analysis.analyze_m_byte_fields')
globals().update({name: getattr(_module, name) for name in dir(_module) if not name.startswith('__')})

if __name__ == '__main__' and hasattr(_module, 'main'):
    raise SystemExit(_module.main())
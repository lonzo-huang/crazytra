from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .base import BaseStrategy, StrategyParams

log = structlog.get_logger()

_registry: dict[str, type["BaseStrategy"]] = {}


def register(cls: type["BaseStrategy"]) -> type["BaseStrategy"]:
    if not hasattr(cls, "STRATEGY_ID"):
        raise AttributeError(f"{cls.__name__} must define STRATEGY_ID")
    sid = cls.STRATEGY_ID
    if sid in _registry:
        log.warning("strategy_overwritten", id=sid)
    _registry[sid] = cls
    log.debug("registered", id=sid)
    return cls


class StrategyRegistry:
    def create(self, strategy_id: str, params_dict: dict) -> "BaseStrategy":
        cls    = self._cls(strategy_id)
        schema = cls.get_params_schema()
        params = schema.model_validate(params_dict)
        return cls(params)

    def _cls(self, sid: str) -> type["BaseStrategy"]:
        if sid not in _registry:
            raise KeyError(f"Strategy '{sid}' not found. Available: {list(_registry)}")
        return _registry[sid]

    def list_all(self) -> list[dict]:
        return [{"id": sid, "name": cls.STRATEGY_NAME,
                 "params": cls.get_params_schema().model_json_schema()}
                for sid, cls in _registry.items()]

    def load_plugin_dir(self, plugin_dir: Path) -> int:
        before = len(_registry)
        for f in sorted(plugin_dir.glob("*.py")):
            if not f.name.startswith("_"):
                self._load_module(f)
        loaded = len(_registry) - before
        log.info("plugins_loaded", dir=str(plugin_dir), count=loaded)
        return loaded

    def _load_module(self, path: Path) -> None:
        name = f"strategies.{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        if not spec or not spec.loader:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            log.exception("plugin_load_error", file=str(path))
            sys.modules.pop(name, None)

    def reload_plugin(self, path: Path) -> list[str]:
        before = set(_registry)
        self._load_module(path)
        after = set(_registry)
        return list(after - before) + [
            sid for sid in after & before
            if _registry[sid].__module__.endswith(path.stem)
        ]


registry = StrategyRegistry()

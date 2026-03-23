from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .base import Tick
from .combinator import SignalCombinator
from .registry import registry

log = structlog.get_logger()


class _FileHandler(FileSystemEventHandler):
    def __init__(self, runner: "StrategyRunner", loop: asyncio.AbstractEventLoop) -> None:
        self._runner = runner
        self._loop   = loop

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".py"):
            asyncio.run_coroutine_threadsafe(
                self._runner.hot_reload(Path(str(event.src_path))),
                self._loop,
            )


class StrategyRunner:
    """Manages strategy lifecycle, dispatches ticks, handles hot reload."""

    def __init__(self, plugin_dir: Path, combinator: SignalCombinator) -> None:
        self.combinator  = combinator
        self._strategies = {}
        self._plugin_dir = plugin_dir
        self._observer   = Observer()

    async def start(self) -> None:
        registry.load_plugin_dir(self._plugin_dir)
        loop = asyncio.get_event_loop()
        handler = _FileHandler(self, loop)
        self._observer.schedule(handler, str(self._plugin_dir), recursive=False)
        self._observer.start()
        log.info("runner_started")

    async def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
        for s in self._strategies.values():
            await s.stop()

    async def add_strategy(self, strategy_id: str, params: dict) -> None:
        s = registry.create(strategy_id, params)
        await s.start()
        self._strategies[strategy_id] = s
        log.info("strategy_added", id=strategy_id)

    async def remove_strategy(self, strategy_id: str) -> None:
        s = self._strategies.pop(strategy_id, None)
        if s:
            await s.stop()

    async def dispatch_tick(self, tick: Tick) -> None:
        for s in self._strategies.values():
            for sig in s.process_tick(tick):
                await self.combinator.ingest(sig)
        combined = await self.combinator.combine(tick.symbol)
        if combined and combined.direction.value != "hold":
            log.info("signal", symbol=combined.symbol,
                     direction=combined.direction.value,
                     strength=f"{combined.strength:.3f}",
                     contributors=combined.contributors)

    async def hot_reload(self, path: Path) -> None:
        log.info("hot_reload", file=str(path))
        new_ids = registry.reload_plugin(path)
        for sid in new_ids:
            if sid not in self._strategies:
                continue
            old = self._strategies[sid]
            state = old.export_state()
            params = old.params.model_dump()
            await old.stop()
            try:
                new = registry.create(sid, params)
                new.import_state(state)
                await new.start()
                self._strategies[sid] = new
                log.info("hot_reload_ok", id=sid, state=state)
            except Exception:
                log.exception("hot_reload_failed_rollback", id=sid)
                await old.start()
                self._strategies[sid] = old

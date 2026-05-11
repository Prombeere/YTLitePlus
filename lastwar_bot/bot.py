"""
Main bot logic – configurable action loop for Last War: Survival.
Each action is an independently enabled/disabled module.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable

from config import BotConfig
from input_controller import InputController, ClickMethod
from memory_reader import MemoryReader
from window_manager import WindowManager

log = logging.getLogger("lastwar_bot")


@dataclass
class ActionResult:
    name: str
    success: bool
    message: str = ""


class LastWarBot:
    def __init__(self, config: BotConfig):
        self.cfg = config
        self.wm = WindowManager(target_titles=config.window_titles)
        self.inp: InputController | None = None
        self.mem: MemoryReader | None = None
        self._running = False
        self._actions: list[tuple[str, Callable, float]] = []  # (name, fn, interval_s)
        self._last_run: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        log.info("Starting bot...")
        win = self.wm.find_window()
        if not win:
            raise RuntimeError(f"No matching window found. Searched: {self.cfg.window_titles}")
        log.info(f"Found window: '{win.title}' (PID {win.pid}, {win.width}x{win.height})")

        self.inp = InputController(self.wm, ClickMethod[self.cfg.click_method])
        self.inp._humanize = self.cfg.humanize_input

        if self.cfg.enable_memory_reading:
            self.mem = MemoryReader(win.pid)
            if not self.mem._handle:
                log.warning("Could not open process for memory reading (try running as Administrator)")
                self.mem = None
            else:
                log.info("Memory reader attached to PID %d", win.pid)

        self._register_actions()
        self._running = True
        self._loop()

    def stop(self):
        self._running = False
        if self.mem:
            self.mem.close()

    # ------------------------------------------------------------------
    # Action registration
    # ------------------------------------------------------------------

    def _register_actions(self):
        cfg = self.cfg
        if cfg.auto_collect_excavators:
            self._actions.append(("collect_excavators", self._collect_excavators, cfg.excavator_interval))
        if cfg.auto_heal_troops:
            self._actions.append(("heal_troops", self._heal_troops, cfg.heal_interval))
        if cfg.auto_grab_red_packets:
            self._actions.append(("grab_red_packets", self._grab_red_packets, cfg.red_packet_interval))
        if cfg.auto_attack_zombies:
            self._actions.append(("attack_zombies", self._attack_zombies, cfg.zombie_interval))
        if cfg.enable_memory_reading and self.mem:
            self._actions.append(("memory_dump", self._dump_memory_values, cfg.memory_poll_interval))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self):
        log.info("Bot running. Press Ctrl+C to stop.")
        try:
            while self._running:
                now = time.time()
                for name, fn, interval in self._actions:
                    if now - self._last_run.get(name, 0) >= interval:
                        self._last_run[name] = now
                        try:
                            result = fn()
                            level = logging.INFO if result.success else logging.WARNING
                            log.log(level, "[%s] %s", result.name, result.message or ("OK" if result.success else "FAILED"))
                        except Exception as e:
                            log.error("[%s] Exception: %s", name, e)
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _collect_excavators(self) -> ActionResult:
        """
        Clicks the excavator collect button.
        Coordinates are relative (0.0-1.0) to the emulator window.
        Adjust these offsets to match the actual UI layout.
        """
        if not self.wm.get_window():
            return ActionResult("collect_excavators", False, "Window not found")
        # Example relative click positions – tune to actual game UI:
        collect_positions = self.cfg.excavator_positions
        clicked = 0
        for rx, ry in collect_positions:
            self.inp.click_rel(rx, ry)
            time.sleep(random.uniform(0.3, 0.7))
            clicked += 1
        return ActionResult("collect_excavators", True, f"Clicked {clicked} excavator(s)")

    def _heal_troops(self) -> ActionResult:
        if not self.wm.get_window():
            return ActionResult("heal_troops", False, "Window not found")
        for rx, ry in self.cfg.heal_positions:
            self.inp.click_rel(rx, ry)
            time.sleep(random.uniform(0.4, 0.8))
        return ActionResult("heal_troops", True, "Heal sequence executed")

    def _grab_red_packets(self) -> ActionResult:
        if not self.wm.get_window():
            return ActionResult("grab_red_packets", False, "Window not found")
        for rx, ry in self.cfg.red_packet_positions:
            self.inp.click_rel(rx, ry)
            time.sleep(random.uniform(0.2, 0.5))
        return ActionResult("grab_red_packets", True, "Red packet grab sequence executed")

    def _attack_zombies(self) -> ActionResult:
        if not self.wm.get_window():
            return ActionResult("attack_zombies", False, "Window not found")
        for rx, ry in self.cfg.zombie_positions:
            self.inp.click_rel(rx, ry)
            time.sleep(random.uniform(0.5, 1.0))
        return ActionResult("attack_zombies", True, "Zombie attack sequence executed")

    def _dump_memory_values(self) -> ActionResult:
        """Reads configured memory addresses and logs values (for anti-cheat analysis)."""
        if not self.mem:
            return ActionResult("memory_dump", False, "Memory reader not available")
        results = []
        for label, address, type_name in self.cfg.memory_targets:
            val = self.mem.read(address, type_name)
            results.append(f"{label}@0x{address:X}={val}")
        log.debug("Memory: %s", " | ".join(results))
        return ActionResult("memory_dump", True, f"Read {len(results)} value(s)")

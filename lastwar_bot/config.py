"""
Bot configuration. Edit this file to tune all bot behaviour.
All click positions are relative (0.0–1.0) to the emulator window size,
so they work regardless of window resolution.
"""

from dataclasses import dataclass, field


@dataclass
class BotConfig:
    # ------------------------------------------------------------------
    # Window detection
    # ------------------------------------------------------------------
    window_titles: list[str] = field(default_factory=lambda: [
        "BlueStacks", "BlueStacks App Player",
        "LDPlayer", "NoxPlayer", "MuMu Player",
        "Last War", "Last War: Survival",
    ])

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    # "SEND_MESSAGE" = background clicks (no focus needed)
    # "WIN32_API"    = foreground clicks (moves real cursor)
    click_method: str = "SEND_MESSAGE"
    humanize_input: bool = True  # Add small random jitter to clicks/delays

    # ------------------------------------------------------------------
    # Feature toggles
    # ------------------------------------------------------------------
    auto_collect_excavators: bool = True
    auto_heal_troops: bool = True
    auto_grab_red_packets: bool = True
    auto_attack_zombies: bool = True
    enable_memory_reading: bool = True

    # ------------------------------------------------------------------
    # Action intervals (seconds)
    # ------------------------------------------------------------------
    excavator_interval: float = 30.0
    heal_interval: float = 60.0
    red_packet_interval: float = 15.0
    zombie_interval: float = 45.0
    memory_poll_interval: float = 5.0

    # ------------------------------------------------------------------
    # Click positions (relative x, y within emulator window)
    # These are placeholder coordinates – replace with actual UI positions
    # by inspecting the game with a coordinate overlay tool.
    # ------------------------------------------------------------------
    excavator_positions: list[tuple] = field(default_factory=lambda: [
        (0.50, 0.40),  # Example: excavator collect button
        (0.70, 0.60),
    ])
    heal_positions: list[tuple] = field(default_factory=lambda: [
        (0.50, 0.85),  # Hospital / heal button
        (0.65, 0.85),
    ])
    red_packet_positions: list[tuple] = field(default_factory=lambda: [
        (0.50, 0.50),  # Red packet popup center
    ])
    zombie_positions: list[tuple] = field(default_factory=lambda: [
        (0.30, 0.50),  # Zombie on map
        (0.50, 0.70),  # Attack confirm button
    ])

    # ------------------------------------------------------------------
    # Memory targets for anti-cheat testing
    # Each entry: (label, address, type)
    # type = "int" | "uint" | "float" | "byte" | "short" | "long"
    # Find addresses with Cheat Engine or AOB scan first.
    # ------------------------------------------------------------------
    memory_targets: list[tuple] = field(default_factory=lambda: [
        # ("gold",       0x00000000, "int"),   # placeholder – replace with real address
        # ("troops",     0x00000000, "int"),
        # ("stamina",    0x00000000, "float"),
    ])

"""One edge dispatcher for the firmware's held keys, used by both companions."""


class HotkeyState:
    MODE_KEYS = {
        "compose": (0x7C, 0x78),
        "dictate": (0x7D, 0x79),
        "paste": (0x7E, 0x7A),
        "media": (0x7F, 0x77),
        "library": (0x80, 0x76),
        "onenote_display": (0x81, 0x75),  # F18 / Ctrl+Alt+Shift+F6; optional, off by default
    }
    DEFAULT_MODES = ("compose", "dictate", "paste", "media", "library")

    def __init__(self, enabled_modes=None):
        modes = tuple(self.DEFAULT_MODES if enabled_modes is None else enabled_modes)
        unknown = [mode for mode in modes if mode not in self.MODE_KEYS]
        if unknown:
            raise ValueError(f"Unsupported hotkey mode: {unknown[0]}")
        self.enabled_modes = modes
        self.held = {mode: set() for mode in modes}

    def update(self, is_down):
        events = []
        modifiers = all(is_down(key) for key in (0x11, 0x10, 0x12))
        for mode in self.enabled_modes:
            extended, standard = self.MODE_KEYS[mode]
            previous = self.held[mode]
            # Once a chord starts, track its function key until release, even if
            # Windows or another keyboard releases a modifier in the meantime.
            current = {key for key in previous if is_down(key)}
            if is_down(extended):
                current.add(extended)
            if modifiers and is_down(standard):
                current.add(standard)
            if current and not previous:
                events.append((mode, "down"))
            elif previous and not current:
                events.append((mode, "up"))
            self.held[mode] = current
        return events

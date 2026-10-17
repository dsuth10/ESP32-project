"""One edge dispatcher for the firmware's held keys, used by both companions."""


class HotkeyState:
    def __init__(self):
        self.held = {mode: set() for mode in ("compose", "dictate", "paste")}

    def update(self, is_down):
        events = []
        modifiers = all(is_down(key) for key in (0x11, 0x10, 0x12))
        for mode, extended, standard in (
            ("compose", 0x7C, 0x78),
            ("dictate", 0x7D, 0x79),
            ("paste", 0x7E, 0x7A),
        ):
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

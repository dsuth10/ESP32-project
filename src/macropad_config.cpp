#include "macropad_config.h"

const MacroProfile PROFILES[NUM_PAGES] = {
  // Page 0: Media & Volume
  {
    "Media & Audio",
    0x39BF, // Indigo accent
    6,      // 6 buttons
    {
      { "PLAY/PAUSE", "[ > / || ]",  0x18F4, 0x529F, ACTION_MEDIA, &KEY_MEDIA_PLAY_PAUSE, 0, 0, 0, 0, nullptr },
      { "MUTE",       "[ Audio Off ]",0x18F4, 0x529F, ACTION_MEDIA, &KEY_MEDIA_MUTE,       0, 0, 0, 0, nullptr },
      { "VOL UP",     "[ + ]",        0x2176, 0x633F, ACTION_MEDIA, &KEY_MEDIA_VOLUME_UP,  0, 0, 0, 0, nullptr },
      { "PREV",       "[ |<< ]",      0x18F4, 0x529F, ACTION_MEDIA, &KEY_MEDIA_PREVIOUS_TRACK, 0, 0, 0, 0, nullptr },
      { "NEXT",       "[ >>| ]",      0x18F4, 0x529F, ACTION_MEDIA, &KEY_MEDIA_NEXT_TRACK, 0, 0, 0, 0, nullptr },
      { "VOL DOWN",   "[ - ]",        0x2176, 0x633F, ACTION_MEDIA, &KEY_MEDIA_VOLUME_DOWN,0, 0, 0, 0, nullptr }
    }
  },

  // Page 1: Productivity & Editing
  {
    "Productivity",
    0x04F2, // Emerald green accent
    6,      // 6 buttons
    {
      { "COPY",       "Ctrl + C",     0x0270, 0x1CB2, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 'c', nullptr },
      { "PASTE",      "Ctrl + V",     0x0270, 0x1CB2, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 'v', nullptr },
      { "UNDO",       "Ctrl + Z",     0x0270, 0x1CB2, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 'z', nullptr },
      { "SELECT ALL", "Ctrl + A",     0x0270, 0x1CB2, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 'a', nullptr },
      { "SAVE",       "Ctrl + S",     0x0312, 0x2D75, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 's', nullptr },
      { "CUT",        "Ctrl + X",     0x0270, 0x1CB2, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, 0, 0, 'x', nullptr }
    }
  },

  // Page 2: Windows System & Utilities
  {
    "Windows Tools",
    0xFD20, // Warm amber accent
    6,      // 6 buttons
    {
      { "SNIP/SHOT",  "Win+Shift+S",  0x4A69, 0xFDA0, ACTION_KEY_COMBO, nullptr, KEY_LEFT_GUI, KEY_LEFT_SHIFT, 0, 's', nullptr },
      { "TASK MGR",   "Ctrl+Shft+Esc",0x4A69, 0xFDA0, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, KEY_LEFT_SHIFT, 0, KEY_ESC, nullptr },
      { "DESKTOP",    "Win + D",      0x39E7, 0xD4C0, ACTION_KEY_COMBO, nullptr, KEY_LEFT_GUI, 0, 0, 'd', nullptr },
      { "EXPLORER",   "Win + E",      0x39E7, 0xD4C0, ACTION_KEY_COMBO, nullptr, KEY_LEFT_GUI, 0, 0, 'e', nullptr },
      { "LOCK PC",    "Win + L",      0x5184, 0xF900, ACTION_KEY_COMBO, nullptr, KEY_LEFT_GUI, 0, 0, 'l', nullptr },
      { "CALCULATOR", "Open App",     0x39E7, 0xD4C0, ACTION_MEDIA, &KEY_MEDIA_CALCULATOR, 0, 0, 0, 0, nullptr }
    }
  },

  // Page 3: Custom Keys (Only 3 Buttons)
  {
    "Custom Keys",
    0x07FF, // Vibrant Cyan accent
    3,      // 3 buttons!
    {
      { "WIN + CTRL + SPACE", "Ctrl + Win + Spacebar", 0x0273, 0x07BF, ACTION_KEY_COMBO, nullptr, KEY_LEFT_CTRL, KEY_LEFT_GUI, 0, ' ', nullptr },
      { "ENTER",              "Return [Enter]",        0x126E, 0x243F, ACTION_KEY_COMBO, nullptr, 0, 0, 0, KEY_RETURN, nullptr },
      { "SHIFT + ENTER",      "New Line in Chat",      0x39AF, 0x7BDF, ACTION_KEY_COMBO, nullptr, KEY_LEFT_SHIFT, 0, 0, KEY_RETURN, nullptr },
      { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr },
      { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr },
      { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr }
    }
  }
};

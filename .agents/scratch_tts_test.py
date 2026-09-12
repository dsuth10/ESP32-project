import re

def sanitize_for_tts(text: str, max_chars: int = 260) -> str:
    if not text:
        return ""
    # Strip dangerous punctuation for Qwen-TTS (colons & semicolons cause phonemizer loops)
    text = text.replace(":", ", ").replace(";", ", ")
    text = text.replace("ESP32", "ESP 32").replace("esp32", "ESP 32")
    # Clean up non-pronounceable markdown / technical symbols
    for ch in ['*', '#', '`', '[', ']', '(', ')', '{', '}', '<', '>', '|', '\\', '/', '"', '_', '~']:
        text = text.replace(ch, " ")
    # Normalize multiple whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    if len(text) > max_chars:
        best_cut = -1
        for sep in [". ", "! ", "? "]:
            pos = 0
            while True:
                idx = text.find(sep, pos)
                if idx == -1:
                    break
                cut_idx = idx + 1
                if 100 <= cut_idx <= max_chars:
                    if cut_idx > best_cut:
                        best_cut = cut_idx
                pos = idx + 1
        if best_cut != -1:
            text = text[:best_cut]
        else:
            parts = text[:max_chars].rsplit(" ", 1)
            text = (parts[0] if len(parts) > 1 else text[:max_chars]) + "."
    return text.strip()

limerick = "A fisherman fond of the Moy, Caught salmon and pike with great joy. Said he with a cheer, The fish gather here, For tackle and tales I am the boy!"
print("Length:", len(limerick))
print("TTS Output:")
print(sanitize_for_tts(limerick))

long_text = "Here is the first sentence that is quite complete. Here is the second sentence that adds important information. And here is a third sentence that goes beyond the limit and should be trimmed safely."
print("\nLong text length:", len(long_text))
print("Long text TTS Output:")
print(sanitize_for_tts(long_text, max_chars=140))

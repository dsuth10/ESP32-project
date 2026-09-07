import socket
import json

def blender_exec(code: str, strict_json: bool = False) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15.0)
    try:
        s.connect(("127.0.0.1", 9876))
        payload = json.dumps({"type": "execute", "code": code, "strict_json": strict_json}) + "\0"
        s.sendall(payload.encode("utf-8"))
        buf = bytearray()
        while b"\0" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
        null_idx = buf.index(b"\0") if b"\0" in buf else len(buf)
        return json.loads(buf[:null_idx])
    finally:
        s.close()

if __name__ == "__main__":
    code = """
import bpy
result = {
    'version': bpy.app.version_string,
    'objects': [o.name for o in bpy.data.objects]
}
"""
    res = blender_exec(code)
    print("Blender response:")
    print(json.dumps(res, indent=2))

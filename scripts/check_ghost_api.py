"""End-to-end check against a test Ghost (never production), standard library only.

  GHOST_URL=http://localhost:2368 GHOST_ADMIN_KEY=id:secret SERVICE_URL=http://127.0.0.1:8000 \
  python3 scripts/check_ghost_api.py photo.jpg

Filters the photo, uploads it, creates a draft tagged #ilustracion, swaps its featured image
(with and without updated_at, to see whether Ghost requires it) and deletes the draft.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

GHOST_API = os.environ["GHOST_URL"].rstrip("/") + "/ghost/api/admin"
KEY_ID, SECRET = os.environ["GHOST_ADMIN_KEY"].split(":")
SERVICE_URL = os.environ.get("SERVICE_URL", "http://127.0.0.1:8000")


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def admin_token():
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KEY_ID}).encode())
    now = int(time.time())
    payload = b64url(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
    signature = hmac.new(bytes.fromhex(SECRET), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url(signature)}"


def ghost(method, path, data=None, content_type="application/json"):
    request = urllib.request.Request(GHOST_API + path, data=data, method=method, headers={
        "Authorization": f"Ghost {admin_token()}", "Accept-Version": "v6.0", "Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:300]


photo = open(sys.argv[1], "rb").read()
with urllib.request.urlopen(urllib.request.Request(f"{SERVICE_URL}/filter?seed=check-ghost-api", data=photo),
                            timeout=180) as response:
    png, variant = response.read(), response.headers["X-Variant"]
print("1. filter ok", variant)

boundary = uuid.uuid4().hex
body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="check-ghost-api.png"\r\n'
        "Content-Type: image/png\r\n\r\n").encode() + png + f"\r\n--{boundary}--\r\n".encode()
code, result = ghost("POST", "/images/upload/", body, f"multipart/form-data; boundary={boundary}")
assert code == 201, (code, result)
image_url = result["images"][0]["url"]
print("2. upload ok", image_url)

draft = {"posts": [{"title": "Brand filter check", "status": "draft", "tags": [{"name": "#ilustracion"}]}]}
code, result = ghost("POST", "/posts/", json.dumps(draft).encode())
assert code == 201, (code, result)
post_id = result["posts"][0]["id"]
print("3. draft created", post_id)

code, _ = ghost("PUT", f"/posts/{post_id}/", json.dumps({"posts": [{"feature_image": image_url}]}).encode())
print("4. PUT without updated_at ->", code, "(required)" if code >= 400 else "(not required)")

code, result = ghost("GET", f"/posts/{post_id}/")
update = {"posts": [{"feature_image": image_url, "updated_at": result["posts"][0]["updated_at"]}]}
code, result = ghost("PUT", f"/posts/{post_id}/", json.dumps(update).encode())
assert code == 200 and result["posts"][0]["feature_image"] == image_url, (code, result)
print("5. featured image swapped ok")

print("6. draft deleted", ghost("DELETE", f"/posts/{post_id}/")[0])

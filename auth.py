import base64, hashlib, hmac, json, os, time
def _key(): return (os.getenv("JWT_SECRET") or "socialgraph-demo-secret").encode()
def hash_pw(pw):
    salt = os.urandom(8).hex()
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()
def verify_pw(pw, stored):
    try:
        salt, h = stored.split("$")
        return hmac.compare_digest(h, hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex())
    except Exception:
        return False
def make_token(uid, hours=8):
    body = base64.urlsafe_b64encode(json.dumps({"uid": uid, "exp": int(time.time()) + hours * 3600}).encode()).decode()
    return body + "." + hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
def read_token(t):
    try:
        body, sig = t.split(".")
        if not hmac.compare_digest(sig, hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()): return None
        d = json.loads(base64.urlsafe_b64decode(body))
        return d["uid"] if d["exp"] > time.time() else None
    except Exception:
        return None

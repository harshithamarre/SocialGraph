import os, time, uuid
from collections import deque
from fastapi import FastAPI, Response, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from neo4j import GraphDatabase
load_dotenv()
from auth import hash_pw, verify_pw, make_token, read_token
from catalog import MUTUAL, SHARED, LIKESQ, HYB, RECPOSTS, CATALOG
driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")))
ME = int(os.getenv("ME_ID", 1))  # the one person this site belongs to
app = FastAPI(title="SocialGraph")
def uid(authorization: str = Header(None)):   # the logged-in user, taken ONLY from the signed token
    u = read_token(authorization.split()[-1]) if authorization else None
    if u is None: raise HTTPException(401, "Please log in")
    return u

LOG = deque(maxlen=80)   # live query log shown on the DBMS Queries page
def note(cy, p, ms):
    LOG.appendleft({"t": time.strftime("%H:%M:%S"), "ms": ms, "cypher": cy.strip(),
                    "owner": p.get("id") or p.get("a") or p.get("m"), "params": {k: (v if isinstance(v, (int, float, str)) else "...") for k, v in p.items()}})

def q(cy, _log=True, **p):
    t = time.perf_counter()
    with driver.session() as s: rows = [r.data() for r in s.run(cy, **p)]
    ms = round((time.perf_counter() - t) * 1000, 2)
    if _log: note(cy, p, ms)
    return rows, ms
qs = lambda cy, **p: q(cy, _log=False, **p)   # quiet version for page-refresh reads

class Ints(BaseModel): interests: list[str]

class Login(BaseModel): email: str; password: str
class Signup(BaseModel): name: str; email: str; password: str

def make_user(name, email, pw):
    email = email.strip().lower()
    if "@" not in email or len(name.strip()) < 2: raise HTTPException(400, "Enter a valid name and email")
    if len(pw) < 6: raise HTTPException(400, "Password needs at least 6 characters")
    if qs("MATCH (u:User {email:$e}) RETURN u.id AS id", e=email)[0]: raise HTTPException(400, "That email is already registered")
    i = qs("MATCH (u:User) RETURN coalesce(max(u.id),0)+1 AS id")[0][0]["id"]
    qs("CREATE (:User {id:$i,name:$n,email:$e,pw:$pw})", i=i, n=name.strip(), e=email, pw=hash_pw(pw)); return i

@app.post("/api/login")
def login(b: Login):
    r = qs("MATCH (u:User {email:$e}) RETURN u.id AS id,u.name AS name,u.pw AS pw", e=b.email.strip().lower())[0]
    if not r or not verify_pw(b.password, r[0]["pw"]): raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(r[0]["id"]), "name": r[0]["name"]}

@app.post("/api/signup")
def signup(b: Signup):
    i = make_user(b.name, b.email, b.password)
    return {"token": make_token(i), "name": b.name.strip()}

@app.get("/api/me")
def me(u: int = Depends(uid)):
    r = qs("""MATCH (u:User {id:$id}) RETURN u.id AS id,u.name AS name,COUNT{(u)-[:FRIEND]-()} AS friends,
             [(u)-[:LIKES]->(i) | i.name] AS interests""", id=u)[0]
    if not r: raise HTTPException(500, "Run load_neo4j.py first")
    return r[0]

@app.get("/api/system")
def system(u: int = Depends(uid)):
    n = qs("MATCH (n) RETURN count(n) AS n")[0][0]["n"]; r = qs("MATCH ()-[r]->() RETURN count(r) AS n")[0][0]["n"]
    return {"nodes": n, "rels": r}

@app.get("/api/interests")
def interests(u: int = Depends(uid)): return [x["n"] for x in qs("MATCH (i:Interest) RETURN i.name AS n ORDER BY n")[0]]

@app.post("/api/interests")
def set_ints(b: Ints, u: int = Depends(uid)):
    q("MATCH (:User {id:$id})-[r:LIKES]->() DELETE r", id=u)
    q("UNWIND $l AS x MATCH (u:User {id:$id}),(i:Interest {name:x}) MERGE (u)-[:LIKES]->(i)", l=b.interests, id=u)
    return {"ok": True}

@app.get("/api/recommend/{kind}")
def recommend(kind: str, w1: float = 0.5, w2: float = 0.3, w3: float = 0.2, u: int = Depends(uid)):
    if kind in ("mutual", "interest", "postlikes"):
        cy, word = {"mutual": (MUTUAL, "mutual friend(s)"), "interest": (SHARED, "shared interest(s)"), "postlikes": (LIKESQ, "post(s) we both liked")}[kind]
        rows, ms = q(cy, id=u, k=8)
        for r in rows: r["why"] = f'{r["score"]} {word}'
        return {"rows": rows, "ms": ms, "cypher": cy, "key": kind}
    if kind == "hybrid":
        rows, ms = q(HYB, id=u, k=200)
        mm = max([r["m"] for r in rows] or [1]) or 1; ms_ = max([r["s"] for r in rows] or [1]) or 1; ml = max([r["l"] for r in rows] or [1]) or 1
        tot = (w1 + w2 + w3) or 1
        for r in rows:
            r["score"] = round((w1 * r["m"] / mm + w2 * r["s"] / ms_ + w3 * r["l"] / ml) / tot, 3)
            r["why"] = f'{r["m"]} mutual · {r["s"]} interests · {r["l"]} post-likes'
        rows = sorted(rows, key=lambda r: -r["score"])[:8]
        return {"rows": rows, "ms": ms, "key": "hybrid", "cypher": HYB + f"\n\n// weights applied in the app: {w1} x mutual + {w2} x interests + {w3} x post-likes (each divided by its max)"}
    if kind == "posts":
        rows, ms = q(RECPOSTS, id=u, k=6)
        for r in rows: r["why"] = f'Matches your interest in {r["tag"]}' + (f' · liked by {r["friend_likes"]} friend(s)' if r["friend_likes"] else "")
        return {"rows": rows, "ms": ms, "cypher": RECPOSTS, "key": "rec_posts"}
    raise HTTPException(404, "Unknown type")

# ---------- DBMS Queries page ----------
@app.get("/api/dbms/queries")
def dbms_queries(u: int = Depends(uid)): return CATALOG

@app.get("/api/dbms/log")
def dbms_log(u: int = Depends(uid)): return [x for x in LOG if x["owner"] == u]

def plan_lines(n, d=0):
    ar = n.get("args") or {}
    h = n.get("dbHits", ar.get("DbHits", 0)) or 0; r = n.get("rows", ar.get("Rows", 0))
    out = ["  " * d + f'{n.get("operatorType", "?")}   rows={r}   dbHits={h}']
    for c in n.get("children") or []:
        o, t = plan_lines(c, d + 1); out += o; h += t
    return out, h

@app.get("/api/dbms/run/{key}")
def dbms_run(key: str, other: int = 1500, profile: int = 0, u: int = Depends(uid)):
    e = next((x for x in CATALOG if x["key"] == key), None)
    if not e or not e["run"]: raise HTTPException(400, "This query is display-only because it changes data")
    params = {"id": u, "k": 10, "other": other}; t = time.perf_counter(); plan = hits = None
    with driver.session() as s:
        res = s.run(("PROFILE " if profile and e["profile"] else "") + e["cypher"], **params)
        rows = [r.data() for r in res]; summ = res.consume()
    ms = round((time.perf_counter() - t) * 1000, 2); note(e["cypher"], params, ms)
    if profile and e["profile"] and getattr(summ, "profile", None):
        lines, hits = plan_lines(summ.profile); plan = "\n".join(lines)
    return {"rows": rows[:25], "total": len(rows), "ms": ms, "hits": hits, "plan": plan}

@app.get("/api/feed")
def feed(u: int = Depends(uid)):
    return q("""MATCH (a:User)-[:POSTED]->(p:Post) WHERE a.id=$id OR (a)-[:FRIEND]-(:User {id:$id})
                RETURN p.id AS id,p.text AS text,p.ts AS ts,p.media AS media,p.type AS type,a.id AS aid,a.name AS author,
                  COUNT{(p)<-[:LIKED]-()} AS likes, EXISTS{(:User {id:$id})-[:LIKED]->(p)} AS liked
                ORDER BY p.ts DESC LIMIT 30""", id=u)[0]

EXT = {"jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image", "mp4": "video", "webm": "video", "mov": "video"}

@app.post("/api/post")
async def new_post(text: str = Form(""), file: UploadFile = File(None), u: int = Depends(uid)):
    t = text.strip()[:280]; media = ""; typ = "text"
    if file is not None and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in EXT: raise HTTPException(400, "Use a JPG, PNG, GIF, WEBP, MP4 or WEBM file")
        data = await file.read()
        if len(data) > 50 * 1024 * 1024: raise HTTPException(400, "File is over 50 MB")
        os.makedirs("static/uploads", exist_ok=True); name = f"{uuid.uuid4().hex}.{ext}"
        with open(f"static/uploads/{name}", "wb") as f: f.write(data)
        media = "/uploads/" + name; typ = EXT[ext]
    if not t and not media: raise HTTPException(400, "Write something or add a photo or video")
    pid = q("MATCH (p:Post) RETURN coalesce(max(p.id),0)+1 AS id")[0][0]["id"]
    q("MATCH (u:User {id:$id}) CREATE (u)-[:POSTED]->(:Post {id:$pid,text:$t,ts:$ts,media:$m,type:$ty})",
      id=u, pid=pid, t=t, ts=int(time.time() * 1000), m=media, ty=typ)
    return {"ok": True}

@app.post("/api/like/{pid}")
def like(pid: int, u: int = Depends(uid)):
    r = q("MATCH (:User {id:$id})-[l:LIKED]->(:Post {id:$p}) DELETE l RETURN 1 AS x", id=u, p=pid)[0]
    if not r: q("MATCH (u:User {id:$id}),(p:Post {id:$p}) MERGE (u)-[:LIKED]->(p)", id=u, p=pid)
    return {"ok": True}

@app.get("/api/friends")
def friends(u: int = Depends(uid)): return qs("MATCH (:User {id:$id})-[:FRIEND]-(f:User) RETURN f.id AS id,f.name AS name ORDER BY name", id=u)[0]

@app.get("/api/requests")
def requests(u: int = Depends(uid)): return qs("MATCH (o:User)-[:REQUESTED]->(:User {id:$id}) RETURN o.id AS id,o.name AS name", id=u)[0]

@app.post("/api/request/{o}")
def send(o: int, u: int = Depends(uid)):
    q("""MATCH (a:User {id:$a}),(b:User {id:$b}) WHERE a<>b AND NOT (a)-[:FRIEND]-(b) AND NOT (b)-[:REQUESTED]->(a)
         MERGE (a)-[:REQUESTED]->(b)""", a=u, b=o); return {"ok": True}

@app.post("/api/accept/{o}")
def accept(o: int, u: int = Depends(uid)):
    q("MATCH (x:User {id:$o})-[r:REQUESTED]->(m:User {id:$m}) DELETE r MERGE (x)-[:FRIEND]->(m)", o=o, m=u); return {"ok": True}

@app.post("/api/decline/{o}")
def decline(o: int, u: int = Depends(uid)):
    q("MATCH (:User {id:$o})-[r:REQUESTED]->(:User {id:$m}) DELETE r", o=o, m=u); return {"ok": True}

@app.post("/api/unfriend/{o}")
def unfriend(o: int, u: int = Depends(uid)):
    q("MATCH (:User {id:$a})-[r:FRIEND]-(:User {id:$b}) DELETE r", a=u, b=o); return {"ok": True}

@app.get("/api/search")
def search(t: str, u: int = Depends(uid)):
    return q("""MATCH (c:User) WHERE toLower(c.name) CONTAINS toLower($t) AND c.id<>$id
                RETURN c.id AS id,c.name AS name, EXISTS{(:User {id:$id})-[:FRIEND]-(c)} AS friend,
                  EXISTS{(:User {id:$id})-[:REQUESTED]-(c)} AS pending LIMIT 8""", t=t, id=u)[0]

@app.get("/api/path/{o}")
def path(o: int, u: int = Depends(uid)):
    r, ms = q("""MATCH (a:User {id:$a}),(b:User {id:$b}) MATCH p=shortestPath((a)-[:FRIEND*..6]-(b))
                 RETURN [n IN nodes(p) | n.name] AS names""", a=u, b=o)
    return {"names": r[0]["names"] if r else None, "ms": ms}


# ================= ADMIN (DBMS control room) =================
import secrets, hmac, csv, statistics
ADMIN_PW = os.getenv("ADMIN_PASSWORD", "admin1234"); TOKENS = set()
class AdminLogin(BaseModel): password: str
class NewUser(BaseModel): name: str; email: str = ""; password: str = "demo1234"
class Pair(BaseModel): a: int; b: int

@app.post("/api/admin/login")
def admin_login(b: AdminLogin):
    if not hmac.compare_digest(b.password, ADMIN_PW): raise HTTPException(401, "Wrong admin password")
    t = secrets.token_hex(16); TOKENS.add(t); return {"token": t}

def admin(x_admin: str = Header(None)):
    if x_admin not in TOKENS: raise HTTPException(401, "Admin login required")

SAMPLE = "MATCH (u:User) WITH u, rand() AS r ORDER BY r LIMIT $n RETURN u.id AS id"
D2 = "MATCH (u:User {id:$id})-[:FRIEND]-(f:User)-[:FRIEND]-(c:User) WHERE c<>u RETURN count(DISTINCT c) AS n"

@app.get("/api/admin/overview")
def overview(_=Depends(admin)):
    r = qs("""MATCH (u:User) WITH count(u) AS users MATCH (p:Post) WITH users,count(p) AS posts
             MATCH ()-[f:FRIEND]->() WITH users,posts,count(f) AS fr MATCH ()-[l:LIKES]->() RETURN users,posts,fr,count(l) AS likes""")[0][0]
    n = qs("MATCH (n) RETURN count(n) AS n")[0][0]["n"]; rel = qs("MATCH ()-[r]->() RETURN count(r) AS n")[0][0]["n"]
    return {"users": r["users"], "posts": r["posts"], "friendships": r["fr"], "interest_links": r["likes"],
            "nodes": n, "relationships": rel, "avg_friends": round(2 * r["fr"] / max(r["users"], 1), 1)}

@app.get("/api/admin/graph")
def graph(user: int = 1, _=Depends(admin)):
    m = qs("MATCH (u:User {id:$i}) RETURN u.id AS id,u.name AS name", i=user)[0]
    if not m: raise HTTPException(404, "No such user")
    fr = qs("MATCH (:User {id:$i})-[:FRIEND]-(f:User) RETURN f.id AS id,f.name AS name LIMIT 12", i=user)[0]
    sg = qs(MUTUAL, id=user, k=6)[0]
    ed = qs("MATCH (a:User)-[:FRIEND]-(b:User) WHERE a.id IN $f AND b.id IN $c RETURN DISTINCT a.id AS a,b.id AS b",
           f=[x["id"] for x in fr], c=[x["id"] for x in sg])[0]
    return {"me": m[0], "friends": fr, "suggestions": sg, "edges": ed}

@app.post("/api/admin/benchmark")
def benchmark(_=Depends(admin)):
    ids = [r["id"] for r in qs(SAMPLE, n=20)[0]]
    Q = {"Friend-of-friend (depth 2)": (MUTUAL, {"k": 10}), "Interest-based": (SHARED, {"k": 10}), "Shared post likes": (LIKESQ, {"k": 10}), "Hybrid (single query)": (HYB, {"k": 200}),
         "Reach within 3 hops (depth 3)": ("MATCH (u:User {id:$id})-[:FRIEND*1..3]-(c:User) WHERE c<>u RETURN count(DISTINCT c) AS n", {})}
    users = qs("MATCH (u:User) RETURN count(u) AS n")[0][0]["n"]; out = []
    for name, (cy, extra) in Q.items():
        qs(cy, id=ids[0], **extra)  # warm-up
        t = [qs(cy, id=i, **extra)[1] for i in ids]
        out.append({"query": name, "avg_ms": round(statistics.mean(t), 2), "max_ms": max(t)})
    new = not os.path.exists("results.csv")
    with open("results.csv", "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["users", "query", "avg_ms", "max_ms", "time"])
        for r in out: w.writerow([users, r["query"], r["avg_ms"], r["max_ms"], time.strftime("%Y-%m-%d %H:%M")])
    return {"users": users, "runs": len(ids), "rows": out}

@app.post("/api/admin/index-test")
def index_test(_=Depends(admin)):
    ids = [r["id"] for r in qs(SAMPLE, n=20)[0]]
    run = lambda: round(statistics.mean(qs(D2, id=i)[1] for i in ids), 2)
    run(); with_idx = run()
    qs("DROP CONSTRAINT u_id IF EXISTS")
    try: run(); without = run()
    finally: qs("CREATE CONSTRAINT u_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
    return {"with_index_ms": with_idx, "without_index_ms": without, "speedup": round(without / max(with_idx, 0.01), 1)}

@app.post("/api/admin/quality")
def quality(_=Depends(admin)):
    pairs = qs("""MATCH (u:User)-[:FRIEND]-(h:User) WHERE COUNT{(u)-[:FRIEND]-()} >= 3
                 WITH u,h,rand() AS r ORDER BY r LIMIT 40 RETURN u.id AS u, h.id AS h""")[0]
    cy = """MATCH (u:User {id:$u}) MATCH (u)-[:FRIEND]-(f:User)-[:FRIEND]-(c:User)
            WHERE f.id<>$h AND c<>u AND (c.id=$h OR NOT (u)-[:FRIEND]-(c))
            WITH c, count(DISTINCT f) AS s ORDER BY s DESC LIMIT 10 RETURN collect(c.id) AS top"""
    hits = sum(1 for p in pairs if p["h"] in qs(cy, u=p["u"], h=p["h"])[0][0]["top"])
    return {"tested": len(pairs), "hits": hits, "hit_rate": round(100 * hits / max(len(pairs), 1), 1)}

@app.get("/api/admin/users")
def admin_users(response: Response, t: str = "", skip: int = 0, limit: int = 30, sort: str = "newest", _=Depends(admin)):
    # sort: newest (highest id first, so new sign-ups show on top), oldest, friends (most connected first)
    order = {"newest": "c.id DESC", "oldest": "c.id ASC", "friends": "friends DESC, c.id ASC"}.get(sort, "c.id DESC")
    limit = max(1, min(limit, 200)); skip = max(0, skip)
    where = "WHERE toLower(c.name) CONTAINS toLower($t) OR toLower(coalesce(c.email,'')) CONTAINS toLower($t) OR toString(c.id)=$t"
    total = qs(f"MATCH (c:User) {where} RETURN count(c) AS n", t=t)[0][0]["n"]
    response.headers["X-Total-Count"] = str(total)   # the page can use this to show "1-30 of 3001" and build pagination
    return qs(f"""MATCH (c:User) {where}
                  RETURN c.id AS id,c.name AS name,c.email AS email,COUNT{{(c)-[:FRIEND]-()}} AS friends
                  ORDER BY {order} SKIP $skip LIMIT $limit""", t=t, skip=skip, limit=limit)[0]

@app.get("/api/admin/users/{i}/friends")
def admin_user_friends(i: int, _=Depends(admin)):
    return qs("MATCH (:User {id:$i})-[:FRIEND]-(f:User) RETURN f.id AS id,f.name AS name ORDER BY name", i=i)[0]

@app.post("/api/admin/users")
def admin_add(b: NewUser, _=Depends(admin)):
    if not b.name.strip(): raise HTTPException(400, "Name is required")
    i = qs("MATCH (u:User) RETURN coalesce(max(u.id),0)+1 AS id")[0][0]["id"]
    email = b.email.strip().lower() or f"user{i}@demo.com"
    if qs("MATCH (u:User {email:$e}) RETURN u.id AS id", e=email)[0]: raise HTTPException(400, "That email is already registered")
    qs("CREATE (:User {id:$i,name:$n,email:$e,pw:$pw})", i=i, n=b.name.strip(), e=email, pw=hash_pw(b.password))
    return {"id": i, "name": b.name.strip(), "email": email, "friends": 0}

@app.delete("/api/admin/users/{i}")
def admin_del(i: int, _=Depends(admin)):
    qs("MATCH (c:User {id:$i}) OPTIONAL MATCH (c)-[:POSTED]->(p:Post) DETACH DELETE p, c", i=i); return {"ok": True}

@app.post("/api/admin/friendship")
def admin_friend(b: Pair, _=Depends(admin)):
    if b.a == b.b: raise HTTPException(400, "A user cannot befriend themselves")
    if len(qs("MATCH (u:User) WHERE u.id IN [$a,$b] RETURN u.id AS id", a=b.a, b=b.b)[0]) < 2: raise HTTPException(404, "One of the users does not exist")
    qs("MATCH (x:User {id:$a}),(y:User {id:$b}) WHERE NOT (x)-[:FRIEND]-(y) CREATE (x)-[:FRIEND]->(y)", a=b.a, b=b.b)
    # return fresh counts for both people so the list can update without a full reload
    return {"ok": True, "users": qs("MATCH (u:User) WHERE u.id IN [$a,$b] RETURN u.id AS id,u.name AS name,COUNT{(u)-[:FRIEND]-()} AS friends", a=b.a, b=b.b)[0]}

app.mount("/", StaticFiles(directory="static", html=True), name="static")

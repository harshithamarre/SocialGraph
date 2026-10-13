# usage: python load_neo4j.py   (WIPES the database, then loads the CSVs)
import csv, os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from auth import hash_pw
load_dotenv()
d = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
rd = lambda f: list(csv.DictReader(open(f, encoding="utf-8")))
def ch(l, n=1000):
    for i in range(0, len(l), n): yield l[i:i + n]
I = lambda r, *k: {**r, **{x: int(r[x]) for x in k}}
PW = hash_pw("demo1234")  # shared demo password for the seeded accounts
with d.session() as s:
    s.run("MATCH (n) DETACH DELETE n")
    for r in s.run("SHOW CONSTRAINTS YIELD name RETURN name").data(): s.run(f"DROP CONSTRAINT `{r['name']}` IF EXISTS")
    for r in s.run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name").data(): s.run(f"DROP INDEX `{r['name']}` IF EXISTS")
    for c in ["CREATE CONSTRAINT u_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
              "CREATE CONSTRAINT i_name IF NOT EXISTS FOR (i:Interest) REQUIRE i.name IS UNIQUE",
              "CREATE CONSTRAINT p_id IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE", "CREATE CONSTRAINT u_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE"]: s.run(c)
    s.run("UNWIND $r AS r CREATE (:Interest {name:r.name})", r=rd("interests.csv"))
    for c in ch([I(r, "id") for r in rd("users.csv")]): s.run("UNWIND $r AS r CREATE (:User {id:r.id,name:r.name,email:'user'+toString(r.id)+'@demo.com',pw:$pw})", r=c, pw=PW)
    for c in ch([I(r, "a", "b") for r in rd("friends.csv")]): s.run("UNWIND $r AS r MATCH (a:User {id:r.a}),(b:User {id:r.b}) CREATE (a)-[:FRIEND]->(b)", r=c)
    for c in ch([{"u": int(r["user_id"]), "i": r["interest"]} for r in rd("likes.csv")]): s.run("UNWIND $r AS r MATCH (u:User {id:r.u}),(i:Interest {name:r.i}) CREATE (u)-[:LIKES]->(i)", r=c)
    for c in ch([I(r, "id", "author", "ts") for r in rd("posts.csv")]): s.run("UNWIND $r AS r MATCH (u:User {id:r.author}),(i:Interest {name:r.tag}) CREATE (u)-[:POSTED]->(:Post {id:r.id,text:r.text,ts:r.ts,media:r.media,type:CASE WHEN r.media='' THEN 'text' ELSE 'image' END})-[:TAGGED]->(i)", r=c)
    for c in ch([{"u": int(r["user_id"]), "p": int(r["post_id"])} for r in rd("post_likes.csv")]): s.run("UNWIND $r AS r MATCH (u:User {id:r.u}),(p:Post {id:r.p}) MERGE (u)-[:LIKED]->(p)", r=c)
    for r in rd("requests.csv"): s.run("MATCH (a:User {id:$a}),(b:User {id:$b}) CREATE (a)-[:REQUESTED]->(b)", a=int(r["from"]), b=int(r["to"]))
    print(s.run("MATCH (n) RETURN count(n) AS n").single()["n"], "nodes,", s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"], "relationships")

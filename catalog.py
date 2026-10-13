"""Central query registry: every Cypher query used by the app, with explanations (shown on the DBMS Queries page)."""
MUTUAL = """MATCH (me:User {id:$id})-[:FRIEND]-(f:User)-[:FRIEND]-(c:User)
WHERE c <> me AND NOT (me)-[:FRIEND]-(c) AND NOT (me)-[:REQUESTED]-(c)
RETURN c.id AS id, c.name AS name, count(DISTINCT f) AS score
ORDER BY score DESC LIMIT $k"""
SHARED = """MATCH (me:User {id:$id})-[:LIKES]->(i:Interest)<-[:LIKES]-(c:User)
WHERE c <> me AND NOT (me)-[:FRIEND]-(c) AND NOT (me)-[:REQUESTED]-(c)
RETURN c.id AS id, c.name AS name, count(DISTINCT i) AS score
ORDER BY score DESC LIMIT $k"""
LIKESQ = """MATCH (me:User {id:$id})-[:LIKED]->(p:Post)<-[:LIKED]-(c:User)
WHERE c <> me AND NOT (me)-[:FRIEND]-(c) AND NOT (me)-[:REQUESTED]-(c)
RETURN c.id AS id, c.name AS name, count(DISTINCT p) AS score
ORDER BY score DESC LIMIT $k"""
HYB = """MATCH (me:User {id:$id})-[:FRIEND]-(f:User)-[:FRIEND]-(c:User)
WHERE c <> me AND NOT (me)-[:FRIEND]-(c) AND NOT (me)-[:REQUESTED]-(c)
WITH me, c, count(DISTINCT f) AS m
OPTIONAL MATCH (me)-[:LIKES]->(i:Interest)<-[:LIKES]-(c)
WITH me, c, m, count(DISTINCT i) AS s
OPTIONAL MATCH (me)-[:LIKED]->(p:Post)<-[:LIKED]-(c)
WITH c, m, s, count(DISTINCT p) AS l
RETURN c.id AS id, c.name AS name, m, s, l
ORDER BY m + s + l DESC LIMIT $k"""
RECPOSTS = """MATCH (me:User {id:$id})-[:LIKES]->(i:Interest)<-[:TAGGED]-(p:Post)<-[:POSTED]-(a:User)
WHERE a <> me AND NOT (me)-[:LIKED]->(p)
WITH me, i, p, a, COUNT { (p)<-[:LIKED]-(:User)-[:FRIEND]-(me) } AS fl, COUNT { (p)<-[:LIKED]-() } AS total
RETURN p.id AS id, p.text AS text, p.media AS media, p.type AS type, p.ts AS ts,
       a.id AS aid, a.name AS author, i.name AS tag, fl AS friend_likes, total AS likes, 3*fl + total + 2 AS score
ORDER BY score DESC LIMIT $k"""
FEED = """MATCH (a:User)-[:POSTED]->(p:Post) WHERE a.id=$id OR (a)-[:FRIEND]-(:User {id:$id})
RETURN p.id AS id,p.text AS text,p.ts AS ts,p.media AS media,p.type AS type,a.id AS aid,a.name AS author,
  COUNT{(p)<-[:LIKED]-()} AS likes, EXISTS{(:User {id:$id})-[:LIKED]->(p)} AS liked
ORDER BY p.ts DESC LIMIT 30"""

def E(key, cat, title, purpose, concept, cypher, sql, run=True, profile=True, other=False):
    return dict(key=key, category=cat, title=title, purpose=purpose, concept=concept, cypher=cypher, sql=sql,
                run=run, profile=profile, needs_other=other)

CATALOG = [
 E("constraints", "Schema and constraints", "List constraints", "Shows the uniqueness rules on User.id, Interest.name and Post.id.", "Integrity constraints (like PRIMARY KEY)",
   "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties\nRETURN name, type, labelsOrTypes, properties", "SELECT constraint_name, constraint_type FROM information_schema.table_constraints;", profile=False),
 E("indexes", "Schema and constraints", "List indexes", "Each uniqueness constraint creates an index, so a lookup by id does not scan every user.", "Indexing",
   "SHOW INDEXES YIELD name, type, labelsOrTypes, properties\nRETURN name, type, labelsOrTypes, properties", "SELECT indexname, indexdef FROM pg_indexes;", profile=False),
 E("create_constraint", "Schema and constraints", "Create a uniqueness constraint (display only)", "Run once at load time. Dropping it is what the Index experiment on the Admin page measures.", "Constraint + index creation",
   "CREATE CONSTRAINT u_id IF NOT EXISTS\nFOR (u:User) REQUIRE u.id IS UNIQUE", "ALTER TABLE users ADD PRIMARY KEY (id);", run=False),
 E("my_profile", "CRUD", "Read my profile", "Reads one user by id, with friend count, interests and liked-post count.", "Index lookup, subquery counts, list comprehension",
   "MATCH (u:User {id:$id})\nRETURN u.id AS id, u.name AS name, COUNT { (u)-[:FRIEND]-() } AS friends,\n       [(u)-[:LIKES]->(i) | i.name] AS interests, COUNT { (u)-[:LIKED]->() } AS liked_posts",
   "SELECT u.*, (SELECT COUNT(*) FROM friends WHERE a=u.id) AS friends FROM users u WHERE u.id = ?;"),
 E("my_friends", "CRUD", "Read my friends", "Follows FRIEND relationships from me to my friends. No join table needed.", "Relationship traversal",
   "MATCH (:User {id:$id})-[:FRIEND]-(f:User)\nRETURN f.id AS id, f.name AS name ORDER BY name LIMIT $k",
   "SELECT u.* FROM friends f JOIN users u ON u.id = f.b WHERE f.a = ? ORDER BY u.name;"),
 E("send_request", "CRUD", "Send a friend request (display only)", "Creates a REQUESTED relationship unless they are already friends.", "CREATE / MERGE a relationship",
   "MATCH (a:User {id:$a}), (b:User {id:$b})\nWHERE a <> b AND NOT (a)-[:FRIEND]-(b) AND NOT (b)-[:REQUESTED]->(a)\nMERGE (a)-[:REQUESTED]->(b)",
   "INSERT INTO friend_requests (from_id, to_id) VALUES (?, ?);", run=False),
 E("accept_request", "CRUD", "Accept a friend request (display only)", "Deletes the REQUESTED relationship and creates a FRIEND one, in a single query.", "Atomic update of relationships",
   "MATCH (x:User {id:$o})-[r:REQUESTED]->(m:User {id:$m})\nDELETE r\nMERGE (x)-[:FRIEND]->(m)",
   "DELETE FROM friend_requests WHERE ...; INSERT INTO friends VALUES (?, ?);  -- two statements in a transaction", run=False),
 E("mutual", "Friend recommendations", "People you may know: mutual friends", "Goes me → my friends → their friends, drops people I already know, and ranks by how many friends we share.", "Pattern matching (2 hops), aggregation",
   MUTUAL, "SELECT f2.b, COUNT(*) AS mutual FROM friends f1 JOIN friends f2 ON f1.b = f2.a\nWHERE f1.a = ? AND f2.b <> ? AND f2.b NOT IN (SELECT b FROM friends WHERE a = ?)\nGROUP BY f2.b ORDER BY mutual DESC LIMIT 10;"),
 E("interest", "Interest recommendations", "People you may know: shared interests", "Finds people who like the same Interest nodes as me and ranks by how many they share.", "Shared-neighbour pattern, aggregation",
   SHARED, "SELECT l2.user_id, COUNT(*) AS shared FROM user_interest l1 JOIN user_interest l2 ON l1.interest = l2.interest\nWHERE l1.user_id = ? AND l2.user_id <> ? GROUP BY l2.user_id ORDER BY shared DESC LIMIT 10;"),
 E("postlikes", "Interest recommendations", "People you may know: posts we both liked", "Finds people who liked the same posts I liked (behaviour-based similarity).", "Collaborative filtering over LIKED relationships",
   LIKESQ, "SELECT l2.user_id, COUNT(*) AS shared FROM post_likes l1 JOIN post_likes l2 ON l1.post_id = l2.post_id\nWHERE l1.user_id = ? AND l2.user_id <> ? GROUP BY l2.user_id ORDER BY shared DESC LIMIT 10;"),
 E("hybrid", "Hybrid scoring", "Hybrid: mutual friends + interests + post likes", "One query computes all three signals for every friend-of-friend. The app then applies the three slider weights to each normalised signal.", "Multi-signal scoring, OPTIONAL MATCH, WITH pipelining",
   HYB, "-- Three grouped sub-queries joined with LEFT JOINs, then a weighted sum.\n-- Needs ~25 lines of SQL and a join per signal.\nSELECT c.id, m.cnt, s.cnt, l.cnt FROM ... LEFT JOIN ... LEFT JOIN ...;"),
 E("rec_posts", "Post recommendations", "Recommended posts", "Posts tagged with my interests that I haven't liked, boosted when my friends liked them.", "Multi-hop pattern, subquery counts, scoring",
   RECPOSTS, "SELECT p.* FROM user_interest ui JOIN post_tags pt ON pt.interest = ui.interest JOIN posts p ON p.id = pt.post_id\nWHERE ui.user_id = ? AND p.id NOT IN (SELECT post_id FROM post_likes WHERE user_id = ?) ORDER BY ... LIMIT 6;"),
 E("feed", "Post recommendations", "Home feed", "My posts and my friends' posts, newest first, with like counts.", "Pattern with OR, subquery counts, ORDER BY",
   FEED, "SELECT p.* FROM posts p WHERE p.author = ? OR p.author IN (SELECT b FROM friends WHERE a = ?) ORDER BY p.ts DESC LIMIT 30;"),
 E("shortest", "Graph algorithms", "Shortest path between two users", "Finds the fewest friend hops between me and another user (set the other user id).", "shortestPath, variable-length paths",
   "MATCH (a:User {id:$id}), (b:User {id:$other})\nMATCH p = shortestPath((a)-[:FRIEND*..6]-(b))\nRETURN [n IN nodes(p) | n.name] AS path, length(p) AS hops",
   "WITH RECURSIVE walk AS (SELECT a, b, 1 AS depth FROM friends WHERE a = ? UNION ALL SELECT w.a, f.b, depth+1 FROM walk w JOIN friends f ON f.a = w.b WHERE depth < 6)\nSELECT MIN(depth) FROM walk WHERE b = ?;", other=True),
 E("mutual_with", "Graph algorithms", "Mutual friends with one user", "Lists the friends I share with a specific user.", "Pattern matching (2 hops, fixed ends)",
   "MATCH (a:User {id:$id})-[:FRIEND]-(m:User)-[:FRIEND]-(b:User {id:$other})\nRETURN m.id AS id, m.name AS name",
   "SELECT f1.b FROM friends f1 JOIN friends f2 ON f1.b = f2.a WHERE f1.a = ? AND f2.b = ?;", other=True),
 E("reach3", "Graph algorithms", "Reach within 3 hops", "Counts everyone I can reach through up to 3 friend hops. In SQL this needs three self-joins.", "Variable-length traversal",
   "MATCH (u:User {id:$id})-[:FRIEND*1..3]-(c:User)\nWHERE c <> u\nRETURN count(DISTINCT c) AS reach",
   "SELECT COUNT(DISTINCT f3.b) FROM friends f1 JOIN friends f2 ON f2.a=f1.b JOIN friends f3 ON f3.a=f2.b WHERE f1.a = ?;"),
 E("triangles", "Graph algorithms", "Triangle count", "Counts friend triangles around me (two of my friends who are also friends). Shows how tight my circle is.", "Cyclic pattern matching",
   "MATCH (me:User {id:$id})-[:FRIEND]-(a:User)-[:FRIEND]-(b:User)-[:FRIEND]-(me)\nWHERE a.id < b.id\nRETURN count(*) AS triangles",
   "SELECT COUNT(*) FROM friends f1 JOIN friends f2 ON f1.b=f2.a JOIN friends f3 ON f2.b=f3.a AND f3.b=f1.a WHERE f1.a = ? AND f1.b < f2.b;"),
 E("centrality", "Graph algorithms", "Most connected users (degree centrality)", "Ranks users by number of friends.", "Degree centrality",
   "MATCH (u:User)\nRETURN u.id AS id, u.name AS name, COUNT { (u)-[:FRIEND]-() } AS degree\nORDER BY degree DESC LIMIT $k",
   "SELECT a, COUNT(*) AS degree FROM friends GROUP BY a ORDER BY degree DESC LIMIT 10;"),
 E("avg_degree", "Analytics", "Friend-count statistics", "Average, minimum and maximum friends per user (the dataset guarantees at least 20).", "Aggregation",
   "MATCH (u:User)\nWITH u, COUNT { (u)-[:FRIEND]-() } AS d\nRETURN round(avg(d), 1) AS avg_friends, min(d) AS min_friends, max(d) AS max_friends",
   "SELECT AVG(d), MIN(d), MAX(d) FROM (SELECT a, COUNT(*) AS d FROM friends GROUP BY a) t;"),
 E("popular_interests", "Analytics", "Most popular interests", "Counts how many users like each interest.", "Group and count over a relationship",
   "MATCH (:User)-[:LIKES]->(i:Interest)\nRETURN i.name AS interest, count(*) AS fans\nORDER BY fans DESC LIMIT $k",
   "SELECT interest, COUNT(*) AS fans FROM user_interest GROUP BY interest ORDER BY fans DESC LIMIT 10;"),
 E("top_posts", "Analytics", "Most liked posts", "Ranks posts by number of likes.", "Join through relationships + aggregation",
   "MATCH (a:User)-[:POSTED]->(p:Post)<-[l:LIKED]-(:User)\nRETURN p.id AS id, left(p.text, 40) AS text, a.name AS author, count(l) AS likes\nORDER BY likes DESC LIMIT $k",
   "SELECT p.id, p.text, u.name, COUNT(*) AS likes FROM posts p JOIN users u ON u.id=p.author JOIN post_likes l ON l.post_id=p.id GROUP BY p.id, u.name ORDER BY likes DESC LIMIT 10;"),
 E("drop_index", "Performance", "Drop / restore the id index (display only)", "The Admin page's Index experiment runs these two statements and times the friend-of-friend query in between.", "Effect of indexing",
   "DROP CONSTRAINT u_id IF EXISTS;\n-- ...time the query...\nCREATE CONSTRAINT u_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE", "DROP INDEX idx_users_id; -- time the query -- CREATE INDEX idx_users_id ON users(id);", run=False),
]

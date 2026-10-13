SocialGraph - graph-based social recommendation system (Neo4j + FastAPI + plain HTML/JS)

SETUP (Windows)
1. Start Neo4j Desktop and make sure your database shows "Running" (Neo4j 5 or newer).
2. Open .env in Notepad, replace PUT_YOUR_NEO4J_PASSWORD_HERE with your Neo4j password, save.
3. Open a terminal INSIDE this folder (the prompt must end with \sg>) and run:
     python -m pip install -r requirements.txt
     python load_neo4j.py            (wipes the database and loads 3,000 users, 20+ friends each)
     python -m uvicorn app:app --reload
4. Open http://localhost:8000 and log in (or sign up).

PAGES
  /               Home: feed, posts (text/photo/video), People You May Know (mutual friends,
                  shared interests, posts we both liked, hybrid with 3 sliders), recommended posts,
                  friend requests, search, shortest path. Use the top dropdown to act as another user.
  /dbms.html      DBMS Queries: catalog of every Cypher query with its SQL equivalent, Run / PROFILE
                  buttons, and a live query log. The "View query" buttons on Home open the exact query.
  /admin.html     Admin (password = ADMIN_PASSWORD in .env, default admin1234): overview, graph view,
                  benchmark, index experiment, quality test, user management.

DATA: python gen_data.py 3000  regenerates the CSVs (every user gets at least 20 friends); then run load_neo4j.py again.
DEPLOY: docker build -t socialgraph . ; docker run -p 8000:8000 --env-file .env socialgraph

LOGIN: user1@demo.com / demo1234 (Aarav Reddy). Seeded users are user<id>@demo.com, all with password demo1234.
Each person sees only their own account, friends, requests and query log. Admins use /admin.html.

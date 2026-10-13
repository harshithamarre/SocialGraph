# SocialGraph

SocialGraph is a graph-based social networking and recommendation system built with **Python, FastAPI, Neo4j, and HTML/CSS/JavaScript**. It
demonstrates how graph databases can support social features and personalized recommendations.

## 🚀 Features

-   **User authentication:** Sign up and log in with an email and
    password.
-   **Social feed:** View posts from yourself and your friends.
-   **Posts and media:** Create text posts and share supported media.
-   **People you may know:** Discover people using mutual friends,
    shared interests, and posts you both liked.
-   **Hybrid recommendations:** Combine multiple recommendation signals
    with adjustable weights.
-   **Post recommendations:** Discover posts based on interests and
    engagement from friends.
-   **Friend requests:** Send and manage connection requests.
-   **Search and shortest path:** Explore people and connections in the
    social graph.
-   **DBMS query explorer:** Review Cypher queries alongside SQL
    equivalents, run supported queries, inspect query plans, and view
    query timing.
-   **Admin dashboard:** View graph statistics and access administration
    and performance-testing tools.

## 👩🏻‍💻 Technology stack

-   **Backend:** Python, FastAPI, Uvicorn
-   **Graph database:** Neo4j 5+
-   **Frontend:** HTML, CSS, JavaScript
-   **Configuration:** `python-dotenv`
-   **Deployment option:** Docker

## ⚙️ Project structure

``` text
sg/
├── app.py             # FastAPI application and API routes
├── auth.py            # Password hashing and token helpers
├── catalog.py         # Cypher query catalogue and SQL equivalents
├── gen_data.py        # Generate sample CSV datasets
├── load_neo4j.py      # Load CSV data into Neo4j
├── requirements.txt   # Python dependencies
├── Dockerfile         # Docker image configuration
├── users.csv
├── friends.csv
├── interests.csv
├── likes.csv
├── posts.csv
├── post_likes.csv
├── requests.csv
└── static/            # HTML, CSS, JavaScript, and uploaded media
```

## ✨ Prerequisites

Install or prepare the following:

1.  Python 3.10+ (the included Dockerfile uses Python 3.12).
2.  Neo4j 5 or newer, running locally or at a reachable database URL.
3.  Git (optional, for version control).

## ▶️ Setup and run locally

### 1. Clone the repository

``` bash
git clone https://github.com/YOUR_USERNAME/SocialGraph.git
cd SocialGraph
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file in the project root.

``` dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
JWT_SECRET=replace_with_a_long_random_secret
ADMIN_PASSWORD=choose_a_strong_admin_password
```

Use the credentials and connection URI for your own Neo4j instance. Keep secrets private and use strong values, especially before deploying the
application publicly.

### 5. Load the sample graph data

Make sure Neo4j is running, then run:

``` bash
python load_neo4j.py
```

**Warning:** `load_neo4j.py` deletes existing nodes and relationships, constraints, and indexes in the connected Neo4j database before loading
the project's CSV data. Use a dedicated development database and back up any data you need before running it.

### 6. Start the application

``` bash
python -m uvicorn app:app --reload
```

Open **http://localhost:8000** in your browser.

## 📄 Main pages

-   `/` --- Social feed, profile-related features, friend requests,
    search, and recommendations.
-   `/dbms.html` --- Cypher query catalogue, SQL comparisons, query
    execution, profiling, and query log.
-   `/admin.html` --- Administrative overview and graph/performance
    tools.

The exact features available depend on the current database contents and
application configuration.

## 🔬 Demo account

The sample data loader creates demo accounts with email addresses
following this pattern:

``` text
user<ID>@demo.com
```

The seeded demo password is `demo1234`. For example, the documented
sample account is `user1@demo.com`.

These are **development-only demo credentials**. Do not use them in
production or expose a publicly deployed instance with default
credentials.

## 🌱 Regenerate sample data

To regenerate the CSV datasets, run:

``` bash
python gen_data.py 3000
```

Then reload the graph with `python load_neo4j.py`. Review the warning
above first because the loader clears the connected graph database.

## ▶️ Run with Docker

After configuring a local `.env` file and ensuring the Neo4j database is reachable from the container:

``` bash
docker build -t socialgraph .
docker run --rm -p 8000:8000 --env-file .env socialgraph
```

If Neo4j is running on your host machine, `localhost` inside the
container usually refers to the container itself, not the host.
Configure `NEO4J_URI` to use a host-reachable address or a Docker
network service name.

## 🎯 Learning objectives

This project can be used to explore:

-   Graph modelling with nodes and relationships
-   Cypher queries and graph traversal
-   Recommendation approaches based on mutual connections, interests,
    and shared likes
-   Comparing graph-query concepts with relational SQL
-   Query profiling and basic performance experiments
-   Building a web application with a Python API and browser-based
    frontend

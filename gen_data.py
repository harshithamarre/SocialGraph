# usage: python gen_data.py 3000   (every user gets at least 20 friends)
import csv, os, random, sys, time
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
MINF = 20
random.seed(7); now = int(time.time() * 1000)
FIRST = "Aarav Vivaan Aditya Sai Arjun Krishna Ishaan Rohan Karthik Ananya Diya Meera Saanvi Kavya Riya Priya Neha Pooja Isha Tara".split()
LAST = "Reddy Sharma Rao Naidu Patel Iyer Nair Gupta Verma Khan Singh Das Menon Joshi Kumar".split()
INT = "Cricket Music Movies Travel Coding Gaming Cooking Photography Reading Fitness Art Fashion Football Dance Yoga Hiking Anime Tech Finance Pets".split()
TPL = ["Spent the whole weekend on {x}. Zero regrets.", "Anyone else here into {x}? Looking for recommendations!",
       "Small win today thanks to {x}.", "Can't stop thinking about {x} lately.", "Best part of my week: {x}. Highly recommend."]
os.makedirs("static/uploads", exist_ok=True)
for i in range(12):
    h = i * 30
    open(f"static/uploads/seed{i}.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl({h},60%,45%)"/><stop offset="1" stop-color="hsl({(h+60)%360},65%,25%)"/></linearGradient></defs><rect width="800" height="500" fill="url(#g)"/><circle cx="620" cy="140" r="70" fill="#fff" opacity=".25"/><path d="M0 400 Q200 300 400 380 T800 340 V500 H0Z" fill="#fff" opacity=".2"/></svg>')
def w(name, head, rows):
    with open(name, "w", newline="", encoding="utf-8") as f:
        c = csv.writer(f); c.writerow(head); c.writerows(rows)
names = ["Aarav Reddy"] + [f"{random.choice(FIRST)} {random.choice(LAST)}" for _ in range(n - 1)]
w("users.csv", ["id", "name"], [(i + 1, nm) for i, nm in enumerate(names)])
adj = {i: set() for i in range(1, n + 1)}
for a in range(1, n + 1):          # keep adding random friends until everyone has at least MINF
    while len(adj[a]) < MINF:
        b = random.randint(1, n)
        if b != a and b not in adj[a]: adj[a].add(b); adj[b].add(a)
pairs = sorted((a, b) for a in adj for b in adj[a] if a < b)
w("friends.csv", ["a", "b"], pairs)
w("interests.csv", ["name"], [(x,) for x in INT])
likes = [(i, x) for i in range(1, n + 1) for x in random.sample(INT, random.randint(3, 5))]
w("likes.csv", ["user_id", "interest"], likes)
ints = {}
for u, x in likes: ints.setdefault(u, []).append(x)
posts = []; by_tag = {}; pid = 0
for u in range(1, n + 1):
    for _ in range(random.randint(1, 2)):
        pid += 1; tag = random.choice(ints[u]); by_tag.setdefault(tag, []).append(pid)
        posts.append((pid, u, random.choice(TPL).format(x=tag), now - random.randint(60000, 7 * 86400000),
                      f"/uploads/seed{random.randint(0, 11)}.svg" if random.random() < 0.3 else "", tag))
w("posts.csv", ["id", "author", "text", "ts", "media", "tag"], posts)
pl = set()   # people mostly like posts about their own interests, so "posts we both liked" is meaningful
for u in range(1, n + 1):
    for _ in range(6): pl.add((u, random.choice(by_tag[random.choice(ints[u])])))
    for _ in range(2): pl.add((u, random.randint(1, pid)))
w("post_likes.csv", ["user_id", "post_id"], sorted(pl))
cands = [u for u in range(2, n + 1) if u not in adj[1]]
w("requests.csv", ["from", "to"], [(u, 1) for u in random.sample(cands, 5)])
print(n, "users,", len(pairs), "friendships (min friends:", min(len(v) for v in adj.values()), "),", len(posts), "posts,", len(pl), "post likes")

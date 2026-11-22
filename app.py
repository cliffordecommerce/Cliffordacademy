import os, sqlite3, secrets
from functools import wraps
from flask import (Flask, g, send_from_directory, request, session, redirect, url_for,
                   render_template_string as rts, abort, flash, get_flashed_messages)
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash

SITE = os.environ.get("SITE_NAME", "Clifford Academy")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
WHATSAPP = os.environ.get("WHATSAPP", "50900000000")      # san + ni espas
MONCASH = os.environ.get("MONCASH", "38 60 33 10 (Jean Esaie Clifford)")
NATCASH = os.environ.get("NATCASH", "+509 33 36 12 53 (Jean Esaie Clifford)")
DB_PATH = os.environ.get("DB_PATH", "site.db")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chanje-sa-a-nan-pwodiksyon")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=int(os.environ.get("MAX_MB", "500")) * 1024 * 1024)

@app.errorhandler(413)
def too_big(_):
    return "Fichye a twò gwo. Retounen epi eseye yon videyo ki pi piti.", 413

# ---------- baz done ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, pw TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS videos(id INTEGER PRIMARY KEY, title TEXT NOT NULL, descr TEXT, price INTEGER NOT NULL, embed TEXT NOT NULL DEFAULT '', file TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, video_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', created TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, video_id));
    """)
    try:
        c.execute("ALTER TABLE videos ADD COLUMN file TEXT")
    except sqlite3.OperationalError:
        pass
    c.commit(); c.close()

init_db()

# ---------- sekirite ----------
@app.before_request
def load_user():
    g.user = None
    if "uid" in session:
        g.user = db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400)

@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "same-origin"
    return r

def is_admin():
    return bool(g.user and ADMIN_EMAIL and g.user["email"] == ADMIN_EMAIL)

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if not is_admin():
            abort(403)
        return f(*a, **k)
    return w

def has_access(vid):
    if not g.user:
        return False
    if is_admin():
        return True
    return db().execute("SELECT 1 FROM orders WHERE user_id=? AND video_id=? AND status='approved'",
                        (g.user["id"], vid)).fetchone() is not None

# ---------- mizanpaj ----------
BASE = """<!doctype html><html lang="ht"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{site}}</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f4f5f7;--bd:#ddd;--acc:#e8590c}
@media(prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#f1f1f1;--mut:#9aa0a6;--card:#202328;--bd:#33373d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
nav{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--bd);flex-wrap:wrap}
nav a{color:var(--fg);text-decoration:none;margin-right:10px}.logo{font-weight:800;font-size:20px}.logo span{color:var(--acc)}
main{max-width:760px;margin:0 auto;padding:16px}.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px;margin-bottom:14px}
.btn,button{display:inline-block;border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:600;background:var(--acc);color:#fff;text-decoration:none;cursor:pointer}
.sec{background:transparent;color:var(--fg);border:1px solid var(--bd)}
input,textarea{width:100%;padding:10px;margin:4px 0 10px;border-radius:10px;border:1px solid var(--bd);background:var(--bg);color:var(--fg);font:inherit}
.mut{color:var(--mut);font-size:14px}.price{color:var(--acc);font-weight:700}.flash{padding:10px;border-radius:10px;background:var(--card);border:1px solid var(--acc);margin-bottom:12px}
.vid{position:relative;padding-top:56.25%}.vid iframe{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:10px}
table{width:100%;border-collapse:collapse}td,th{padding:6px;border-bottom:1px solid var(--bd);text-align:left;font-size:14px}
</style></head><body>
<nav><div><a class="logo" href="/">{{site_a}} <span>{{site_b}}</span></a></div>
<div>{% if user %}<a href="/mes-videyo">Videyo mwen</a>{% if admin %}<a href="/admin">Admin</a>{% endif %}
<a href="/logout">Dekonekte</a>{% else %}<a href="/login">Konekte</a><a class="btn" href="/register">Kreye kont</a>{% endif %}</div></nav>
<main>{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{{body}}</main></body></html>"""

def page(tpl, **ctx):
    body = Markup(rts(tpl, csrf=session["csrf"], **ctx))
    a, _, b = SITE.partition(" ")
    return rts(BASE, site=SITE, site_a=a, site_b=b, user=g.user, admin=is_admin(),
               msgs=get_flashed_messages(), body=body)

# ---------- kont ----------
FORM_REG = """<div class="card"><h2>Kreye kont</h2><form method="post">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Non</label><input name="name" required maxlength="80">
<label>Imèl</label><input name="email" type="email" required>
<label>Modpas (omwen 8 karaktè)</label><input name="pw" type="password" required minlength="8">
<button>Kreye kont</button></form></div>"""
FORM_LOGIN = """<div class="card"><h2>Konekte</h2><form method="post">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Imèl</label><input name="email" type="email" required>
<label>Modpas</label><input name="pw" type="password" required>
<button>Konekte</button></form></div>"""

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["pw"]
        if len(pw) < 8:
            flash("Modpas la twò kout."); return page(FORM_REG)
        try:
            cur = db().execute("INSERT INTO users(email,name,pw) VALUES(?,?,?)",
                               (email, request.form["name"].strip()[:80], generate_password_hash(pw)))
            db().commit()
        except sqlite3.IntegrityError:
            flash("Imèl sa a deja gen yon kont."); return page(FORM_REG)
        session.clear(); session["uid"] = cur.lastrowid
        return redirect("/")
    return page(FORM_REG)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if u and check_password_hash(u["pw"], request.form["pw"]):
            session.clear(); session["uid"] = u["id"]
            nxt = request.args.get("next", "/")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "/")
        flash("Imèl oswa modpas pa kòrèk.")
    return page(FORM_LOGIN)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

# ---------- katalòg ----------
@app.route("/")
def catalogue():
    vids = db().execute("SELECT id,title,descr,price FROM videos ORDER BY id DESC").fetchall()
    return page("""<h1>Fòmasyon videyo</h1>
{% for v in vids %}<div class="card"><h3>{{v.title}}</h3><div class="mut">{{v.descr}}</div>
<p><span class="price">{{v.price}} HTG</span> <a class="btn" href="/acheter/{{v.id}}">Achte</a></p></div>
{% else %}<p class="mut">Poko gen videyo. Tounen talè!</p>{% endfor %}""", vids=vids)

@app.route("/acheter/<int:vid>", methods=["GET", "POST"])
@login_required
def buy(vid):
    v = db().execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone() or abort(404)
    if has_access(vid):
        return redirect(f"/video/{vid}")
    db().execute("INSERT OR IGNORE INTO orders(user_id,video_id) VALUES(?,?)", (g.user["id"], vid)); db().commit()
    o = db().execute("SELECT * FROM orders WHERE user_id=? AND video_id=?", (g.user["id"], vid)).fetchone()
    if o["status"] == "rejected":
        db().execute("UPDATE orders SET status='pending' WHERE id=?", (o["id"],)); db().commit()
    from urllib.parse import quote
    msg = quote(f"Bonjou, m peye {v['title']} ({v['price']} HTG). Imèl kont mwen: {g.user['email']}. Kòmand #{o['id']}")
    return page("""<div class="card"><h2>{{v.title}} — {{v.price}} HTG</h2>
<p>1. Voye <b>{{v.price}} HTG</b> sou MonCash: <b>{{mc}}</b> oswa NatCash: <b>{{nc}}</b></p>
<p>2. Voye prèv peman an (screenshot) sou WhatsApp.</p>
<p><a class="btn" target="_blank" rel="noopener" href="https://wa.me/{{wa}}?text={{msg}}">Voye prèv sou WhatsApp</a></p>
<p>3. Apre n verifye peman an, videyo a parèt nan <a href="/mes-videyo">Videyo mwen</a>.</p>
<p class="mut">Kòmand #{{o.id}} — an atant verifikasyon.</p></div>""", v=v, o=o, mc=MONCASH, nc=NATCASH, wa=WHATSAPP, msg=msg)

@app.route("/mes-videyo")
@login_required
def mine():
    rows = db().execute("""SELECT v.id,v.title,o.status FROM orders o JOIN videos v ON v.id=o.video_id
                           WHERE o.user_id=? ORDER BY o.id DESC""", (g.user["id"],)).fetchall()
    return page("""<h1>Videyo mwen</h1>{% for r in rows %}<div class="card"><b>{{r.title}}</b><br>
{% if r.status=='approved' %}<a class="btn" href="/video/{{r.id}}">▶ Gade</a>
{% elif r.status=='pending' %}<span class="mut">An atant verifikasyon peman</span>
{% else %}<span class="mut">Peman pa aksepte. <a href="/acheter/{{r.id}}">Eseye ankò</a></span>{% endif %}</div>
{% else %}<p class="mut">Ou poko achte okenn videyo.</p>{% endfor %}""", rows=rows)

@app.route("/video/<int:vid>")
@login_required
def watch(vid):
    v = db().execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone() or abort(404)
    if not has_access(vid):
        return redirect(f"/acheter/{vid}")
    r = page("""<h2>{{v.title}}</h2>{% if v.file %}<video controls controlsList="nodownload" playsinline preload="metadata"
style="width:100%;border-radius:10px;background:#000" src="/media/{{v.id}}"></video>
{% else %}<div class="vid"><iframe src="{{v.embed}}" allow="encrypted-media; fullscreen"
allowfullscreen referrerpolicy="origin"></iframe></div>{% endif %}<p class="mut">{{v.descr}}</p>""", v=v)
    return r, 200, {"Cache-Control": "no-store"}

@app.route("/media/<int:vid>")
@login_required
def media(vid):
    v = db().execute("SELECT file FROM videos WHERE id=?", (vid,)).fetchone()
    if not v or not v["file"]:
        abort(404)
    if not has_access(vid):
        abort(403)
    r = send_from_directory(UPLOAD_DIR, v["file"], conditional=True)
    r.headers["Cache-Control"] = "private, no-store"
    return r

# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin():
    orders = db().execute("""SELECT o.id,o.status,u.email,u.name,v.title,v.price FROM orders o
        JOIN users u ON u.id=o.user_id JOIN videos v ON v.id=o.video_id ORDER BY (o.status='pending') DESC, o.id DESC""").fetchall()
    vids = db().execute("SELECT * FROM videos ORDER BY id DESC").fetchall()
    return page("""<h2>Ajoute yon videyo</h2><form class="card" method="post" action="/admin/video" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Tit</label><input name="title" required maxlength="120">
<label>Deskripsyon</label><textarea name="descr" rows="2" maxlength="500"></textarea>
<label>Pri (HTG)</label><input name="price" type="number" min="0" required>
<label>Fichye videyo (MP4, WEBM oswa MOV)</label><input name="file" type="file" accept="video/*">
<label>OSWA lyen embed (https://…), si ou pa voye fichye</label><input name="embed" type="url" placeholder="https://…">
<button>Pibliye</button></form>
<h2>Peman yo</h2><div class="card" style="overflow-x:auto"><table><tr><th>#</th><th>Kliyan</th><th>Videyo</th><th>Eta</th><th></th></tr>
{% for o in orders %}<tr><td>{{o.id}}</td><td>{{o.name}}<br><span class="mut">{{o.email}}</span></td><td>{{o.title}}<br>{{o.price}} HTG</td><td>{{o.status}}</td>
<td>{% for a,l in [('approve','Bay aksè'),('reject','Rejte')] %}<form method="post" action="/admin/order/{{o.id}}/{{a}}" style="display:inline">
<input type="hidden" name="csrf" value="{{csrf}}"><button class="{{'sec' if a=='reject' else ''}}">{{l}}</button></form> {% endfor %}</td></tr>
{% else %}<tr><td colspan=5 class="mut">Pa gen kòmand.</td></tr>{% endfor %}</table></div>
<h2>Videyo yo</h2>{% for v in vids %}<div class="card">{{v.title}} — {{v.price}} HTG
<form method="post" action="/admin/video/{{v.id}}/delete" style="display:inline" onsubmit="return confirm('Efase?')">
<input type="hidden" name="csrf" value="{{csrf}}"><button class="sec">Efase</button></form></div>{% endfor %}""", orders=orders, vids=vids)

@app.post("/admin/video")
@admin_required
def add_video():
    f = request.form
    embed = f.get("embed", "").strip()
    up = request.files.get("file")
    fname = ""
    if up and up.filename:
        ext = os.path.splitext(up.filename)[1].lower()
        if ext not in (".mp4", ".webm", ".mov", ".m4v"):
            flash("Fòma pa aksepte. Itilize MP4, WEBM oswa MOV."); return redirect("/admin")
        fname = secrets.token_hex(12) + ext
        up.save(os.path.join(UPLOAD_DIR, fname))
        embed = ""
    elif not embed.startswith("https://"):
        flash("Voye yon fichye videyo oswa mete yon lyen https://"); return redirect("/admin")
    db().execute("INSERT INTO videos(title,descr,price,embed,file) VALUES(?,?,?,?,?)",
                 (f["title"].strip(), f.get("descr", "").strip(), int(f["price"]), embed, fname))
    db().commit(); flash("✅ Videyo a pibliye."); return redirect("/admin")

@app.post("/admin/order/<int:oid>/<action>")
@admin_required
def order_action(oid, action):
    if action not in ("approve", "reject"):
        abort(404)
    db().execute("UPDATE orders SET status=? WHERE id=?", ("approved" if action == "approve" else "rejected", oid))
    db().commit(); flash("Fèt."); return redirect("/admin")

@app.post("/admin/video/<int:vid>/delete")
@admin_required
def del_video(vid):
    row = db().execute("SELECT file FROM videos WHERE id=?", (vid,)).fetchone()
    if row and row["file"]:
        try: os.remove(os.path.join(UPLOAD_DIR, row["file"]))
        except OSError: pass
    db().execute("DELETE FROM orders WHERE video_id=?", (vid,))
    db().execute("DELETE FROM videos WHERE id=?", (vid,)); db().commit()
    return redirect("/admin")

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))

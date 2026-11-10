
import csv
import io
import math
import os
import random
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from data import (ACCOUNT_TYPES, CATEGORIES, COUNTRIES, CURRENCIES, FEES,
                  STATUSES)

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ZENDPAY_DB", os.path.join(BASE, "zendpay.db"))
TZ_OFFSET_HOURS = float(os.environ.get("ZENDPAY_TZ_OFFSET", "1"))  # Lagos = UTC+1
UNAVAILABLE_MSG = "Service unavailable for this financial institution"
REJECTED_MSG = "Sorry, you currently cannot have an account with us. Thanks for trying Zendpay."
SUSPENDED_MSG = "Your account has been suspended. Please contact Zendpay support."

# Static files live in public/ so Vercel serves them from its CDN (Flask serves them locally).
app = Flask(__name__, static_folder="public/static", static_url_path="/static")


DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
IS_PG = bool(DATABASE_URL)
ON_VERCEL = bool(os.environ.get("VERCEL"))


def _secret():
    env = os.environ.get("SECRET_KEY") or os.environ.get("ZENDPAY_SECRET")
    if env:
        return env
    if IS_PG or ON_VERCEL:
        raise RuntimeError("SECRET_KEY environment variable is required in production")
    path = os.path.join(BASE, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(path, 0o600)
    return open(path).read().strip()


app.secret_key = _secret()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=ON_VERCEL,
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=12))

# --------------------------------------------------------------------------- db
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role TEXT NOT NULL DEFAULT 'user',
  surname TEXT NOT NULL, first_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  country TEXT, dial TEXT, phone TEXT,
  account_type TEXT, currency TEXT NOT NULL,
  account_number TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL, pin_hash TEXT,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending|active|restricted|suspended|rejected|deleted
  status_note TEXT,
  balance INTEGER NOT NULL DEFAULT 0 CHECK(balance>=0),  -- minor units (cents)
  created_at TEXT NOT NULL, decided_at TEXT, last_login TEXT
);
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT NOT NULL, user_id INTEGER NOT NULL,
  category TEXT NOT NULL, direction TEXT NOT NULL,  -- in|out
  amount INTEGER NOT NULL, fee INTEGER NOT NULL DEFAULT 0, currency TEXT NOT NULL,
  status TEXT NOT NULL,                              -- Successful|Pending|Failed
  cp_name TEXT, cp_account TEXT, cp_bank TEXT, note TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS tx_user ON transactions(user_id, created_at);
CREATE TABLE IF NOT EXISTS deposit_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL, tx_id INTEGER,
  amount INTEGER NOT NULL, currency TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',            -- pending|approved|declined
  created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS bank_accounts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bank_name TEXT NOT NULL, account_number TEXT NOT NULL, account_name TEXT NOT NULL,
  currency TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
  UNIQUE(bank_name, account_number)
);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, k TEXT NOT NULL, ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_k ON attempts(k, ts);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT, action TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL
);
"""


def to_pg(sql):
    """Translate the app's SQL (written with ? placeholders) for Postgres."""
    sql = sql.replace("?", "%s").replace(" LIKE ", " ILIKE ")
    return "BEGIN" if sql.strip() == "BEGIN IMMEDIATE" else sql


def to_sqlite(sql):
    return sql.replace(" FOR UPDATE", "")


class Result:
    """Cursor-like wrapper so the rest of the app is database-agnostic."""
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class DB:
    def __init__(self):
        if IS_PG:
            import psycopg
            from psycopg.rows import dict_row
            # autocommit + explicit BEGIN/COMMIT in the app; prepare_threshold=None is
            # required for Supabase's transaction pooler (port 6543).
            self.conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row,
                                        prepare_threshold=None, connect_timeout=10, sslmode="require")
        else:
            self.conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=15)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql, params=()):
        if not IS_PG:
            return self.conn.execute(to_sqlite(sql), params)
        sql = to_pg(sql)
        is_insert = sql.lstrip().upper().startswith("INSERT") and "RETURNING" not in sql.upper()
        if is_insert:
            sql += " RETURNING id"
        cur = self.conn.execute(sql, params)
        if is_insert:
            return Result(cur, cur.fetchone()["id"])
        return Result(cur)

    def close(self):
        self.conn.close()


def get_db():
    if "db" not in g:
        g.db = DB()
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def log(action, detail="", actor=None):
    if actor is None:
        u = getattr(g, "user", None)
        actor = f"{u['first_name']} {u['surname']}" if u else "system"
    get_db().execute("INSERT INTO activity(actor,action,detail,created_at) VALUES(?,?,?,?)",
                     (actor, action, detail, now()))


def new_account_number(db):
    while True:
        n = str(random.randint(10**9, 10**10 - 1))
        if not db.execute("SELECT 1 FROM users WHERE account_number=?", (n,)).fetchone() and \
           not db.execute("SELECT 1 FROM bank_accounts WHERE account_number=?", (n,)).fetchone():
            return n


def new_ref():
    return "ZP" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))


def seed_owner(db):
    """Create the single owner account if missing. Production reads OWNER_EMAIL / OWNER_PASSWORD."""
    if db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
        return
    email = os.environ.get("OWNER_EMAIL") or os.environ.get("ZENDPAY_OWNER_EMAIL") or "owner@zendpay.local"
    pw = os.environ.get("OWNER_PASSWORD") or os.environ.get("ZENDPAY_OWNER_PASSWORD")
    if not pw:
        if IS_PG or ON_VERCEL:
            print("[zendpay] No owner exists and OWNER_PASSWORD is not set. Set OWNER_EMAIL and OWNER_PASSWORD.")
            return
        pw = secrets.token_urlsafe(10)
    first = random.choice(["Adrian", "Selene", "Marcus", "Ingrid", "Tobias", "Amara", "Dario", "Lucia"])
    last = random.choice(["Holloway", "Okonkwo", "Verhoeven", "Castellan", "Brandt", "Mbeki", "Larsen", "Ferrer"])
    acct = new_account_number(db)
    db.execute("""INSERT INTO users(role,surname,first_name,email,currency,account_number,password_hash,
                  status,created_at) VALUES('owner',?,?,?,?,?,?, 'active',?)""",
               (last, first, email.strip().lower(), "USD", acct, generate_password_hash(pw), now()))
    if not (IS_PG or ON_VERCEL or os.environ.get("ZENDPAY_OWNER_PASSWORD")):
        path = os.path.join(BASE, "owner_credentials.txt")
        with open(path, "w") as f:
            f.write(f"Owner login\nEmail: {email}\nPassword: {pw}\nAccount: {acct}  Name: {first} {last}\n"
                    "Change the password from Owner > Settings after first login.\n")
        os.chmod(path, 0o600)
        print("[zendpay] Owner created. Credentials saved to owner_credentials.txt")
    else:
        print(f"[zendpay] Owner account created for {email}")


def init_db():
    if not IS_PG:  # on Supabase the schema comes from supabase/migrations/*.sql
        with sqlite3.connect(DB_PATH) as c:
            c.executescript(SCHEMA)
    db = DB()
    try:
        seed_owner(db)
    finally:
        db.close()


# ------------------------------------------------------------------ money utils
def D(x):
    return Decimal(str(x))


def parse_amount(s):
    try:
        v = D(str(s).replace(",", "").strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if v <= 0 or v > Decimal("1000000000"):
        return None
    return int(v * 100)


def convert(minor, frm, to):
    if frm == to:
        return minor
    rf, rt = D(CURRENCIES[frm][2]), D(CURRENCIES[to][2])
    return int((D(minor) * rt / rf).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calc_fee(minor, cur, kind):
    cfg = FEES[kind]
    rate = D(CURRENCIES[cur][2])
    usd = D(minor) / 100 / rate
    fee_usd = min(max(usd * D(cfg["pct"]), D(cfg["min_usd"])), D(cfg["max_usd"]))
    return int((fee_usd * rate * 100).quantize(Decimal("1"), rounding=ROUND_CEILING))


def money(minor, cur):
    sym = CURRENCIES.get(cur, ("", cur, 1))[1]
    return f"{sym}{minor / 100:,.2f}"


def local_dt(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=TZ_OFFSET_HOURS)


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


@app.template_filter("money")
def _money(minor, cur):
    return money(minor, cur)


@app.template_filter("dt")
def _dt(s):
    if not s:
        return "—"
    d = local_dt(s)
    return f"{d.strftime('%b')} {ordinal(d.day)}, {d.strftime('%H:%M:%S')}"


@app.template_filter("dfull")
def _dfull(s):
    return local_dt(s).strftime("%d %b %Y, %H:%M:%S") if s else "—"


if IS_PG:
    import psycopg.errors
    INTEGRITY_ERRORS = (psycopg.errors.UniqueViolation,)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def full_name(u):
    return f"{u['first_name']} {u['surname']}".strip()


app.jinja_env.globals.update(full_name=full_name, money=money, CURRENCIES=CURRENCIES)

# ------------------------------------------------------------------ security
def client_ip():
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() or request.remote_addr or "?"


def throttled(key, limit=5, window=300):
    """Rate limit state lives in the database (serverless instances share nothing in memory)."""
    r = get_db().execute("SELECT COUNT(*) c FROM attempts WHERE k=? AND ts>?", (key, time.time() - window)).fetchone()
    return r["c"] >= limit


def hit(key):
    db = get_db()
    db.execute("INSERT INTO attempts(k,ts) VALUES(?,?)", (key, time.time()))
    if random.random() < 0.02:
        db.execute("DELETE FROM attempts WHERE ts<?", (time.time() - 3600,))


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def guard():
    if request.endpoint == "static":
        return
    if request.method == "POST":
        tok = request.form.get("_csrf") or request.headers.get("X-CSRF")
        if not tok or not secrets.compare_digest(tok, session.get("_csrf", "")):
            abort(400, "Invalid form token. Reload the page and try again.")
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if g.user and g.user["status"] in ("suspended", "deleted", "rejected"):
            msg = {"suspended": SUSPENDED_MSG, "rejected": REJECTED_MSG}.get(g.user["status"], "Please sign in again.")
            session.clear()
            flash(msg, "error")
            g.user = None
            return redirect(url_for("login"))
        if not g.user:
            session.clear()
    ep = request.endpoint or ""
    if g.user and g.user["role"] != "owner" and g.user["status"] == "pending" and \
            ep not in ("status", "logout", "static", "set_theme"):
        return redirect(url_for("status"))


@app.after_request
def headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user:
            return redirect(url_for("login"))
        if g.user["role"] == "owner":
            return redirect(url_for("owner_home"))
        return f(*a, **k)
    return w


def owner_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user or g.user["role"] != "owner":
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


def can_send(u):
    return u["status"] == "active"


def owner_row():
    return get_db().execute("SELECT * FROM users WHERE role='owner'").fetchone()


# --------------------------------------------------------------- public pages
@app.route("/")
def index():
    if g.user:
        return redirect(url_for("owner_home" if g.user["role"] == "owner" else "home"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if g.user:
            return redirect(url_for("index"))
        return render_template("signup.html", countries=COUNTRIES, account_types=ACCOUNT_TYPES)
    f = request.get_json(silent=True) or {}
    get = lambda k: str(f.get(k, "")).strip()

    def err(msg, step, field=None):
        return jsonify(ok=False, error=msg, step=step, field=field), 400

    surname, first, email = get("surname"), get("first_name"), get("email").lower()
    country, phone = get("country"), re.sub(r"\D", "", get("phone"))
    if not surname or not first:
        return err("Enter your surname and first name.", 1)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return err("Enter a valid email address.", 1, "email")
    c = next((x for x in COUNTRIES if x["name"] == country), None)
    if not c:
        return err("Choose your country of residence.", 1, "country")
    if not 6 <= len(phone) <= 14:
        return err("Enter a valid phone number.", 1, "phone")
    if get("account_type") not in ACCOUNT_TYPES:
        return err("Choose an account type.", 2)
    cur = get("currency")
    if cur not in CURRENCIES:
        return err("Choose a primary currency.", 2)
    pw, pw2, pin = str(f.get("password", "")), str(f.get("confirm", "")), get("pin")
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return err("Password must be at least 8 characters with letters and numbers.", 3)
    if pw != pw2:
        return err("Passwords do not match.", 3)
    if not re.fullmatch(r"\d{4}", pin):
        return err("Transaction PIN must be exactly 4 digits.", 3)
    if not f.get("terms"):
        return err("Please accept the Terms of Service and Privacy Policy.", 3)
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return err("An account with this email already exists.", 1, "email")
    acct = new_account_number(db)
    try:
        cur_row = db.execute(
            """INSERT INTO users(surname,first_name,email,country,dial,phone,account_type,currency,account_number,
               password_hash,pin_hash,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
            (surname.title(), first.title(), email, country, c["dial"], phone, get("account_type"), cur, acct,
             generate_password_hash(pw), generate_password_hash(pin), now()))
    except INTEGRITY_ERRORS:
        return err("An account with this email already exists.", 1, "email")
    session.clear()
    session["uid"] = cur_row.lastrowid
    session.permanent = True
    g.user = db.execute("SELECT * FROM users WHERE id=?", (cur_row.lastrowid,)).fetchone()
    log("Signup", f"{email} ({country}, {cur}) awaiting verification")
    return jsonify(ok=True, next=url_for("status"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        key = f"login:{client_ip()}:{email}"
        if throttled(key):
            flash("Too many attempts. Try again in a few minutes.", "error")
            return redirect(url_for("login"))
        u = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u or u["status"] == "deleted" or not check_password_hash(u["password_hash"], request.form.get("password", "")):
            hit(key)
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        if u["status"] == "rejected":
            flash(REJECTED_MSG, "error")
            return redirect(url_for("login"))
        if u["status"] == "suspended":
            flash(SUSPENDED_MSG, "error")
            return redirect(url_for("login"))
        session.clear()
        session["uid"] = u["id"]
        session.permanent = True
        get_db().execute("UPDATE users SET last_login=? WHERE id=?", (now(), u["id"]))
        g.user = u
        log("Login", u["email"])
        return redirect(url_for("index"))
    if g.user:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/status")
def status():
    if not g.user:
        return redirect(url_for("login"))
    if g.user["role"] == "owner" or g.user["status"] != "pending":
        return redirect(url_for("index"))
    return render_template("status.html")


@app.route("/set-theme", methods=["POST"])
def set_theme():
    return ("", 204)


@app.route("/legal/<page>")
def legal(page):
    if page not in ("terms", "privacy"):
        abort(404)
    return render_template("legal.html", page=page)


# ---------------------------------------------------------------- user pages
def recent_tx(uid, n=5):
    return get_db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, n)).fetchall()


@app.route("/home")
@login_required
def home():
    return render_template("home.html", txs=recent_tx(g.user["id"]), nav="home")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    u, db = g.user, get_db()
    if request.method == "POST":
        if not can_send(u):
            flash("Your account is restricted. Deposit requests are unavailable.", "error")
            return redirect(url_for("deposit"))
        amt = parse_amount(request.form.get("amount"))
        if not amt:
            flash("Enter a valid amount.", "error")
            return redirect(url_for("deposit"))
        if db.execute("SELECT COUNT(*) c FROM deposit_requests WHERE user_id=? AND status='pending'",
                      (u["id"],)).fetchone()["c"] >= 3:
            flash("You already have 3 pending deposit requests. Please wait for approval.", "error")
            return redirect(url_for("deposit"))
        ow = owner_row()
        db.execute("BEGIN IMMEDIATE")
        ref = new_ref()
        t = db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,currency,status,cp_name,
                          cp_account,note,created_at) VALUES(?,?, 'Deposit','in',?,?, 'Pending',?,?, 'Deposit request',?)""",
                       (ref, u["id"], amt, u["currency"], full_name(ow), ow["account_number"], now()))
        db.execute("INSERT INTO deposit_requests(user_id,tx_id,amount,currency,created_at) VALUES(?,?,?,?,?)",
                   (u["id"], t.lastrowid, amt, u["currency"], now()))
        log("Deposit request", f"{money(amt, u['currency'])} by {u['email']}")
        db.execute("COMMIT")
        flash("Deposit request sent. The owner will review and fund your account.", "ok")
        return redirect(url_for("tx_detail", ref=ref))
    pend = db.execute("SELECT * FROM deposit_requests WHERE user_id=? AND status='pending' ORDER BY id DESC",
                      (u["id"],)).fetchall()
    return render_template("deposit.html", pend=pend, owner=owner_row(), nav="home")


@app.route("/api/lookup")
@login_required
def api_lookup():
    acct = re.sub(r"\D", "", request.args.get("acct", ""))
    r = get_db().execute("SELECT * FROM users WHERE account_number=? AND role='user' AND status IN ('active','restricted')",
                         (acct,)).fetchone()
    if not r or r["id"] == g.user["id"]:
        return jsonify(found=False)
    return jsonify(found=True, name=full_name(r).upper(), currency=r["currency"])


@app.route("/api/quote")
@login_required
def api_quote():
    amt = parse_amount(request.args.get("amount"))
    kind = "bank" if request.args.get("kind") == "bank" else "internal"
    to = request.args.get("to") or g.user["currency"]
    if not amt or to not in CURRENCIES:
        return jsonify(ok=False)
    cur = g.user["currency"]
    fee = calc_fee(amt, cur, kind)
    return jsonify(ok=True, fee=money(fee, cur), total=money(amt + fee, cur),
                   receives=money(convert(amt, cur, to), to), converted=(to != cur))


def verify_pin(u, pin):
    key = f"pin:{u['id']}"
    if throttled(key, 3, 600):
        return "Too many wrong PIN attempts. Try again in 10 minutes."
    if not re.fullmatch(r"\d{4}", pin or "") or not check_password_hash(u["pin_hash"], pin):
        hit(key)
        return "Incorrect transaction PIN."
    return None


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    u, db = g.user, get_db()
    if request.method == "POST":
        if not can_send(u):
            flash("Your account is restricted. You cannot send money.", "error")
            return redirect(url_for("transfer"))
        acct = re.sub(r"\D", "", request.form.get("account", ""))
        amt = parse_amount(request.form.get("amount"))
        note = request.form.get("note", "").strip()[:80]
        rcv = db.execute("SELECT * FROM users WHERE account_number=? AND role='user'", (acct,)).fetchone()
        if not rcv:
            flash(UNAVAILABLE_MSG, "error")  # account not in our database => treated as external institution
            return redirect(url_for("transfer"))
        if rcv["id"] == u["id"]:
            flash("You cannot transfer to your own account.", "error")
            return redirect(url_for("transfer"))
        if rcv["status"] not in ("active", "restricted"):
            flash("This account cannot receive money right now.", "error")
            return redirect(url_for("transfer"))
        if not amt:
            flash("Enter a valid amount.", "error")
            return redirect(url_for("transfer"))
        e = verify_pin(u, request.form.get("pin", ""))
        if e:
            flash(e, "error")
            return redirect(url_for("transfer"))
        fee = calc_fee(amt, u["currency"], "internal")
        got = convert(amt, u["currency"], rcv["currency"])
        db.execute("BEGIN IMMEDIATE")
        db.execute("SELECT id FROM users WHERE id IN (?,?) ORDER BY id FOR UPDATE", (u["id"], rcv["id"]))
        cur = db.execute("SELECT balance FROM users WHERE id=?", (u["id"],)).fetchone()
        if cur["balance"] < amt + fee:
            db.execute("ROLLBACK")
            flash("Insufficient balance (amount + fee).", "error")
            return redirect(url_for("transfer"))
        ref, t = new_ref(), now()
        db.execute("UPDATE users SET balance=balance-? WHERE id=?", (amt + fee, u["id"]))
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (got, rcv["id"]))
        db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,fee,currency,status,cp_name,cp_account,note,created_at)
                      VALUES(?,?, 'Transfer to','out',?,?,?, 'Successful',?,?,?,?)""",
                   (ref, u["id"], amt, fee, u["currency"], full_name(rcv), rcv["account_number"], note, t))
        db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,fee,currency,status,cp_name,cp_account,note,created_at)
                      VALUES(?,?, 'Transfer from','in',?,0,?, 'Successful',?,?,?,?)""",
                   (ref, rcv["id"], got, rcv["currency"], full_name(u), u["account_number"], note, t))
        log("Transfer", f"{money(amt, u['currency'])} {u['account_number']} -> {rcv['account_number']} fee {money(fee, u['currency'])}")
        db.execute("COMMIT")
        return redirect(url_for("tx_detail", ref=ref))
    return render_template("transfer.html", nav="home", fee=FEES["internal"])


@app.route("/transfer/bank", methods=["GET", "POST"])
@login_required
def transfer_bank():
    u, db = g.user, get_db()
    banks = db.execute("SELECT DISTINCT bank_name FROM bank_accounts WHERE active=1 ORDER BY bank_name").fetchall()
    if request.method == "POST":
        if not can_send(u):
            flash("Your account is restricted. You cannot send money.", "error")
            return redirect(url_for("transfer_bank"))
        bank = request.form.get("bank", "").strip()
        acct = re.sub(r"\D", "", request.form.get("account", ""))
        amt = parse_amount(request.form.get("amount"))
        note = request.form.get("note", "").strip()[:80]
        ba = db.execute("SELECT * FROM bank_accounts WHERE active=1 AND lower(bank_name)=lower(?) AND account_number=?",
                        (bank, acct)).fetchone()
        if not ba:
            flash(UNAVAILABLE_MSG, "error")
            return redirect(url_for("transfer_bank"))
        if not amt:
            flash("Enter a valid amount.", "error")
            return redirect(url_for("transfer_bank"))
        e = verify_pin(u, request.form.get("pin", ""))
        if e:
            flash(e, "error")
            return redirect(url_for("transfer_bank"))
        fee = calc_fee(amt, u["currency"], "bank")
        got = convert(amt, u["currency"], ba["currency"])
        ow = owner_row()
        db.execute("BEGIN IMMEDIATE")
        db.execute("SELECT id FROM users WHERE id=? FOR UPDATE", (u["id"],))
        if db.execute("SELECT balance FROM users WHERE id=?", (u["id"],)).fetchone()["balance"] < amt + fee:
            db.execute("ROLLBACK")
            flash("Insufficient balance (amount + fee).", "error")
            return redirect(url_for("transfer_bank"))
        ref, t = new_ref(), now()
        db.execute("UPDATE users SET balance=balance-? WHERE id=?", (amt + fee, u["id"]))
        db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,fee,currency,status,cp_name,cp_account,cp_bank,note,created_at)
                      VALUES(?,?, 'Bank Transfer','out',?,?,?, 'Successful',?,?,?,?,?)""",
                   (ref, u["id"], amt, fee, u["currency"], ba["account_name"], ba["account_number"], ba["bank_name"], note, t))
        db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,fee,currency,status,cp_name,cp_account,cp_bank,note,created_at)
                      VALUES(?,?, 'Bank Transfer','in',?,0,?, 'Successful',?,?,?,?,?)""",
                   (ref, ow["id"], got, ba["currency"], full_name(u), u["account_number"], ba["bank_name"], note, t))
        log("Bank transfer", f"{money(amt, u['currency'])} {u['account_number']} -> {ba['bank_name']} {ba['account_number']}")
        db.execute("COMMIT")
        return redirect(url_for("tx_detail", ref=ref))
    return render_template("transfer_bank.html", banks=banks, nav="home", fee=FEES["bank"])


def tx_filters(uid, args):
    month = args.get("month") or local_dt(now()).strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        month = local_dt(now()).strftime("%Y-%m")
    y, m = map(int, month.split("-"))
    start = datetime(y, m, 1) - timedelta(hours=TZ_OFFSET_HOURS)
    end = (datetime(y + (m == 12), 1 if m == 12 else m + 1, 1)) - timedelta(hours=TZ_OFFSET_HOURS)
    q, p = "user_id=? AND created_at>=? AND created_at<?", [uid, start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")]
    cat, st = args.get("category", ""), args.get("status", "")
    if cat in CATEGORIES:
        q += " AND category=?"; p.append(cat)
    if st in STATUSES:
        q += " AND status=?"; p.append(st)
    rows = get_db().execute(f"SELECT * FROM transactions WHERE {q} ORDER BY id DESC LIMIT 500", p).fetchall()
    return month, cat, st, rows


@app.route("/transactions")
@login_required
def transactions():
    month, cat, st, rows = tx_filters(g.user["id"], request.args)
    tin = sum(r["amount"] for r in rows if r["direction"] == "in" and r["status"] == "Successful")
    tout = sum(r["amount"] + r["fee"] for r in rows if r["direction"] == "out" and r["status"] == "Successful")
    return render_template("transactions.html", rows=rows, month=month, cat=cat, st=st, tin=tin, tout=tout,
                           categories=CATEGORIES, statuses=STATUSES, nav="tx")


@app.route("/transactions/download")
@login_required
def tx_download():
    month, cat, st, rows = tx_filters(g.user["id"], request.args)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ZENDPAY SIMULATION - virtual funds only. Not a bank statement."])
    w.writerow(["Account", g.user["account_number"], full_name(g.user), g.user["currency"], month])
    w.writerow(["Date", "Reference", "Category", "Counterparty", "Account", "Direction", "Amount", "Fee", "Currency", "Status"])
    for r in rows:
        w.writerow([_dfull(r["created_at"]), r["ref"], r["category"], r["cp_name"], r["cp_account"],
                    r["direction"], f"{r['amount'] / 100:.2f}", f"{r['fee'] / 100:.2f}", r["currency"], r["status"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=zendpay-{month}.csv"})


@app.route("/tx/<ref>")
@login_required
def tx_detail(ref):
    t = get_db().execute("SELECT * FROM transactions WHERE ref=? AND user_id=?", (ref, g.user["id"])).fetchone()
    if not t:
        abort(404)
    return render_template("tx_detail.html", t=t, nav="tx")


@app.route("/me")
@login_required
def me():
    return render_template("me.html", nav="me")


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html", nav="me")


@app.route("/settings/profile")
@login_required
def profile():
    return render_template("profile.html", nav="me")


@app.route("/settings/theme")
@login_required
def theme():
    return render_template("theme.html", nav="me")


@app.route("/settings/about")
@login_required
def about():
    return render_template("about.html", nav="me")


@app.route("/settings/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        u = g.user
        new = request.form.get("new", "")
        if not check_password_hash(u["password_hash"], request.form.get("current", "")):
            flash("Current password is incorrect.", "error")
        elif len(new) < 8 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
            flash("New password must be at least 8 characters with letters and numbers.", "error")
        elif new != request.form.get("confirm"):
            flash("Passwords do not match.", "error")
        else:
            get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), u["id"]))
            log("Password changed", u["email"])
            flash("Password updated.", "ok")
            return redirect(url_for("settings"))
        return redirect(url_for("change_password"))
    return render_template("password.html", nav="me")


@app.route("/settings/pin", methods=["GET", "POST"])
@login_required
def change_pin():
    if request.method == "POST":
        u = g.user
        new = request.form.get("new", "")
        if not check_password_hash(u["password_hash"], request.form.get("current", "")):
            flash("Account password is incorrect.", "error")
        elif not re.fullmatch(r"\d{4}", new):
            flash("PIN must be exactly 4 digits.", "error")
        else:
            get_db().execute("UPDATE users SET pin_hash=? WHERE id=?", (generate_password_hash(new), u["id"]))
            log("PIN changed", u["email"])
            flash("Transaction PIN updated.", "ok")
            return redirect(url_for("settings"))
        return redirect(url_for("change_pin"))
    return render_template("pin.html", nav="me")


# --------------------------------------------------------------------- owner
@app.route("/owner")
@owner_required
def owner_home():
    db = get_db()
    stats = {
        "customers": db.execute("SELECT COUNT(*) c FROM users WHERE role='user' AND status NOT IN ('deleted','rejected')").fetchone()["c"],
        "verify": db.execute("SELECT COUNT(*) c FROM users WHERE status='pending'").fetchone()["c"],
        "deposits": db.execute("SELECT COUNT(*) c FROM deposit_requests WHERE status='pending'").fetchone()["c"],
        "banks": db.execute("SELECT COUNT(*) c FROM bank_accounts WHERE active=1").fetchone()["c"],
    }
    fees = db.execute("SELECT currency, CAST(SUM(fee) AS BIGINT) f FROM transactions WHERE direction='out' AND status='Successful' AND fee>0 GROUP BY currency").fetchall()
    pend_users = db.execute("SELECT * FROM users WHERE status='pending' ORDER BY id").fetchall()
    pend_dep = db.execute("""SELECT d.*, u.first_name, u.surname, u.account_number FROM deposit_requests d
                             JOIN users u ON u.id=d.user_id WHERE d.status='pending' ORDER BY d.id""").fetchall()
    return render_template("owner_home.html", stats=stats, fees=fees, pend_users=pend_users, pend_dep=pend_dep, onav="home")


@app.route("/owner/verify/<int:uid>", methods=["POST"])
@owner_required
def owner_verify(uid):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=? AND status='pending'", (uid,)).fetchone()
    if not u:
        abort(404)
    if request.form.get("decision") == "approve":
        db.execute("UPDATE users SET status='active', decided_at=? WHERE id=?", (now(), uid))
        log("Account approved", u["email"])
        flash(f"{full_name(u)} approved.", "ok")
    else:
        db.execute("UPDATE users SET status='rejected', decided_at=? WHERE id=?", (now(), uid))
        log("Account rejected", u["email"])
        flash(f"{full_name(u)} declined.", "ok")
    return redirect(request.referrer or url_for("owner_home"))


@app.route("/owner/deposits")
@owner_required
def owner_deposits():
    rows = get_db().execute("""SELECT d.*, u.first_name, u.surname, u.account_number FROM deposit_requests d
                               JOIN users u ON u.id=d.user_id ORDER BY d.id DESC LIMIT 200""").fetchall()
    return render_template("owner_deposits.html", rows=rows, onav="dep")


@app.route("/owner/deposits/<int:did>", methods=["POST"])
@owner_required
def owner_deposit_decide(did):
    db, ow = get_db(), g.user
    db.execute("BEGIN IMMEDIATE")
    d = db.execute("SELECT * FROM deposit_requests WHERE id=? AND status='pending' FOR UPDATE", (did,)).fetchone()
    if not d:
        db.execute("ROLLBACK")
        abort(404)
    u = db.execute("SELECT * FROM users WHERE id=?", (d["user_id"],)).fetchone()
    if request.form.get("decision") == "approve":
        if u["status"] not in ("active", "restricted"):
            db.execute("ROLLBACK")
            flash("That account is not active, so it can't be funded.", "error")
            return redirect(url_for("owner_deposits"))
        t = now()
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (d["amount"], u["id"]))
        db.execute("UPDATE deposit_requests SET status='approved', decided_at=? WHERE id=?", (t, did))
        db.execute("UPDATE transactions SET status='Successful', created_at=? WHERE id=?", (t, d["tx_id"]))
        ref = db.execute("SELECT ref FROM transactions WHERE id=?", (d["tx_id"],)).fetchone()["ref"]
        db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,currency,status,cp_name,cp_account,note,created_at)
                      VALUES(?,?, 'Deposit','out',?,?, 'Successful',?,?, 'Deposit to customer',?)""",
                   (ref, ow["id"], d["amount"], d["currency"], full_name(u), u["account_number"], t))
        log("Deposit approved", f"{money(d['amount'], d['currency'])} to {u['account_number']}")
        flash("Deposit approved and credited.", "ok")
    else:
        db.execute("UPDATE deposit_requests SET status='declined', decided_at=? WHERE id=?", (now(), did))
        db.execute("UPDATE transactions SET status='Failed' WHERE id=?", (d["tx_id"],))
        log("Deposit declined", f"{money(d['amount'], d['currency'])} for {u['account_number']}")
        flash("Deposit declined.", "ok")
    db.execute("COMMIT")
    return redirect(request.referrer or url_for("owner_deposits"))


@app.route("/owner/customers")
@owner_required
def owner_customers():
    q, st = request.args.get("q", "").strip(), request.args.get("status", "")
    sql, p = "SELECT * FROM users WHERE role='user'", []
    if st:
        sql += " AND status=?"; p.append(st)
    else:
        sql += " AND status!='deleted'"
    if q:
        sql += " AND (email LIKE ? OR account_number LIKE ? OR surname LIKE ? OR first_name LIKE ?)"
        p += [f"%{q}%"] * 4
    rows = get_db().execute(sql + " ORDER BY id DESC LIMIT 300", p).fetchall()
    return render_template("owner_customers.html", rows=rows, q=q, st=st, onav="cust")


@app.route("/owner/customers/<int:uid>")
@owner_required
def owner_customer(uid):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=? AND role='user'", (uid,)).fetchone()
    if not u:
        abort(404)
    txs = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    acts = db.execute("SELECT * FROM activity WHERE detail LIKE ? ORDER BY id DESC LIMIT 30",
                      (f"%{u['email']}%",)).fetchall()
    return render_template("owner_customer.html", u=u, txs=txs, acts=acts, onav="cust")


@app.route("/owner/customers/<int:uid>/action", methods=["POST"])
@owner_required
def owner_customer_action(uid):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=? AND role='user'", (uid,)).fetchone()
    if not u:
        abort(404)
    act = request.form.get("action")
    if act == "fund":
        amt = parse_amount(request.form.get("amount"))
        if not amt:
            flash("Enter a valid amount.", "error")
        elif u["status"] not in ("active", "restricted"):
            flash("Only active or restricted accounts can be funded.", "error")
        else:
            ow, t, ref = g.user, now(), new_ref()
            note = request.form.get("note", "").strip()[:80] or "Deposit"
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE users SET balance=balance+? WHERE id=?", (amt, uid))
            db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,currency,status,cp_name,cp_account,note,created_at)
                          VALUES(?,?, 'Deposit','in',?,?, 'Successful',?,?,?,?)""",
                       (ref, uid, amt, u["currency"], full_name(ow), ow["account_number"], note, t))
            db.execute("""INSERT INTO transactions(ref,user_id,category,direction,amount,currency,status,cp_name,cp_account,note,created_at)
                          VALUES(?,?, 'Deposit','out',?,?, 'Successful',?,?,?,?)""",
                       (ref, ow["id"], amt, u["currency"], full_name(u), u["account_number"], note, t))
            log("Funded account", f"{money(amt, u['currency'])} to {u['account_number']} ({u['email']})")
            db.execute("COMMIT")
            flash(f"Funded {money(amt, u['currency'])}.", "ok")
    elif act in ("restrict", "unrestrict", "suspend", "unsuspend", "delete"):
        new = {"restrict": "restricted", "unrestrict": "active", "suspend": "suspended",
               "unsuspend": "active", "delete": "deleted"}[act]
        if u["status"] in ("pending", "rejected"):
            flash("Approve this account first.", "error")
        else:
            db.execute("UPDATE users SET status=? WHERE id=?", (new, uid))
            log(f"Account {new}", u["email"])
            flash(f"Account is now {new}.", "ok")
            if act == "delete":
                return redirect(url_for("owner_customers"))
    return redirect(url_for("owner_customer", uid=uid))


@app.route("/owner/banks", methods=["GET", "POST"])
@owner_required
def owner_banks():
    db = get_db()
    if request.method == "POST":
        act = request.form.get("action")
        if act == "add":
            bank = request.form.get("bank_name", "").strip()[:60]
            name = request.form.get("account_name", "").strip()[:80]
            acct = re.sub(r"\D", "", request.form.get("account_number", ""))
            cur = request.form.get("currency", "")
            if not bank or not name or not 6 <= len(acct) <= 20 or cur not in CURRENCIES:
                flash("Fill in bank name, account name, a 6-20 digit account number and a currency.", "error")
            else:
                try:
                    db.execute("INSERT INTO bank_accounts(bank_name,account_number,account_name,currency,created_at) VALUES(?,?,?,?,?)",
                               (bank, acct, name, cur, now()))
                    log("Bank account added", f"{bank} {acct}")
                    flash("Bank account added.", "ok")
                except INTEGRITY_ERRORS:
                    flash("That bank account already exists.", "error")
        elif act in ("toggle", "remove"):
            bid = int(request.form.get("id", 0))
            if act == "toggle":
                db.execute("UPDATE bank_accounts SET active=1-active WHERE id=?", (bid,))
            else:
                db.execute("DELETE FROM bank_accounts WHERE id=?", (bid,))
            log(f"Bank account {act}", str(bid))
        return redirect(url_for("owner_banks"))
    rows = db.execute("SELECT * FROM bank_accounts ORDER BY id DESC").fetchall()
    return render_template("owner_banks.html", rows=rows, onav="bank")


@app.route("/owner/transactions")
@owner_required
def owner_transactions():
    st = request.args.get("status", "")
    sql = """SELECT t.*, u.first_name, u.surname, u.account_number acct FROM transactions t
             JOIN users u ON u.id=t.user_id WHERE u.role='user'"""
    p = []
    if st in STATUSES:
        sql += " AND t.status=?"; p.append(st)
    rows = get_db().execute(sql + " ORDER BY t.id DESC LIMIT 300", p).fetchall()
    return render_template("owner_transactions.html", rows=rows, st=st, statuses=STATUSES, onav="tx")


@app.route("/owner/ledger")
@owner_required
def owner_ledger():
    rows = get_db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 300", (g.user["id"],)).fetchall()
    return render_template("owner_ledger.html", rows=rows, onav="tx")


@app.route("/owner/activity")
@owner_required
def owner_activity():
    rows = get_db().execute("SELECT * FROM activity ORDER BY id DESC LIMIT 300").fetchall()
    return render_template("owner_activity.html", rows=rows, onav="act")


@app.route("/owner/settings", methods=["GET", "POST"])
@owner_required
def owner_settings():
    if request.method == "POST":
        u, new = g.user, request.form.get("new", "")
        if not check_password_hash(u["password_hash"], request.form.get("current", "")):
            flash("Current password is incorrect.", "error")
        elif len(new) < 8 or new != request.form.get("confirm"):
            flash("New password must be 8+ characters and match the confirmation.", "error")
        else:
            get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), u["id"]))
            log("Owner password changed")
            flash("Password updated.", "ok")
        return redirect(url_for("owner_settings"))
    return render_template("owner_settings.html", onav="set")


@app.errorhandler(400)
@app.errorhandler(404)
def err_page(e):
    return render_template("error.html", e=e), e.code


try:
    init_db()
except Exception as exc:  # don't crash every request if the DB is briefly unreachable at cold start
    print(f"[zendpay] init_db failed: {exc}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

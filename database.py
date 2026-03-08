"""
Database v5 — SQLite (default) or MongoDB.
New: notes, file history, reminders, bulk sessions.
"""
import sqlite3, os, datetime
from config import MONGODB_URL

_mongo_db = None
if MONGODB_URL:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client = AsyncIOMotorClient(MONGODB_URL)
        _mongo_db = _mongo_client["pdf_doctor"]
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"⚠️ MongoDB failed: {e}, using SQLite")

_SQLITE_PATH = "data/pdf_doctor.db"
os.makedirs("data", exist_ok=True)

def _get_conn():
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite():
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            name        TEXT,
            username    TEXT,
            joined_at   TEXT,
            plan        TEXT DEFAULT 'free',
            plan_expiry TEXT,
            referrer_id INTEGER DEFAULT NULL,
            total_ops   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS daily_usage (
            user_id INTEGER,
            date    TEXT,
            count   INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        );
        CREATE TABLE IF NOT EXISTS feature_usage (
            user_id  INTEGER,
            date     TEXT,
            feature  TEXT,
            count    INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date, feature)
        );
        CREATE TABLE IF NOT EXISTS monthly_stats (
            month    TEXT,
            feature  TEXT,
            count    INTEGER DEFAULT 0,
            PRIMARY KEY (month, feature)
        );
        CREATE TABLE IF NOT EXISTS payment_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            plan        TEXT,
            screenshot_file_id TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id  INTEGER,
            referred_id  INTEGER,
            created_at   TEXT,
            PRIMARY KEY (referred_id)
        );
        CREATE TABLE IF NOT EXISTS user_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            title       TEXT,
            content     TEXT,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS file_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            feature     TEXT,
            filename    TEXT,
            file_id     TEXT,
            size_str    TEXT,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            chat_id     INTEGER,
            message     TEXT,
            fire_at     TEXT,
            done        INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS streaks (
            user_id     INTEGER PRIMARY KEY,
            streak      INTEGER DEFAULT 0,
            last_date   TEXT,
            best_streak INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            rating      INTEGER,
            message     TEXT,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS daily_bonus (
            user_id     INTEGER PRIMARY KEY,
            last_bonus  TEXT
        );
        """)

init_sqlite()

def _now():
    return datetime.datetime.now().isoformat()

def _today():
    return datetime.date.today().isoformat()

def _this_month():
    return datetime.date.today().strftime("%Y-%m")


# ── User Management ───────────────────────────────────────────────────────────

async def ensure_user(user_id: int, name: str, username: str, referrer_id: int = None):
    if _mongo_db:
        await _mongo_db.users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"user_id": user_id, "name": name, "username": username,
                              "joined_at": _now(), "plan": "free", "plan_expiry": None,
                              "referrer_id": referrer_id, "total_ops": 0}},
            upsert=True
        )
        if referrer_id:
            await _mongo_db.referrals.update_one(
                {"referred_id": user_id},
                {"$setOnInsert": {"referrer_id": referrer_id, "referred_id": user_id, "created_at": _now()}},
                upsert=True
            )
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(user_id,name,username,joined_at,plan,plan_expiry,referrer_id,total_ops) VALUES(?,?,?,?,?,?,?,?)",
                (user_id, name, username, _now(), "free", None, referrer_id, 0)
            )
            if referrer_id:
                conn.execute(
                    "INSERT OR IGNORE INTO referrals(referrer_id,referred_id,created_at) VALUES(?,?,?)",
                    (referrer_id, user_id, _now())
                )

async def get_user(user_id: int) -> dict | None:
    if _mongo_db:
        return await _mongo_db.users.find_one({"user_id": user_id})
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

async def get_plan(user_id: int) -> str:
    user = await get_user(user_id)
    if not user:
        return "free"
    plan   = user.get("plan", "free")
    expiry = user.get("plan_expiry")
    if plan != "free" and expiry:
        if datetime.datetime.fromisoformat(expiry) < datetime.datetime.now():
            await _expire_plan(user_id)
            return "free"
    return plan

async def _expire_plan(user_id: int):
    if _mongo_db:
        await _mongo_db.users.update_one({"user_id": user_id}, {"$set": {"plan": "free", "plan_expiry": None}})
    else:
        with _get_conn() as conn:
            conn.execute("UPDATE users SET plan='free', plan_expiry=NULL WHERE user_id=?", (user_id,))

async def set_premium(user_id: int, plan: str, expiry: datetime.datetime):
    expiry_str = expiry.isoformat()
    if _mongo_db:
        await _mongo_db.users.update_one(
            {"user_id": user_id},
            {"$set": {"plan": plan, "plan_expiry": expiry_str}}, upsert=True
        )
    else:
        with _get_conn() as conn:
            conn.execute("UPDATE users SET plan=?, plan_expiry=? WHERE user_id=?",
                         (plan, expiry_str, user_id))

async def get_all_users() -> list:
    if _mongo_db:
        return await _mongo_db.users.find({}).to_list(None)
    with _get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]


# ── Usage Tracking ─────────────────────────────────────────────────────────────

async def get_usage(user_id: int) -> int:
    today = _today()
    if _mongo_db:
        doc = await _mongo_db.daily_usage.find_one({"user_id": user_id, "date": today})
        return doc["count"] if doc else 0
    with _get_conn() as conn:
        row = conn.execute("SELECT count FROM daily_usage WHERE user_id=? AND date=?",
                           (user_id, today)).fetchone()
        return row["count"] if row else 0

async def get_feature_usage(user_id: int, feature: str) -> int:
    today = _today()
    if _mongo_db:
        doc = await _mongo_db.feature_usage.find_one({"user_id": user_id, "date": today, "feature": feature})
        return doc["count"] if doc else 0
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM feature_usage WHERE user_id=? AND date=? AND feature=?",
            (user_id, today, feature)
        ).fetchone()
        return row["count"] if row else 0

async def increment_usage(user_id: int, feature: str = "general"):
    today = _today()
    month = _this_month()
    if _mongo_db:
        await _mongo_db.daily_usage.update_one(
            {"user_id": user_id, "date": today}, {"$inc": {"count": 1}}, upsert=True)
        await _mongo_db.feature_usage.update_one(
            {"user_id": user_id, "date": today, "feature": feature}, {"$inc": {"count": 1}}, upsert=True)
        await _mongo_db.monthly_stats.update_one(
            {"month": month, "feature": feature}, {"$inc": {"count": 1}}, upsert=True)
        await _mongo_db.users.update_one({"user_id": user_id}, {"$inc": {"total_ops": 1}})
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO daily_usage(user_id,date,count) VALUES(?,?,1) "
                "ON CONFLICT(user_id,date) DO UPDATE SET count=count+1",
                (user_id, today))
            conn.execute(
                "INSERT INTO feature_usage(user_id,date,feature,count) VALUES(?,?,?,1) "
                "ON CONFLICT(user_id,date,feature) DO UPDATE SET count=count+1",
                (user_id, today, feature))
            conn.execute(
                "INSERT INTO monthly_stats(month,feature,count) VALUES(?,?,1) "
                "ON CONFLICT(month,feature) DO UPDATE SET count=count+1",
                (month, feature))
            conn.execute("UPDATE users SET total_ops=total_ops+1 WHERE user_id=?", (user_id,))

async def check_feature_limit(user_id: int, feature: str) -> tuple[bool, str]:
    from config import FEATURE_LIMITS
    plan   = await get_plan(user_id)
    limits = FEATURE_LIMITS.get(feature, {"free": 3, "basic": 30, "pro": None})
    limit  = limits.get(plan)

    if limit is None:
        return True, ""

    if limit == 0:
        plan_needed = "Pro" if limits.get("pro") is None else "Basic"
        return False, f"🔒 <b>{feature.title()}</b> requires <b>{plan_needed} plan</b>!\nUse /premium to upgrade."

    used = await get_feature_usage(user_id, feature)
    if used >= limit:
        return False, (
            f"⚠️ <b>Daily limit reached for {feature.title()}!</b>\n\n"
            f"📊 Used: <b>{used}/{limit}</b> today\n"
            f"🔄 Resets at midnight\n\n"
            f"💎 Upgrade to get more — use /premium"
        )
    return True, ""


# ── Dashboard Stats ────────────────────────────────────────────────────────────

async def get_user_dashboard(user_id: int) -> dict:
    today = _today()
    month = _this_month()

    if _mongo_db:
        today_features = {}
        async for doc in _mongo_db.feature_usage.find({"user_id": user_id, "date": today}):
            today_features[doc["feature"]] = doc["count"]
        month_total = 0
        async for doc in _mongo_db.daily_usage.find(
            {"user_id": user_id, "date": {"$gte": month + "-01"}}
        ):
            month_total += doc.get("count", 0)
        user = await get_user(user_id) or {}
        total_ops = user.get("total_ops", 0)
        ref_count = await _mongo_db.referrals.count_documents({"referrer_id": user_id})
    else:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT feature, count FROM feature_usage WHERE user_id=? AND date=?",
                (user_id, today)
            ).fetchall()
            today_features = {r["feature"]: r["count"] for r in rows}
            month_row = conn.execute(
                "SELECT SUM(count) as total FROM daily_usage WHERE user_id=? AND date LIKE ?",
                (user_id, month + "%")
            ).fetchone()
            month_total = month_row["total"] or 0
            user = await get_user(user_id) or {}
            total_ops = user.get("total_ops", 0)
            ref_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id=?", (user_id,)
            ).fetchone()
            ref_count = ref_row["cnt"] if ref_row else 0

    return {
        "today_features": today_features,
        "month_total":    month_total,
        "total_ops":      total_ops,
        "ref_count":      ref_count,
    }


async def get_admin_stats() -> dict:
    today = _today()
    month = _this_month()

    if _mongo_db:
        total_users   = await _mongo_db.users.count_documents({})
        free_users    = await _mongo_db.users.count_documents({"plan": "free"})
        basic_users   = await _mongo_db.users.count_documents({"plan": "basic"})
        pro_users     = await _mongo_db.users.count_documents({"plan": "pro"})
        today_active  = await _mongo_db.daily_usage.count_documents({"date": today})
        today_ops_doc = await _mongo_db.daily_usage.aggregate(
            [{"$match": {"date": today}}, {"$group": {"_id": None, "total": {"$sum": "$count"}}}]
        ).to_list(None)
        today_ops = today_ops_doc[0]["total"] if today_ops_doc else 0
        month_stats_docs = await _mongo_db.monthly_stats.find({"month": month}).to_list(None)
        month_stats = {d["feature"]: d["count"] for d in month_stats_docs}
        pending_payments = await _mongo_db.payment_requests.count_documents({"status": "pending"})
    else:
        with _get_conn() as conn:
            total_users  = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            free_users   = conn.execute("SELECT COUNT(*) as c FROM users WHERE plan='free'").fetchone()["c"]
            basic_users  = conn.execute("SELECT COUNT(*) as c FROM users WHERE plan='basic'").fetchone()["c"]
            pro_users    = conn.execute("SELECT COUNT(*) as c FROM users WHERE plan='pro'").fetchone()["c"]
            today_active = conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM daily_usage WHERE date=?", (today,)).fetchone()["c"]
            today_ops    = conn.execute("SELECT SUM(count) as s FROM daily_usage WHERE date=?", (today,)).fetchone()["s"] or 0
            rows = conn.execute("SELECT feature, count FROM monthly_stats WHERE month=?", (month,)).fetchall()
            month_stats = {r["feature"]: r["count"] for r in rows}
            pending_payments = conn.execute(
                "SELECT COUNT(*) as c FROM payment_requests WHERE status='pending'"
            ).fetchone()["c"]

    return {
        "total_users":      total_users,
        "free_users":       free_users,
        "basic_users":      basic_users,
        "pro_users":        pro_users,
        "today_active":     today_active,
        "today_ops":        today_ops,
        "month_stats":      month_stats,
        "pending_payments": pending_payments,
        "today":            today,
        "month":            month,
    }


async def save_payment_request(user_id: int, plan: str, file_id: str):
    if _mongo_db:
        await _mongo_db.payment_requests.insert_one(
            {"user_id": user_id, "plan": plan, "screenshot_file_id": file_id,
             "status": "pending", "created_at": _now()}
        )
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO payment_requests(user_id,plan,screenshot_file_id,status,created_at) VALUES(?,?,?,?,?)",
                (user_id, plan, file_id, "pending", _now())
            )


# ── Notes System ──────────────────────────────────────────────────────────────

async def save_note(user_id: int, title: str, content: str):
    if _mongo_db:
        await _mongo_db.user_notes.insert_one(
            {"user_id": user_id, "title": title, "content": content, "created_at": _now()}
        )
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO user_notes(user_id,title,content,created_at) VALUES(?,?,?,?)",
                (user_id, title, content, _now())
            )

async def get_notes(user_id: int) -> list:
    if _mongo_db:
        return await _mongo_db.user_notes.find({"user_id": user_id}).sort("created_at", -1).to_list(20)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM user_notes WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

async def delete_note(user_id: int, note_id: int):
    if _mongo_db:
        await _mongo_db.user_notes.delete_one({"user_id": user_id})
    else:
        with _get_conn() as conn:
            conn.execute("DELETE FROM user_notes WHERE id=? AND user_id=?", (note_id, user_id))


# ── File History ──────────────────────────────────────────────────────────────

async def save_file_history(user_id: int, feature: str, filename: str, file_id: str, size_str: str):
    if _mongo_db:
        await _mongo_db.file_history.insert_one(
            {"user_id": user_id, "feature": feature, "filename": filename,
             "file_id": file_id, "size_str": size_str, "created_at": _now()}
        )
        docs = await _mongo_db.file_history.find(
            {"user_id": user_id}, sort=[("created_at", -1)]
        ).to_list(None)
        if len(docs) > 10:
            old_ids = [d["_id"] for d in docs[10:]]
            await _mongo_db.file_history.delete_many({"_id": {"$in": old_ids}})
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO file_history(user_id,feature,filename,file_id,size_str,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, feature, filename, file_id, size_str, _now())
            )
            conn.execute("""
                DELETE FROM file_history WHERE user_id=? AND id NOT IN (
                    SELECT id FROM file_history WHERE user_id=? ORDER BY created_at DESC LIMIT 10
                )
            """, (user_id, user_id))

async def get_file_history(user_id: int) -> list:
    if _mongo_db:
        return await _mongo_db.file_history.find(
            {"user_id": user_id}, sort=[("created_at", -1)]
        ).to_list(10)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM file_history WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Reminders ─────────────────────────────────────────────────────────────────

async def save_reminder(user_id: int, chat_id: int, message: str, fire_at: datetime.datetime):
    if _mongo_db:
        await _mongo_db.reminders.insert_one({
            "user_id": user_id, "chat_id": chat_id,
            "message": message, "fire_at": fire_at.isoformat(), "done": False
        })
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO reminders(user_id,chat_id,message,fire_at,done) VALUES(?,?,?,?,0)",
                (user_id, chat_id, message, fire_at.isoformat())
            )

async def get_due_reminders() -> list:
    now = datetime.datetime.now().isoformat()
    if _mongo_db:
        return await _mongo_db.reminders.find(
            {"fire_at": {"$lte": now}, "done": False}
        ).to_list(None)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE fire_at <= ? AND done=0", (now,)
        ).fetchall()
        return [dict(r) for r in rows]

async def mark_reminder_done(reminder_id: int):
    if _mongo_db:
        await _mongo_db.reminders.update_one(
            {"_id": reminder_id}, {"$set": {"done": True}}
        )
    else:
        with _get_conn() as conn:
            conn.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))


# ── Streak System ─────────────────────────────────────────────────────────────

async def update_streak(user_id: int) -> tuple:
    """
    Call once per day on first use.
    Returns (current_streak, is_milestone, bonus_ops)
    """
    from config import STREAK_BONUS_OPS
    today = _today()
    if _mongo_db:
        doc = await _mongo_db.streaks.find_one({"user_id": user_id})
        if doc:
            last = doc.get("last_date", "")
            import datetime as dt
            yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
            if last == today:
                return doc["streak"], False, 0
            streak = doc["streak"] + 1 if last == yesterday else 1
            best   = max(streak, doc.get("best_streak", 0))
            await _mongo_db.streaks.update_one(
                {"user_id": user_id},
                {"$set": {"streak": streak, "last_date": today, "best_streak": best}}
            )
        else:
            streak = 1
            await _mongo_db.streaks.insert_one(
                {"user_id": user_id, "streak": 1, "last_date": today, "best_streak": 1}
            )
    else:
        with _get_conn() as conn:
            row = conn.execute("SELECT streak, last_date, best_streak FROM streaks WHERE user_id=?", (user_id,)).fetchone()
            if row:
                last = row["last_date"]
                import datetime as dt
                yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
                if last == today:
                    return row["streak"], False, 0
                streak = row["streak"] + 1 if last == yesterday else 1
                best   = max(streak, row["best_streak"] or 0)
                conn.execute("UPDATE streaks SET streak=?, last_date=?, best_streak=? WHERE user_id=?",
                             (streak, today, best, user_id))
            else:
                streak = 1
                conn.execute("INSERT INTO streaks(user_id,streak,last_date,best_streak) VALUES(?,1,?,1)",
                             (user_id, today))

    bonus     = STREAK_BONUS_OPS.get(streak, 0)
    milestone = streak in STREAK_BONUS_OPS
    return streak, milestone, bonus


async def get_streak(user_id: int) -> dict:
    """Return user's streak info."""
    if _mongo_db:
        doc = await _mongo_db.streaks.find_one({"user_id": user_id}) or {}
        return {"streak": doc.get("streak", 0), "best": doc.get("best_streak", 0)}
    with _get_conn() as conn:
        row = conn.execute("SELECT streak, best_streak FROM streaks WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return {"streak": row["streak"], "best": row["best_streak"]}
        return {"streak": 0, "best": 0}


# ── Daily Bonus ───────────────────────────────────────────────────────────────

async def claim_daily_bonus(user_id: int) -> bool:
    """Returns True if bonus was given (first time today), False if already claimed."""
    from config import DAILY_BONUS_OPS
    today = _today()
    if _mongo_db:
        doc = await _mongo_db.daily_bonus.find_one({"user_id": user_id})
        if doc and doc.get("last_bonus") == today:
            return False
        await _mongo_db.daily_bonus.update_one(
            {"user_id": user_id}, {"$set": {"last_bonus": today}}, upsert=True
        )
    else:
        with _get_conn() as conn:
            row = conn.execute("SELECT last_bonus FROM daily_bonus WHERE user_id=?", (user_id,)).fetchone()
            if row and row["last_bonus"] == today:
                return False
            conn.execute("INSERT OR REPLACE INTO daily_bonus(user_id,last_bonus) VALUES(?,?)",
                         (user_id, today))
    return True


# ── Feedback ─────────────────────────────────────────────────────────────────

async def save_feedback(user_id: int, rating: int, message: str = ""):
    if _mongo_db:
        await _mongo_db.feedback.insert_one({
            "user_id": user_id, "rating": rating,
            "message": message, "created_at": _now()
        })
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO feedback(user_id,rating,message,created_at) VALUES(?,?,?,?)",
                (user_id, rating, message, _now())
            )


async def get_feedback_stats() -> dict:
    if _mongo_db:
        total = await _mongo_db.feedback.count_documents({})
        pipe  = [{"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]
        res   = await _mongo_db.feedback.aggregate(pipe).to_list(1)
        avg   = round(res[0]["avg"], 1) if res else 0.0
        return {"total": total, "avg_rating": avg}
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*), AVG(rating) FROM feedback").fetchone()
        return {"total": row[0] or 0, "avg_rating": round(row[1] or 0.0, 1)}


async def get_recent_feedback(limit: int = 10) -> list:
    if _mongo_db:
        return await _mongo_db.feedback.find().sort("created_at", -1).to_list(limit)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, rating, message, created_at FROM feedback ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Referral System ───────────────────────────────────────────────────────────

async def get_referral_count(user_id: int) -> int:
    if _mongo_db:
        return await _mongo_db.users.count_documents({"referred_by": user_id})
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)).fetchone()
        return row[0] if row else 0


async def get_referral_link_text(user_id: int, bot_username: str) -> str:
    count = await get_referral_count(user_id)
    from config import REFERRAL_NEEDED, REFERRAL_BONUS_DAYS
    remaining = max(0, REFERRAL_NEEDED - (count % REFERRAL_NEEDED))
    link      = f"https://t.me/{bot_username}?start=ref_{user_id}"
    return (
        f"👥 <b>Your Referral Link:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📊 Total referred: <b>{count}</b>\n"
        f"🎯 {remaining} more → <b>+{REFERRAL_BONUS_DAYS} days Basic FREE!</b>\n\n"
        f"💡 Share this link and earn rewards!"
    )


# ── v7: Coin System ───────────────────────────────────────────────────────────

async def _init_coins_tables():
    if _mongo_db:
        return
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS coins (
            user_id   INTEGER PRIMARY KEY,
            balance   INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS coin_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            amount     INTEGER,
            reason     TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS promo_uses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            code       TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS trials (
            user_id    INTEGER PRIMARY KEY,
            expires_at TEXT,
            used       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS achievements (
            user_id    INTEGER,
            badge_id   TEXT,
            earned_at  TEXT,
            PRIMARY KEY (user_id, badge_id)
        );
        """)

asyncio.get_event_loop().run_until_complete(_init_coins_tables()) if not _mongo_db else None


async def get_coins(user_id: int) -> int:
    if _mongo_db:
        doc = await _mongo_db.coins.find_one({"user_id": user_id})
        return doc["balance"] if doc else 0
    with _get_conn() as conn:
        row = conn.execute("SELECT balance FROM coins WHERE user_id=?", (user_id,)).fetchone()
        return row["balance"] if row else 0


async def add_coins(user_id: int, amount: int, reason: str = "") -> int:
    """Add coins, return new balance."""
    if _mongo_db:
        await _mongo_db.coins.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount, "total_earned": max(0, amount)}},
            upsert=True
        )
        await _mongo_db.coin_log.insert_one(
            {"user_id": user_id, "amount": amount, "reason": reason, "created_at": _now()}
        )
        doc = await _mongo_db.coins.find_one({"user_id": user_id})
        return doc["balance"]
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO coins(user_id,balance,total_earned) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance=balance+?, total_earned=total_earned+?",
            (user_id, amount, max(0, amount), amount, max(0, amount))
        )
        conn.execute(
            "INSERT INTO coin_log(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user_id, amount, reason, _now())
        )
        row = conn.execute("SELECT balance FROM coins WHERE user_id=?", (user_id,)).fetchone()
        return row["balance"] if row else 0


async def spend_coins(user_id: int, amount: int, reason: str = "") -> bool:
    """Spend coins. Returns False if insufficient balance."""
    balance = await get_coins(user_id)
    if balance < amount:
        return False
    await add_coins(user_id, -amount, reason)
    return True


async def get_coin_log(user_id: int, limit: int = 10) -> list:
    if _mongo_db:
        return await _mongo_db.coin_log.find({"user_id": user_id}).sort("created_at", -1).to_list(limit)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT amount, reason, created_at FROM coin_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ── v7: Promo Codes ───────────────────────────────────────────────────────────

async def redeem_promo(user_id: int, code: str) -> dict:
    """Returns {ok, message, type, value} dict."""
    from config import PROMO_CODES
    code = code.upper().strip()
    if code not in PROMO_CODES:
        return {"ok": False, "message": "❌ Invalid promo code!"}
    promo = PROMO_CODES[code]
    # Check if user already used
    if _mongo_db:
        existing = await _mongo_db.promo_uses.find_one({"user_id": user_id, "code": code})
        count    = await _mongo_db.promo_uses.count_documents({"code": code})
    else:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM promo_uses WHERE user_id=? AND code=?", (user_id, code)
            ).fetchone()
            count_row = conn.execute(
                "SELECT COUNT(*) FROM promo_uses WHERE code=?", (code,)
            ).fetchone()
            count = count_row[0] if count_row else 0
    if existing:
        return {"ok": False, "message": "⚠️ You already used this code!"}
    if count >= promo.get("max_uses", 9999):
        return {"ok": False, "message": "⚠️ This promo code has expired!"}
    # Record use
    if _mongo_db:
        await _mongo_db.promo_uses.insert_one({"user_id": user_id, "code": code, "created_at": _now()})
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO promo_uses(user_id,code,created_at) VALUES(?,?,?)",
                (user_id, code, _now())
            )
    return {"ok": True, "type": promo["type"], "value": promo["value"],
            "days": promo.get("days", 0), "message": "✅ Promo redeemed!"}


# ── v7: Trial System ─────────────────────────────────────────────────────────

async def activate_trial(user_id: int) -> dict:
    """Activate free trial. Returns {ok, message, expires_at}."""
    from config import TRIAL_DURATION_DAYS, TRIAL_PLAN
    if _mongo_db:
        existing = await _mongo_db.trials.find_one({"user_id": user_id})
    else:
        with _get_conn() as conn:
            existing = conn.execute("SELECT used FROM trials WHERE user_id=?", (user_id,)).fetchone()
    if existing:
        return {"ok": False, "message": "⚠️ You already used your free trial!"}
    # Check current plan
    plan = await get_plan(user_id)
    if plan != "free":
        return {"ok": False, "message": "⚠️ Trial only available for Free users!"}
    expires = (datetime.datetime.now() + datetime.timedelta(days=TRIAL_DURATION_DAYS)).isoformat()
    if _mongo_db:
        await _mongo_db.trials.insert_one({"user_id": user_id, "expires_at": expires, "used": 1})
        await _mongo_db.users.update_one(
            {"user_id": user_id},
            {"$set": {"plan": TRIAL_PLAN, "trial_expires": expires}}
        )
    else:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO trials(user_id,expires_at,used) VALUES(?,?,1)", (user_id, expires)
            )
            conn.execute(
                "UPDATE users SET plan=?, premium_until=? WHERE user_id=?",
                (TRIAL_PLAN, expires, user_id)
            )
    return {"ok": True, "message": f"🎉 Trial activated!", "expires_at": expires}


async def check_trial_expiry(user_id: int):
    """Call on each message — downgrade if trial expired."""
    if _mongo_db:
        trial = await _mongo_db.trials.find_one({"user_id": user_id, "used": 1})
        if trial:
            if datetime.datetime.now().isoformat() > trial["expires_at"]:
                user = await _mongo_db.users.find_one({"user_id": user_id})
                if user and user.get("plan") == "basic" and user.get("trial_expires"):
                    await _mongo_db.users.update_one(
                        {"user_id": user_id}, {"$set": {"plan": "free", "trial_expires": None}}
                    )
    else:
        with _get_conn() as conn:
            trial = conn.execute(
                "SELECT expires_at FROM trials WHERE user_id=? AND used=1", (user_id,)
            ).fetchone()
            if trial and datetime.datetime.now().isoformat() > trial["expires_at"]:
                user = conn.execute(
                    "SELECT plan FROM users WHERE user_id=?", (user_id,)
                ).fetchone()
                if user and user["plan"] == "basic":
                    conn.execute("UPDATE users SET plan='free' WHERE user_id=?", (user_id,))


# ── v7: Achievements ─────────────────────────────────────────────────────────

async def check_and_award_achievements(user_id: int) -> list:
    """Check all achievements, award new ones. Returns list of newly earned badges."""
    from config import ACHIEVEMENTS
    new_badges = []
    # Get user stats
    total_ops = 0
    streak    = 0
    refs      = 0
    if _mongo_db:
        doc = await _mongo_db.users.find_one({"user_id": user_id}) or {}
        total_ops = doc.get("total_ops", 0)
        s_doc     = await _mongo_db.streaks.find_one({"user_id": user_id}) or {}
        streak    = s_doc.get("streak", 0)
        refs      = await _mongo_db.users.count_documents({"referred_by": user_id})
        earned    = {d["badge_id"] for d in await _mongo_db.achievements.find({"user_id": user_id}).to_list(None)}
    else:
        with _get_conn() as conn:
            u_row = conn.execute("SELECT total_ops FROM users WHERE user_id=?", (user_id,)).fetchone()
            total_ops = (u_row["total_ops"] if u_row and "total_ops" in u_row.keys() else 0) or 0
            s_row = conn.execute("SELECT streak FROM streaks WHERE user_id=?", (user_id,)).fetchone()
            streak = s_row["streak"] if s_row else 0
            r_row = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)).fetchone()
            refs  = r_row[0] if r_row else 0
            e_rows = conn.execute("SELECT badge_id FROM achievements WHERE user_id=?", (user_id,)).fetchall()
            earned = {r["badge_id"] for r in e_rows}

    for badge_id, badge in ACHIEVEMENTS.items():
        if badge_id in earned:
            continue
        award = False
        if "ops"    in badge and total_ops >= badge["ops"]:    award = True
        if "streak" in badge and streak    >= badge["streak"]: award = True
        if "refs"   in badge and refs      >= badge["refs"]:   award = True
        if award:
            if _mongo_db:
                await _mongo_db.achievements.insert_one(
                    {"user_id": user_id, "badge_id": badge_id, "earned_at": _now()}
                )
            else:
                with _get_conn() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO achievements(user_id,badge_id,earned_at) VALUES(?,?,?)",
                        (user_id, badge_id, _now())
                    )
            new_badges.append(badge)
    return new_badges


async def get_achievements(user_id: int) -> list:
    from config import ACHIEVEMENTS
    if _mongo_db:
        earned = {d["badge_id"] for d in await _mongo_db.achievements.find({"user_id": user_id}).to_list(None)}
    else:
        with _get_conn() as conn:
            rows   = conn.execute("SELECT badge_id FROM achievements WHERE user_id=?", (user_id,)).fetchall()
            earned = {r["badge_id"] for r in rows}
    result = []
    for bid, badge in ACHIEVEMENTS.items():
        result.append({**badge, "id": bid, "earned": bid in earned})
    return result

"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Database     ║
╚══════════════════════════════════════════╝
"""

import aiosqlite
import os
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from config import DB_PATH, OWNER_IDS


async def init_db():
    """Initialize database and create tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                plan        TEXT DEFAULT 'free',
                plan_expiry TEXT DEFAULT NULL,
                daily_count INTEGER DEFAULT 0,
                last_reset  TEXT DEFAULT NULL,
                joined_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                is_banned   INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                url         TEXT,
                title       TEXT,
                file_size   INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                text        TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def ensure_user(user_id: int, username: str = None):
    """Insert user if not exists; handle owner plan."""
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await get_user(user_id)
        if not existing:
            plan = "owner" if user_id in OWNER_IDS else "free"
            await db.execute(
                """INSERT OR IGNORE INTO users
                   (user_id, username, plan, joined_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, username or "", plan, datetime.utcnow().isoformat())
            )
            await db.commit()
        else:
            if username:
                await db.execute(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (username, user_id)
                )
                await db.commit()


async def check_and_reset_daily(user_id: int):
    """Reset daily count if it's a new day."""
    user = await get_user(user_id)
    if not user:
        return
    today = date.today().isoformat()
    if user.get("last_reset") != today:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET daily_count = 0, last_reset = ? WHERE user_id = ?",
                (today, user_id)
            )
            await db.commit()


async def check_plan_expiry(user_id: int):
    """Revert plan to free if expired."""
    user = await get_user(user_id)
    if not user:
        return
    if user["plan"] in ("basic", "premium") and user.get("plan_expiry"):
        try:
            expiry = datetime.fromisoformat(user["plan_expiry"])
            if datetime.utcnow() > expiry:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE users SET plan = 'free', plan_expiry = NULL WHERE user_id = ?",
                        (user_id,)
                    )
                    await db.commit()
        except Exception:
            pass


async def get_daily_limit(user_id: int) -> int:
    from config import PLANS, FREE_LIMIT
    user = await get_user(user_id)
    if not user:
        return FREE_LIMIT
    plan = user.get("plan", "free")
    return PLANS.get(plan, PLANS["free"])["limit"]


async def increment_daily_count(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET daily_count = daily_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def set_plan(user_id: int, plan: str, days: int = 0):
    from datetime import timedelta
    expiry = None
    if days > 0:
        expiry = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET plan = ?, plan_expiry = ? WHERE user_id = ?",
            (plan, expiry, user_id)
        )
        await db.commit()


async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def log_download(user_id: int, url: str, title: str = "", file_size: int = 0, status: str = "done"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO downloads (user_id, url, title, file_size, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, url, title, file_size, status, datetime.utcnow().isoformat())
        )
        await db.commit()


async def get_user_history(user_id: int, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM downloads WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_banned_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_banned = 1") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c:
            banned = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM downloads") as c:
            total_dl = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM downloads WHERE status = 'done'") as c:
            success_dl = (await c.fetchone())[0]
        async with db.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan") as c:
            plan_rows = await c.fetchall()
        plans = {row[0]: row[1] for row in plan_rows}
    return {
        "total_users": total_users,
        "banned": banned,
        "total_downloads": total_dl,
        "successful_downloads": success_dl,
        "plans": plans
    }


async def save_feedback(user_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO feedback (user_id, text, created_at) VALUES (?, ?, ?)",
            (user_id, text, datetime.utcnow().isoformat())
        )
        await db.commit()

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite

from app.data import DEFAULT_SLOTS, SERVICES


class Database:
    def __init__(self, path: str, timezone: str = "Europe/Minsk"):
        self.path = path
        self.timezone = timezone

    def today(self):
        return datetime.now(ZoneInfo(self.timezone)).date()

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row

    async def close(self):
        await self.conn.close()

    async def init(self):
        await self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, phone TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL UNIQUE, description TEXT NOT NULL, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS slots (time TEXT PRIMARY KEY, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS blocked_slots (date TEXT NOT NULL, time TEXT, PRIMARY KEY(date, time));
        CREATE TABLE IF NOT EXISTS appointments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, services TEXT NOT NULL,
          brand TEXT NOT NULL, model TEXT NOT NULL, car_year TEXT NOT NULL, plate TEXT, body_type TEXT,
          comment TEXT, photos TEXT DEFAULT '[]', phone TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', manager_note TEXT, proposed_date TEXT, proposed_time TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS active_slot_unique ON appointments(date, time) WHERE status IN ('pending', 'confirmed', 'proposed');
        """)
        for title, description in SERVICES:
            await self.conn.execute("INSERT OR IGNORE INTO services(title, description) VALUES (?, ?)", (title, description))
        for item in DEFAULT_SLOTS:
            await self.conn.execute("INSERT OR IGNORE INTO slots(time) VALUES (?)", (item,))
        await self.conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('workdays', '0,1,2,3,4,5')")
        await self.conn.commit()

    async def upsert_user(self, user, phone=None):
        await self.conn.execute("""INSERT INTO users(telegram_id,full_name,username,phone) VALUES(?,?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET full_name=excluded.full_name,username=excluded.username,phone=COALESCE(excluded.phone,users.phone)""", (user.id, user.full_name, user.username or "", phone))
        await self.conn.commit()

    async def user_phone(self, user_id):
        row = await (await self.conn.execute("SELECT phone FROM users WHERE telegram_id=?", (user_id,))).fetchone()
        return row["phone"] if row else None

    async def services(self):
        return await (await self.conn.execute("SELECT * FROM services WHERE active=1 ORDER BY id")).fetchall()

    async def slots(self):
        return [r["time"] for r in await (await self.conn.execute("SELECT time FROM slots WHERE active=1 ORDER BY time")).fetchall()]

    async def workdays(self):
        row = await (await self.conn.execute("SELECT value FROM settings WHERE key='workdays' ")).fetchone()
        return {int(x) for x in row["value"].split(",")} if row else set(range(6))

    async def available_dates(self):
        today, days = self.today(), await self.workdays()
        return [today + timedelta(days=i) for i in range(14) if (today + timedelta(days=i)).weekday() in days]

    async def free_slots(self, day):
        busy = {r["time"] for r in await (await self.conn.execute("SELECT time FROM appointments WHERE date=? AND status IN ('pending','confirmed','proposed')", (day,))).fetchall()}
        blocked = {r["time"] for r in await (await self.conn.execute("SELECT time FROM blocked_slots WHERE date=?", (day,))).fetchall()}
        return [] if None in blocked else [item for item in await self.slots() if item not in busy and item not in blocked]

    async def create_appointment(self, values):
        keys, marks = ", ".join(values), ", ".join("?" for _ in values)
        try:
            cur = await self.conn.execute(f"INSERT INTO appointments({keys}) VALUES({marks})", tuple(values.values()))
            await self.conn.commit(); return cur.lastrowid
        except aiosqlite.IntegrityError: return None

    async def appointment(self, appointment_id):
        return await (await self.conn.execute("SELECT a.*,u.full_name,u.username FROM appointments a LEFT JOIN users u ON u.telegram_id=a.user_id WHERE a.id=?", (appointment_id,))).fetchone()

    async def user_appointments(self, user_id):
        return await (await self.conn.execute("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC,time DESC", (user_id,))).fetchall()

    async def set_status(self, appointment_id, status, note=None):
        await self.conn.execute("UPDATE appointments SET status=?,manager_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status,note,appointment_id)); await self.conn.commit()

    async def propose(self, appointment_id, day, time):
        try:
            await self.conn.execute("UPDATE appointments SET date=?,time=?,status='proposed',proposed_date=?,proposed_time=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (day,time,day,time,appointment_id)); await self.conn.commit(); return True
        except aiosqlite.IntegrityError:
            return False

    async def accept_proposal(self, appointment_id):
        await self.conn.execute("UPDATE appointments SET status='confirmed',proposed_date=NULL,proposed_time=NULL WHERE id=?", (appointment_id,)); await self.conn.commit(); return True

    async def active_appointments(self, day=None):
        sql, args = "SELECT * FROM appointments WHERE status IN ('pending','confirmed','proposed')", []
        if day: sql += " AND date=?"; args.append(day)
        return await (await self.conn.execute(sql + " ORDER BY date,time", args)).fetchall()

    async def search(self, term):
        return await (await self.conn.execute("SELECT * FROM appointments WHERE CAST(id AS TEXT)=? OR phone LIKE ? ORDER BY created_at DESC LIMIT 20", (term, f"%{term}%"))).fetchall()

    async def block(self, day, time=None):
        await self.conn.execute("INSERT OR IGNORE INTO blocked_slots(date,time) VALUES(?,?)", (day,time)); await self.conn.commit()

    async def stats(self):
        output = {}
        for days, name in ((7,'week'),(30,'month')):
            rows = await (await self.conn.execute("SELECT status,COUNT(*) count FROM appointments WHERE date(created_at)>=date('now',?) GROUP BY status", (f'-{days} days',))).fetchall()
            output[name] = {r['status']:r['count'] for r in rows}
        return output

    @staticmethod
    def photos(value): return json.loads(value or '[]')

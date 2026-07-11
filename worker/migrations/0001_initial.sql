CREATE TABLE IF NOT EXISTS users (
  telegram_id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL DEFAULT '',
  username TEXT NOT NULL DEFAULT '',
  phone TEXT
);
CREATE TABLE IF NOT EXISTS services (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS slots (time TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS blocked_slots (date TEXT NOT NULL, time TEXT, PRIMARY KEY(date, time));
CREATE TABLE IF NOT EXISTS sessions (
  chat_id INTEGER PRIMARY KEY,
  state TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  services TEXT NOT NULL,
  brand TEXT NOT NULL,
  model TEXT NOT NULL,
  car_year TEXT NOT NULL,
  plate TEXT,
  body_type TEXT,
  comment TEXT,
  photos TEXT NOT NULL DEFAULT '[]',
  phone TEXT NOT NULL,
  date TEXT NOT NULL,
  time TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  manager_note TEXT,
  proposed_date TEXT,
  proposed_time TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS active_slot_unique ON appointments(date, time)
  WHERE status IN ('pending', 'confirmed', 'proposed');

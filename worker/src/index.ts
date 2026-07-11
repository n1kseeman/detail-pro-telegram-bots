export interface Env {
  DB: D1Database;
  BOT_TOKEN: string;
  ADMIN_GROUP_ID: string;
  WEBHOOK_SECRET?: string;
  CENTER_NAME?: string;
}

type Session = { state: string; data: Record<string, unknown> };
type Appointment = Record<string, unknown>;

const SERVICES: [string, string][] = [
  ["Оклейка автомобиля пленкой", "Защита кузова и выразительный внешний вид автомобиля."],
  ["Полировка", "Деликатное восстановление глубины цвета и блеска покрытия."],
  ["Химчистка салона", "Бережная глубокая очистка салона и его деталей."],
  ["Антикоррозийная обработка", "Защита скрытых полостей и днища от влаги."],
  ["Шумоизоляция", "Повышение акустического комфорта в поездках."],
  ["Тонировка", "Аккуратное оформление стекол качественной пленкой."],
  ["Керамическое покрытие", "Долговременная защита и насыщенный блеск кузова."],
  ["Антидождь", "Улучшение видимости в дождливую погоду."],
  ["Мойка", "Тщательная мойка и уход за автомобилем."]
];
const SLOTS = ["10:00", "12:00", "14:00", "16:00", "18:00"];
const STATUS: Record<string, string> = { pending: "Ожидает подтверждения", confirmed: "Подтверждена", cancelled: "Отменена", completed: "Завершена", rejected: "Отклонена", proposed: "Предложено другое время" };

const b = (text: string, callback_data: string) => ({ text, callback_data });
const keyboard = (rows: unknown[][]) => ({ inline_keyboard: rows });
const dayLabel = (day: string) => new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Minsk", day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(`${day}T12:00:00Z`));
const esc = (v: unknown) => String(v ?? "—").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

async function telegram(env: Env, method: string, payload: Record<string, unknown>) {
  const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json<{ ok?: boolean; result?: unknown; description?: string }>().catch(() => ({} as { ok?: boolean; result?: unknown; description?: string }));
  if (!response.ok || result.ok === false) console.error(`Telegram ${method} failed: ${result.description || response.status}`);
  return result.result;
}
async function send(env: Env, chat_id: number | string, text: string, reply_markup?: unknown) {
  return telegram(env, "sendMessage", { chat_id, text, parse_mode: "HTML", reply_markup });
}
async function edit(env: Env, chat_id: number, message_id: number, text: string, reply_markup?: unknown) {
  await telegram(env, "editMessageText", { chat_id, message_id, text, parse_mode: "HTML", reply_markup });
}
async function answer(env: Env, callback_query_id: string, text?: string) { await telegram(env, "answerCallbackQuery", { callback_query_id, text }); }

async function seed(db: D1Database) {
  const statements = [
    db.prepare("INSERT OR IGNORE INTO settings(key,value) VALUES('workdays','0,1,2,3,4,5')"),
    ...SLOTS.map((time) => db.prepare("INSERT OR IGNORE INTO slots(time,active) VALUES(?,1)").bind(time)),
    ...SERVICES.map(([title, description]) => db.prepare("INSERT OR IGNORE INTO services(title,description) VALUES(?,?)").bind(title, description))
  ];
  await db.batch(statements);
}
async function session(db: D1Database, chatId: number): Promise<Session> {
  const row = await db.prepare("SELECT state,data FROM sessions WHERE chat_id=?").bind(chatId).first<{ state: string; data: string }>();
  return row ? { state: row.state, data: JSON.parse(row.data) } : { state: "", data: {} };
}
async function setSession(db: D1Database, chatId: number, state: string, data: Record<string, unknown>) {
  await db.prepare("INSERT INTO sessions(chat_id,state,data,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(chat_id) DO UPDATE SET state=excluded.state,data=excluded.data,updated_at=CURRENT_TIMESTAMP").bind(chatId, state, JSON.stringify(data)).run();
}
async function clearSession(db: D1Database, chatId: number) { await db.prepare("DELETE FROM sessions WHERE chat_id=?").bind(chatId).run(); }
function mainMenu() { return keyboard([[b("🚗 Записаться", "book"), b("📅 Мои записи", "my")], [b("Наши услуги", "services"), b("📩 Связаться с менеджером", "contact")]]); }
function back() { return [b("← В меню", "home")]; }
function apText(ap: Appointment) { return `<b>Заявка №${ap.id}</b>\n📅 ${dayLabel(String(ap.date))}, 🕒 ${esc(ap.time)}\nУслуги: ${esc(ap.services)}\nСтатус: <b>${STATUS[String(ap.status)] ?? ap.status}</b>`; }

async function home(env: Env, chatId: number) { await send(env, chatId, `Добро пожаловать в <b>${esc(env.CENTER_NAME || "Detail Pro")}</b>.\nВыберите действие:`, mainMenu()); }
async function dates(db: D1Database) {
  const work = (await db.prepare("SELECT value FROM settings WHERE key='workdays'").first<{ value: string }>())?.value.split(",").map(Number) ?? [0,1,2,3,4,5];
  const now = new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Minsk" }));
  return Array.from({ length: 14 }, (_, i) => { const x = new Date(now); x.setDate(x.getDate() + i); return x; }).filter((x) => work.includes((x.getDay() + 6) % 7)).map((x) => x.toISOString().slice(0, 10));
}
async function freeSlots(db: D1Database, day: string) {
  const [slots, busy, blocks] = await Promise.all([
    db.prepare("SELECT time FROM slots WHERE active=1 ORDER BY time").all<{ time: string }>(),
    db.prepare("SELECT time FROM appointments WHERE date=? AND status IN ('pending','confirmed','proposed')").bind(day).all<{ time: string }>(),
    db.prepare("SELECT time FROM blocked_slots WHERE date=?").bind(day).all<{ time: string | null }>()
  ]);
  const blocked = new Set(blocks.results.map((x) => x.time));
  if (blocked.has(null)) return [];
  const reserved = new Set(busy.results.map((x) => x.time));
  return slots.results.map((x) => x.time).filter((x) => !reserved.has(x) && !blocked.has(x));
}
async function servicePicker(env: Env, db: D1Database, chatId: number, messageId?: number) {
  const s = await session(db, chatId); const selected = (s.data.services as string[] | undefined) ?? [];
  const rows = SERVICES.map(([title]) => [b(`${selected.includes(title) ? "✅ " : ""}${title}`, `svc:${title}`)]);
  rows.push([b("Продолжить", "svc_done")], back());
  const text = "<b>Выберите услуги</b>\nМожно отметить несколько вариантов.";
  if (messageId) await edit(env, chatId, messageId, text, keyboard(rows)); else await send(env, chatId, text, keyboard(rows));
}
async function showServices(env: Env, chatId: number) {
  const text = "<b>Услуги Detail Pro</b>\n\n" + SERVICES.map(([title, desc]) => `<b>${title}</b>\n${desc}\nСтоимость рассчитывается индивидуально после оценки автомобиля и объема работ.`).join("\n\n");
  await send(env, chatId, text, keyboard([[b("🚗 Записаться", "book")], back()]));
}
async function showMine(env: Env, db: D1Database, chatId: number) {
  const rows = await db.prepare("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC,time DESC").bind(chatId).all<Appointment>();
  const text = `<b>Мои записи</b>\n\n${rows.results.length ? rows.results.map(apText).join("\n\n") : "Записей пока нет."}`;
  const active = rows.results.filter((x) => ["pending", "confirmed", "proposed"].includes(String(x.status))).map((x) => [b(`Отменить №${x.id}`, `cancel:${x.id}`)]);
  await send(env, chatId, text, keyboard([...active, back()]));
}
async function notifyGroup(env: Env, db: D1Database, id: number) {
  if (!env.ADMIN_GROUP_ID) return;
  const ap = await db.prepare("SELECT a.*,u.full_name,u.username FROM appointments a LEFT JOIN users u ON u.telegram_id=a.user_id WHERE a.id=?").bind(id).first<Appointment>();
  if (!ap) return;
  const text = `${apText(ap)}\nКлиент: ${esc(ap.full_name)} @${esc(ap.username || "нет")}\nТелефон: ${esc(ap.phone)}\nАвто: ${esc(ap.brand)} ${esc(ap.model)}, ${esc(ap.car_year)}; ${esc(ap.plate)}\nКомментарий: ${esc(ap.comment)}`;
  const kb = keyboard([[b("✅ Подтвердить", `mgr:confirm:${id}`), b("Предложить другое время", `mgr:reschedule:${id}`)], [b("Отклонить", `mgr:reject:${id}`), b("Завершить", `mgr:complete:${id}`)]]);
  const groupMessage = await send(env, env.ADMIN_GROUP_ID, text, kb) as { message_id?: number } | undefined;
  if (groupMessage?.message_id) await db.prepare("UPDATE appointments SET group_message_id=? WHERE id=?").bind(groupMessage.message_id, id).run();
  for (const photo of JSON.parse(String(ap.photos || "[]")) as string[]) await telegram(env, "sendPhoto", { chat_id: env.ADMIN_GROUP_ID, photo, caption: `Фото к заявке №${id}` });
}

async function onCallback(env: Env, update: any) {
  const q = update.callback_query; const data = String(q.data || ""); const chatId = q.message.chat.id as number; const messageId = q.message.message_id as number;
  await answer(env, q.id);
  if (data === "home") { await clearSession(env.DB, chatId); await edit(env, chatId, messageId, `Добро пожаловать в <b>${esc(env.CENTER_NAME || "Detail Pro")}</b>.`, mainMenu()); return; }
  if (data === "book") { await clearSession(env.DB, chatId); await setSession(env.DB, chatId, "services", { services: [] }); await servicePicker(env, env.DB, chatId, messageId); return; }
  if (data === "services") { await showServices(env, chatId); return; }
  if (data === "my") { await showMine(env, env.DB, chatId); return; }
  if (data === "contact") { await send(env, chatId, "📩 Менеджер свяжется с вами после заявки. Для вопросов используйте указанный в профиле центр контакт.", keyboard([back()])); return; }
  if (data.startsWith("svc:")) { const s = await session(env.DB, chatId); const title = data.slice(4); const values = ((s.data.services as string[]) || []); const next = values.includes(title) ? values.filter((x) => x !== title) : [...values, title]; await setSession(env.DB, chatId, "services", { services: next }); await servicePicker(env, env.DB, chatId, messageId); return; }
  if (data === "svc_done") { const s = await session(env.DB, chatId); if (!((s.data.services as string[]) || []).length) { await answer(env, q.id, "Выберите хотя бы одну услугу"); return; } await setSession(env.DB, chatId, "brand", s.data); await edit(env, chatId, messageId, "Марка автомобиля (например, BMW):"); return; }
  if (data === "skip_plate" || data === "skip_body" || data === "skip_comment") { const s = await session(env.DB, chatId); const key = data.slice(5); const next = { ...s.data, [key === "plate" ? "plate" : key === "body" ? "body" : "comment"]: "—" }; const state = key === "plate" ? "body" : key === "body" ? "comment" : "photos"; await setSession(env.DB, chatId, state, next); await sendNext(env, chatId, state); return; }
  if (data === "photos_done") { const s = await session(env.DB, chatId); await setSession(env.DB, chatId, "phone", s.data); await send(env, chatId, "Поделитесь телефоном через кнопку ниже.", { keyboard: [[{ text: "Поделиться номером", request_contact: true }]], resize_keyboard: true, one_time_keyboard: true }); return; }
  if (data.startsWith("day:")) { const day = data.slice(4); const slots = await freeSlots(env.DB, day); await setSession(env.DB, chatId, "time", { ...(await session(env.DB, chatId)).data, date: day }); await edit(env, chatId, messageId, `🕒 Свободное время на ${dayLabel(day)}:`, keyboard([...slots.map((x) => [b(x, `time:${x}`)]), [b("← В меню", "home")]])); return; }
  if (data.startsWith("time:")) { const s = await session(env.DB, chatId); const next = { ...s.data, time: data.slice(5) }; await setSession(env.DB, chatId, "review", next); await edit(env, chatId, messageId, reviewText(next), keyboard([[b("✅ Подтвердить заявку", "submit")], [b("Отменить", "home")]])); return; }
  if (data === "submit") { await submit(env, chatId, messageId); return; }
  if (data.startsWith("cancel:")) { const id = Number(data.slice(7)); const ap = await env.DB.prepare("SELECT user_id,status FROM appointments WHERE id=?").bind(id).first<{ user_id: number; status: string }>(); if (ap?.user_id !== chatId || !["pending", "confirmed", "proposed"].includes(ap.status)) return; await env.DB.prepare("UPDATE appointments SET status='cancelled',manager_note='Отменена клиентом' WHERE id=?").bind(id).run(); await edit(env, chatId, messageId, "Запись отменена. Временной слот снова доступен."); if (env.ADMIN_GROUP_ID) await send(env, env.ADMIN_GROUP_ID, `Заявка №${id} отменена клиентом.`); return; }
  if (data.startsWith("proposal:")) { const [, action, raw] = data.split(":"); const id = Number(raw); const ap = await env.DB.prepare("SELECT * FROM appointments WHERE id=? AND user_id=?").bind(id, chatId).first<Appointment>(); if (!ap) return; await env.DB.prepare("UPDATE appointments SET status=? WHERE id=?").bind(action === "yes" ? "confirmed" : "cancelled", id).run(); await edit(env, chatId, messageId, action === "yes" ? "✅ Новое время подтверждено." : "Предложенное время отклонено."); return; }
  if (data.startsWith("mgr:")) { await managerAction(env, q, data); return; }
  if (data.startsWith("mpday:")) { const [, id, day] = data.split(":"); const slots = await freeSlots(env.DB, day); await edit(env, chatId, messageId, `Выберите время на ${dayLabel(day)}:`, keyboard(slots.map((x) => [b(x, `mptime:${id}:${day}:${x}`)]))); return; }
  if (data.startsWith("mptime:")) { const [, raw, day, ...timeParts] = data.split(":"); const time = timeParts.join(":"); const id = Number(raw); const ap = await env.DB.prepare("SELECT * FROM appointments WHERE id=?").bind(id).first<Appointment>(); if (!ap) return; try { await env.DB.prepare("UPDATE appointments SET date=?,time=?,status='proposed',proposed_date=?,proposed_time=? WHERE id=?").bind(day,time,day,time,id).run(); } catch { await answer(env, q.id, "Этот слот уже заняли"); return; } await edit(env, chatId, messageId, "Предложение времени отправлено клиенту."); await send(env, Number(ap.user_id), `📅 По заявке №${id} предлагается время: <b>${dayLabel(day)}, ${time}</b>. Подходит?`, keyboard([[b("✅ Принять", `proposal:yes:${id}`), b("Отклонить", `proposal:no:${id}`)]])); return; }
}

function reviewText(d: Record<string, unknown>) { return `<b>Проверьте заявку</b>\nУслуги: ${esc((d.services as string[]).join(", "))}\nАвтомобиль: ${esc(d.brand)} ${esc(d.model)}, ${esc(d.year)}\nНомер: ${esc(d.plate)} · Кузов: ${esc(d.body)}\n📅 ${dayLabel(String(d.date))}, 🕒 ${esc(d.time)}\nТелефон: ${esc(d.phone)}\nКомментарий: ${esc(d.comment)}\nФото: ${((d.photos as string[]) || []).length}`; }
async function sendNext(env: Env, chatId: number, state: string) {
  const messages: Record<string, string> = { body: "Тип кузова — необязательно. Напишите его или нажмите «Пропустить».", comment: "Опишите пожелания или проблему.", photos: "Прикрепите до 5 фото или продолжите без фото." };
  const buttons: Record<string, unknown> = { body: keyboard([[b("Пропустить", "skip_body")]]), comment: keyboard([[b("Пропустить", "skip_comment")]]), photos: keyboard([[b("Продолжить без фото", "photos_done")]]) };
  await send(env, chatId, messages[state], buttons[state]);
}
async function submit(env: Env, chatId: number, messageId: number) {
  const s = await session(env.DB, chatId); const d = s.data; const result = await env.DB.prepare("INSERT INTO appointments(user_id,services,brand,model,car_year,plate,body_type,comment,photos,phone,date,time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").bind(chatId, (d.services as string[]).join(", "), d.brand, d.model, d.year, d.plate, d.body, d.comment, JSON.stringify(d.photos || []), d.phone, d.date, d.time).run().catch(() => null);
  if (!result?.meta.last_row_id) { await edit(env, chatId, messageId, "Этот слот уже заняли. Выберите другую дату и время.", keyboard([[b("В меню", "home")]])); return; }
  await clearSession(env.DB, chatId); await edit(env, chatId, messageId, "✅ <b>Заявка принята.</b>\nМенеджер подтвердит запись в ближайшее время."); await notifyGroup(env, env.DB, Number(result.meta.last_row_id));
}
async function managerAction(env: Env, q: any, data: string) {
  const [, action, raw] = data.split(":"); const id = Number(raw); const ap = await env.DB.prepare("SELECT * FROM appointments WHERE id=?").bind(id).first<Appointment>(); if (!ap) return;
  if (action === "reschedule") { const rows = await dates(env.DB); await edit(env, q.message.chat.id, q.message.message_id, "Выберите новую дату:", keyboard(rows.map((x) => [b(dayLabel(x), `mpday:${id}:${x}`)]))); return; }
  const status = action === "confirm" ? "confirmed" : action === "complete" ? "completed" : "rejected";
  await env.DB.prepare("UPDATE appointments SET status=? WHERE id=?").bind(status, id).run(); await edit(env, q.message.chat.id, q.message.message_id, `${apText({ ...ap, status })}`); const texts: Record<string, string> = { confirmed: `✅ Ваша запись №${id} подтверждена.`, completed: `✅ Работы по заявке №${id} завершены. Спасибо!`, rejected: `К сожалению, заявка №${id} отклонена. Менеджер свяжется с вами.` }; await send(env, Number(ap.user_id), texts[status]);
}
async function onMessage(env: Env, update: any) {
  const m = update.message; const chatId = m.chat.id as number; const text = String(m.text || "");
  if (text.startsWith("/chatid")) { await send(env, chatId, m.chat.type === "private" ? "Добавьте бота в рабочую группу и отправьте там /chatid." : `ID этой группы: <code>${chatId}</code>`); return; }
  if (text.startsWith("/start")) { await clearSession(env.DB, chatId); await home(env, chatId); return; }
  if (m.chat.type !== "private") return;
  await env.DB.prepare("INSERT INTO users(telegram_id,full_name,username) VALUES(?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET full_name=excluded.full_name,username=excluded.username").bind(chatId, m.from?.first_name || "", m.from?.username || "").run();
  const s = await session(env.DB, chatId);
  if (s.state === "photos" && m.photo) { const photos = [...((s.data.photos as string[]) || []), m.photo.at(-1).file_id].slice(0,5); await setSession(env.DB,chatId,"photos",{...s.data,photos}); await send(env,chatId,`Фото добавлено (${photos.length}/5).`,keyboard([[b("Продолжить", "photos_done")]])); return; }
  if (s.state === "phone" && m.contact?.phone_number) { const next={...s.data,phone:m.contact.phone_number}; await setSession(env.DB,chatId,"date",next); const days=await dates(env.DB); await send(env,chatId,"📅 Выберите удобную дату:",keyboard(days.map((x)=>[b(dayLabel(x),`day:${x}`)]))); return; }
  if (!text) return;
  const stateMap: Record<string, [string, string, unknown?]> = { brand:["model","Модель автомобиля:"], model:["year","Год выпуска:"], year:["plate","Госномер — необязательно.",keyboard([[b("Пропустить","skip_plate")]])], plate:["body","Тип кузова — необязательно.",keyboard([[b("Пропустить","skip_body")]])], body:["comment","Опишите пожелания или проблему.",keyboard([[b("Пропустить","skip_comment")]])], comment:["photos","Прикрепите до 5 фото или продолжите без фото.",keyboard([[b("Продолжить без фото","photos_done")]])] };
  if (s.state === "year" && !/^\d{4}$/.test(text)) { await send(env,chatId,"Введите год четырьмя цифрами, например 2020."); return; }
  const step=stateMap[s.state]; if (!step) return; const key=s.state === "year" ? "year" : s.state; const next={...s.data,[key]:text}; await setSession(env.DB,chatId,step[0],next); await send(env,chatId,step[1],step[2]);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (new URL(request.url).pathname !== "/telegram") return new Response("Detail Pro bot worker", { status: 200 });
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
    if (env.WEBHOOK_SECRET && request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) return new Response("Forbidden", { status: 403 });
    await seed(env.DB);
    const update = await request.json<any>();
    if (update.callback_query) await onCallback(env, update); else if (update.message) await onMessage(env, update);
    return new Response("OK");
  }
};

const base = process.env.WORKER_URL || "http://127.0.0.1:8788";
const secret = process.env.WEBHOOK_SECRET || "e2e-test-secret";
let updateId = 1000;

async function post(payload) {
  const response = await fetch(`${base}/telegram`, { method: "POST", headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret }, body: JSON.stringify({ update_id: updateId++, ...payload }) });
  if (!response.ok || await response.text() !== "OK") throw new Error(`Webhook failed: ${response.status}`);
}
function message(user, id, text, extras = {}) { return { message: { message_id: id, chat: { id: user, type: "private" }, from: { id: user, first_name: `Тест ${user}` }, text, ...extras } }; }
function callback(user, id, data) { return { callback_query: { id: `conflict-${user}-${id}`, from: { id: user }, data, message: { message_id: id, chat: { id: user, type: "private" } } } }; }
async function book(user, day) {
  await post(message(user, 1, "/start"));
  await post(callback(user, 2, "book"));
  await post(callback(user, 3, "svc:Мойка"));
  await post(callback(user, 4, "svc_done"));
  await post(message(user, 5, "BMW"));
  await post(message(user, 6, "X3"));
  await post(message(user, 7, "2022"));
  await post(callback(user, 8, "skip_plate"));
  await post(callback(user, 9, "skip_body"));
  await post(callback(user, 10, "skip_comment"));
  await post(callback(user, 11, "photos_done"));
  await post(message(user, 12, "", { contact: { phone_number: `+37529${user}` } }));
  await post(callback(user, 13, `day:${day}`));
  await post(callback(user, 14, "time:14:00"));
  await post(callback(user, 15, "submit"));
}

const day = new Date().toISOString().slice(0, 10);
await book(2001, day);
await book(2002, day);
console.log("Same-slot conflict scenario completed");

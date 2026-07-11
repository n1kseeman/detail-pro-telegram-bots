const base = process.env.WORKER_URL;
const secret = process.env.WEBHOOK_SECRET;
if (!base || !secret || process.env.ALLOW_LIVE_E2E !== "1") throw new Error("Set WORKER_URL, WEBHOOK_SECRET and ALLOW_LIVE_E2E=1");

let updateId = Date.now();
const clientId = 909001;
async function post(payload) {
  const response = await fetch(`${base}/telegram`, { method: "POST", headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret }, body: JSON.stringify({ update_id: updateId++, ...payload }) });
  if (!response.ok || await response.text() !== "OK") throw new Error(`Webhook failed: ${response.status}`);
}
const message = (id, text, extras = {}) => ({ message: { message_id: id, chat: { id: clientId, type: "private" }, from: { id: clientId, first_name: "Автотест", username: "detail_pro_test" }, text, ...extras } });
const callback = (id, data) => ({ callback_query: { id: `live-${id}`, from: { id: clientId }, data, message: { message_id: id, chat: { id: clientId, type: "private" } } } });

const target = new Date();
target.setUTCDate(target.getUTCDate() + 13);
const day = target.toISOString().slice(0, 10);

await post(message(1, "/start"));
await post(callback(2, "book"));
await post(callback(3, "svc:Мойка"));
await post(callback(4, "svc_done"));
await post(message(5, "TEST"));
await post(message(6, "Cloudflare E2E"));
await post(message(7, "2026"));
await post(callback(8, "skip_plate"));
await post(callback(9, "skip_body"));
await post(message(10, "🧪 Автотест: удалить после проверки"));
await post(callback(11, "photos_done"));
await post(message(12, "", { contact: { phone_number: "+375290000001" } }));
await post(callback(13, `day:${day}`));
await post(callback(14, "time:18:00"));
await post(callback(15, "submit"));
console.log(`Created live test booking for ${day} at 18:00`);

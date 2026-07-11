const base = process.env.WORKER_URL || "http://127.0.0.1:8788";
const secret = process.env.WEBHOOK_SECRET || "e2e-test-secret";
let updateId = 1;

async function update(payload) {
  const response = await fetch(`${base}/telegram`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret },
    body: JSON.stringify({ update_id: updateId++, ...payload })
  });
  if (!response.ok || await response.text() !== "OK") throw new Error(`Webhook failed: ${response.status}`);
}
const privateMessage = (id, text, extras = {}) => ({ message: { message_id: id, chat: { id: 1001, type: "private" }, from: { id: 1001, first_name: "Тест", username: "tester" }, text, ...extras } });
const callback = (id, data, chat = { id: 1001, type: "private" }) => ({ callback_query: { id: `callback-${id}`, from: { id: 1001 }, data, message: { message_id: id, chat } } });

await update(privateMessage(1, "/start"));
await update(callback(2, "book"));
await update(callback(3, "svc:Мойка"));
await update(callback(4, "svc_done"));
await update(privateMessage(5, "BMW"));
await update(privateMessage(6, "X5"));
await update(privateMessage(7, "2020"));
await update(callback(8, "skip_plate"));
await update(callback(9, "skip_body"));
await update(callback(10, "skip_comment"));
await update(privateMessage(11, "", { photo: [{ file_id: "small" }, { file_id: "photo-file-id" }] }));
await update(callback(12, "photos_done"));
await update(privateMessage(13, "", { contact: { phone_number: "+375291112233" } }));
const day = new Date().toISOString().slice(0, 10);
await update(callback(14, `day:${day}`));
await update(callback(15, "time:10:00"));
await update(callback(16, "submit"));
await update(callback(17, "mgr:confirm:1", { id: -999999999, type: "group", title: "Тестовая группа" }));
await update(callback(18, "mgr:reschedule:1", { id: -999999999, type: "group", title: "Тестовая группа" }));
await update(callback(19, `mpday:1:${day}`, { id: -999999999, type: "group", title: "Тестовая группа" }));
await update(callback(20, `mptime:1:${day}:12:00`, { id: -999999999, type: "group", title: "Тестовая группа" }));
await update(callback(21, "proposal:yes:1"));
await update(callback(22, "cancel:1"));
await update(privateMessage(23, "/start"));
await update(callback(24, "my"));
await update({ message: { message_id: 25, chat: { id: -999999999, type: "group", title: "Тестовая группа" }, from: { id: 1001 }, text: "/chatid" } });
console.log("Webhook client and manager scenario completed");

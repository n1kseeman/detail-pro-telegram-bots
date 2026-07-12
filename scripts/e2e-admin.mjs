const base = process.env.WORKER_URL || "http://127.0.0.1:8788";
const secret = process.env.WEBHOOK_SECRET || "e2e-test-secret";
let updateId = 3000;

async function post(payload, id = updateId++) {
  const response = await fetch(`${base}/telegram`, { method: "POST", headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret }, body: JSON.stringify({ update_id: id, ...payload }) });
  if (!response.ok || await response.text() !== "OK") throw new Error(`Webhook failed: ${response.status}`);
}
const managerMessage = (id, text, chat = { id: 1001, type: "private" }) => ({ message: { message_id: id, chat, from: { id: 1001, first_name: "Менеджер" }, text } });
const callback = (id, data, chat = { id: 1001, type: "private" }) => ({ callback_query: { id: `admin-${id}`, from: { id: 1001 }, data, message: { message_id: id, chat } } });
const group = { id: -999999999, type: "group", title: "Тестовая группа" };

await post(managerMessage(1, "/admin"));
await post(callback(2, "adm:workdays"));
await post(callback(3, "wd:6"));
await post(callback(4, "wd:6"));
await post(callback(5, "adm:slots"));
await post(callback(6, "slot:10:00"), 9001);
await post(callback(6, "slot:10:00"), 9001); // same Telegram update must be ignored
await post(callback(7, "slot:10:00")); // restore slot state
await post(managerMessage(8, "/block 2030-01-01 10:00"));
await post(managerMessage(9, "/unblock 2030-01-01 10:00"));
await post(managerMessage(10, "/service add E2E услуга | Тестовое описание"));
await post(managerMessage(11, "/service edit 10 | E2E услуга 2 | Обновлённое описание"));
await post(managerMessage(12, "/service off 10"));
await post(managerMessage(13, "/service on 10"));
await post(callback(14, "mgr:reject:2", group));
await post(managerMessage(15, "Тестовая причина отказа", group));
await post(managerMessage(16, "/find 2"));
console.log("Admin, permissions, rejection reason and idempotency scenario completed");

import asyncio
import json
import logging
from datetime import date

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.data import STATUS
from app.db import Database


class Booking(StatesGroup):
    services = State(); brand = State(); model = State(); year = State(); plate = State(); body = State(); comment = State(); photos = State(); phone = State(); date = State(); time = State(); review = State()
class AdminInput(StatesGroup):
    search = State(); block = State(); service = State(); slots = State(); schedule = State(); reject = State()


def main_menu(is_admin=False):
    rows = [[KeyboardButton(text="🚗 Записаться"), KeyboardButton(text="📅 Мои записи")], [KeyboardButton(text="Наши услуги"), KeyboardButton(text="📩 Связаться с менеджером")]]
    if is_admin: rows.append([KeyboardButton(text="⚙️ Админ-меню")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def back_row(): return [InlineKeyboardButton(text="← Назад", callback_data="home")]
def cancel_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отменить", callback_data="cancel_flow")]])
def fmt_day(day): return date.fromisoformat(day).strftime("%d.%m.%Y")
def ap_text(ap):
    return (f"<b>Заявка №{ap['id']}</b>\n📅 {fmt_day(ap['date'])}, 🕒 {ap['time']}\n"
            f"Услуги: {ap['services']}\nСтатус: <b>{STATUS.get(ap['status'], ap['status'])}</b>")


class DetailBot:
    def __init__(self, settings: Settings, db: Database, is_admin_bot: bool):
        self.settings, self.db = settings, db
        self.is_admin_bot = is_admin_bot
        self.client_bot: Bot | None = None
        self.admin_bot: Bot | None = None
        self.router = Router()
        self.register()

    def admin(self, user_id): return self.is_admin_bot
    def admin_recipients(self):
        return {self.settings.admin_group_id} if self.settings.admin_group_id is not None else set()
    async def answer_home(self, message):
        if self.is_admin_bot:
            if self.admin(message.from_user.id):
                await self.show_admin(message)
            else:
                await message.answer("Этот бот предназначен для сотрудников центра. Доступ не предоставлен.", reply_markup=ReplyKeyboardRemove())
            return
        await message.answer(f"Добро пожаловать в <b>{self.settings.center_name}</b>.\nВыберите действие в меню.", reply_markup=main_menu(False))
    async def edit_or_answer(self, event, text, markup=None):
        if isinstance(event, CallbackQuery): await event.message.edit_text(text, reply_markup=markup)
        else: await event.answer(text, reply_markup=markup)

    def register(self):
        r = self.router
        @r.message(Command("chatid"))
        async def chat_id(m: Message):
            if not self.is_admin_bot:
                return
            if m.chat.type == "private":
                await m.answer("Добавьте админ-бота в рабочую группу и отправьте там команду /chatid.")
                return
            await m.answer(f"ID этой группы: <code>{m.chat.id}</code>")
        @r.message(CommandStart())
        async def start(m: Message):
            await self.db.upsert_user(m.from_user); await self.answer_home(m)
        @r.callback_query(F.data == "home")
        async def home(c: CallbackQuery, state: FSMContext):
            await state.clear(); await c.answer(); await c.message.delete(); await self.answer_home(c.message)
        @r.callback_query(F.data == "cancel_flow")
        async def cancel_flow(c: CallbackQuery, state: FSMContext):
            await state.clear(); await c.answer("Действие отменено"); await c.message.delete(); await self.answer_home(c.message)
        @r.message(F.text == "🚗 Записаться")
        async def book(m: Message, state: FSMContext): await self.show_service_picker(m, state)
        @r.callback_query(F.data == "book")
        async def book_cb(c: CallbackQuery, state: FSMContext): await c.answer(); await self.show_service_picker(c, state)
        @r.message(F.text == "Наши услуги")
        async def services(m: Message): await self.show_services(m)
        @r.callback_query(F.data == "services")
        async def services_cb(c: CallbackQuery): await c.answer(); await self.show_services(c)
        @r.message(F.text == "📩 Связаться с менеджером")
        async def contact(m: Message): await self.show_contact(m)
        @r.callback_query(F.data == "contact")
        async def contact_cb(c: CallbackQuery): await c.answer(); await self.show_contact(c)
        @r.message(F.text == "📅 Мои записи")
        async def my(m: Message): await self.show_my(m)
        @r.callback_query(F.data == "my")
        async def mycb(c: CallbackQuery): await c.answer(); await self.show_my(c)

        @r.callback_query(Booking.services, F.data.startswith("svc:"))
        async def choose_service(c: CallbackQuery, state: FSMContext):
            selected = (await state.get_data()).get("services", [])
            title = c.data.split(":", 1)[1]
            selected.remove(title) if title in selected else selected.append(title)
            await state.update_data(services=selected); await self.show_service_picker(c, state, selected)
        @r.callback_query(Booking.services, F.data == "svc_done")
        async def services_done(c: CallbackQuery, state: FSMContext):
            if not (await state.get_data()).get("services"): await c.answer("Выберите хотя бы одну услугу", show_alert=True); return
            await state.set_state(Booking.brand); await c.message.edit_text("Марка автомобиля (например, BMW):", reply_markup=cancel_kb())
        @r.message(Booking.brand, F.text)
        async def brand(m: Message, state: FSMContext): await state.update_data(brand=m.text.strip()); await state.set_state(Booking.model); await m.answer("Модель автомобиля:", reply_markup=cancel_kb())
        @r.message(Booking.model, F.text)
        async def model(m: Message, state: FSMContext): await state.update_data(model=m.text.strip()); await state.set_state(Booking.year); await m.answer("Год выпуска:", reply_markup=cancel_kb())
        @r.message(Booking.year, F.text)
        async def year(m: Message, state: FSMContext):
            if not (m.text.isdigit() and 1900 <= int(m.text) <= self.db.today().year + 1): await m.answer("Введите год четырьмя цифрами, например 2020."); return
            await state.update_data(year=m.text); await state.set_state(Booking.plate); await m.answer("Госномер — необязательно:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_plate")], back_row()]))
        @r.message(Booking.plate, F.text)
        async def plate(m: Message, state: FSMContext): await state.update_data(plate=m.text); await self.ask_body(m, state)
        @r.callback_query(Booking.plate, F.data == "skip_plate")
        async def skip_plate(c: CallbackQuery, state: FSMContext): await state.update_data(plate="—"); await self.ask_body(c, state)
        @r.message(Booking.body, F.text)
        async def body(m: Message, state: FSMContext): await state.update_data(body=m.text); await self.ask_comment(m, state)
        @r.callback_query(Booking.body, F.data == "skip_body")
        async def skip_body(c: CallbackQuery, state: FSMContext): await state.update_data(body="—"); await self.ask_comment(c, state)
        @r.message(Booking.comment, F.text)
        async def comment(m: Message, state: FSMContext): await state.update_data(comment=m.text); await self.ask_photos(m, state)
        @r.callback_query(Booking.comment, F.data == "skip_comment")
        async def skip_comment(c: CallbackQuery, state: FSMContext): await state.update_data(comment="—"); await self.ask_photos(c, state)
        @r.message(Booking.photos, F.photo)
        async def photo(m: Message, state: FSMContext):
            values = (await state.get_data()).get("photos", [])
            if len(values) >= 5: await m.answer("Можно приложить не более 5 фотографий."); return
            values.append(m.photo[-1].file_id); await state.update_data(photos=values)
            await m.answer(f"Фото добавлено ({len(values)}/5). Добавьте ещё или нажмите «Продолжить».", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Продолжить", callback_data="photos_done")], [InlineKeyboardButton(text="Без фото", callback_data="photos_done")], back_row()]))
        @r.callback_query(Booking.photos, F.data == "photos_done")
        async def photos_done(c: CallbackQuery, state: FSMContext):
            await state.set_state(Booking.phone); await c.message.answer("Поделитесь номером телефона — менеджер свяжется с вами для уточнения деталей.", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True))
        @r.message(Booking.phone, F.contact)
        async def phone(m: Message, state: FSMContext):
            await self.db.upsert_user(m.from_user, m.contact.phone_number); await state.update_data(phone=m.contact.phone_number); await m.answer("Спасибо, номер сохранён.", reply_markup=ReplyKeyboardRemove()); await self.show_dates(m, state)
        @r.message(Booking.phone)
        async def phone_other(m: Message): await m.answer("Используйте кнопку «Поделиться номером» ниже.")
        @r.callback_query(Booking.date, F.data.startswith("day:"))
        async def pick_day(c: CallbackQuery, state: FSMContext):
            day = c.data.split(":",1)[1]; await state.update_data(date=day); await self.show_times(c, state, day)
        @r.callback_query(Booking.time, F.data == "day_back")
        async def day_back(c: CallbackQuery, state: FSMContext):
            await self.show_dates(c, state)
        @r.callback_query(Booking.time, F.data.startswith("time:"))
        async def pick_time(c: CallbackQuery, state: FSMContext):
            await state.update_data(time=c.data.split(":",1)[1]); await state.set_state(Booking.review); await self.show_review(c, state)
        @r.callback_query(Booking.review, F.data == "submit")
        async def submit(c: CallbackQuery, state: FSMContext):
            data = await state.get_data(); data["user_id"] = c.from_user.id; data["services"] = ", ".join(data["services"]); data["photos"] = json.dumps(data.get("photos", []))
            aid = await self.db.create_appointment(data)
            if not aid: await c.answer("Этот слот уже заняли. Пожалуйста, выберите другое время.", show_alert=True); await self.show_times(c, state, data["date"]); return
            await state.clear(); await c.message.edit_text("✅ <b>Заявка принята.</b>\nМенеджер подтвердит запись в ближайшее время.")
            await self.notify_manager(aid)
        @r.callback_query(Booking.review, F.data == "edit_booking")
        async def edit_booking(c: CallbackQuery, state: FSMContext): await self.show_service_picker(c, state, (await state.get_data()).get("services", []))

        @r.callback_query(F.data.startswith("cancel_ap:"))
        async def cancel_ap(c: CallbackQuery):
            aid=int(c.data.split(":")[1]); ap=await self.db.appointment(aid)
            if not ap or ap['user_id'] != c.from_user.id or ap['status'] not in ('pending','confirmed','proposed'): await c.answer("Эту заявку уже нельзя отменить.", show_alert=True); return
            await self.db.set_status(aid,'cancelled','Отменена клиентом'); await c.answer(); await c.message.edit_text("Запись отменена. Временной слот снова доступен."); await self.notify_admins(f"Заявка №{aid} отменена клиентом.")
        @r.callback_query(F.data.startswith("proposal:"))
        async def proposal(c: CallbackQuery):
            _, action, raw = c.data.split(":"); aid=int(raw); ap=await self.db.appointment(aid)
            if not ap or ap['user_id'] != c.from_user.id: return
            if action == 'yes':
                ok=await self.db.accept_proposal(aid)
                await c.message.edit_text("✅ Новое время подтверждено." if ok else "К сожалению, это время уже заняли. Менеджер свяжется с вами.")
            else: await self.db.set_status(aid,'cancelled','Клиент не принял новое время'); await c.message.edit_text("Предложенное время отклонено. Менеджер свяжется с вами.")

        @r.callback_query(F.data.startswith("mgr:"))
        async def manager_action(c: CallbackQuery, state: FSMContext):
            if not self.admin(c.from_user.id): await c.answer("Нет доступа",show_alert=True); return
            _, action, raw = c.data.split(":"); aid=int(raw); ap=await self.db.appointment(aid)
            if not ap: await c.answer("Заявка не найдена",show_alert=True); return
            if action == 'confirm':
                await self.db.set_status(aid,'confirmed'); await c.message.edit_text(ap_text(ap).replace(STATUS['pending'], STATUS['confirmed'])); await self.safe_send(ap['user_id'], f"✅ Ваша запись №{aid} на {fmt_day(ap['date'])} в {ap['time']} подтверждена. До встречи в {self.settings.center_name}!")
            elif action == 'complete':
                await self.db.set_status(aid,'completed'); await c.message.edit_text(ap_text(ap).replace(STATUS.get(ap['status'], ap['status']), STATUS['completed'])); await self.safe_send(ap['user_id'], f"✅ Работы по заявке №{aid} завершены. Спасибо, что выбрали {self.settings.center_name}!")
            elif action == 'reject':
                await state.update_data(reject_id=aid); await state.set_state(AdminInput.reject); await c.message.edit_text("Укажите причину отклонения одним сообщением:")
            elif action == 'reschedule': await self.show_manager_dates(c, aid)
            else: await c.answer("Свяжитесь с клиентом по указанному телефону или username.", show_alert=True)
        @r.message(AdminInput.reject, F.text)
        async def reject_reason(m: Message, state: FSMContext):
            aid=(await state.get_data())['reject_id']; ap=await self.db.appointment(aid); await self.db.set_status(aid,'rejected',m.text); await state.clear(); await m.answer(f"Заявка №{aid} отклонена."); await self.safe_send(ap['user_id'],f"К сожалению, заявка №{aid} отклонена. Причина: {m.text}")
        @r.callback_query(F.data.startswith("mpday:"))
        async def manager_day(c: CallbackQuery):
            _, aid, day = c.data.split(":"); await self.show_manager_times(c,int(aid),day)
        @r.callback_query(F.data.startswith("mptime:"))
        async def manager_time(c: CallbackQuery):
            _, aid, day, time = c.data.split(":"); ap=await self.db.appointment(int(aid)); ok=await self.db.propose(int(aid),day,time)
            if not ok: await c.answer("Этот слот уже заняли. Выберите другой.",show_alert=True); await self.show_manager_times(c,int(aid),day); return
            await c.message.edit_text("Предложение времени отправлено клиенту."); kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принять",callback_data=f"proposal:yes:{aid}"),InlineKeyboardButton(text="Отклонить",callback_data=f"proposal:no:{aid}")]])
            await self.safe_send(ap['user_id'],f"📅 По заявке №{aid} менеджер предлагает другое время: <b>{fmt_day(day)}, {time}</b>. Подходит ли вам?",kb)

        @r.message(F.text == "⚙️ Админ-меню")
        async def admin_menu(m: Message):
            if not self.admin(m.from_user.id): return
            await self.show_admin(m)
        @r.callback_query(F.data == "admin")
        async def admin_cb(c: CallbackQuery):
            if self.admin(c.from_user.id): await self.show_admin(c)
        @r.callback_query(F.data.startswith("adm:"))
        async def admin_action(c: CallbackQuery, state: FSMContext):
            if not self.admin(c.from_user.id): return
            action=c.data.split(":",1)[1]
            if action == 'today': await self.list_admin(c, self.db.today().isoformat(), "Заявки на сегодня")
            elif action == 'active': await self.list_admin(c, None, "Все активные записи")
            elif action == 'stats':
                s=await self.db.stats(); await c.message.edit_text(f"<b>Статистика</b>\nЗа неделю: новых {s['week'].get('pending',0)}, подтверждено {s['week'].get('confirmed',0)}, отменено {s['week'].get('cancelled',0)}\nЗа месяц: новых {s['month'].get('pending',0)}, подтверждено {s['month'].get('confirmed',0)}, отменено {s['month'].get('cancelled',0)}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_row()]))
            elif action == 'search': await state.set_state(AdminInput.search); await c.message.edit_text("Введите номер заявки или телефон:")
            elif action == 'block': await state.set_state(AdminInput.block); await c.message.edit_text("Введите дату и необязательное время: <code>2026-07-20</code> или <code>2026-07-20 14:00</code>.")
            elif action == 'service': await state.set_state(AdminInput.service); await c.message.edit_text("Добавить: <code>Название | описание</code>. Скрыть: <code>- Название</code>. Изменить описание: <code>~ Название | новое описание</code>.")
            elif action == 'slots': await state.set_state(AdminInput.slots); await c.message.edit_text("Активные слоты: <b>"+", ".join(await self.db.slots())+"</b>\nОтправьте <code>+ 11:00</code> чтобы добавить или <code>- 12:00</code> чтобы отключить слот.")
            elif action == 'date_schedule': await state.set_state(AdminInput.schedule); await c.message.edit_text("Введите дату в формате <code>2026-07-20</code>.")
            elif action == 'schedule': await self.show_workdays(c)
        @r.message(AdminInput.search,F.text)
        async def search(m: Message,state: FSMContext):
            rows=await self.db.search(m.text.strip()); await state.clear(); await m.answer("\n\n".join(ap_text(x) for x in rows) or "Ничего не найдено.")
        @r.message(AdminInput.block,F.text)
        async def block(m: Message,state: FSMContext):
            parts=m.text.split()
            try: date.fromisoformat(parts[0]); assert len(parts) < 2 or len(parts[1]) == 5
            except (ValueError,AssertionError): await m.answer("Неверный формат. Пример: 2026-07-20 14:00"); return
            await self.db.block(parts[0],parts[1] if len(parts)>1 else None); await state.clear(); await m.answer("Дата/время заблокированы.")
        @r.message(AdminInput.service,F.text)
        async def add_service(m: Message,state: FSMContext):
            if m.text.startswith('- '):
                cur=await self.db.conn.execute("UPDATE services SET active=0 WHERE title=?",(m.text[2:].strip(),)); await self.db.conn.commit(); await state.clear(); await m.answer("Услуга скрыта." if cur.rowcount else "Услуга не найдена."); return
            if m.text.startswith('~ ') and '|' in m.text:
                title,desc=map(str.strip,m.text[2:].split('|',1)); cur=await self.db.conn.execute("UPDATE services SET description=?,active=1 WHERE title=?",(desc,title)); await self.db.conn.commit(); await state.clear(); await m.answer("Услуга обновлена." if cur.rowcount else "Услуга не найдена."); return
            if '|' not in m.text: await m.answer("Используйте разделитель |."); return
            title,desc=map(str.strip,m.text.split('|',1))
            try: await self.db.conn.execute("INSERT INTO services(title,description) VALUES(?,?)",(title,desc)); await self.db.conn.commit(); reply="Услуга добавлена."
            except Exception: reply="Услуга с таким названием уже есть."
            await state.clear(); await m.answer(reply)
        @r.message(AdminInput.slots,F.text)
        async def slots(m: Message,state: FSMContext):
            parts=m.text.split()
            if len(parts) != 2 or parts[0] not in ('+','-') or len(parts[1]) != 5:
                await m.answer("Формат: + 11:00 или - 12:00"); return
            if parts[0] == '+':
                await self.db.conn.execute("INSERT INTO slots(time,active) VALUES(?,1) ON CONFLICT(time) DO UPDATE SET active=1",(parts[1],)); text="Слот добавлен."
            else: await self.db.conn.execute("UPDATE slots SET active=0 WHERE time=?",(parts[1],)); text="Слот отключён."
            await self.db.conn.commit(); await state.clear(); await m.answer(text)
        @r.message(AdminInput.schedule,F.text)
        async def date_schedule(m: Message,state: FSMContext):
            try: day=date.fromisoformat(m.text.strip()).isoformat()
            except ValueError: await m.answer("Нужен формат ГГГГ-ММ-ДД."); return
            rows=await self.db.active_appointments(day); free=await self.db.free_slots(day); await state.clear()
            await m.answer(f"<b>Расписание на {fmt_day(day)}</b>\n\n"+('\n'.join(ap_text(x) for x in rows) if rows else 'Записей нет.')+f"\n\nСвободно: {', '.join(free) or 'нет'}")
        @r.callback_query(F.data.startswith("wd:"))
        async def workday(c: CallbackQuery):
            day=int(c.data.split(':')[1]); current=await self.db.workdays(); current.remove(day) if day in current else current.add(day)
            if not current: await c.answer("Нужен хотя бы один рабочий день",show_alert=True); return
            await self.db.conn.execute("UPDATE settings SET value=? WHERE key='workdays'",(','.join(map(str,sorted(current))),)); await self.db.conn.commit(); await self.show_workdays(c)

    async def show_service_picker(self, event, state, selected=None):
        await state.set_state(Booking.services); selected=selected if selected is not None else (await state.get_data()).get('services',[]); b=InlineKeyboardBuilder()
        for row in await self.db.services(): b.button(text=("✅ " if row['title'] in selected else "")+row['title'],callback_data=f"svc:{row['title']}")
        b.adjust(1); b.row(InlineKeyboardButton(text="Продолжить",callback_data="svc_done")); b.row(*back_row()); await self.edit_or_answer(event,"<b>Выберите услуги</b>\nМожно отметить несколько вариантов.",b.as_markup())
    async def ask_body(self,event,state): await state.set_state(Booking.body); await self.edit_or_answer(event,"Тип кузова — необязательно:",InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пропустить",callback_data="skip_body")],back_row()]))
    async def ask_comment(self,event,state): await state.set_state(Booking.comment); await self.edit_or_answer(event,"Опишите пожелания или проблему — это поможет подготовиться к визиту.",InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пропустить",callback_data="skip_comment")],back_row()]))
    async def ask_photos(self,event,state): await state.set_state(Booking.photos); await self.edit_or_answer(event,"Прикрепите до 5 фотографий автомобиля или сразу продолжите.",InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Продолжить без фото",callback_data="photos_done")],back_row()]))
    async def show_dates(self,event,state):
        await state.set_state(Booking.date); b=InlineKeyboardBuilder()
        for d in await self.db.available_dates(): b.button(text=d.strftime('%d.%m (%a)').replace('Mon','Пн').replace('Tue','Вт').replace('Wed','Ср').replace('Thu','Чт').replace('Fri','Пт').replace('Sat','Сб').replace('Sun','Вс'),callback_data=f"day:{d.isoformat()}")
        b.adjust(2); b.row(*back_row()); await self.edit_or_answer(event,"📅 Выберите удобную дату:",b.as_markup())
    async def show_times(self,event,state,day):
        await state.set_state(Booking.time); b=InlineKeyboardBuilder()
        for time in await self.db.free_slots(day): b.button(text=time,callback_data=f"time:{time}")
        b.adjust(3); b.row(InlineKeyboardButton(text="← К датам",callback_data="day_back")); await self.edit_or_answer(event,f"🕒 Свободное время на {fmt_day(day)}:",b.as_markup())
    async def show_review(self,event,state):
        d=await state.get_data(); photos=len(d.get('photos',[])); text=(f"<b>Проверьте заявку</b>\nУслуги: {', '.join(d['services'])}\nАвтомобиль: {d['brand']} {d['model']}, {d['year']}\nНомер: {d['plate']} · Кузов: {d['body']}\n📅 {fmt_day(d['date'])}, 🕒 {d['time']}\nТелефон: {d['phone']}\nКомментарий: {d['comment']}\nФото: {photos}")
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить заявку",callback_data="submit")],[InlineKeyboardButton(text="Изменить",callback_data="edit_booking")],[InlineKeyboardButton(text="Отменить",callback_data="cancel_flow")]])
        await self.edit_or_answer(event,text,kb)
    async def show_services(self,event):
        b=InlineKeyboardBuilder(); text="<b>Услуги Detail Pro</b>\n\n"
        for row in await self.db.services(): text += f"<b>{row['title']}</b>\n{row['description']}\nСтоимость рассчитывается индивидуально после оценки автомобиля и объема работ.\n\n"; b.button(text=f"Записаться: {row['title']}",callback_data="book")
        b.adjust(1); b.row(*back_row()); await self.edit_or_answer(event,text,b.as_markup())
    async def show_contact(self,event):
        rows=[]
        if self.settings.manager_username: rows.append([InlineKeyboardButton(text="Написать менеджеру",url=f"https://t.me/{self.settings.manager_username}")])
        if self.settings.manager_phone: rows.append([InlineKeyboardButton(text="Позвонить",url=f"tel:{self.settings.manager_phone}")])
        rows.append(back_row()); await self.edit_or_answer(event,"📩 Менеджер поможет подобрать услугу и ответит на вопросы.",InlineKeyboardMarkup(inline_keyboard=rows))
    async def show_my(self,event):
        rows=await self.db.user_appointments(event.from_user.id); active=[]; past=[]
        for ap in rows: (active if ap['status'] in ('pending','confirmed','proposed') else past).append(ap)
        text='<b>Мои записи</b>\n\n' + ('<b>Активные</b>\n'+'\n'.join(ap_text(x) for x in active) if active else 'Активных записей нет.')
        if past: text += '\n\n<b>Прошлые</b>\n'+'\n'.join(ap_text(x) for x in past)
        b=InlineKeyboardBuilder()
        for ap in active: b.button(text=f"Отменить №{ap['id']}",callback_data=f"cancel_ap:{ap['id']}")
        b.adjust(1); b.row(*back_row()); await self.edit_or_answer(event,text,b.as_markup())
    async def notify_manager(self, aid):
        ap=await self.db.appointment(aid); text=ap_text(ap)+f"\nКлиент: {ap['full_name']} @{ap['username'] or 'нет'}\nТелефон: {ap['phone']}\nАвто: {ap['brand']} {ap['model']}, {ap['car_year']}; {ap['plate']}\nКомментарий: {ap['comment']}"
        contact_url = f"https://t.me/{ap['username']}" if ap['username'] else f"tg://user?id={ap['user_id']}"
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить",callback_data=f"mgr:confirm:{aid}"),InlineKeyboardButton(text="Предложить другое время",callback_data=f"mgr:reschedule:{aid}")],[InlineKeyboardButton(text="Отклонить",callback_data=f"mgr:reject:{aid}"),InlineKeyboardButton(text="Завершить",callback_data=f"mgr:complete:{aid}")],[InlineKeyboardButton(text="Связаться с клиентом",url=contact_url)]])
        for admin_id in self.admin_recipients():
            await self.send_admin(admin_id,text,kb)
            for photo in self.db.photos(ap['photos']):
                try: await self.admin_bot.send_photo(admin_id,photo,caption=f"Фото к заявке №{aid}")
                except Exception: logging.exception("Cannot send photo")
    async def notify_admins(self,text):
        for admin in self.admin_recipients(): await self.send_admin(admin,text)
    async def send_admin(self,user_id,text,markup=None):
        try: await self.admin_bot.send_message(user_id,text,reply_markup=markup)
        except Exception: logging.exception("Cannot send message to admin %s",user_id)
    async def safe_send(self,user_id,text,markup=None):
        try: await self.client_bot.send_message(user_id,text,reply_markup=markup)
        except Exception: logging.exception("Cannot send message to %s",user_id)
    async def show_manager_dates(self,c,aid):
        b=InlineKeyboardBuilder()
        for d in await self.db.available_dates(): b.button(text=fmt_day(d.isoformat()),callback_data=f"mpday:{aid}:{d.isoformat()}")
        b.adjust(2); await c.message.edit_text("Выберите новую дату:",reply_markup=b.as_markup())
    async def show_manager_times(self,c,aid,day):
        b=InlineKeyboardBuilder()
        for time in await self.db.free_slots(day): b.button(text=time,callback_data=f"mptime:{aid}:{day}:{time}")
        b.adjust(3); await c.message.edit_text(f"Свободное время на {fmt_day(day)}:",reply_markup=b.as_markup())
    async def show_admin(self,event):
        b=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Заявки на сегодня",callback_data="adm:today"),InlineKeyboardButton(text="Активные записи",callback_data="adm:active")],[InlineKeyboardButton(text="Поиск записи",callback_data="adm:search"),InlineKeyboardButton(text="Расписание на дату",callback_data="adm:date_schedule")],[InlineKeyboardButton(text="Рабочий график",callback_data="adm:schedule"),InlineKeyboardButton(text="Управление слотами",callback_data="adm:slots")],[InlineKeyboardButton(text="Блокировать дату/время",callback_data="adm:block"),InlineKeyboardButton(text="Управление услугами",callback_data="adm:service")],[InlineKeyboardButton(text="Статистика",callback_data="adm:stats")]])
        await self.edit_or_answer(event,"<b>Админ-меню</b>\nУправление записями и расписанием.",b)
    async def list_admin(self,c,day,title):
        rows=await self.db.active_appointments(day); await c.message.edit_text(f"<b>{title}</b>\n\n"+('\n\n'.join(ap_text(x) for x in rows) if rows else 'Записей нет.'),reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_row()]))
    async def show_workdays(self,c):
        labels=['Пн','Вт','Ср','Чт','Пт','Сб','Вс']; chosen=await self.db.workdays(); b=InlineKeyboardBuilder()
        for n,label in enumerate(labels): b.button(text=("✅ " if n in chosen else "")+label,callback_data=f"wd:{n}")
        b.adjust(4); b.row(*back_row()); await c.message.edit_text("Настройте рабочие дни:",reply_markup=b.as_markup())

    async def run(self, bot: Bot):
        dp=Dispatcher(); dp.include_router(self.router)
        await dp.start_polling(bot)

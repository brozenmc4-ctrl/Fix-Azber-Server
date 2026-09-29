import asyncio
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

MAIN_BOT_TOKEN = os.environ["MAIN_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]

ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
}

CARD_NUMBER = os.getenv("CARD_NUMBER", "6221061258444610")
CARD_NAME = os.getenv("CARD_NAME", "علیرضا قایدی")

DB = os.getenv("DB_PATH", "shop.db")

PRODUCTS = {
    "vip": {
        "title": "💎 VIP",
        "price": 100000,
        "description": (
            "💎 رنک VIP — ۱۰۰,۰۰۰ تومان\n\n"
            "✨ کیت دایموندی\n"
            "⚒️ /craft\n"
            "💎 دایموند با اینچنت کامل"
        ),
    },
    "legend": {
        "title": "👑 LEGEND",
        "price": 150000,
        "description": (
            "👑 رنک LEGEND\n\n"
            "🟣 کیت ندرایتی\n"
            "⚔️ اینچنت متوسط\n"
            "⚒️ /anvil\n"
            "🛠️ /craft\n"
            "✨ /enchantingtable"
        ),
    },
    "nick": {
        "title": "🏷️ /NICK",
        "price": 200000,
        "description": "🏷️ قابلیت تغییر نیک با /NICK — ۲۰۰,۰۰۰ تومان",
    },
}

# ---------- database ----------
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            product TEXT NOT NULL,
            base_price INTEGER NOT NULL,
            discount_percent INTEGER DEFAULT 0,
            final_price INTEGER NOT NULL,
            coupon TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            percent INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)
    con.commit()
    con.close()

def create_order(user_id, username, product, coupon, discount):
    p = PRODUCTS[product]
    final = round(p["price"] * (100 - discount) / 100)
    con = db()
    cur = con.execute("""
        INSERT INTO orders
        (user_id, username, product, base_price, discount_percent, final_price, coupon, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, username, product, p["price"], discount,
        final, coupon, datetime.now().isoformat(timespec="seconds")
    ))
    con.commit()
    oid = cur.lastrowid
    con.close()
    return oid, final

def get_coupon(code):
    con = db()
    row = con.execute(
        "SELECT code, percent FROM coupons WHERE UPPER(code)=UPPER(?) AND active=1",
        (code.strip(),)
    ).fetchone()
    con.close()
    return row

def set_coupon(code, percent):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO coupons(code, percent, active) VALUES (?, ?, 1)",
        (code.upper(), percent)
    )
    con.commit()
    con.close()

def set_order_status(order_id, status):
    con = db()
    con.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    con.commit()
    con.close()

def get_order(order_id):
    con = db()
    row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    con.close()
    return row

# ---------- state ----------
class Purchase(StatesGroup):
    coupon = State()
    receipt = State()

main_dp = Dispatcher()
admin_dp = Dispatcher()

def is_admin(uid):
    return uid in ADMIN_IDS

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 رنک VIP | ۱۰۰,۰۰۰ تومان", callback_data="product:vip")],
        [InlineKeyboardButton(text="👑 رنک LEGEND | ۱۵۰,۰۰۰ تومان", callback_data="product:legend")],
        [InlineKeyboardButton(text="🏷️ قابلیت /NICK | ۲۰۰,۰۰۰ تومان", callback_data="product:nick")],
    ])

def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت و ارسال رسید", callback_data="pay")]
    ])

def coupon_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ وارد کردن کد تخفیف", callback_data="coupon")],
        [InlineKeyboardButton(text="🚫 بدون کد تخفیف", callback_data="nocoupon")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="home")],
    ])

@main_dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔥🎮 به ربات خرید رنک سرور ازبر خیلی خوش اومدی! 🎮🔥\n\n"
        "💰 اگه رنک یا قابلیت می‌خوای، یکی از گزینه‌های زیر رو انتخاب کن 👇",
        reply_markup=menu()
    )

@main_dp.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🔥 فروشگاه سرور ازبر 🔥\n\nیکی از گزینه‌ها رو انتخاب کن 👇",
        reply_markup=menu()
    )
    await call.answer()

@main_dp.callback_query(F.data.startswith("product:"))
async def product(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    p = PRODUCTS[key]
    await state.update_data(product=key)
    await call.message.edit_text(
        f"🔥 {p['title']}\n\n{p['description']}\n\n"
        f"💰 قیمت: {p['price']:,} تومان",
        reply_markup=payment_keyboard()
    )
    await call.answer()

@main_dp.callback_query(F.data == "pay")
async def pay(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🎟️ برای خرید می‌تونی کد تخفیف وارد کنی.\n"
        "اگر کد نداری، گزینه «بدون کد تخفیف» رو بزن 👇",
        reply_markup=coupon_keyboard()
    )
    await call.answer()

@main_dp.callback_query(F.data == "coupon")
async def coupon(call: CallbackQuery, state: FSMContext):
    await state.set_state(Purchase.coupon)
    await call.message.answer("🎟️ کد تخفیف رو همینجا ارسال کن:")
    await call.answer()

@main_dp.message(Purchase.coupon)
async def coupon_message(message: Message, state: FSMContext):
    code = message.text.strip()
    row = get_coupon(code)
    if not row:
        await message.answer("❌ این کد تخفیف معتبر نیست. دوباره وارد کن:")
        return
    await state.update_data(coupon=code.upper(), discount=int(row["percent"]))
    await show_payment(message, state)

@main_dp.callback_query(F.data == "nocoupon")
async def no_coupon(call: CallbackQuery, state: FSMContext):
    await state.update_data(coupon="", discount=0)
    await show_payment(call.message, state)
    await call.answer()

async def show_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["product"]
    p = PRODUCTS[key]
    discount = data.get("discount", 0)
    final = round(p["price"] * (100 - discount) / 100)

    await state.update_data(final_price=final)

    await message.answer(
        f"💳 اطلاعات پرداخت\n\n"
        f"🛒 محصول: {p['title']}\n"
        f"💵 قیمت اصلی: {p['price']:,} تومان\n"
        f"🎟️ تخفیف: {discount}%\n"
        f"💰 مبلغ نهایی: {final:,} تومان\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_NAME}\n\n"
        "📸 بعد از پرداخت، عکس رسید رو همینجا ارسال کن.\n"
        "⚠️ لطفاً فقط رسید واقعی پرداخت رو ارسال کن.",
        parse_mode="Markdown"
    )
    await state.set_state(Purchase.receipt)

@main_dp.message(Purchase.receipt, F.photo)
async def receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["product"]
    coupon = data.get("coupon", "")
    discount = int(data.get("discount", 0))
    final = int(data.get("final_price", PRODUCTS[key]["price"]))

    oid, _ = create_order(
        message.from_user.id,
        message.from_user.username or "",
        key, coupon, discount
    )

    admin_bot = Bot(ADMIN_BOT_TOKEN)
    p = PRODUCTS[key]

    text = (
        f"🧾 <b>رسید جدید</b>\n\n"
        f"🔢 کد سفارش: <b>#{oid}</b>\n"
        f"👤 کاربر: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"🔗 Username: @{message.from_user.username or 'ندارد'}\n\n"
        f"🛒 محصول: {p['title']}\n"
        f"💰 مبلغ: <b>{final:,} تومان</b>\n"
        f"🎟️ تخفیف: {discount}%\n"
        f"🏷️ کد تخفیف: {coupon or 'ندارد'}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تأیید", callback_data=f"approve:{oid}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{oid}")
        ]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await admin_bot.send_photo(
                admin_id,
                message.photo[-1].file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception:
            pass

    await admin_bot.session.close()

    await message.answer(
        f"✅ رسیدت با موفقیت ثبت شد!\n\n"
        f"🔢 کد سفارش: <b>#{oid}</b>\n"
        "⏳ رسید توسط مدیریت بررسی می‌شود و نتیجه همینجا برایت ارسال خواهد شد.",
        parse_mode="HTML"
    )
    await state.clear()

@main_dp.message(Purchase.receipt)
async def receipt_wrong_type(message: Message):
    await message.answer("📸 لطفاً عکس رسید پرداخت رو ارسال کن.")

# ---------- admin bot ----------
@admin_dp.message(Command("start"))
async def admin_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید.")
        return
    await message.answer(
        "🛡️ پنل مدیریت ربات\n\n"
        "برای ساخت کد تخفیف:\n"
        "/coupon CODE PERCENT\n\n"
        "مثال:\n"
        "/coupon AZER10 10"
    )

@admin_dp.message(Command("coupon"))
async def admin_coupon(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("فرمت صحیح:\n/coupon CODE PERCENT")
        return
    code = parts[1].upper()
    try:
        percent = int(parts[2])
    except ValueError:
        await message.answer("❌ درصد باید عدد باشد.")
        return
    if not 1 <= percent <= 100:
        await message.answer("❌ درصد باید بین ۱ تا ۱۰۰ باشد.")
        return
    set_coupon(code, percent)
    await message.answer(f"✅ کد تخفیف <b>{code}</b> با تخفیف {percent}% ساخته شد.", parse_mode="HTML")

async def notify_user(main_bot, order_id, status):
    row = get_order(order_id)
    if not row:
        return
    if status == "approved":
        msg = (
            f"🎉 <b>پرداخت تأیید شد!</b>\n\n"
            f"🔢 سفارش: #{order_id}\n"
            f"🛒 محصول: {PRODUCTS[row['product']]['title']}\n\n"
            "✅ سفارش شما توسط مدیریت تأیید شد."
        )
    else:
        msg = (
            f"❌ <b>پرداخت رد شد.</b>\n\n"
            f"🔢 سفارش: #{order_id}\n"
            "📩 لطفاً با مدیریت سرور تماس بگیر و رسید/پرداختت رو بررسی کن."
        )
    try:
        await main_bot.send_message(row["user_id"], msg, parse_mode="HTML")
    except Exception:
        pass

@admin_dp.callback_query(F.data.startswith("approve:"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    oid = int(call.data.split(":")[1])
    row = get_order(oid)
    if not row:
        await call.answer("سفارش پیدا نشد.", show_alert=True)
        return
    set_order_status(oid, "approved")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ سفارش #{oid} تأیید شد.")
    main_bot = Bot(MAIN_BOT_TOKEN)
    await notify_user(main_bot, oid, "approved")
    await main_bot.session.close()
    await call.answer("تأیید شد ✅")

@admin_dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    oid = int(call.data.split(":")[1])
    row = get_order(oid)
    if not row:
        await call.answer("سفارش پیدا نشد.", show_alert=True)
        return
    set_order_status(oid, "rejected")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ سفارش #{oid} رد شد.")
    main_bot = Bot(MAIN_BOT_TOKEN)
    await notify_user(main_bot, oid, "rejected")
    await main_bot.session.close()
    await call.answer("رد شد ❌")

async def main():
    init_db()
    main_bot = Bot(MAIN_BOT_TOKEN)
    admin_bot = Bot(ADMIN_BOT_TOKEN)

    await asyncio.gather(
        main_dp.start_polling(main_bot),
        admin_dp.start_polling(admin_bot),
    )

if __name__ == "__main__":
    asyncio.run(main())

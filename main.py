import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Any

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ===== ТВОЙ ТОКЕН БОТА (ВСТАВЬ СЮДА) =====
BOT_TOKEN = "1780244382:eE4a-M8aZ-v5ODD5Ed2EF8kFINirIM44-yQ"
# ========================================

CUSTOM_API_SERVER = os.environ.get(
    "TELEGRAM_API_SERVER", "http://31.76.20.193:8081"
).rstrip("/")

# Твои ID администраторов
ADMIN_IDS = {
    1780243221,
    1780243215,
    1780244382,
}

if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_БОТА":
    raise RuntimeError("Укажи токен бота в переменной BOT_TOKEN!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("gorilla-case-bot")


@dataclass
class UserData:
    username: str
    stars: int = 100
    total_spent: int = 0
    inventory: dict[str, int] = field(default_factory=dict)


ITEMS_BY_ID = {
    "880000001": "Pretty Posy",
    "880000002": "Desk Calendar",
    "880000003": "Mouse Cake",
    "880000004": "Evil Eye",
    "880000005": "Timeless Book",
    "880000006": "Mood Pack",
    "880000007": "Money Pot",
}

users_db: dict[int, UserData] = {}
promo_db: dict[str, dict[str, Any]] = {}

CASES: dict[str, dict[str, Any]] = {
    "schoolboy": {
        "title": "🎒 Кейс Школьник",
        "price": 100,
        "description": "Содержит: 50 ⭐ на баланс, 250⭐️ на баланс, Evil Eye",
        "rewards": [
            ("stars", 50, 100),
        ],
    },
    "player": {
        "title": "🎮 Кейс Player",
        "price": 250,
        "description": "Содержит: 100 ⭐ на баланс, 500⭐️ на баланс, Evil Eye",
        "rewards": [
            ("stars", 100, 30),
            ("nft", "Evil Eye", 70),
        ],
    },
    "bear": {
        "title": "🐻 Кейс Bear",
        "price": 500,
        "description": "Содержит: 250 ⭐ на баланс, Evil Eye Black Фон, Timeless Book Black Фон",
        "rewards": [
            ("stars", 250, 10),
            ("nft", "Evil Eye", 60),
            ("nft", "Timeless Book", 30),
        ],
    },
    "rich": {
        "title": "💸 Кейс Rich",
        "price": 1000,
        "description": "Содержит: Evil Eye, Mood Pack, Money Pot Black Фон",
        "rewards": [
            ("nft", "Evil Eye", 40),
            ("nft", "Mood Pack", 40),
            ("nft", "Money Pot", 20),
        ],
    },
}


class PromoState(StatesGroup):
    waiting_for_code = State()


class WithdrawState(StatesGroup):
    waiting_for_item = State()


class SupportState(StatesGroup):
    waiting_for_message = State()


def get_user_data(user: types.User) -> UserData:
    username = user.username or user.first_name or str(user.id)
    if user.id not in users_db:
        users_db[user.id] = UserData(username=username)
    else:
        users_db[user.id].username = username
    return users_db[user.id]


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Баланс"),
                KeyboardButton(text="🎁 Кейсы"),
            ],
            [
                KeyboardButton(text="⚙️ Общее"),
                KeyboardButton(text="📦 Инвентарь"),
                KeyboardButton(text="🎟️ Промо"),
            ],
            [
                KeyboardButton(text="📤 Вывод NFT"),
            ],
            [
                KeyboardButton(text="🆘 Поддержка"),
            ],
            [
                KeyboardButton(text="↩️ Назад в меню"),
            ],
        ],
        resize_keyboard=True,
    )

def get_cases_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎒 Школьник — 100⭐", callback_data="case_schoolboy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 Player — 250⭐", callback_data="case_player"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🐻 Bear — 500⭐", callback_data="case_bear"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Rich — 1000⭐", callback_data="case_rich"
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад в меню", callback_data="back_menu"
                )
            ],
        ]
    )


def pick_case_reward(case: dict[str, Any]) -> tuple[str, int | str]:
    roll = random.uniform(0, 100)
    current = 0.0
    for reward_type, value, chance in case["rewards"]:
        current += chance
        if roll < current:
            return reward_type, value
    last_type, last_value, _ = case["rewards"][-1]
    return last_type, last_value


router = Router()@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    get_user_data(message.from_user)
    welcome_text = (
        "🦍 **Добро пожаловать в Gorilla Case!**\n\n"
        "🎁 Открывайте кейсы с NFT и звёздами\n"
        "⭐ Собирайте редкие призы и пополняйте инвентарь\n\n"
        "👇 Выберите нужный раздел в меню:"
    )
    photo_path = "attached_assets/IMG_7905_1786375216637.jpeg"
    if os.path.isfile(photo_path):
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


@router.message(F.text.in_({"Профиль", "👤 Профиль", "💰 Баланс"}))
async def show_profile(message: types.Message) -> None:
    data = get_user_data(message.from_user)
    username = (
        f"@{data.username}" if message.from_user.username else data.username
    )
    await message.answer(
        f"👤 **Профиль пользователя**\n\n"
        f"Юзернейм: {username}\n"
        f"💰 Баланс: {data.stars} ⭐\n"
        f"📈 Всего вложено звёзд: {data.total_spent} ⭐\n\n"
        "➕ **Пополнение баланса**\n"
        "Чтобы пополнить баланс ⭐, напишите оператору: @Relayer",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 Пополнить баланс", url="https://t.me/Relayer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="↩️ Назад в меню", callback_data="back_menu"
                    )
                ],
            ]
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text.in_({"Кейсы", "🎁 Кейсы"}))
async def show_cases(message: types.Message) -> None:
    data = get_user_data(message.from_user)
    case_descriptions = "\n\n".join(
        f"{case['title']} — {case['price']} ⭐\n{case['description']}"
        for case in CASES.values()
    )
    await message.answer(
        f"{case_descriptions}\n\n"
        f"💰 Ваш баланс: {data.stars} ⭐\n\n"
        "👇 Выберите кейс:",
        reply_markup=get_cases_inline_kb(),
    )


@router.message(F.text.in_({"Инвентарь", "📦 Инвентарь"}))
async def show_inventory(message: types.Message) -> None:
    data = get_user_data(message.from_user)
    if not data.inventory:
        await message.answer(
            "📦 Ваш инвентарь пока пуст.\n"
            "🎁 Откройте кейс, чтобы получить свой первый NFT!",
            reply_markup=get_main_keyboard(),
        )
        return

    lines = ["📦 **Ваш инвентарь:**", ""]
    lines.extend(
        f"{index}. {item} — x{count}"
        for index, (item, count) in enumerate(data.inventory.items(), 1)
    )
    await message.answer(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text.in_({"Общее", "⚙️ Общее"}))
async def show_general(message: types.Message) -> None:
    await message.answer(
        "⚙️ **Общее меню**\n\n"
        "📦 Откройте инвентарь\n"
        "📤 Оставьте заявку на вывод NFT\n"
        "🎟️ Активируйте промокод\n"
        "🆘 Напишите в поддержку",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text.in_({"Назад в меню", "↩️ Назад в меню"}))
async def back_to_menu(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await show_general(message)


@router.message(F.text.in_({"Вывод", "📤 Вывод NFT"}))
async def start_withdraw(message: types.Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in {
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    data = get_user_data(message.from_user)
    items = [item for item, count in data.inventory.items() if count > 0]

    if not items:
        await message.answer(
            "📦 У вас пока нет NFT для вывода.\n"
            "🎁 Откройте кейс — и полученный NFT появится здесь!",
            reply_markup=get_main_keyboard(),
        )
        return

    lines = [
        "📤 **Заявка на вывод NFT**",
        "",
        "💎 Выберите подарок из инвентаря:",
        "",
    ]
    lines.extend(
        f"{index}. {item} (x{data.inventory[item]})"
        for index, item in enumerate(items, 1)
    )
    lines.extend(
        [
            "",
            "✍️ Введите номер или точное название NFT.",
            "👤 После отправки заявки свяжитесь с оператором: @Relayer",
        ]
    )

    await state.update_data(withdraw_items=items)
    await state.set_state(WithdrawState.waiting_for_item)

    await message.answer(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(WithdrawState.waiting_for_item)
async def process_withdraw(
    message: types.Message, state: FSMContext, bot: Bot
) -> None:
    if message.text and message.text.strip() in {
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    state_data = await state.get_data()
    items = state_data.get("withdraw_items", [])
    user_data = get_user_data(message.from_user)
    user_input = (message.text or "").strip()
    selected_item = None

    if user_input.isdigit():
        index = int(user_input) - 1
        if 0 <= index < len(items):
            selected_item = items[index]
    else:
        selected_item = next(
            (item for item in items if item.lower() == user_input.lower()),
            None,
        )

    if not selected_item or user_data.inventory.get(selected_item, 0) <= 0:
        await message.answer(
            "❌ Некорректный выбор. Заявка отменена.\n"
            "↩️ Попробуйте снова через меню."
        )
        await state.clear()
        return

    user_data.inventory[selected_item] -= 1
    if user_data.inventory[selected_item] <= 0:
        del user_data.inventory[selected_item]

    admin_message = (
        "🚨 **Новая заявка на вывод NFT!**\n\n"
        f"👤 Пользователь: @{user_data.username} (ID: `{message.from_user.id}`)\n"
        f"💎 Предмет: **{selected_item}**\n"
        "📩 Пользователю нужно связаться с оператором: @Relayer"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_message, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            logger.exception("Could not notify admin %s", admin_id)

    await message.answer(
        f"✅ Заявка на вывод {selected_item} отправлена администраторам!\n\n"
        "👤 Теперь напишите оператору: @Relayer\n"
        "📩 Укажите свой Telegram ID и название NFT.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Написать @Relayer", url="https://t.me/Relayer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="↩️ Назад в меню", callback_data="back_menu"
                    )
                ],
            ]
        ),
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.clear()


@router.message(F.text.in_({"Промо", "🎟️ Промо"}))
async def ask_promo(message: types.Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in {
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    await state.set_state(PromoState.waiting_for_code)
    await message.answer(
        "🎟️ **Активация промокода**\n\n🔑 Введите промокод:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text.
                in_({"Поддержка", "🆘 Поддержка"}))
async def start_support(message: types.Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in {
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    await state.set_state(SupportState.waiting_for_message)
    await message.answer(
        "🆘 **Служба поддержки**\n\n"
        "✍️ Напишите одним сообщением, что случилось или какой вопрос у вас возник.\n"
        "📨 Сообщение сразу увидят администраторы и ответят вам здесь.\n\n"
        "↩️ Для отмены нажмите «⚙️ Общее».",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(SupportState.waiting_for_message)
async def process_support(
    message: types.Message, state: FSMContext, bot: Bot
) -> None:
    if message.text and message.text.strip() in {
        "⚙️ Общее",
        "Общее",
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    user = get_user_data(message.from_user)
    username = (
        f"@{user.username}" if message.from_user.username else user.username
    )
    support_header = (
        "🆘 **Новое сообщение в поддержку**\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"💬 Чат: `{message.chat.id}`"
    )

    delivered = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, support_header, parse_mode=ParseMode.MARKDOWN
            )
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            delivered = True
        except Exception:
            logger.exception(
                "Could not forward support message to admin %s", admin_id
            )

    if delivered:
        await message.answer(
            "✅ Сообщение отправлено в поддержку!\n⏳ Администраторы скоро ответят вам.",
            reply_markup=get_main_keyboard(),
        )
    else:
        await message.answer(
            "⚠️ Не удалось отправить сообщение в поддержку.\nПопробуйте ещё раз чуть позже.",
            reply_markup=get_main_keyboard(),
        )
    await state.clear()


@router.message(PromoState.waiting_for_code)
async def use_promo(message: types.Message, state: FSMContext) -> None:
    if message.text and message.text.strip() in {
        "↩️ Назад в меню",
        "Назад в меню",
    }:
        await state.clear()
        await show_general(message)
        return

    code = (message.text or "").strip()
    user_data = get_user_data(message.from_user)
    promo = promo_db.get(code)

    if not promo or promo["uses"] <= 0:
        await message.answer("❌ Промокод недействителен или исчерпал лимит.")
        await state.clear()
        return

    promo["uses"] -= 1

    if promo["type"] == "stars":
        user_data.stars += int(promo["value"])
        await message.answer(
            f"✅ Промокод активирован! Вы получили {promo['value']} ⭐",
            reply_markup=get_main_keyboard(),
        )
    else:
        add_to_inventory(message.from_user.id, str(promo["value"]))
        await message.answer(
            f"✅ В инвентарь добавлен NFT: **{promo['value']}**",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    if promo["uses"] <= 0:
        del promo_db[code]
    await state.clear()


@router.message(Command("pay"))
async def cmd_pay(message: types.Message) -> None:
    """Команда для администраторов: /pay <id_пользователя> <сумма>"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат.\nИспользование: `/pay <id_пользователя> <сумма>`",
            parse_mode=ParseMode.MARKDOWN,
            )
        return

    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("❌ ID и сумма должны быть числами.")
        return

    if target_id not in users_db:
        users_db[target_id] = UserData(username=str(target_id))

    users_db[target_id].stars += amount

    await message.answer(
        f"✅ Баланс пользователя {target_id} пополнен на {amount} ⭐.",
        parse_mode=ParseMode.MARKDOWN,
    )


@router.callback_query(F.data.startswith("case_"))
async def open_case(callback: types.CallbackQuery) -> None:
    case_id = callback.data.removeprefix("case_")
    case = CASES.get(case_id)

    if case is None:
        await callback.answer("❌ Кейс не найден.", show_alert=True)
        return

    user_data = get_user_data(callback.from_user)
    price = int(case["price"])

    if user_data.stars < price:
        await callback.answer(
            f"❌ Недостаточно звёзд. Нужно {price} ⭐.", show_alert=True
        )
        return

    user_data.stars -= price
    user_data.total_spent += price
    reward_type, reward_value = pick_case_reward(case)

    if reward_type == "stars":
        user_data.stars += int(reward_value)
        result = (
            f"💰 **Вам выпало {reward_value} ⭐!**\n"
            f"💰 Новый баланс: {user_data.stars} ⭐"
        )
    else:
        add_to_inventory(callback.from_user.id, str(reward_value))
        result = (
            f"🎉 **Вам выпал NFT {reward_value}!**\n"
            "📦 NFT добавлен в ваш инвентарь."
        )

    await callback.message.answer(
        f"✨ **Кейс открыт!**\n\n"
        f"{case['title']}\n"
        f"🎟️ Стоимость: {price} ⭐\n\n"
        f"{result}",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer("✅ Кейс открыт!")


@router.callback_query(F.data == "back_menu")
async def back_menu(callback: types.CallbackQuery) -> None:
    await callback.message.answer(
        "↩️ **Вы вернулись в главное меню.**\n\nВыберите нужный раздел:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


async def main() -> None:
    session = None
    if CUSTOM_API_SERVER:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(CUSTOM_API_SERVER)
        )

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started successfully!")
    await dp.start_polling(bot)


if name == "__main__":
    asyncio.run(main())
    

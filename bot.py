import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MENTORS = {
    "tinkov": {
        "name": "Тиньков",
        "emoji": "🔥",
        "prompt": "Ты — Олег Тиньков, жёсткий предприниматель. Говоришь коротко, прямо, без нюней. Требуешь конкретики и результатов. Не хвалишь без причины. Провоцируешь. Максимум 3 предложения. Без эмодзи."
    },
    "osipov": {
        "name": "Осипов",
        "emoji": "💡",
        "prompt": "Ты — Михаил Осипов, эксперт по продажам и бизнесу. Говоришь чётко, по делу, с конкретными советами. Задаёшь правильные вопросы. Помогаешь найти точку роста. Максимум 3 предложения."
    },
    "hartman": {
        "name": "Хартман",
        "emoji": "⚡",
        "prompt": "Ты — Хартман, жёсткий drill sergeant. Кричишь, давишь, не даёшь расслабиться. Каждое слово как пинок. Требуешь действий прямо сейчас. Максимум 3 предложения. Без мягкости."
    },
    "torbасов": {
        "name": "Торбасов",
        "emoji": "🎯",
        "prompt": "Ты — Антон Торбасов, эксперт по недвижимости и бизнесу. Говоришь уверенно, со знанием дела. Даёшь конкретные стратегии. Мотивируешь через логику и факты. Максимум 3 предложения."
    }
}

user_data = {}

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "mentor": None,
            "tasks": [],
            "goal": "",
            "history": []
        }
    return user_data[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔥 Тиньков", callback_data="mentor_tinkov"),
         InlineKeyboardButton("💡 Осипов", callback_data="mentor_osipov")],
        [InlineKeyboardButton("⚡ Хартман", callback_data="mentor_hartman"),
         InlineKeyboardButton("🎯 Торбасов", callback_data="mentor_torbасов")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👊 *PUSHER — твой личный AI-наставник*\n\n"
        "Выбери наставника который будет тебя пушить:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def mentor_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    mentor_key = query.data.replace("mentor_", "")
    user["mentor"] = mentor_key
    mentor = MENTORS[mentor_key]
    
    await query.edit_message_text(
        f"{mentor['emoji']} *Наставник: {mentor['name']}*\n\n"
        f"Теперь расскажи — какая твоя главная цель на этот месяц?",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    text = update.message.text
    
    if not user["mentor"]:
        await start(update, context)
        return
    
    if not user["goal"]:
        user["goal"] = text
        mentor = MENTORS[user["mentor"]]
        await update.message.reply_text(
            f"✅ Цель записана: *{text}*\n\n"
            f"Теперь можешь:\n"
            f"• Просто писать мне — отвечу как {mentor['name']}\n"
            f"• /tasks — список задач на день\n"
            f"• /add задача — добавить задачу\n"
            f"• /done — отметить выполненное\n"
            f"• /checkin — еженедельный разбор\n"
            f"• /mentor — сменить наставника",
            parse_mode="Markdown"
        )
        return
    
    mentor = MENTORS[user["mentor"]]
    user["history"].append({"role": "user", "content": text})
    
    if len(user["history"]) > 10:
        user["history"] = user["history"][-10:]
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=mentor["prompt"] + f"\n\nЦель пользователя: {user['goal']}\nЗадачи сегодня: {', '.join(user['tasks']) if user['tasks'] else 'не поставлены'}",
            messages=user["history"]
        )
        reply = response.content[0].text
        user["history"].append({"role": "assistant", "content": reply})
        await update.message.reply_text(f"{mentor['emoji']} {reply}")
    except Exception as e:
        await update.message.reply_text("Ошибка соединения. Попробуй снова.")

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user["tasks"]:
        await update.message.reply_text("📋 Задач нет. Добавь: /add купить хлеб")
        return
    
    task_list = "\n".join([f"{'✅' if t.get('done') else '⬜'} {t['text']}" for t in user["tasks"]])
    done = sum(1 for t in user["tasks"] if t.get("done"))
    await update.message.reply_text(f"📋 *Задачи на сегодня* ({done}/{len(user['tasks'])}):\n\n{task_list}", parse_mode="Markdown")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    task_text = " ".join(context.args)
    if not task_text:
        await update.message.reply_text("Напиши задачу: /add позвонить клиенту")
        return
    
    user["tasks"].append({"text": task_text, "done": False})
    await update.message.reply_text(f"✅ Задача добавлена: {task_text}")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user["mentor"]:
        await start(update, context)
        return
    
    mentor = MENTORS[user["mentor"]]
    done = sum(1 for t in user["tasks"] if t.get("done"))
    total = len(user["tasks"])
    
    checkin_prompt = f"Проведи жёсткий еженедельный разбор. Цель пользователя: {user['goal']}. Выполнено задач: {done} из {total}. Задай 2 неудобных вопроса и дай один конкретный совет."
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=mentor["prompt"],
            messages=[{"role": "user", "content": checkin_prompt}]
        )
        await update.message.reply_text(f"{mentor['emoji']} *Еженедельный разбор:*\n\n{response.content[0].text}", parse_mode="Markdown")
    except:
        await update.message.reply_text("Ошибка. Попробуй снова.")

async def change_mentor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    user["mentor"] = None
    await start(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("mentor", change_mentor))
    app.add_handler(CallbackQueryHandler(mentor_selected, pattern="^mentor_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("PUSHER bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()

# === bot.py ===
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
import os
import cv2

ADMIN_ID = 123456789  # Замените на свой Telegram user ID
bot = TeleBot(API_TOKEN)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.message.chat.id

    if manager.get_prize_winner_count(prize_id) < 3:
        if not manager.has_user_won_prize(user_id, prize_id):
            if manager.add_winner(user_id, prize_id):
                manager.add_bonus_points(user_id, 5)
            img = manager.get_prize_img(prize_id)
            if img:
                with open(f'img/{img}', 'rb') as photo:
                    bot.send_photo(user_id, photo)
        else:
            bot.answer_callback_query(call.id, "Ты уже получил этот приз!")
    else:
        bot.answer_callback_query(call.id, "Приз уже забрали 3 пользователя!")

def send_message():
    prize = manager.get_random_prize()
    if not prize:
        return

    prize_id, img = prize[:2]
    manager.set_last_prize_id(prize_id)
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id=prize_id))

def process_resend_requests():
    for user_id, prize_id in manager.get_resend_requests():
        img = manager.get_prize_img(prize_id)
        if img:
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Вот твоя повторная картинка!")
    manager.clear_resend_requests()

def shedule_thread():
    schedule.every().minute.do(send_message)
    schedule.every().minute.do(process_resend_requests)
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    rating = manager.get_user_rating()
    if not rating:
        bot.reply_to(message, "Рейтинг пока пуст.")
        return

    table = "🏆 Текущий рейтинг:\n\n"
    for i, (username, points) in enumerate(rating, 1):
        table += f"{i}. @{username} — {points} баллов\n"
    bot.reply_to(message, table)

@bot.message_handler(commands=['my_score'])
def get_my_score(message):
    user_id = message.chat.id
    user_imgs = manager.get_winners_img(user_id)
    all_imgs = manager.get_all_img_names()

    if not all_imgs:
        bot.reply_to(message, "Пока нет доступных картинок.")
        return

    collage = create_collage(user_imgs, all_imgs)
    if collage is None:
        bot.reply_to(message, "Произошла ошибка при создании коллажа.")
        return

    output_path = f'temp_collage_{user_id}.jpg'
    cv2.imwrite(output_path, collage)

    with open(output_path, 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Вот твои достижения!")

    os.remove(output_path)

@bot.message_handler(commands=['points'])
def handle_points(message):
    user_id = message.chat.id
    points = manager.get_user_points(user_id)
    bot.reply_to(message, f"У тебя {points} бонусных монет 🪙")

@bot.message_handler(commands=['resend'])
def handle_resend_request(message):
    user_id = message.chat.id
    last_prize = manager.get_last_prize_id()
    cost = 5
    if not last_prize:
        bot.reply_to(message, "Пока нет доступных картинок для повторной отправки.")
        return
    if manager.spend_points(user_id, cost):
        manager.request_resend(user_id, last_prize)
        bot.reply_to(message, f"Запрос на повторную отправку картинки отправлен! С вас списано {cost} монет.")
    else:
        bot.reply_to(message, "Недостаточно бонусных монет для запроса повторной отправки.")

@bot.message_handler(commands=['admin_add'])
def admin_add(message):
    if message.from_user.id != ADMIN_ID:
        return
    files = os.listdir('img')
    manager.add_prize([(f,) for f in files])
    bot.reply_to(message, f"Добавлено {len(files)} новых призов.")

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()

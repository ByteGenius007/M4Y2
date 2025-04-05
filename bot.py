from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *

bot = TeleBot(API_TOKEN)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=str(id)))
    return markup

def send_message():
    result = manager.get_random_prize()
    if result is None:
        print("Ошибка: Приз не найден!")
        return
    prize_id, img = result[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    
    for user in manager.get_users():
        user_id = user[0]  # Достаем user_id из кортежа
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user_id, photo, reply_markup=gen_markup(prize_id))

def schedule_thread():
    schedule.every().minute.do(send_message)  # Измени на `hour` если нужно каждый час
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    registered_users = [user[0] for user in manager.get_users()]  # Создаем список user_id
    if user_id in registered_users:
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Ты успешно зарегистрирован!
Каждый час тебе будут приходить новые картинки, и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating()
    if not res:
        bot.send_message(message.chat.id, "Рейтинг пока пуст.")
        return
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = int(call.data)
    user_id = call.message.chat.id

    winners_count = manager.get_winners_count(prize_id)

    if winners_count < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_schedule = threading.Thread(target=schedule_thread)

    polling_thread.start()
    polling_schedule.start()


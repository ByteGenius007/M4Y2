from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
from logic import create_collage
import cv2
import os 

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
            bot.send_photo(user_id, photo, caption="Нажми ' Получить!' быстрее всех!", reply_markup=gen_markup(prize_id))

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

@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.send_message(message.chat.id, """
📝 **Доступные команды:**

/start — регистрация в системе. Получай шанс выигрывать призы каждую минуту!  
/help — справка по боту (ты сейчас на этой странице!).  
/rating — посмотри рейтинг игроков, кто выиграл больше всего призов!  
/get_my_score — посмотри свой коллаж с полученными призами и уровнем.  
/achievements — твой текущий уровень и количество полученных картинок! Получай новые достижения за активность!  

💎 **Как работает бот?**  
Каждую минуту мы проводим аукцион с новыми призами! Ты можешь выиграть их, нажав на кнопку **Получить!**. Но будь быстрым — только первые 3 пользователя получат картинку! 🎉

🏆 **Уровни и достижения:**  
С каждым полученным призом ты будешь повышать свой уровень! За 5, 10 и 15 картинок ты получишь новые звания. Пиши /achievements, чтобы узнать свой текущий уровень!

💡 **Советы:**  
- Следи за появлением новых картинок! Чем быстрее нажмешь **Получить!**, тем выше шансы на победу.  
- Заходи в рейтинг, чтобы узнать, кто лучший в этом аукционе!

📩 Если есть вопросы — пишите в поддержку!
""")

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

@bot.message_handler(commands=['get_my_score'])
def get_my_score(message):
    user_id = message.chat.id
    info = manager.get_winners_img(user_id)
    prizes = [x[0] for x in info]

    image_paths = os.listdir('img')
    image_paths = [f'img/{x}' if x in prizes else f'hidden_img/{x}' for x in image_paths]

    collage = create_collage(image_paths)
    
    # Создаём папку, если нет
    if not os.path.exists('collages'):
        os.makedirs('collages')
    
    path_to_collage = f'collages/{user_id}_collage.jpg'
    cv2.imwrite(path_to_collage, collage)

    with open(path_to_collage, 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Вот твой коллаж с полученными призами!")

@bot.message_handler(commands=['achievements'])
def handle_achievements(message):
    user_id = message.chat.id
    level = manager.get_user_achievements(user_id)
    
    # Получим количество полученных призов для отображения
    conn = sqlite3.connect(DATABASE)
    with conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(winners.prize_id)
            FROM winners
            WHERE winners.user_id = ?
        ''', (user_id,))
        count = cur.fetchone()[0]
    
    bot.send_message(message.chat.id, f"Ваш уровень: {level}\nКоличество полученных картинок: {count}")

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_schedule = threading.Thread(target=schedule_thread)

    polling_thread.start()
    polling_schedule.start()


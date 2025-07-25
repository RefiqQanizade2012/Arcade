# === logic.py ===
import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2
import numpy as np
from math import sqrt, ceil, floor

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS bonus_points (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS resend_requests (
                user_id INTEGER,
                prize_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT INTO users VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('''INSERT INTO prizes (image) VALUES (?)''', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor() 
            cur.execute("SELECT * FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
            if cur.fetchall():
                return 0
            else:
                conn.execute('''INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)''', (user_id, prize_id, win_time))
                conn.commit()
                return 1

    def mark_prize_used(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
            conn.commit()

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users')
            return [x[0] for x in cur.fetchall()] 

    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id, ))
            result = cur.fetchall()
            return result[0][0] if result else None

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM prizes WHERE used = 0 ORDER BY RANDOM()')
            result = cur.fetchall()
            return result[0] if result else None

    def get_winners_img(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(''' 
                SELECT image FROM winners 
                INNER JOIN prizes ON 
                winners.prize_id = prizes.prize_id
                WHERE user_id = ?''', (user_id, ))
            return [row[0] for row in cur.fetchall()]

    def get_all_img_names(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT image FROM prizes')
            return [row[0] for row in cur.fetchall()]

    def get_user_rating(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT users.user_name, COUNT(*) as score
                FROM winners
                INNER JOIN users ON users.user_id = winners.user_id
                GROUP BY winners.user_id
                ORDER BY score DESC
            ''')
            return cur.fetchall()

    def add_bonus_points(self, user_id, amount):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
                INSERT INTO bonus_points (user_id, points)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET points = points + ?
            ''', (user_id, amount, amount))

    def get_user_points(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT points FROM bonus_points WHERE user_id = ?', (user_id,))
            res = cur.fetchone()
            return res[0] if res else 0

    def spend_points(self, user_id, cost):
        current = self.get_user_points(user_id)
        if current >= cost:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.execute('UPDATE bonus_points SET points = points - ? WHERE user_id = ?', (cost, user_id))
            return True
        return False

    def request_resend(self, user_id, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT INTO resend_requests VALUES (?, ?)', (user_id, prize_id))

    def get_resend_requests(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT user_id, prize_id FROM resend_requests')
            return cur.fetchall()

    def clear_resend_requests(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('DELETE FROM resend_requests')

    def set_last_prize_id(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
                INSERT INTO state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?
            ''', ("last_prize", str(prize_id), str(prize_id)))

    def get_last_prize_id(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT value FROM state WHERE key = ?', ("last_prize",))
            row = cur.fetchone()
            return int(row[0]) if row else None

def hide_img(img_name):
    image = cv2.imread(f'img/{img_name}')
    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated_image)

def create_collage(user_images, all_images):
    image_paths = []
    for img in all_images:
        if img in user_images:
            image_paths.append(f'img/{img}')
        else:
            image_paths.append(f'hidden_img/{img}')

    images = [cv2.imread(path) for path in image_paths if os.path.exists(path)]
    if not images:
        return None

    num_images = len(images)
    num_cols = floor(sqrt(num_images))
    num_rows = ceil(num_images / num_cols)

    img_h, img_w = images[0].shape[:2]
    collage = np.zeros((num_rows * img_h, num_cols * img_w, 3), dtype=np.uint8)

    for i, image in enumerate(images):
        row, col = divmod(i, num_cols)
        collage[row*img_h:(row+1)*img_h, col*img_w:(col+1)*img_w] = image

    return collage

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)

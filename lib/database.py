import sqlite3


class UserDatabase:
    def __init__(self, db_name):
        print(f"Connecting to {db_name}")
        self.conn = sqlite3.connect(database=str(db_name))
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                consecutive_wins INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buddies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                buddy_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (buddy_id) REFERENCES users(id)
            )
        ''')
        self.conn.commit()

    def add_user(self, username, password=None):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (username, password) VALUES (?, ?)
            ''', (username, password))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # User already exists

    def delete_user(self, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM users WHERE username = ?
        ''', (username,))
        cursor.execute('''
            DELETE FROM buddies WHERE username = ? OR buddy = ?
        ''', (username, username))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_stats(self, username, games_played, games_won, consecutive_wins, rank):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users
            SET games_played = games_played + ?,
                games_won = games_won + ?,
                consecutive_wins = MAX(consecutive_wins, ?),
                rank = ?
            WHERE username = ?
        ''', (games_played, games_won, consecutive_wins, rank, username))
        self.conn.commit()

    def get_user_info(self, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE username = ?
        ''', (username,))
        return cursor.fetchone()

    def add_buddy(self, username, buddy):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO buddies (user_id, buddy_id)
            SELECT u1.id, u2.id
            FROM users u1, users u2
            WHERE u1.username = ? AND u2.username = ?
        ''', (username, buddy))
        self.conn.commit()

    def get_buddies(self, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.username
            FROM users u
            JOIN buddies b ON u.id = b.buddy_id
            JOIN users u2 ON b.user_id = u2.id
            WHERE u2.username = ?
        ''', (username,))
        return [buddy[0] for buddy in cursor.fetchall()]


    def authenticate(self, username, password):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT password FROM users WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        if result:
            return result[0] == password
        return False
    
    def get_counter(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM users
        ''')
        return cursor.fetchone()[0]

    def get_all_ids(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id FROM users
        ''')
        return [id[0] for id in cursor.fetchall()]

    def buddy_check(self, user1, user2):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM buddies WHERE user_id =? AND buddy_id =?
         ''', (user1, user2))
        return bool(cursor.fetchone()[0])


if __name__ == "__main__":
    # Example usage:
    db = UserDatabase('data/user.db')
    db.add_user('user1', 'password1')
    db.add_user('user2', 'password2')

    db.update_stats('user1', 10, 5, 3, 5)
    db.update_stats('user2', 8, 3, 2, 3)

    db.add_buddy('user1', 'user2')

    print(db.get_user_info('user1'))
    print(db.authenticate('user1', 'password1'))
    print(db.authenticate('user1', 'password2'))
    print(db.get_buddies('user1'))

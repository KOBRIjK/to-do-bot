import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Не выполнено',
            deadline TEXT,
            category TEXT,
            priority TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_user_tasks(user_id, status=None):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    if status:
        cursor.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND status = ?",
            (user_id, status)
        )
    else:
        cursor.execute(
            "SELECT * FROM tasks WHERE user_id = ?",
            (user_id,)
        )
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def add_task(user_id, name, description, deadline=None, category=None, priority=None):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, name, description, deadline, category, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, description, deadline, category, priority)
    )
    conn.commit()
    conn.close()

def update_task(user_id, task_id, field, value):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE tasks SET {field} = ? WHERE user_id = ? AND id = ?",
        (value, user_id, task_id)
    )
    conn.commit()
    conn.close()

def delete_task(user_id, task_id):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM tasks WHERE user_id = ? AND id = ?",
        (user_id, task_id)
    )
    conn.commit()
    conn.close()
import os
import sqlite3
import psycopg2
from urllib.parse import urlparse

class DatabaseManager:
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        self.use_postgres = bool(self.db_url)
        
    def get_connection(self):
        if self.use_postgres:
            return psycopg2.connect(self.db_url)
        else:
            return sqlite3.connect('billing_records.db')
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bills (
                    id SERIAL PRIMARY KEY,
                    bill_no VARCHAR(50) UNIQUE,
                    date TIMESTAMP,
                    customer_name VARCHAR(255),
                    customer_phone VARCHAR(20),
                    customer_address TEXT,
                    subtotal DECIMAL(10,2),
                    cgst DECIMAL(10,2),
                    sgst DECIMAL(10,2),
                    total_amount DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            # SQLite schema (existing)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_no TEXT UNIQUE,
                    date TEXT,
                    customer_name TEXT,
                    customer_phone TEXT,
                    customer_address TEXT,
                    subtotal REAL,
                    cgst REAL,
                    sgst REAL,
                    total_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        conn.commit()
        conn.close()

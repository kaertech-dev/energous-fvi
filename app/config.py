import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "packing-scan-secret-2024")
    TRAY_LIMIT = 50

class DBConfig:
    HOST = os.environ.get("DB_HOST", "192.168.1.38")
    USER = os.environ.get("DB_USER", "labeling")
    PASSWORD = os.environ.get("DB_PASSWORD", "labeling")
    DATABASE = os.environ.get("DB_NAME", "energous")
    PORT = int(os.environ.get("DB_PORT", 3306))

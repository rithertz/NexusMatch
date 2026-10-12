import psycopg
from app.core.config import settings
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def check_postgres() -> bool:
    try:
        with (
            psycopg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                connect_timeout=2,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except psycopg.Error:
        return False


def check_mongodb() -> bool:
    try:
        with MongoClient(
            host=settings.mongodb_host,
            port=settings.mongodb_port,
            username=settings.mongo_initdb_root_username,
            password=settings.mongo_initdb_root_password,
            authSource="admin",
            serverSelectionTimeoutMS=2000,
        ) as client:
            return client.admin.command("ping").get("ok") == 1
    except PyMongoError:
        return False

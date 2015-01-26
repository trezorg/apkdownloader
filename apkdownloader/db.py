import os
import sqlite3
from collections import namedtuple

__all__ = (
    'create_db',
    'get_access_token',
    'get_apks_records',
    'delete_apks_records',
    'update_access_token',
    'update_apk_info',
    'ApkInfo',
)


DB_APK_TABLE_NAME = "apk"
DB_APK_TRIGGER_NAME = "apk_trig"
DB_TOKEN_TABLE_NAME = "token"
DB_TABLES = [DB_APK_TABLE_NAME, DB_TOKEN_TABLE_NAME, DB_APK_TRIGGER_NAME]
DB_APK_TABLE_SQL = """
create table {0} (
    name text not null,
    code int not null,
    version text not null,
    offer text not null,
    size int not null,
    updated datetime not null default current_timestamp,
    unique(name) on conflict replace
)
""".format(DB_APK_TABLE_NAME)
DB_APK_TRIGGER_SQL = """
create trigger {1} after update on {0}
    begin
        update {0} SET updated = datetime('now') where name = NEW.name;
    end;
""".format(DB_APK_TABLE_NAME, DB_APK_TRIGGER_NAME)
DB_TOKEN_TABLE_SQL = """
create table {0} (
    token text not null
);
""".format(DB_TOKEN_TABLE_NAME)
DB_TABLES_SQL = {
    DB_APK_TABLE_NAME: DB_APK_TABLE_SQL,
    DB_APK_TRIGGER_NAME: DB_APK_TRIGGER_SQL,
    DB_TOKEN_TABLE_NAME: DB_TOKEN_TABLE_SQL
}
ApkInfo = namedtuple("ApkInfo", ["name", "code", "version", "offer", "size"])


def check_db_tables(cursor):
    query = "select name from sqlite_master where type in ('table', 'trigger')"
    cursor.execute(query)
    tables = [rec[0] for rec in cursor.fetchall()]
    absent_tables = [table for table in DB_TABLES if table not in set(tables)]
    return absent_tables


def create_db(db, force=False):
    if force and os.path.isfile(db):
        os.remove(db)
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    absent_tables = check_db_tables(cursor)
    for table in absent_tables:
        table_sql = DB_TABLES_SQL[table]
        cursor.execute(table_sql)
    conn.commit()
    cursor.close()


def get_access_token(db):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("Select token from {}".format(DB_TOKEN_TABLE_NAME))
    records = cursor.fetchone()
    cursor.close()
    if records:
        return records[0]


def update_access_token(db, token):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("Select token from {0}".format(DB_TOKEN_TABLE_NAME))
    records = cursor.fetchone()
    if not records:
        cursor.execute(
            "Insert into {0} (token) values(?)".
            format(DB_TOKEN_TABLE_NAME), [token])
    else:
        cursor.execute(
            "Update {0} set token = ?".format(DB_TOKEN_TABLE_NAME), [token])
    conn.commit()
    cursor.close()


def get_apks_records(db):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(
        "Select name, code, version, offer, size from {}".
        format(DB_APK_TABLE_NAME))
    records = cursor.fetchall()
    cursor.close()
    return dict((record[0], ApkInfo(*record)) for record in records)


def delete_apks_records(db, records):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(
        "Delete from {} where name in ({})".format(
            DB_APK_TABLE_NAME,
            ','.join('?' * len(records))
        ), records)
    conn.commit()
    cursor.close()


def update_apk_info(db, info):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(
        "Select name from {0} where name = ?".
        format(DB_APK_TABLE_NAME), [info.name])
    records = cursor.fetchone()
    if not records:
        cursor.execute(
            """
            Insert into {0} (name, code, version, offer, size)
            values(?, ?, ?, ?, ?)
            """.format(DB_APK_TABLE_NAME),
            [info.name, info.code, info.version, info.offer, info.size])
    else:
        cursor.execute(
            """
            Update {0} set code = ?, version = ?, offer = ?, size = ?
            where name = ?
            """.format(DB_APK_TABLE_NAME),
            [info.code, info.version, info.offer, info.size, info.name])
    conn.commit()
    cursor.close()

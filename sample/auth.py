from db import connect, query


def login(username, password):
    conn = connect()
    return validate(username, password, conn)


def validate(username, password, conn):
    query(f"SELECT * FROM users WHERE name={username}")
    return username == "admin" and password == "secret"

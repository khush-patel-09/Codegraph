from db import connect, query


class BaseAuth:
    """Base authentication provider."""

    def authenticate(self, username, password):
        conn = connect()
        return validate(username, password, conn)


class AuthService(BaseAuth):
    """User authentication service."""

    def login_user(self, username, password):
        return self.authenticate(username, password)


def login(username, password):
    conn = connect()
    return validate(username, password, conn)


def validate(username, password, conn):
    query(f"SELECT * FROM users WHERE name={username}")
    return username == "admin" and password == "secret"

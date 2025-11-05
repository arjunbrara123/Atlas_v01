# auth/auth_service.py

from typing import Optional


class AuthResult:
    def __init__(self, authenticated: bool, user: Optional[str], role: Optional[str], error: Optional[str] = None):
        self.authenticated = authenticated
        self.user = user
        self.role = role
        self.error = error


class AuthService:
    """
    The idea: main_app only talks to AuthService.
    Today we back it with a simple local username/password file.
    Later we swap it to corporate SSO, but keep the same interface.
    """

    def __init__(self, mode="local"):
        self.mode = mode
        # 'local' -> check static dict
        # 'sso'   -> call corporate SSO (future)

    def login(self, username: str, password: str) -> AuthResult:
        if self.mode == "local":
            from .users_local import USERS
            if username in USERS and USERS[username]["password"] == password:
                return AuthResult(
                    authenticated=True,
                    user=username,
                    role=USERS[username]["role"]
                )
            else:
                return AuthResult(
                    authenticated=False,
                    user=None,
                    role=None,
                    error="Invalid credentials"
                )

        elif self.mode == "sso":
            # future: talk to corporate SSO / JWT / headers
            # for now we just stub it
            return AuthResult(
                authenticated=False,
                user=None,
                role=None,
                error="SSO mode not implemented yet"
            )

        else:
            return AuthResult(
                authenticated=False,
                user=None,
                role=None,
                error=f"Unknown auth mode {self.mode}"
            )

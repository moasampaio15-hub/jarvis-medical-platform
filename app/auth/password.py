from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=True
)


class PasswordValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_password_strength(password: str) -> None:
    errors: list[str] = []

    if len(password) < 8:
        errors.append("A senha deve ter pelo menos 8 caracteres.")
    if len(password.encode("utf-8")) > 72:
        errors.append("A senha deve ter no máximo 72 bytes para compatibilidade com bcrypt.")
    if not any(character.islower() for character in password):
        errors.append("A senha deve conter pelo menos uma letra minúscula.")
    if not any(character.isupper() for character in password):
        errors.append("A senha deve conter pelo menos uma letra maiúscula.")
    if not any(character.isdigit() for character in password):
        errors.append("A senha deve conter pelo menos um número.")
    if not any(not character.isalnum() for character in password):
        errors.append("A senha deve conter pelo menos um caractere especial.")

    if errors:
        raise PasswordValidationError(errors)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

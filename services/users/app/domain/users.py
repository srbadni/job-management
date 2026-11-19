from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from email_validator import EmailNotValidError, validate_email


class InvalidEmail(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    email: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        try:
            # Syntax only: creating a User never performs DNS/network requests.
            address = validate_email(
                self.email.strip(),
                check_deliverability=False,
                allow_smtputf8=False,
            ).ascii_email
        except EmailNotValidError as exc:
            raise InvalidEmail("Invalid email address") from exc
        if address is None:
            raise InvalidEmail("Invalid email address")
        # Product policy: identity by email is case insensitive, including local part.
        object.__setattr__(self, "email", address.lower())

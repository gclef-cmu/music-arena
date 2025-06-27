import logging
from typing import Optional

from .dataclass import Battle, Session, User


def get_battle_logger(
    name: str = "",
    session: Optional[Session | str] = None,
    user: Optional[User | str] = None,
    battle: Optional[Battle | str] = None,
):
    components = []
    if session is not None:
        if isinstance(session, Session):
            session = session.uuid
        components.append(f"S-{session[:8]}")
    if user is not None:
        if isinstance(user, User):
            user = user.checksum
        components.append(f"U-{user[:8]}")
    if battle is not None:
        if isinstance(battle, Battle):
            battle = battle.uuid
        components.append(f"B-{battle[:8]}")
    components.append(name)
    return logging.getLogger(":".join(components))

from app.repositories.base_repository import BaseRepository
from app.models.user import User

class UserRepository(BaseRepository):
    def create_user(self, username: str, password_hash: str) -> User:
        user = User(username=username, password_hash=password_hash)
        self.add(user)
        self.commit()
        return user

    def get_by_username(self, username: str) -> User:
        return self.session.query(User).filter(
            User.username == username,
            User.deleted_at.is_(None)
        ).first()

    def get_by_id(self, user_id: int) -> User:
        return self.session.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None)
        ).first()

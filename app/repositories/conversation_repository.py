import datetime
from app.repositories.base_repository import BaseRepository
from app.models.conversation import Conversation

class ConversationRepository(BaseRepository):
    def create_conversation(self, user_id: int, title: str, mode: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, mode=mode)
        self.add(conversation)
        self.commit()
        return conversation

    def get_user_conversations(self, user_id: int):
        return self.session.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None)
        ).order_by(Conversation.updated_at.desc()).all()

    def get_conversation(self, conversation_id: int, user_id: int) -> Conversation:
        return self.session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None)
        ).first()

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        conv = self.get_conversation(conversation_id, user_id)
        if conv:
            conv.soft_delete()
            # Also soft delete its messages!
            for msg in conv.messages:
                msg.soft_delete()
            self.commit()
            return True
        return False

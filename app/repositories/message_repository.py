import datetime
from sqlalchemy import desc
from app.repositories.base_repository import BaseRepository
from app.models.message import ChatMessage
from app.models.conversation import Conversation

class MessageRepository(BaseRepository):
    def add_message(self, conversation_id: int, role: str, content: str, tokens: int) -> ChatMessage:
        msg = ChatMessage(conversation_id=conversation_id, role=role, content=content, tokens=tokens)
        self.add(msg)
        
        # Update conversation updated_at timestamp
        conv = self.session.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            conv.updated_at = datetime.datetime.utcnow()
            
        self.commit()
        return msg

    def get_messages(self, conversation_id: int, limit: int = None):
        if limit:
            # Get latest limit messages, then sort ASC
            sub_query = self.session.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.deleted_at.is_(None)
            ).order_by(desc(ChatMessage.timestamp)).limit(limit).all()
            # Reverse order to be chronological
            return sorted(sub_query, key=lambda x: x.timestamp)
        else:
            return self.session.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.deleted_at.is_(None)
            ).order_by(ChatMessage.timestamp).all()

    def clear_conversation_messages(self, conversation_id: int) -> bool:
        messages = self.session.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.deleted_at.is_(None)
        ).all()
        for msg in messages:
            msg.soft_delete()
        self.commit()
        return True

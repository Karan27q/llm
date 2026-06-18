from typing import List, Optional
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.audit_service import AuditService
from app.models.conversation import Conversation
from app.models.message import ChatMessage

class ChatService:
    def __init__(self):
        self.conv_repo = ConversationRepository()
        self.msg_repo = MessageRepository()
        self.audit_service = AuditService()

    def get_user_conversations(self, user_id: int) -> List[Conversation]:
        return self.conv_repo.get_user_conversations(user_id)

    def create_conversation(self, user_id: int, title: str, mode: str, ip_address: str) -> Conversation:
        conv = self.conv_repo.create_conversation(user_id, title, mode)
        self.audit_service.log_event(
            user_id=user_id,
            action="CREATE_CONVERSATION",
            ip_address=ip_address,
            details=f"Created conversation {conv.id} with mode '{mode}'"
        )
        return conv

    def get_conversation(self, conversation_id: int, user_id: int) -> Optional[Conversation]:
        return self.conv_repo.get_conversation(conversation_id, user_id)

    def delete_conversation(self, conversation_id: int, user_id: int, ip_address: str) -> bool:
        success = self.conv_repo.delete_conversation(conversation_id, user_id)
        if success:
            self.audit_service.log_event(
                user_id=user_id,
                action="DELETE_CONVERSATION",
                ip_address=ip_address,
                details=f"Soft-deleted conversation {conversation_id}"
            )
        return success

    def get_messages(self, conversation_id: int, user_id: int, limit: Optional[int] = None) -> Optional[List[ChatMessage]]:
        # Verify ownership first
        conv = self.conv_repo.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        return self.msg_repo.get_messages(conversation_id, limit)

    def add_message(self, conversation_id: int, user_id: int, role: str, content: str, tokens: int) -> Optional[ChatMessage]:
        # Verify ownership first
        conv = self.conv_repo.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        return self.msg_repo.add_message(conversation_id, role, content, tokens)

    def clear_conversation_messages(self, conversation_id: int, user_id: int, ip_address: str) -> bool:
        conv = self.conv_repo.get_conversation(conversation_id, user_id)
        if not conv:
            return False
        success = self.msg_repo.clear_conversation_messages(conversation_id)
        if success:
            self.audit_service.log_event(
                user_id=user_id,
                action="CLEAR_CONVERSATION",
                ip_address=ip_address,
                details=f"Cleared all messages in conversation {conversation_id}"
            )
        return success

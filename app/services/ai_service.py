from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from app.config import Config
from app.repositories.message_repository import MessageRepository

class AIService:
    def __init__(self):
        api_key = Config.GOOGLE_GEMINI_API_KEY
        if not api_key:
            # Note: We fallback or raise when actual calls are made or at launch.
            # Raising here helps catch env issues early.
            raise ValueError("GOOGLE_GEMINI_API_KEY not found in configuration.")
            
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7
        )
        self.msg_repo = MessageRepository()
        
        self.prompt_templates = {
            "assistant": ChatPromptTemplate.from_messages([
                ("system", "You are a helpful, harmless, and honest AI assistant. Your goal is to provide accurate and useful information to the user."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]),
            "tutor": ChatPromptTemplate.from_messages([
                ("system", "You are an expert tutor. Explain concepts clearly and simply, using analogies when helpful. Verify the user's understanding by asking follow-up questions."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]),
            "code_expert": ChatPromptTemplate.from_messages([
                ("system", "You are a senior software engineer. Provide efficient, clean, and well-documented code. Explain your logic and potential trade-offs. Always prefer modern best practices."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]),
            "creative": ChatPromptTemplate.from_messages([
                ("system", "You are a creative writer and storyteller. Be imaginative, descriptive, and engaging. Feel free to use metaphors and vivid imagery."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
        }

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def get_langchain_history(self, conversation_id: int, user_msg: str):
        db_messages = self.msg_repo.get_messages(conversation_id, limit=20)
        history = []
        for msg in db_messages:
            role = msg.role
            content = msg.content
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "model":
                history.append(AIMessage(content=content))
                
        # Exclude the message we just added (if get_messages includes it).
        if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_msg:
            history = history[:-1]
            
        return history

    def get_modes(self):
        return {
            key: {"name": key.replace('_', ' ').title()}
            for key in self.prompt_templates.keys()
        }

    def get_chain(self, mode: str):
        prompt = self.prompt_templates.get(mode, self.prompt_templates["assistant"])
        return prompt | self.llm | StrOutputParser()

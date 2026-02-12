# AI Chatbot with Persistent Memory

A modern, full-stack AI chatbot application featuring persistent memory, multiple personas (Assistant, Code Expert, Tutor, Creative), and a sleek, responsive UI. Built with Flask, SQLite, and Google Gemini API.

## � Features

- **Persistent Conversations**: Histories are saved indefinitely in a local SQLite database. By default, it uses `gemini-1.5-flash` for high speed and low latency.
- **Multi-Persona System**: Switch specialized modes:
  - 🤖 **Assistant**: General helpful AI.
  - 💻 **Code Expert**: Specialized in programming and debugging.
  - 🎓 **Tutor**: For learning and educational explanations.
  - ✨ **Creative**: For brainstorming and storytelling.
- **Streaming Responses**: Real-time typing effect using Server-Sent Events (SSE).
- **Rich Text Support**: Full Markdown rendering and Syntax Highlighting for code.
- **User System**: Secure Authentication (Signup/Login) with hashed passwords.
- **Modern UI**: Dark-themed, glassmorphism design that is fully responsive.

## 🛠️ Tech Stack

- **Backend**: Python (Flask)
- **Database**: SQLite (managed via `db.py` context managers)
- **AI Model**: Google Gemini (`gemini-1.5-flash`)
- **Frontend**: HTML5, CSS3 (Glassmorphism), Vanilla JS
- **Dependencies**: `flask`, `google-generativeai`, `python-dotenv`

## � Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd llm_chatbot
   ```

2. **Create a virtual environment**:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Mac/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install flask google-generativeai python-dotenv
   ```

4. **Setup Environment**:
   Create a `.env` file in the root directory:
   ```ini
   SECRET_KEY=your_secret_key_here
   GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here
   ```
   *Get your API key from [Google AI Studio](https://aistudio.google.com/).*

## ▶️ Usage

1. **Run the application**:
   ```bash
   python app.py
   ```
2. **Open your browser**:
   Navigate to `http://localhost:5000`

3. **Get Started**:
   - Sign up for an account.
   - Choose a mode from the Dashboard.
   - Start chatting!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

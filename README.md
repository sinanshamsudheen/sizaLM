# Telegram PDF Bot

A modular FastAPI project that integrates with Telegram to process PDF documents and answer questions using LLMs (Groq's LLaMA3 or Cohere).

## 📋 Features

- **Telegram Integration**: Process messages using the Telegram Bot API
- **PDF Processing**: Extract text from uploaded PDF documents
- **Question Analysis**: Extract important questions from user messages
- **LLM Integration**: Generate detailed responses using Groq's LLaMA3 or Cohere
- **Customizable Responses**: Format responses with configurable templates

## 🔧 Project Structure

```
projectSIZA/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── telegram.py    # Telegram bot routes
│   │   ├── api.py             # API router configuration
│   │   └── __init__.py
│   ├── models/
│   │   ├── schemas.py         # Pydantic models
│   │   └── __init__.py
│   ├── app.py                 # FastAPI application factory
│   └── __init__.py
├── config/
│   ├── settings.py            # Application settings
│   ├── response_template.py   # Response formatting templates
│   └── __init__.py
├── services/
│   ├── llm_handler.py         # LLM integration (Groq/Cohere)
│   ├── whatsapp_handler.py    # WhatsApp API integration
│   └── __init__.py
├── utils/
│   ├── logging.py             # Async logging utilities
│   ├── pdf_handler.py         # PDF processing utilities
│   └── __init__.py
├── uploads/                   # Temporary PDF storage
├── .env                       # Environment variables
├── requirements.txt           # Project dependencies
└── main.py                    # Application entry point
```

## 🚀 Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd projectSIZA
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the `.env` file with your API keys and settings:
   ```
   # LLM API Keys
   GROQ_API_KEY=your-groq-api-key
   COHERE_API_KEY=your-cohere-api-key

   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your-telegram-bot-token  # Get from BotFather

   # LLM Configuration
   LLM_PROVIDER=GROQ  # GROQ or COHERE
   GROQ_MODEL=llama3-70b-8192
   COHERE_MODEL=command-light

   # App Configuration
   DEBUG=True
   LOG_LEVEL=INFO
   APP_PORT=8000
   APP_HOST=0.0.0.0
   ```

## 🏃‍♂️ Running the Application

1. Start the server:
   ```bash
   python main.py
   ```

2. The API will be available at `http://localhost:8000`
   - API documentation: `http://localhost:8000/docs` (when DEBUG=True)
   - Telegram endpoints: 
     - Webhook: `http://localhost:8000/api/telegram/webhook`
     - Start Polling: `http://localhost:8000/api/telegram/start-polling`
     - Send Message: `http://localhost:8000/api/telegram/send-message`
     - Process PDF: `http://localhost:8000/api/telegram/process-pdf`

## 📝 Usage

### Telegram Bot Setup

1. Create a Telegram bot using BotFather:
   - Open Telegram and search for `@BotFather`
   - Send the command `/newbot`
   - Follow the instructions to create a bot
   - Copy the bot token provided by BotFather

2. Add the bot token to your `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
   ```

3. Choose how to run your bot:

   **Option 1: Using Webhook** (requires public server)
   - Set up a public HTTPS endpoint for your server
   - Configure the webhook with Telegram: 
     ```
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-server.com/api/telegram/webhook
     ```

   **Option 2: Using Polling** (works on local development)
   - Start polling by visiting `/api/telegram/start-polling` endpoint
   - The server will periodically check for new messages

4. Interact with your bot:
   - Start a chat with your bot on Telegram
   - Send the `/start` command to get started
   - Send PDF documents and questions about them

### API Testing

```bash
# Process a PDF and send results to a Telegram chat
curl -X POST http://localhost:8000/api/telegram/process-pdf \
  -H "Content-Type: multipart/form-data" \
  -F "pdf_file=@/path/to/your/document.pdf" \
  -F "questions=What is quantum computing?
How does machine learning work?
What are the ethical implications of AI?" \
  -F "chat_id=your-telegram-chat-id"

# Send a Telegram message directly
curl -X POST http://localhost:8000/api/telegram/send-message \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "chat_id=your-telegram-chat-id&message=Hello from PDF Bot!" \
  -d "phone=+1234567890&message=Hello from WhatsApp PDF Bot!"
```

### Meta/UltraMsg WhatsApp Integration (Alternative)

1. Set up a webhook in your WhatsApp API provider (Meta Cloud API or UltraMsg)
2. Point the webhook to your deployed API endpoint
3. Verify the webhook using the verification token in your `.env` file
4. Users can now interact with the bot through WhatsApp:
   - Send questions as text messages
   - Upload PDF documents
   - Receive structured answers based on the PDF content

## ⚙️ Configuration

### Response Templates

Customize the format of responses in `config/response_template.py`:

- Section titles and separators
- Question formatting
- Detailed (10-mark) answer formatting
- Concise (4-mark) bullet point formatting
- Emphasis and styling markers

### LLM Providers

Choose between:
- **Groq's LLaMA3**: Faster responses with state-of-the-art LLaMA models
- **Cohere**: Alternative option with command-light or command-r models

## 🔒 Security Notes

- Webhook endpoints should be secured with HTTPS in production
- API keys should be kept confidential and not committed to version control
- Consider adding rate limiting for production deployments

## 📄 License

[MIT License](LICENSE)

## ✨ Acknowledgements

- FastAPI: https://fastapi.tiangolo.com/
- Groq: https://groq.com/
- Cohere: https://cohere.com/
- Telegram Bot API: https://core.telegram.org/bots/api
- PyMuPDF: https://pymupdf.readthedocs.io/

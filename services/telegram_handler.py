"""
Telegram bot service for handling interactions with the Telegram API.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional, Union, BinaryIO
import httpx
from io import BytesIO
from pathlib import Path
import uuid

from config.settings import settings
from utils.logging import app_logger, async_logger
from utils.pdf_handler import PDFHandler
from services.llm_handler import LLMHandler
from config.response_template import ResponseTemplate


class TelegramHandler:
    """Service for handling Telegram bot interactions."""
    
    def __init__(self):
        """Initialize the Telegram handler with configuration."""
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.file_url = f"https://api.telegram.org/file/bot{self.token}"
        self.pdf_handler = PDFHandler()
        self.llm_handler = LLMHandler()
        # Initialize storage for user PDF data
        self._user_pdf_data = {}
    
    async def send_message(self, chat_id: Union[str, int], text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """
        Send a text message via Telegram.
        
        Args:
            chat_id: Chat ID to send the message to
            text: Message content to send
            parse_mode: Message parsing mode (HTML or Markdown)
            
        Returns:
            Response from the Telegram API
        """
        try:
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                await async_logger.info(f"Message sent to Telegram chat {chat_id}")
                return response.json()
                
        except Exception as e:
            await async_logger.error(f"Error sending Telegram message: {str(e)}")
            raise
    
    async def download_document(self, file_id: str) -> bytes:
        """
        Download a document from Telegram.
        
        Args:
            file_id: ID of the file to download
            
        Returns:
            Binary content of the file
        """
        try:
            # First, get the file path
            url = f"{self.base_url}/getFile"
            params = {"file_id": file_id}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                file_path = response.json()["result"]["file_path"]
                
                # Now download the file
                download_url = f"{self.file_url}/{file_path}"
                download_response = await client.get(download_url)
                download_response.raise_for_status()
                
                await async_logger.info(f"File downloaded from Telegram: {file_id}")
                return download_response.content
                
        except Exception as e:
            await async_logger.error(f"Error downloading file from Telegram: {str(e)}")
            raise
    
    async def handle_update(self, update: Dict[str, Any]) -> None:
        """
        Handle an update from Telegram.
        
        Args:
            update: Update data from Telegram webhook
        """
        try:
            # Make sure storage is initialized
            if not hasattr(self, '_user_pdf_data'):
                self._user_pdf_data = {}
                await async_logger.info("Initialized user PDF data storage in handle_update")
            
            # Log the received update (with sensitive data redacted)
            update_id = update.get("update_id", "unknown")
            await async_logger.info(f"Processing update ID: {update_id}")
            await async_logger.debug(f"Raw update: {update}")
            
            # Check if it's a message
            if "message" not in update:
                await async_logger.warning(f"Update {update_id} does not contain a message field")
                return
            
            message = update["message"]
            chat_id = message["chat"]["id"]
            username = message["chat"].get("username", "unknown")
            
            await async_logger.info(f"Received message from chat_id={chat_id}, username=@{username}")
            
            # Handle document (PDF)
            if "document" in message:
                document = message["document"]
                mime_type = document.get("mime_type", "")
                file_name = document.get("file_name", "unknown")
                file_id = document.get("file_id", "unknown")
                
                await async_logger.info(f"Received document: {file_name}, mime_type: {mime_type}, file_id: {file_id}")
                
                # Some PDFs may have different mime types
                if mime_type == "application/pdf" or file_name.lower().endswith('.pdf'):
                    await async_logger.info(f"Processing PDF document: {file_name}")
                    await self.handle_pdf_document(chat_id, document)
                else:
                    await async_logger.warning(f"Received non-PDF document: {mime_type}")
                    await self.send_message(
                        chat_id,
                        f"I can only process PDF documents. The file you sent appears to be {mime_type}. Please send a PDF file."
                    )
                    
            # Handle text message (questions)
            elif "text" in message:
                text = message["text"]
                await async_logger.info(f"Received text message: {text[:20]}...")
                
                # Check for commands
                if text.startswith("/"):
                    await self.handle_command(chat_id, text)
                else:
                    await self.handle_text_message(chat_id, text)
            
            # Handle other message types
            else:
                await async_logger.info(f"Received unsupported message type: {message.keys()}")
                await self.send_message(
                    chat_id,
                    "I can only process text messages and PDF documents. Please send a PDF file or a question about a PDF you've already sent."
                )
                    
        except Exception as e:
            await async_logger.error(f"Error handling Telegram update: {str(e)}")
            
            try:
                # Try to notify the user of the error
                await self.send_message(
                    chat_id,
                    "Sorry, I encountered an error while processing your message. Please try again."
                )
            except:
                pass
    
    async def handle_command(self, chat_id: Union[str, int], command: str) -> None:
        """
        Handle a command from a Telegram user.
        
        Args:
            chat_id: Chat ID to respond to
            command: Command text
        """
        if command == "/start" or command == "/help":
            help_text = (
                "👋 <b>Welcome to PDF Q&A Bot!</b>\n\n"
                "I can help you analyze PDF documents and answer questions about their content.\n\n"
                "<b>How to use me:</b>\n"
                "1. Send me a PDF document 📄\n"
                "2. Send me questions about the document 🤔\n\n"
                "I'll extract information from the PDF and provide detailed answers to your questions."
            )
            await self.send_message(chat_id, help_text)
        else:
            await self.send_message(
                chat_id, 
                "I don't recognize that command. Send /help to see what I can do."
            )
    
    async def handle_pdf_document(self, chat_id: Union[str, int], document: Dict[str, Any]) -> None:
        """
        Handle a PDF document sent by a Telegram user.
        
        Args:
            chat_id: Chat ID to respond to
            document: Document data
        """
        try:
            # Make sure storage is initialized
            if not hasattr(self, '_user_pdf_data'):
                self._user_pdf_data = {}
                
            # Send acknowledgment
            await self.send_message(
                chat_id,
                "I've received your PDF. Processing now... 🔍"
            )
            
            # Download the document
            file_id = document["file_id"]
            file_name = document.get("file_name", f"{uuid.uuid4()}.pdf")
            
            await async_logger.info(f"Downloading document with file_id={file_id}, file_name={file_name}, chat_id={chat_id}")
            
            try:
                file_content = await self.download_document(file_id)
                await async_logger.info(f"Downloaded PDF content: {len(file_content)} bytes")
            except Exception as e:
                await async_logger.error(f"Error downloading PDF: {str(e)}")
                await self.send_message(
                    chat_id,
                    "I had trouble downloading your PDF. Please try sending it again."
                )
                return
            
            # Ensure upload directory exists
            import os
            from config.settings import settings
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            # Save the PDF temporarily
            await async_logger.info(f"Saving PDF to disk: {file_name} in {settings.UPLOAD_DIR}")
            filepath = await self.pdf_handler.save_pdf(file_content, file_name)
            
            # Extract text from PDF
            await async_logger.info(f"Extracting text from PDF: {filepath}")
            pdf_text = await self.pdf_handler.extract_text(filepath)
            await async_logger.info(f"Extracted {len(pdf_text)} characters from PDF")
            
            # Store the PDF text for this user (in-memory for this example)
            # In a real app, you'd want to use a database for this
            self._user_pdf_data[chat_id] = pdf_text
            await async_logger.info(f"Stored PDF text for chat_id {chat_id}")
            
            # Let the user know it's ready
            await self.send_message(
                chat_id,
                f"✅ PDF processed successfully!\n\nNow you can ask me questions about the content of <b>{file_name}</b>."
            )
            
            # Clean up the PDF
            await self.pdf_handler.cleanup_pdf(filepath)
            await async_logger.info(f"Cleaned up PDF file: {filepath}")
            
        except Exception as e:
            await async_logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
            
            await self.send_message(
                chat_id,
                "Sorry, I encountered an error while processing your PDF. Please try again."
            )
    
    async def handle_text_message(self, chat_id: Union[str, int], text: str) -> None:
        """
        Handle a text message from a Telegram user.
        
        Args:
            chat_id: Chat ID to respond to
            text: Message text
        """
        # Check if the user has uploaded a PDF first
        if chat_id not in self._user_pdf_data:
            await self.send_message(
                chat_id,
                "Please send me a PDF document first, and then I can answer questions about it."
            )
            return
        
        try:
            # Send acknowledgment
            await self.send_message(
                chat_id,
                "Processing your questions... 🧠"
            )
            
            # Parse questions from the message
            pdf_text = self._user_pdf_data[chat_id]
            important_questions = [text]  # Use the entire message as an important question
            other_topics = []
            
            # Generate response using LLM
            result = await self.llm_handler.generate_response(
                pdf_text, 
                important_questions,
                other_topics
            )
            
            # Format the response using the template
            formatted_response = ResponseTemplate.format_response(
                result["important_questions"], 
                result["other_topics"]
            )
            
            # Send the response
            # Split long messages if needed (Telegram has a 4096 character limit)
            if len(formatted_response) > 4000:
                chunks = [formatted_response[i:i+4000] for i in range(0, len(formatted_response), 4000)]
                for chunk in chunks:
                    await self.send_message(chat_id, chunk)
            else:
                await self.send_message(chat_id, formatted_response)
                
        except Exception as e:
            await async_logger.error(f"Error handling text message: {str(e)}")
            
            await self.send_message(
                chat_id,
                "Sorry, I encountered an error while processing your questions. Please try again."
            )
    
    async def start_polling(self, timeout: int = 30) -> None:
        """
        Start polling for updates from Telegram.
        
        Args:
            timeout: Timeout for long polling in seconds
        """
        # Make sure we have the storage initialized
        if not hasattr(self, '_user_pdf_data'):
            self._user_pdf_data = {}
            await async_logger.info("Initialized user PDF data storage")
        
        # Ensure upload directory exists
        import os
        from config.settings import settings
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        await async_logger.info(f"Ensured upload directory exists: {settings.UPLOAD_DIR}")
        
        # Log that we're starting polling
        await async_logger.info(f"Starting Telegram bot polling with token: {self.token[:5]}...{self.token[-5:]}")
        
        # Send a test message to the Telegram API to verify the token
        try:
            me = await self._get_me()
            await async_logger.info(f"Bot connected successfully: @{me.get('username', 'unknown')}")
            await async_logger.info(f"Bot details: {me}")
        except Exception as e:
            await async_logger.error(f"Failed to verify bot token: {str(e)}")
            await async_logger.error("Telegram bot initialization failed! Please check your token.")
            return
        
        last_update_id = 0
        
        while True:
            try:
                await async_logger.debug(f"Polling for updates, last_update_id={last_update_id}")
                updates = await self._get_updates(last_update_id, timeout)
                
                if updates:
                    await async_logger.info(f"Received {len(updates)} updates from Telegram")
                
                for update in updates:
                    try:
                        await self.handle_update(update)
                    except Exception as e:
                        await async_logger.error(f"Error handling update: {str(e)}")
                    
                    # Update the last processed update ID
                    last_update_id = max(last_update_id, update["update_id"] + 1)
                    
            except asyncio.CancelledError:
                await async_logger.info("Polling cancelled, shutting down bot")
                break
            except Exception as e:
                await async_logger.error(f"Error polling updates: {str(e)}")
                # Wait a bit before retrying
                await asyncio.sleep(5)
    
    async def _get_me(self) -> Dict[str, Any]:
        """Get information about the bot."""
        url = f"{self.base_url}/getMe"
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()
            return result.get("result", {})
    
    async def _get_updates(self, offset: int = 0, timeout: int = 30) -> List[Dict[str, Any]]:
        """
        Get updates from Telegram using long polling.
        
        Args:
            offset: Update ID to start from
            timeout: Timeout for long polling in seconds
            
        Returns:
            List of updates
        """
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message"]
        }
        
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            result = response.json()
            return result.get("result", [])

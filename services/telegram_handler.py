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
        # Initialize user state tracking
        self._user_states = {}
        # Initialize important topics by user
        self._important_topics = {}
    
    async def send_message(self, chat_id: Union[str, int], text: str, parse_mode: str = "HTML", 
                   keyboard: Optional[List[List[Dict[str, str]]]] = None) -> Dict[str, Any]:
        """
        Send a text message via Telegram.
        
        Args:
            chat_id: Chat ID to send the message to
            text: Message content to send
            parse_mode: Message parsing mode (HTML or Markdown)
            keyboard: Optional keyboard buttons
            
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
            
            if keyboard:
                reply_markup = {
                    "keyboard": keyboard,
                    "one_time_keyboard": True,
                    "resize_keyboard": True
                }
                payload["reply_markup"] = reply_markup
            
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
        if command == "/start":
            # Reset user state
            self._user_states[chat_id] = "awaiting_document"
            
            welcome_text = (
                "👋 <b>Hello there! I'm SizaLM!</b>\n\n"
                "I can help you analyze PDF documents, answer questions, and create summaries.\n\n"
                "<b>Please send your documents!</b> 📄\n\n"
                "After processing, I can:\n"
                "• Answer specific questions about the content\n"
                "• Create a comprehensive summary of the document\n"
                "• Focus on important topics you specify"
            )
            await self.send_message(chat_id, welcome_text)
        elif command == "/help":
            help_text = (
                "👋 <b>Hello there! I'm SizaLM!</b>\n\n"
                "I can help you analyze PDF documents and summarize their content.\n\n"
                "<b>How to use me:</b>\n"
                "1. Send me a PDF document 📄\n"
                "2. Choose either Q&A or Summarize mode\n"
                "3. For Q&A: Ask me questions about the document 🤔\n"
                "4. For Summarize: Optionally provide important topics to focus on\n\n"
                "I'll extract information from the PDF and provide detailed answers or summaries."
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
            
            # Get PDF metadata first
            await async_logger.info(f"Getting PDF metadata: {filepath}")
            pdf_metadata = await self.pdf_handler.get_pdf_metadata(filepath)
            total_pages = pdf_metadata["total_pages"]
            file_size_mb = pdf_metadata["file_size_mb"]
            await async_logger.info(f"PDF metadata: {total_pages} pages, {file_size_mb:.2f} MB")
            
            # Choose extraction method based on document size
            if total_pages > 100:
                # For large documents, use chunked processing
                await self.send_message(
                    chat_id,
                    f"This is a large document ({total_pages} pages, {file_size_mb:.2f} MB). Processing in chunks for better results..."
                )
                
                # Extract text in chunks
                pdf_chunks = await self.pdf_handler.extract_text_chunked(filepath)
                await async_logger.info(f"Extracted {len(pdf_chunks)} chunks from PDF")
                
                # Store chunked data for this user
                self._user_pdf_data[chat_id] = {
                    "type": "chunked",
                    "chunks": pdf_chunks,
                    "metadata": pdf_metadata
                }
                await async_logger.info(f"Stored chunked PDF data for chat_id {chat_id}")
            else:
                # For smaller documents, use normal processing
                await async_logger.info(f"Extracting text from PDF: {filepath}")
                pdf_text = await self.pdf_handler.extract_text(filepath)
                await async_logger.info(f"Extracted {len(pdf_text)} characters from PDF")
                
                # Store the PDF text for this user
                self._user_pdf_data[chat_id] = {
                    "type": "full",
                    "text": pdf_text,
                    "metadata": pdf_metadata
                }
                await async_logger.info(f"Stored full PDF text for chat_id {chat_id}")
            
            # Let the user know it's ready and provide options
            self._user_states[chat_id] = "awaiting_mode_selection"
            options_text = (
                f"✅ PDF processed successfully!\n\n"
                f"<b>Document:</b> {file_name}\n\n"
                f"Please select what you'd like to do with this document:"
            )
            
            # Create keyboard with options
            keyboard = [
                [{"text": "1️⃣ Q&A - Ask questions about the document"}],
                [{"text": "2️⃣ Summarize - Generate a summary of the document"}]
            ]
            
            await self.send_message(chat_id, options_text, keyboard=keyboard)
            
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
                "Please send me a PDF document first by using the /start command."
            )
            return
        
        # Get user's current state
        user_state = self._user_states.get(chat_id, "awaiting_document")
        
        try:
            # Handle different states
            if user_state == "awaiting_mode_selection":
                # User is selecting between Q&A and Summarize
                if text == "1" or text.lower() == "q&a":
                    self._user_states[chat_id] = "qa_mode"
                    await self.send_message(
                        chat_id,
                        "You've selected <b>Q&A mode</b>. Please ask me any questions about the document."
                    )
                elif text == "2" or text.lower() == "summarize":
                    self._user_states[chat_id] = "awaiting_important_topics"
                    await self.send_message(
                        chat_id,
                        "You've selected <b>Summarize mode</b>.\n\n"
                        "I'll create a structured, exam-friendly summary with:\n"
                        "• Major topics in bold headings\n"
                        "• Subheadings for related subtopics\n"
                        "• Bullet points with concise explanations\n"
                        "• Key terms highlighted for easy revision\n\n"
                        "Please enter a list of important topics to focus on in detail (8-mark level), with each topic on a new line.\n\n"
                        "If you don't have any specific topics, just type 'proceed'."
                    )
                else:
                    await self.send_message(
                        chat_id,
                        "Please select either:\n"
                        "1️⃣ for Q&A mode\n"
                        "2️⃣ for Summarize mode"
                    )
            
            elif user_state == "awaiting_important_topics":
                # User is providing important topics for summarization
                if text.lower() == "proceed":
                    important_topics = []
                    await self.send_message(
                        chat_id,
                        "No specific important topics provided. I'll create a balanced summary of all topics in the document."
                    )
                else:
                    important_topics = [t.strip() for t in text.split('\n') if t.strip()]
                    topics_list = "\n".join([f"• {topic}" for topic in important_topics])
                    await self.send_message(
                        chat_id,
                        f"I'll focus on these important topics in the summary:\n\n{topics_list}"
                    )
                
                # Store the important topics and proceed to summarization
                self._important_topics[chat_id] = important_topics
                await self.generate_summary(chat_id)
            
            elif user_state == "qa_mode":
                # User is asking questions in Q&A mode
                await self.send_message(
                    chat_id,
                    "Processing your question... 🧠"
                )
                
                pdf_data = self._user_pdf_data[chat_id]
                important_questions = [text]  # Use the entire message as an important question
                other_topics = []
                
                # Generate response using LLM based on data type
                if pdf_data["type"] == "chunked":
                    # For chunked data, we need a different approach
                    await self.send_message(
                        chat_id,
                        "For large documents, I'll search through all sections to find relevant information..."
                    )
                    
                    # Combine all chunks into a single response
                    all_results = {"important_questions": {}, "other_topics": {}}
                    chunks = pdf_data["chunks"]
                    
                    # Process chunks in batches to avoid memory issues
                    batch_size = min(3, len(chunks))  # Process up to 3 chunks at a time
                    
                    for i in range(0, len(chunks), batch_size):
                        batch_chunks = chunks[i:i+batch_size]
                        for chunk in batch_chunks:
                            chunk_text = chunk["text"]
                            chunk_range = f"(pages {chunk['start_page']}-{chunk['end_page']})"
                            
                            # Process this chunk
                            chunk_result = await self.llm_handler.generate_response(
                                chunk_text,
                                important_questions,
                                other_topics
                            )
                            
                            # Add page range information to answers
                            for q, a in chunk_result["important_questions"].items():
                                if a and not a.startswith("I couldn't generate"):
                                    if q not in all_results["important_questions"]:
                                        all_results["important_questions"][q] = f"{chunk_range}: {a}"
                                    else:
                                        all_results["important_questions"][q] += f"\n\n{chunk_range}: {a}"
                    
                    result = all_results
                else:
                    # For full text, use the standard approach
                    pdf_text = pdf_data["text"]
                    
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
                
                # Send the response, splitting if needed
                if len(formatted_response) > 4000:
                    chunks = [formatted_response[i:i+4000] for i in range(0, len(formatted_response), 4000)]
                    for chunk in chunks:
                        await self.send_message(chat_id, chunk)
                else:
                    await self.send_message(chat_id, formatted_response)
            
            else:
                # Unknown state, reset to document upload
                self._user_states[chat_id] = "awaiting_document"
                await self.send_message(
                    chat_id,
                    "I'm not sure what to do next. Please send me a PDF document to start over."
                )
                
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
    
    async def generate_summary(self, chat_id: Union[str, int]) -> None:
        """
        Generate a summary of the document for a user.
        
        Args:
            chat_id: Chat ID to respond to
        """
        try:
            if chat_id not in self._user_pdf_data:
                await self.send_message(
                    chat_id,
                    "Please send me a PDF document first before requesting a summary."
                )
                return
                
            pdf_data = self._user_pdf_data[chat_id]
            important_topics = self._important_topics.get(chat_id, [])
            
            # Let the user know we're working on it
            await self.send_message(
                chat_id,
                "Generating summary of the document... 🧠\n\n"
                "This may take a moment depending on the size of the document."
            )
            
            # Generate summary using LLM based on data type
            await async_logger.info(f"Generating summary for chat_id={chat_id} with {len(important_topics)} important topics")
            
            summary_result = None
            
            if pdf_data["type"] == "chunked":
                # For chunked data, use the chunked summary method
                chunks = pdf_data["chunks"]
                metadata = pdf_data["metadata"]
                total_pages = metadata["total_pages"]
                
                await self.send_message(
                    chat_id,
                    f"Processing large document ({total_pages} pages) in chunks for comprehensive summary...\n"
                    f"This may take several minutes. I'll update you on the progress."
                )
                
                # Call our chunked summarization method
                summary_result = await self.llm_handler.generate_summary_from_chunks(chunks, important_topics)
                
            else:
                # For full text, use the standard summary method
                pdf_text = pdf_data["text"]
                
                # Call our standard summarization method
                summary_result = await self.llm_handler.generate_summary(pdf_text, important_topics)
            
            # Send the summary response
            await self.send_message(
                chat_id,
                "📝 <b>EXAM-READY DOCUMENT SUMMARY</b>\n\n"
                "Here is your structured, exam-friendly summary with hierarchical organization:\n"
                "• Major topics appear as <b><u>UNDERLINED HEADINGS</u></b>\n"
                "• Subheadings organize related concepts\n"
                "• <b>Key terms</b> are highlighted for quick revision\n"
                "• Important topics you specified are explained in detail (8-mark level)\n"
                "• Other topics are summarized concisely (4-mark level)\n"
            )
            
            # Format the summary using the template
            from config.response_template import ResponseTemplate
            formatted_summary = ResponseTemplate.format_summary(summary_result)
            
            # Split long messages if needed (Telegram has a 4096 character limit)
            if len(formatted_summary) > 4000:
                chunks = [formatted_summary[i:i+4000] for i in range(0, len(formatted_summary), 4000)]
                for chunk in chunks:
                    await self.send_message(chat_id, chunk)
            else:
                await self.send_message(chat_id, formatted_summary)
                
            # Reset to Q&A mode after sending summary
            self._user_states[chat_id] = "qa_mode"
            await self.send_message(
                chat_id,
                "You can now ask me specific questions about the document, or send /start to process another document."
            )
                
        except Exception as e:
            await async_logger.error(f"Error generating summary: {str(e)}")
            await self.send_message(
                chat_id,
                "Sorry, I encountered an error while generating the summary. Please try again."
            )

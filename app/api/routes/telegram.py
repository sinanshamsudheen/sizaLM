"""
Telegram bot routes for handling webhook and messages.
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Dict, List, Optional, Any

from config.settings import settings
from services.telegram_handler import TelegramHandler
from utils.logging import async_logger

router = APIRouter()

# Create Telegram handler instance
telegram_handler = TelegramHandler()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Process incoming updates from Telegram.
    
    Args:
        request: HTTP request with Telegram update
        
    Returns:
        Empty response to acknowledge receipt
    """
    try:
        # Parse update data
        update = await request.json()
        await async_logger.info(f"Received Telegram update: {update}")
        
        # Process the update
        await telegram_handler.handle_update(update)
        
        # Acknowledge receipt
        return {}
        
    except Exception as e:
        await async_logger.error(f"Error processing Telegram update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-message")
async def send_message(chat_id: str = Form(...), message: str = Form(...)):
    """
    Send a message to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID
        message: Message content to send
        
    Returns:
        Status of message delivery
    """
    try:
        result = await telegram_handler.send_message(chat_id, message)
        return {"status": "success", "result": result}
    except Exception as e:
        await async_logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-pdf")
async def process_pdf(
    pdf_file: UploadFile = File(...),
    questions: str = Form(...),
    chat_id: str = Form(...)
):
    """
    Process a PDF file with questions and send the result to a Telegram chat.
    
    Args:
        pdf_file: PDF file to process
        questions: Questions to answer from the PDF
        chat_id: Telegram chat ID to send results to
        
    Returns:
        Status of processing and message delivery
    """
    try:
        # Read the PDF file
        pdf_content = await pdf_file.read()
        
        # Simulate the PDF document handling process
        await telegram_handler.send_message(chat_id, "Processing your PDF and questions...")
        
        # Save the PDF temporarily
        filename = f"{uuid.uuid4()}.pdf"
        filepath = await telegram_handler.pdf_handler.save_pdf(pdf_content, filename)
        
        # Extract text from PDF
        pdf_text = await telegram_handler.pdf_handler.extract_text(filepath)
        
        # Parse questions
        questions_list = [q.strip() for q in questions.split('\n') if q.strip()]
        
        # Generate response using LLM
        result = await telegram_handler.llm_handler.generate_response(
            pdf_text, 
            questions_list,
            []  # No other topics
        )
        
        # Clean up the PDF file
        await telegram_handler.pdf_handler.cleanup_pdf(filepath)
        
        # Send response to the chat
        from config.response_template import ResponseTemplate
        formatted_response = ResponseTemplate.format_response(
            result["important_questions"], 
            result["other_topics"]
        )
        
        # Split long messages if needed
        if len(formatted_response) > 4000:
            chunks = [formatted_response[i:i+4000] for i in range(0, len(formatted_response), 4000)]
            for chunk in chunks:
                await telegram_handler.send_message(chat_id, chunk)
        else:
            await telegram_handler.send_message(chat_id, formatted_response)
        
        return {"status": "success", "message": "PDF processed and results sent"}
        
    except Exception as e:
        await async_logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/start-polling")
async def start_polling_endpoint(background_tasks: BackgroundTasks):
    """
    Start polling for Telegram updates in the background.
    
    Args:
        background_tasks: FastAPI background tasks
        
    Returns:
        Status message
    """
    try:
        # Start polling in the background
        background_tasks.add_task(telegram_handler.start_polling)
        
        return {"status": "success", "message": "Started polling for Telegram updates"} 
    except Exception as e:
        await async_logger.error(f"Error starting polling: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

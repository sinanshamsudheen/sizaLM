"""
WhatsApp webhook routes for handling incoming messages and webhook verification.
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from typing import Dict, List, Optional, Any

from config.settings import settings
from app.models.schemas import WebhookVerificationRequest, WhatsAppMessage, ProcessedResponse, ErrorResponse
from services.whatsapp_handler import WhatsAppHandler
from services.llm_handler import LLMHandler
from utils.pdf_handler import PDFHandler, parse_questions_from_text
from utils.logging import async_logger
from config.response_template import ResponseTemplate

router = APIRouter()

# Service instances
whatsapp_handler = WhatsAppHandler()
llm_handler = LLMHandler()
pdf_handler = PDFHandler()


@router.get("/webhook")
async def verify_webhook(request: WebhookVerificationRequest = Depends()):
    """
    Verify WhatsApp webhook subscription.
    
    Args:
        request: WebhookVerificationRequest with verification data
        
    Returns:
        Challenge value if verification succeeds
    """
    if whatsapp_handler.verify_webhook(request.hub_mode, request.hub_verify_token):
        await async_logger.info("Webhook verification successful")
        return PlainTextResponse(content=str(request.hub_challenge))
    else:
        await async_logger.warning("Webhook verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive and process incoming WhatsApp messages.
    
    Args:
        request: HTTP request object
        background_tasks: FastAPI background tasks
        
    Returns:
        Empty 200 response to acknowledge receipt
    """
    try:
        # Parse webhook data
        data = await request.json()
        await async_logger.info(f"Received webhook data: {data}")
        
        # Process in background to respond quickly
        background_tasks.add_task(process_incoming_message, data)
        
        # Acknowledge receipt immediately
        return {"status": "received"}
    except Exception as e:
        await async_logger.error(f"Error receiving webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/test/upload")
async def test_upload_endpoint(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(...),
    questions: str = Form(...)
):
    """
    Test endpoint for direct API testing without WhatsApp integration.
    
    Args:
        background_tasks: FastAPI background tasks
        pdf_file: Uploaded PDF file
        questions: Important questions in plain text
        
    Returns:
        Status message
    """
    try:
        # Read the uploaded file
        file_content = await pdf_file.read()
        filename = f"{uuid.uuid4()}.pdf"
        
        # Save PDF to disk
        filepath = await pdf_handler.save_pdf(file_content, filename)
        
        # Extract text from PDF
        pdf_text = await pdf_handler.extract_text(filepath)
        
        # Parse questions from the provided text
        important_questions = [q.strip() for q in questions.split('\n') if q.strip()]
        other_topics = []
        
        # Process the data
        result = await process_pdf_and_questions(pdf_text, important_questions, other_topics)
        
        # Clean up the PDF
        await pdf_handler.cleanup_pdf(filepath)
        
        return result
        
    except Exception as e:
        await async_logger.error(f"Error in test upload: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_incoming_message(data: Dict[str, Any]):
    """
    Process incoming message from webhook.
    
    Args:
        data: Webhook payload data
    """
    try:
        # Parse webhook data
        message_data = await whatsapp_handler.parse_webhook_data(data)
        
        if not message_data["sender"]:
            await async_logger.warning("No sender information in webhook data")
            return
            
        # Initialize variables
        pdf_text = ""
        important_questions = []
        other_topics = []
        
        # Check if the message contains a document
        if message_data["message_type"] == "document" and message_data["media_url"]:
            # Check if it's a PDF
            if message_data["media_mime_type"] == "application/pdf" or \
               (message_data["filename"] and message_data["filename"].endswith(".pdf")):
                
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    "I've received your PDF. Processing now... 🔍"
                )
                
                # Download and process PDF
                media_content = await whatsapp_handler.download_media(message_data["media_url"])
                filename = message_data["filename"] or f"{uuid.uuid4()}.pdf"
                
                # Save PDF to disk
                filepath = await pdf_handler.save_pdf(media_content, filename)
                
                # Extract text from PDF
                pdf_text = await pdf_handler.extract_text(filepath)
                
                # Extract questions and topics from previous message context
                # For simplicity, we'll extract from the PDF text itself in this demo
                important_questions, other_topics = await parse_questions_from_text(pdf_text)
                
                # Process PDF and questions
                result = await process_pdf_and_questions(pdf_text, important_questions, other_topics)
                
                # Format the response using the template
                formatted_response = ResponseTemplate.format_response(
                    result["important_questions"], 
                    result["other_topics"]
                )
                
                # Send response back to user
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    formatted_response
                )
                
                # Clean up the PDF
                await pdf_handler.cleanup_pdf(filepath)
            else:
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    "I can only process PDF documents. Please send a PDF file."
                )
        elif message_data["message_type"] == "text" and message_data["message_text"]:
            # If it's just a text message, extract questions and respond
            important_questions, other_topics = await parse_questions_from_text(message_data["message_text"])
            
            if important_questions:
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    "I've noted your questions. Please send a PDF document that contains information to answer these questions."
                )
            else:
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    "Please send me some questions along with a PDF document that contains information to answer them."
                )
        
    except Exception as e:
        await async_logger.error(f"Error processing message: {str(e)}")
        try:
            # Attempt to notify the user of the error
            if "sender" in message_data:
                await whatsapp_handler.send_message(
                    message_data["sender"],
                    "Sorry, I encountered an error while processing your message. Please try again."
                )
        except:
            pass


async def process_pdf_and_questions(
    pdf_text: str, 
    important_questions: List[str], 
    other_topics: List[str]
) -> Dict[str, Any]:
    """
    Process PDF content and questions using LLM.
    
    Args:
        pdf_text: Text extracted from PDF
        important_questions: List of important questions
        other_topics: List of other topics
        
    Returns:
        Processed response data
    """
    try:
        # Generate response using LLM
        result = await llm_handler.generate_response(
            pdf_text, 
            important_questions,
            other_topics
        )
        
        await async_logger.info("Successfully processed PDF and questions with LLM")
        
        return result
    except Exception as e:
        await async_logger.error(f"Error processing PDF and questions: {str(e)}")
        raise

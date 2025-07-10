"""
Routes for testing and direct API access, since CallMeBot doesn't support webhooks.
"""

import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any

from config.settings import settings
from services.whatsapp_handler import WhatsAppHandler, WhatsAppApiType
from services.llm_handler import LLMHandler
from utils.pdf_handler import PDFHandler, parse_questions_from_text
from utils.logging import async_logger
from config.response_template import ResponseTemplate

router = APIRouter()

# Service instances
whatsapp_handler = WhatsAppHandler()
llm_handler = LLMHandler()
pdf_handler = PDFHandler()


@router.post("/send-message")
async def send_message(phone: str = Form(...), message: str = Form(...)):
    """
    Manually send a WhatsApp message using CallMeBot API.
    
    Args:
        phone: The phone number to send to (only used for non-CallMeBot APIs)
        message: The message to send
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        success = await whatsapp_handler.send_message(phone, message)
        
        if success:
            return {"status": "success", "message": "Message sent successfully"}
        else:
            return {"status": "error", "message": "Failed to send message"}
    except Exception as e:
        await async_logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.post("/process-pdf")
async def process_pdf(
    pdf_file: UploadFile = File(...),
    questions: str = Form(...),
    recipient_phone: Optional[str] = Form(None)
):
    """
    Process a PDF file with specified questions and optionally send the result via WhatsApp.
    This endpoint replaces webhook handling for CallMeBot integration.
    
    Args:
        pdf_file: The PDF file to process
        questions: Important questions to answer from the PDF
        recipient_phone: Optional phone number to send results to
        
    Returns:
        JSON response with results or confirmation of message sent
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
        
        # Process the PDF and questions
        result = await process_pdf_and_questions(pdf_text, important_questions, other_topics)
        
        # Format the response using the template
        formatted_response = ResponseTemplate.format_response(
            result["important_questions"], 
            result["other_topics"]
        )
        
        # Clean up the PDF
        await pdf_handler.cleanup_pdf(filepath)
        
        # If recipient phone is provided and using CallMeBot, send the message
        if recipient_phone and settings.WHATSAPP_API_TYPE == WhatsAppApiType.CALLMEBOT.value:
            success = await whatsapp_handler.send_message(recipient_phone, formatted_response)
            
            if success:
                return {"status": "success", "message": "Results sent via WhatsApp"}
            else:
                return {
                    "status": "partial_success",
                    "message": "Results processed but failed to send via WhatsApp",
                    "results": result
                }
        
        # Return the results directly
        return {"status": "success", "results": result}
        
    except Exception as e:
        await async_logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


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

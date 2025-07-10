"""
Pydantic models for request/response data validation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union


class WebhookVerificationRequest(BaseModel):
    """Model for WhatsApp webhook verification."""
    hub_mode: str = Field(alias="hub.mode")
    hub_challenge: int = Field(alias="hub.challenge")
    hub_verify_token: str = Field(alias="hub.verify_token")


class WhatsAppMessage(BaseModel):
    """Model for incoming WhatsApp message."""
    sender: str
    message_text: Optional[str] = None
    message_type: str
    media_url: Optional[str] = None
    media_mime_type: Optional[str] = None
    filename: Optional[str] = None


class ProcessedResponse(BaseModel):
    """Model for processed response data."""
    important_questions: Dict[str, str]
    other_topics: Dict[str, List[str]]
    
    
class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    details: Optional[str] = None

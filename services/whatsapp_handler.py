"""
WhatsApp service for handling interactions with WhatsApp APIs.
Supports Meta WhatsApp Cloud API and UltraMsg API.
"""

import json
from typing import Dict, List, Any, Optional
import httpx
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.logging import app_logger, async_logger


class WhatsAppApiType(str, Enum):
    """Enum for supported WhatsApp API providers."""
    META = "META"
    ULTRAMSG = "ULTRAMSG"
    CALLMEBOT = "CALLMEBOT"


class WhatsAppHandler:
    """Service for handling WhatsApp interactions."""
    
    def __init__(self):
        """Initialize the WhatsApp handler with configuration."""
        self.api_type = settings.WHATSAPP_API_TYPE
        
        # Meta/UltraMsg configuration
        self.token = settings.WHATSAPP_TOKEN
        self.phone_id = settings.WHATSAPP_PHONE_ID
        self.verify_token = settings.WHATSAPP_VERIFY_TOKEN
        
        # CallMeBot configuration
        self.callmebot_phone = settings.CALLMEBOT_PHONE
        self.callmebot_api_key = settings.CALLMEBOT_API_KEY

    def verify_webhook(self, mode: str, token: str) -> bool:
        """
        Verify the webhook subscription.
        
        Args:
            mode: The hub mode (subscribe)
            token: The token to verify
            
        Returns:
            True if verification is successful, False otherwise
        """
        return mode == "subscribe" and token == self.verify_token
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_message(self, to: str, message: str) -> bool:
        """
        Send a text message via WhatsApp.
        
        Args:
            to: Recipient's phone number (with country code)
            message: Message content to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            if self.api_type == WhatsAppApiType.META:
                return await self._send_via_meta(to, message)
            elif self.api_type == WhatsAppApiType.ULTRAMSG:
                return await self._send_via_ultramsg(to, message)
            elif self.api_type == WhatsAppApiType.CALLMEBOT:
                return await self._send_via_callmebot(to, message)
            else:
                await async_logger.error(f"Unsupported WhatsApp API type: {self.api_type}")
                return False
        except Exception as e:
            await async_logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
    
    async def _send_via_meta(self, to: str, message: str) -> bool:
        """
        Send message via Meta WhatsApp Cloud API.
        
        Args:
            to: Recipient's phone number
            message: Message content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"https://graph.facebook.com/v17.0/{self.phone_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"body": message}
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=data)
                
                response.raise_for_status()
                await async_logger.info(f"Message sent via Meta API: {response.json()}")
                return True
                
        except Exception as e:
            await async_logger.error(f"Error sending via Meta API: {str(e)}")
            return False
    
    async def _send_via_ultramsg(self, to: str, message: str) -> bool:
        """
        Send message via UltraMsg API.
        
        Args:
            to: Recipient's phone number
            message: Message content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = "https://api.ultramsg.com/instance{instance}/messages/chat"
            url = url.format(instance=self.phone_id)
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "token": self.token,
                "to": to,
                "body": message
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, data=data)
                
                response.raise_for_status()
                await async_logger.info(f"Message sent via UltraMsg API: {response.json()}")
                return True
                
        except Exception as e:
            await async_logger.error(f"Error sending via UltraMsg API: {str(e)}")
            return False
    
    async def _send_via_callmebot(self, to: str, message: str) -> bool:
        """
        Send message via CallMeBot API.
        
        Args:
            to: Recipient's phone number (ignored in CallMeBot, using config)
            message: Message content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import urllib.parse
            
            # For CallMeBot, we use the phone number from settings rather than 'to' parameter
            # URL encode the message
            encoded_message = urllib.parse.quote(message)
            
            # Build the URL for the CallMeBot API
            url = f"https://api.callmebot.com/whatsapp.php?phone={self.callmebot_phone}&text={encoded_message}&apikey={self.callmebot_api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                
                # CallMeBot returns HTML, so we check status code
                if response.status_code == 200:
                    await async_logger.info("Message sent via CallMeBot API")
                    return True
                else:
                    await async_logger.error(f"Error sending via CallMeBot API: {response.text}")
                    return False
                    
        except Exception as e:
            await async_logger.error(f"Error sending via CallMeBot API: {str(e)}")
            return False
    
    async def parse_webhook_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming webhook data from WhatsApp.
        
        Args:
            data: Webhook payload data
            
        Returns:
            Parsed message data dictionary
        """
        parsed_data = {
            "sender": None,
            "message_text": None,
            "message_type": None,
            "media_url": None,
            "media_mime_type": None,
            "filename": None
        }
        
        try:
            if self.api_type == WhatsAppApiType.META:
                # Parse Meta WhatsApp Cloud API webhook
                if "entry" in data and data["entry"]:
                    entry = data["entry"][0]
                    if "changes" in entry and entry["changes"]:
                        change = entry["changes"][0]
                        if "value" in change and "messages" in change["value"]:
                            message = change["value"]["messages"][0]
                            parsed_data["sender"] = message["from"]
                            parsed_data["message_type"] = message["type"]
                            
                            if message["type"] == "text":
                                parsed_data["message_text"] = message["text"]["body"]
                            elif message["type"] == "document":
                                parsed_data["media_url"] = message["document"]["id"]
                                parsed_data["media_mime_type"] = message["document"].get("mime_type")
                                parsed_data["filename"] = message["document"].get("filename")
            else:
                # Parse UltraMsg API webhook
                if "data" in data:
                    msg_data = data["data"]
                    parsed_data["sender"] = msg_data.get("from")
                    parsed_data["message_type"] = msg_data.get("type")
                    
                    if msg_data.get("type") == "chat":
                        parsed_data["message_text"] = msg_data.get("body")
                    elif msg_data.get("type") == "document":
                        parsed_data["media_url"] = msg_data.get("file")
                        parsed_data["filename"] = msg_data.get("filename")
                        parsed_data["media_mime_type"] = "application/pdf"  # Assuming PDF
            
            await async_logger.info(f"Parsed webhook data: {parsed_data}")
            return parsed_data
            
        except Exception as e:
            await async_logger.error(f"Error parsing webhook: {str(e)}")
            return parsed_data
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def download_media(self, media_id: str) -> bytes:
        """
        Download media from WhatsApp API.
        
        Args:
            media_id: ID of the media to download
            
        Returns:
            Binary content of the media file
        """
        try:
            if self.api_type == WhatsAppApiType.META:
                return await self._download_media_meta(media_id)
            else:
                return await self._download_media_ultramsg(media_id)
        except Exception as e:
            await async_logger.error(f"Error downloading media: {str(e)}")
            raise
    
    async def _download_media_meta(self, media_id: str) -> bytes:
        """
        Download media from Meta WhatsApp Cloud API.
        
        Args:
            media_id: ID of the media to download
            
        Returns:
            Binary content of the media file
        """
        try:
            # First, get the media URL
            url = f"https://graph.facebook.com/v17.0/{media_id}"
            headers = {
                "Authorization": f"Bearer {self.token}"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                media_url = response.json().get("url")
                if not media_url:
                    raise ValueError("Media URL not found")
                
                # Download the media file
                download_response = await client.get(
                    media_url, 
                    headers=headers
                )
                download_response.raise_for_status()
                
                await async_logger.info(f"Successfully downloaded media from Meta API")
                return download_response.content
                
        except Exception as e:
            await async_logger.error(f"Error downloading media from Meta API: {str(e)}")
            raise
    
    async def _download_media_ultramsg(self, media_url: str) -> bytes:
        """
        Download media from UltraMsg API.
        
        Args:
            media_url: Direct URL to the media
            
        Returns:
            Binary content of the media file
        """
        try:
            # UltraMsg provides direct URLs to media
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(media_url)
                response.raise_for_status()
                
                await async_logger.info("Successfully downloaded media from UltraMsg API")
                return response.content
                
        except Exception as e:
            await async_logger.error(f"Error downloading media from UltraMsg API: {str(e)}")
            raise

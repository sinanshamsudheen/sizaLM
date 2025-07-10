"""
PDF handling utility for extracting text from PDF files.
Supports PDF parsing and text extraction.
"""

import os
import asyncio
import aiofiles
from typing import List, Tuple, Dict, Optional
import fitz  # PyMuPDF
from pathlib import Path

from utils.logging import app_logger, async_logger
from config.settings import settings


class PDFHandler:
    """Utility class for handling PDF operations."""
    
    @staticmethod
    async def save_pdf(file_content: bytes, filename: str) -> str:
        """
        Save PDF file to disk asynchronously.
        
        Args:
            file_content: Binary content of the PDF file
            filename: Name to save the file as
            
        Returns:
            Path to the saved file
        """
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        
        try:
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(file_content)
            
            await async_logger.info(f"PDF saved: {filepath}")
            return filepath
            
        except Exception as e:
            await async_logger.error(f"Error saving PDF: {str(e)}")
            raise
    
    @staticmethod
    async def extract_text(filepath: str) -> str:
        """
        Extract text from a PDF file asynchronously.
        
        Args:
            filepath: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        try:
            # Run in a thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            
            def _extract():
                text_content = ""
                with fitz.open(filepath) as doc:
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        text_content += page.get_text()
                return text_content
            
            text = await loop.run_in_executor(None, _extract)
            
            await async_logger.info(f"Text extracted from PDF: {filepath}")
            return text
            
        except Exception as e:
            await async_logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    @staticmethod
    async def cleanup_pdf(filepath: str) -> None:
        """
        Delete a PDF file asynchronously.
        
        Args:
            filepath: Path to the PDF file to delete
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                await async_logger.info(f"PDF deleted: {filepath}")
        except Exception as e:
            await async_logger.error(f"Error deleting PDF: {str(e)}")


async def parse_questions_from_text(text: str) -> Tuple[List[str], List[str]]:
    """
    Parse important questions and extract other topics from text.
    
    Args:
        text: Text content to parse
        
    Returns:
        Tuple containing:
        - List of important questions
        - List of other topics
    """
    # This is a simple implementation - in a real app, you might use
    # regex patterns or LLM-based extraction for more accurate results
    
    important_questions = []
    other_topics = []
    
    # Extract lines that end with question marks for important questions
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if it's likely a question
        if line.endswith('?'):
            if any(keyword in line.lower() for keyword in ['important', 'key', 'critical', 'main']):
                important_questions.append(line)
            else:
                other_topics.append(line)
        # Check if it's a numbered or bullet point that might be a topic
        elif (line.startswith(('•', '-', '*')) or 
              any(line.startswith(f"{i}.") for i in range(1, 21))):
            other_topics.append(line.lstrip('•-*0123456789. '))
    
    # Limit the number of extracted items
    important_questions = important_questions[:10]  # Limit to 10 important questions
    other_topics = other_topics[:15]  # Limit to 15 other topics
    
    return important_questions, other_topics

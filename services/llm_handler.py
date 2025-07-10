"""
LLM service for handling interactions with various language model providers.
Supports Groq and Cohere APIs.
"""

import asyncio
from typing import Dict, List, Union, Optional
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.logging import app_logger, async_logger


class LLMProvider(str, Enum):
    """Enum for supported LLM providers."""
    GROQ = "GROQ"
    COHERE = "COHERE"


class LLMHandler:
    """Service for handling LLM interactions."""
    
    def __init__(self):
        """Initialize the LLM handler with configuration."""
        self.provider = settings.LLM_PROVIDER
        self.groq_api_key = settings.GROQ_API_KEY
        self.cohere_api_key = settings.COHERE_API_KEY
        self.groq_model = settings.GROQ_MODEL
        self.cohere_model = settings.COHERE_MODEL
        
    async def _call_groq_api(self, prompt: str) -> str:
        """
        Call the Groq API asynchronously.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated text response
        """
        try:
            # Using httpx for async HTTP requests
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 4000,
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data
                )
                
                response.raise_for_status()
                result = response.json()
                await async_logger.info("Successfully received response from Groq API")
                
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            await async_logger.error(f"Error calling Groq API: {str(e)}")
            raise
            
    async def _call_cohere_api(self, prompt: str) -> str:
        """
        Call the Cohere API asynchronously.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated text response
        """
        try:
            # Using httpx for async HTTP requests
            headers = {
                "Authorization": f"Bearer {self.cohere_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.cohere_model,
                "prompt": prompt,
                "max_tokens": 4000,
                "temperature": 0.7,
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.cohere.ai/v1/generate",
                    headers=headers,
                    json=data
                )
                
                response.raise_for_status()
                result = response.json()
                await async_logger.info("Successfully received response from Cohere API")
                
                return result["generations"][0]["text"]
                
        except Exception as e:
            await async_logger.error(f"Error calling Cohere API: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_response(
        self, 
        pdf_text: str, 
        important_questions: List[str],
        other_topics: List[str]
    ) -> Dict[str, Union[Dict[str, str], Dict[str, List[str]]]]:
        """
        Generate a response using the configured LLM.
        
        Args:
            pdf_text: Extracted text from PDF
            important_questions: List of important questions to answer in detail
            other_topics: List of other topics to cover briefly
            
        Returns:
            Dictionary containing:
            - important_questions: Dict mapping questions to detailed answers
            - other_topics: Dict mapping topics to bullet points
        """
        try:
            # Build the prompt for the LLM
            prompt = self._build_prompt(pdf_text, important_questions, other_topics)
            
            # Call the appropriate LLM API
            if settings.LLM_PROVIDER == LLMProvider.GROQ:
                response_text = await self._call_groq_api(prompt)
            else:
                response_text = await self._call_cohere_api(prompt)
                
            # Parse the LLM response
            parsed_response = self._parse_llm_response(response_text, important_questions, other_topics)
            
            return parsed_response
            
        except Exception as e:
            await async_logger.error(f"Error generating response: {str(e)}")
            raise
            
    def _build_prompt(self, pdf_text: str, important_questions: List[str], other_topics: List[str]) -> str:
        """
        Build a prompt for the LLM based on PDF content and questions.
        
        Args:
            pdf_text: Text extracted from PDF
            important_questions: List of important questions
            other_topics: List of other topics
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""
You are an educational assistant that helps students with their questions based on provided PDF content.

PDF CONTENT:
{pdf_text[:10000]}  # Limit to avoid token limits

TASK:
Based on the PDF content above, please provide:

1. Detailed, 10-mark style answers (about 250-300 words each) for these important questions:
{', '.join(important_questions)}

2. Concise, 4-mark style bullet-point answers (4-5 bullet points each) for these topics:
{', '.join(other_topics)}

FORMAT YOUR RESPONSE LIKE THIS:
```
IMPORTANT_QUESTIONS:
[Question 1]
[Detailed answer to question 1]

[Question 2]
[Detailed answer to question 2]

...and so on for all important questions

OTHER_TOPICS:
[Topic 1]
- [Point 1]
- [Point 2]
- [Point 3]
- [Point 4]

[Topic 2]
- [Point 1]
- [Point 2]
- [Point 3]
- [Point 4]

...and so on for all other topics
```
"""
        return prompt
    
    def _parse_llm_response(
        self, 
        response_text: str, 
        important_questions: List[str],
        other_topics: List[str]
    ) -> Dict[str, Union[Dict[str, str], Dict[str, List[str]]]]:
        """
        Parse the LLM response into structured data.
        
        Args:
            response_text: Raw text response from LLM
            important_questions: List of important questions (for fallback)
            other_topics: List of other topics (for fallback)
            
        Returns:
            Dictionary containing parsed responses
        """
        result = {
            "important_questions": {},
            "other_topics": {}
        }
        
        try:
            # Split response by sections
            if "IMPORTANT_QUESTIONS:" in response_text and "OTHER_TOPICS:" in response_text:
                # Split the response into the two main sections
                important_section, other_section = response_text.split("OTHER_TOPICS:", 1)
                important_section = important_section.replace("IMPORTANT_QUESTIONS:", "").strip()
                
                # Parse important questions
                current_question = None
                current_answer = []
                
                for line in important_section.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line is a question (doesn't start with whitespace)
                    if line.endswith("?") or any(q in line for q in important_questions):
                        # Save previous question-answer pair if exists
                        if current_question:
                            result["important_questions"][current_question] = "\n\n".join(current_answer)
                            current_answer = []
                        
                        # Set new current question
                        current_question = line
                    else:
                        # Add line to current answer
                        current_answer.append(line)
                
                # Add the last question-answer pair if exists
                if current_question and current_answer:
                    result["important_questions"][current_question] = "\n\n".join(current_answer)
                
                # Parse other topics
                current_topic = None
                current_points = []
                
                for line in other_section.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line is a bullet point
                    if line.startswith("-") or line.startswith("•"):
                        current_points.append(line.lstrip("-•").strip())
                    else:
                        # Save previous topic if exists
                        if current_topic and current_points:
                            result["other_topics"][current_topic] = current_points
                            current_points = []
                        
                        # Set new current topic
                        if any(t in line for t in other_topics):
                            current_topic = line
                
                # Add the last topic-points pair if exists
                if current_topic and current_points:
                    result["other_topics"][current_topic] = current_points
            
            # Fallback: If parsing failed, create empty entries for each question/topic
            if not result["important_questions"]:
                for q in important_questions:
                    result["important_questions"][q] = "I couldn't generate a detailed answer for this question based on the provided PDF content."
                    
            if not result["other_topics"]:
                for t in other_topics:
                    result["other_topics"][t] = ["No specific information found in the PDF"]
            
            return result
            
        except Exception as e:
            app_logger.error(f"Error parsing LLM response: {str(e)}")
            
            # Fallback for parsing errors
            for q in important_questions:
                result["important_questions"][q] = "I couldn't generate a detailed answer for this question based on the provided PDF content."
                
            for t in other_topics:
                result["other_topics"][t] = ["No specific information found in the PDF"]
            
            return result

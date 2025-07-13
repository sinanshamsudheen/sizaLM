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
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_summary(self, pdf_text: str, important_topics: List[str]) -> str:
        """
        Generate a document summary with focus on important topics.
        
        Args:
            pdf_text: Extracted text from PDF
            important_topics: List of important topics to focus on
            
        Returns:
            Formatted summary text
        """
        try:
            # Build the summarization prompt
            prompt = self._build_summary_prompt(pdf_text, important_topics)
            
            # Call the appropriate LLM API
            if settings.LLM_PROVIDER == LLMProvider.GROQ:
                response_text = await self._call_groq_api(prompt)
            else:
                response_text = await self._call_cohere_api(prompt)
            
            await async_logger.info(f"Generated summary with {len(response_text)} characters")
            return response_text
            
        except Exception as e:
            await async_logger.error(f"Error generating summary: {str(e)}")
            raise
    
    def _build_summary_prompt(self, pdf_text: str, important_topics: List[str]) -> str:
        """
        Build a prompt for the LLM to generate a document summary.
        
        Args:
            pdf_text: Text extracted from PDF
            important_topics: List of important topics to focus on
            
        Returns:
            Formatted prompt string
        """
        # Prepare important topics section
        important_topics_text = ""
        if important_topics:
            important_topics_text = "Important topics to focus on in detail (8-mark level, ~250 words each):\n"
            for i, topic in enumerate(important_topics, 1):
                important_topics_text += f"{i}. {topic}\n"
        else:
            important_topics_text = "No specific important topics provided. Summarize all topics evenly."
        
        prompt = f"""
You are an educational assistant that helps students summarize academic documents for exam revision.

PDF CONTENT:
{pdf_text[:15000]}  # Include more content for better summaries

TASK:
Create a comprehensive summary of the document following these EXACT instructions:

1. Use ONLY content from the PDF.

2. Organize notes in a hierarchical structure:
   - Use ALL CAPS for major topics (e.g., "DATABASE MANAGEMENT SYSTEMS")
   - Use Title Case with a colon for subheadings (e.g., "Transaction Management:")
   - Use bullet points (•) for key points under each topic

3. Format:
   - Keep each subtopic summary to 5-6 lines maximum
   - Use concise, easy-to-understand language
   - Put KEY TERMS in ALL CAPS or *asterisks* to highlight them
   - Make content exam-friendly and easy to revise

4. Special handling for topics:
   - {important_topics_text}
   - For important topics, provide more detailed explanations (8-mark level, ~200-250 words)
   - For all other topics, provide concise explanations (4-mark level, ~100 words)

5. Avoid:
   - Unnecessary examples unless they appear in the PDF
   - Content not present in the PDF
   - Verbose explanations - keep it minimal and structured

Your response should be well-structured with clear hierarchical organization starting with major topics, then subheadings, followed by bullet points with concise explanations.
"""
        return prompt
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_summary_from_chunks(self, pdf_chunks: List[Dict[str, any]], important_topics: List[str]) -> str:
        """
        Generate a summary from chunked PDF text for very large documents.
        
        Args:
            pdf_chunks: List of dictionaries containing chunked PDF text
            important_topics: List of important topics to focus on
            
        Returns:
            Complete formatted summary text
        """
        try:
            await async_logger.info(f"Generating summary from {len(pdf_chunks)} chunks")
            
            # First pass: Generate summaries for each chunk
            chunk_summaries = []
            
            for i, chunk in enumerate(pdf_chunks):
                chunk_start_page = chunk["start_page"]
                chunk_end_page = chunk["end_page"]
                chunk_text = chunk["text"]
                
                await async_logger.info(f"Processing chunk {i+1}/{len(pdf_chunks)}: pages {chunk_start_page}-{chunk_end_page}")
                
                # Create a custom prompt for this chunk
                chunk_prompt = self._build_chunk_summary_prompt(
                    chunk_text, 
                    important_topics,
                    chunk_start_page,
                    chunk_end_page,
                    i+1,
                    len(pdf_chunks)
                )
                
                # Call the appropriate LLM API
                if settings.LLM_PROVIDER == LLMProvider.GROQ:
                    chunk_summary = await self._call_groq_api(chunk_prompt)
                else:
                    chunk_summary = await self._call_cohere_api(chunk_prompt)
                
                chunk_summaries.append({
                    "start_page": chunk_start_page,
                    "end_page": chunk_end_page,
                    "summary": chunk_summary
                })
                
                await async_logger.info(f"Generated summary for chunk {i+1}: {len(chunk_summary)} characters")
            
            # If there's only one chunk, just return its summary
            if len(chunk_summaries) == 1:
                return chunk_summaries[0]["summary"]
            
            # Second pass: Consolidate the chunk summaries into a final summary
            consolidation_prompt = self._build_consolidation_prompt(chunk_summaries, important_topics)
            
            if settings.LLM_PROVIDER == LLMProvider.GROQ:
                final_summary = await self._call_groq_api(consolidation_prompt)
            else:
                final_summary = await self._call_cohere_api(consolidation_prompt)
            
            await async_logger.info(f"Generated final consolidated summary: {len(final_summary)} characters")
            return final_summary
            
        except Exception as e:
            await async_logger.error(f"Error generating summary from chunks: {str(e)}")
            raise
    
    def _build_chunk_summary_prompt(
        self, 
        chunk_text: str, 
        important_topics: List[str],
        start_page: int,
        end_page: int,
        chunk_num: int,
        total_chunks: int
    ) -> str:
        """
        Build a prompt for summarizing a single chunk of a document.
        
        Args:
            chunk_text: Text from this chunk
            important_topics: List of important topics to focus on
            start_page: Starting page number of this chunk
            end_page: Ending page number of this chunk
            chunk_num: Current chunk number
            total_chunks: Total number of chunks
            
        Returns:
            Prompt for summarizing this chunk
        """
        # Prepare important topics section
        important_topics_text = ""
        if important_topics:
            important_topics_text = "Important topics to identify and focus on in this chunk (if present):\n"
            for i, topic in enumerate(important_topics, 1):
                important_topics_text += f"{i}. {topic}\n"
        else:
            important_topics_text = "No specific important topics provided. Summarize key content evenly."
        
        prompt = f"""
You are summarizing a chunk (part {chunk_num} of {total_chunks}) of a large document (pages {start_page}-{end_page}).

CHUNK CONTENT:
{chunk_text[:15000]}

TASK:
Create a concise summary of THIS CHUNK ONLY following these instructions:

1. Use ONLY content from the provided chunk. You are summarizing JUST THIS SECTION of a larger document.

2. Focus on identifying key topics and concepts that appear in this chunk.
   - Use ALL CAPS for major topics
   - Use Title Case with a colon for subtopics

3. {important_topics_text}

4. Organization:
   - Structure your response with headings for each main topic found in this chunk
   - Prioritize content related to the important topics if they appear in this chunk
   - Use bullet points (•) for key information under each topic
   - Keep explanations concise (3-5 lines per subtopic)

5. Important: Indicate where topics appear to be continuing from previous chunks or seem incomplete 
   (this will help when consolidating the full summary later)

Format your summary with clear hierarchical structure and indicate "CHUNK {chunk_num}/{total_chunks}" at the beginning.
"""
        return prompt
        
    def _build_consolidation_prompt(self, chunk_summaries: List[Dict[str, any]], important_topics: List[str]) -> str:
        """
        Build a prompt to consolidate multiple chunk summaries into a final summary.
        
        Args:
            chunk_summaries: List of dictionaries containing summaries for each chunk
            important_topics: List of important topics to focus on
            
        Returns:
            Prompt for consolidating summaries
        """
        # Prepare important topics section
        important_topics_text = ""
        if important_topics:
            important_topics_text = "Important topics to focus on in detail (8-mark level, ~250 words each):\n"
            for i, topic in enumerate(important_topics, 1):
                important_topics_text += f"{i}. {topic}\n"
        else:
            important_topics_text = "No specific important topics provided. Summarize all key topics evenly."
        
        # Combine all chunk summaries
        all_summaries = "\n\n" + "-" * 40 + "\n\n"
        for i, chunk in enumerate(chunk_summaries):
            all_summaries += f"CHUNK {i+1} (PAGES {chunk['start_page']}-{chunk['end_page']}):\n\n"
            all_summaries += chunk['summary']
            all_summaries += "\n\n" + "-" * 40 + "\n\n"
        
        prompt = f"""
You are creating a final consolidated summary of a large document based on individual chunk summaries.

SUMMARIES OF DOCUMENT CHUNKS:
{all_summaries}

TASK:
Create a comprehensive, unified summary of the entire document following these EXACT instructions:

1. Consolidate information from all chunks into a single coherent summary.

2. Organize the final notes in a hierarchical structure:
   - Use ALL CAPS for major topics (e.g., "DATABASE MANAGEMENT SYSTEMS")
   - Use Title Case with a colon for subheadings (e.g., "Transaction Management:")
   - Use bullet points (•) for key points under each topic

3. Format:
   - Keep each subtopic summary to 5-6 lines maximum
   - Use concise, easy-to-understand language
   - Put KEY TERMS in ALL CAPS or *asterisks* to highlight them
   - Make content exam-friendly and easy to revise

4. Special handling for topics:
   - {important_topics_text}
   - For important topics, provide more detailed explanations (8-mark level, ~200-250 words)
   - For all other topics, provide concise explanations (4-mark level, ~100 words)

5. Avoid:
   - Duplication of information from different chunks
   - References to specific chunks or page numbers in the final summary
   - Content that seems contradictory (reconcile any differences)

Your response should be well-structured with clear hierarchical organization suitable for exam revision.
"""
        return prompt

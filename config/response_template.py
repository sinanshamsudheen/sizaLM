"""
Response templating utilities for formatting WhatsApp messages.
Configure the output format for different types of responses.
"""
from typing import Dict, List, Optional


class ResponseTemplate:
    """
    Class to format responses based on configurable templates.
    Can be customized to change how responses look in WhatsApp.
    """
    
    # Section formatting
    SECTION_TITLE = "📌 {title} 📌"
    SECTION_SEPARATOR = "\n\n" + "=" * 30 + "\n\n"
    
    # Question formatting
    QUESTION_PREFIX = "❓ "
    QUESTION_SUFFIX = ""
    
    # 10-mark (long) answer formatting
    LONG_ANSWER_TITLE = "📝 Detailed Answer:"
    LONG_ANSWER_PREFIX = ""
    LONG_ANSWER_SUFFIX = ""
    LONG_ANSWER_PARAGRAPH_SEPARATOR = "\n\n"
    
    # 4-mark (concise) answer formatting
    CONCISE_ANSWER_TITLE = "💡 Key Points:"
    CONCISE_BULLET = "• "
    CONCISE_SUBBULLET = "  - "
    
    # Other formatting options
    IMPORTANT_MARKER = "⚠️"
    EMPHASIS_PREFIX = "*"
    EMPHASIS_SUFFIX = "*"
    
    @classmethod
    def format_section_title(cls, title: str) -> str:
        """Format a section title."""
        return cls.SECTION_TITLE.format(title=title)
    
    @classmethod
    def format_question(cls, question: str) -> str:
        """Format a question."""
        return f"{cls.QUESTION_PREFIX}{question}{cls.QUESTION_SUFFIX}"
    
    @classmethod
    def format_long_answer(cls, content: str) -> str:
        """Format a 10-mark style long answer."""
        paragraphs = content.split('\n\n')
        formatted_paragraphs = [
            f"{cls.LONG_ANSWER_PREFIX}{p}{cls.LONG_ANSWER_SUFFIX}" 
            for p in paragraphs
        ]
        
        return (
            f"{cls.LONG_ANSWER_TITLE}\n\n" + 
            cls.LONG_ANSWER_PARAGRAPH_SEPARATOR.join(formatted_paragraphs)
        )
    
    @classmethod
    def format_concise_answer(cls, points: List[str]) -> str:
        """Format a 4-mark style concise answer with bullet points."""
        formatted_points = [f"{cls.CONCISE_BULLET}{point}" for point in points]
        
        return (
            f"{cls.CONCISE_ANSWER_TITLE}\n\n" +
            "\n".join(formatted_points)
        )
    
    @classmethod
    def emphasize(cls, text: str) -> str:
        """Add emphasis to text (bold in WhatsApp)."""
        return f"{cls.EMPHASIS_PREFIX}{text}{cls.EMPHASIS_SUFFIX}"
    
    @classmethod
    def format_response(
        cls, 
        important_questions: Dict[str, str], 
        other_topics: Dict[str, List[str]]
    ) -> str:
        """
        Format the complete response with both important questions and other topics.
        
        Args:
            important_questions: Dict mapping questions to long-form answers
            other_topics: Dict mapping topics to lists of bullet points
            
        Returns:
            Formatted response string for WhatsApp
        """
        response_parts = []
        
        # Add important questions section if any exist
        if important_questions:
            response_parts.append(cls.format_section_title("Important Questions"))
            
            for question, answer in important_questions.items():
                response_parts.append(cls.format_question(question))
                response_parts.append(cls.format_long_answer(answer))
                response_parts.append("")  # Empty line for spacing
        
        # Add section separator if both sections exist
        if important_questions and other_topics:
            response_parts.append(cls.SECTION_SEPARATOR)
        
        # Add other topics section if any exist
        if other_topics:
            response_parts.append(cls.format_section_title("Other Key Topics"))
            
            for topic, points in other_topics.items():
                response_parts.append(cls.emphasize(topic))
                response_parts.append(cls.format_concise_answer(points))
                response_parts.append("")  # Empty line for spacing
        
        return "\n".join(response_parts)


# Example usage
if __name__ == "__main__":
    important_q = {
        "What is quantum computing?": "Quantum computing is a type of computation that harnesses quantum mechanical phenomena. While traditional computers use bits with values of 0 or 1, quantum computers use quantum bits (qubits) that can represent a 0, 1, or both simultaneously through superposition.\n\nThis allows quantum computers to process a vast number of calculations simultaneously, potentially solving complex problems that are practically impossible for classical computers to solve efficiently."
    }
    
    other_t = {
        "Applications of Quantum Computing": [
            "Cryptography and security",
            "Drug discovery and development",
            "Weather forecasting and climate modeling",
            "Financial modeling and optimization"
        ]
    }
    
    print(ResponseTemplate.format_response(important_q, other_t))

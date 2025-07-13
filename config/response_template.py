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
    
    @classmethod
    def format_summary(cls, summary_text: str) -> str:
        """
        Format a document summary for nice display in Telegram using a hierarchical structure.
        
        Args:
            summary_text: The summary text from the LLM
            
        Returns:
            Formatted summary string with hierarchical structure and proper emphasis
        """
        # Add HTML formatting for Telegram
        formatted_lines = []
        in_bullet_list = False
        current_heading_level = 0
        
        for line in summary_text.split('\n'):
            line = line.strip()
            if not line:
                formatted_lines.append(line)
                in_bullet_list = False
                continue
            
            # Process headings with hierarchical structure
            if line.isupper() or (len(line) < 80 and (
                    line.endswith(':') or 
                    line.startswith('#') or 
                    'TOPIC' in line.upper() or 
                    'SECTION' in line.upper())):
                
                # Determine heading level
                if line.isupper() or 'TOPIC' in line.upper() or line.startswith('# '):
                    # Major heading (H1)
                    clean_line = line.replace('#', '').replace(':', '').strip()
                    formatted_lines.append(f"\n<b><u>{clean_line.upper()}</u></b>\n")
                    current_heading_level = 1
                else:
                    # Subheading (H2)
                    clean_line = line.replace('##', '').replace(':', '').strip()
                    formatted_lines.append(f"\n<b>{clean_line}</b>")
                    current_heading_level = 2
                
                in_bullet_list = False
            
            # Handle bullet points
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                bullet_text = line[1:].strip()
                
                # Highlight key terms (terms in ALL CAPS or surrounded by * or _)
                bullet_text = cls._highlight_key_terms(bullet_text)
                
                formatted_lines.append(f"• {bullet_text}")
                in_bullet_list = True
            
            # Handle normal text - convert to bullet points for consistency if not following a heading
            elif current_heading_level > 0:
                # Highlight key terms in the text
                formatted_text = cls._highlight_key_terms(line)
                
                if current_heading_level == 1:
                    # For text under main headings, make it a bullet point if not already in a list
                    if not in_bullet_list:
                        formatted_lines.append(f"• {formatted_text}")
                        in_bullet_list = True
                    else:
                        formatted_lines.append(f"  {formatted_text}")
                else:
                    # For text under subheadings
                    formatted_lines.append(formatted_text)
            
            else:
                # Regular text
                formatted_text = cls._highlight_key_terms(line)
                formatted_lines.append(formatted_text)
        
        return "\n".join(formatted_lines)
    
    @classmethod
    def _highlight_key_terms(cls, text: str) -> str:
        """
        Highlight key terms in the text for better readability.
        - Terms in ALL CAPS will be bolded
        - Terms surrounded by * or _ will be bolded
        - Common key phrases like "important", "key", "note" will be emphasized
        
        Args:
            text: Original text
            
        Returns:
            Text with key terms highlighted in bold
        """
        import re
        
        # First, escape any HTML tags that might already be in the text to prevent double formatting
        # Check if there are already HTML tags and skip formatting if found
        if "<b>" in text or "</b>" in text:
            return text
            
        # Handle asterisk or underscore emphasis (* or _) - do this first to prevent conflicts
        emphasis_pattern = r'(\*|_)(.*?)(\*|_)'
        text = re.sub(emphasis_pattern, lambda m: f"<b>{m.group(2)}</b>", text)
        
        # Remove any remaining asterisks or underscores that weren't matched in pairs
        text = text.replace('*', '').replace('_', '')
            
        # Find words in ALL CAPS (likely technical terms)
        # More careful pattern to avoid already-bolded text
        uppercase_pattern = r'\b[A-Z]{2,}[A-Z0-9]*\b'
        
        # Track positions of existing tags to avoid overlapping formatting
        tag_positions = [(m.start(), m.end()) for m in re.finditer(r'<[^>]+>', text)]
        
        # Function to check if a position is inside any tag
        def is_in_tag(pos):
            return any(start <= pos <= end for start, end in tag_positions)
            
        # Process each uppercase match
        matches = list(re.finditer(uppercase_pattern, text))
        result = list(text)
        
        # Apply replacements in reverse to avoid position shifts
        for match in reversed(matches):
            start, end = match.span()
            # Check if this match is inside any HTML tag
            if not any(is_in_tag(pos) for pos in range(start, end)):
                term = text[start:end]
                replacement = f"<b>{term}</b>"
                result[start:end] = list(replacement)
        
        text = ''.join(result)
        
        # Highlight important phrases - with more care to avoid overlapping with existing tags
        for key_phrase in ["important", "key", "note", "critical", "essential", "significant"]:
            if key_phrase in text.lower():
                # Use a more careful approach to avoid formatting inside tags
                pattern = re.compile(f'\\b({key_phrase})\\b', re.IGNORECASE)
                
                # Find all matches and replace only those not inside tags
                matches = list(pattern.finditer(text))
                result = list(text)
                
                for match in reversed(matches):
                    start, end = match.span()
                    if not any(is_in_tag(pos) for pos in range(start, end)):
                        phrase = text[start:end]
                        replacement = f"<b>{phrase}</b>"
                        result[start:end] = list(replacement)
                
                text = ''.join(result)
                
        return text
        

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

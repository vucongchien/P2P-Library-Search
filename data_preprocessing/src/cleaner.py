import re

def clean_text(title: str, content: str) -> str:
    """
    Cleans text according to requirements:
    - Merges title + " " + content
    - Converts to lowercase
    - Removes punctuation, numbers, special chars (keeps only a-z and whitespace)
    - Normalizes whitespace
    """
    title = title or ""
    content = content or ""
    text = f"{title} {content}"
    
    # Lowercase
    text = text.lower()
    
    # Remove special chars ([^a-z\s])
    text = re.sub(r'[^a-z\s]', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

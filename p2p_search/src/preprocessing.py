import re
from typing import List

# Extended NLTK-like Stopwords list
STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", 
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", 
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", 
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that", 
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", 
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", 
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", 
    "at", "by", "for", "with", "about", "against", "between", "into", "through", 
    "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", 
    "once", "here", "there", "when", "where", "why", "how", "all", "any", 
    "both", "each", "few", "more", "most", "other", "some", "such", "no", 
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", 
    "t", "can", "will", "just", "don", "should", "now", "would", "could"
}

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

def tokenize(text: str) -> List[str]:
    """
    Tokenizes text:
    - splits by whitespace/regex
    - removes stopwords
    - removes tokens shorter than 3 chars (e.g. 'up')
    - deduplicates tokens
    - no stemming
    """
    # Find all words (a-z)
    tokens = text.split()
    
    result = []
    seen = set()
    
    for t in tokens:
        if t in STOPWORDS:
            continue
        if len(t) < 3:
            continue
            
        if t not in seen:
            seen.add(t)
            result.append(t)
            
    return result

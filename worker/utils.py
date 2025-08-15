import re

def remove_markdown(text):
        patterns = r'(\*\*|__)|(\*|_)|(`)|(\[.*?\]\(.*?\))|(\[|\]|\(|\))'
        return re.sub(patterns, '', text)

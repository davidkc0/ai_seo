"""
Core monitoring logic: query Claude about products and parse responses.
"""
import re
import anthropic
from typing import Optional
from config import settings


client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def build_queries(product_name: str, category: str, use_case: Optional[str], competitors: list[str], keywords: list[str]) -> list[str]:
    """Generate a set of queries to ask AI models about the product's category."""
    queries = [
        f"What are the best {category} tools available right now? Please give me a comprehensive list with brief descriptions.",
        f"Which {category} software do most businesses use in 2024? What are the top options?",
    ]

    if use_case:
        queries.append(
            f"I'm looking for a {category} solution for {use_case}. What do you recommend? List the top options."
        )
        queries.append(
            f"What are the best tools for {use_case}? I need a {category} platform."
        )

    for competitor in competitors[:2]:  # Limit to 2 competitor queries
        queries.append(
            f"What are the best alternatives to {competitor} for {category}? What should I consider?"
        )

    for keyword in keywords[:2]:  # Limit to 2 keyword queries
        queries.append(
            f"What {category} tools are best known for {keyword}?"
        )

    return queries


def query_claude(prompt: str) -> str:
    """Send a query to Claude and return the text response."""
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Haiku is fast and cheap for monitoring
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return message.content[0].text


def analyze_response(
    response: str,
    product_name: str,
    competitors: list[str]
) -> dict:
    """
    Parse an AI response to extract:
    - Whether the product is mentioned
    - Position of mention (1st, 2nd, etc.)
    - Sentiment of mention
    - Which competitors are mentioned
    """
    response_lower = response.lower()
    product_lower = product_name.lower()

    # Check if product is mentioned
    product_mentioned = product_lower in response_lower

    # Find mention position
    mention_position = None
    if product_mentioned:
        # Find all "tool mentions" - look for numbered lists or bold items
        # Split into lines and find which line contains the product
        lines = response.split('\n')
        mention_line_idx = None
        for i, line in enumerate(lines):
            if product_lower in line.lower():
                mention_line_idx = i
                break

        if mention_line_idx is not None:
            # Count how many items appear before this line
            position = 1
            for line in lines[:mention_line_idx]:
                # Count lines that look like list items
                stripped = line.strip()
                if stripped and (
                    stripped[0].isdigit() or
                    stripped.startswith('- ') or
                    stripped.startswith('* ') or
                    stripped.startswith('• ')
                ):
                    position += 1
            mention_position = max(1, position)

    # Determine sentiment around mention
    mention_sentiment = None
    if product_mentioned:
        # Find context around the mention (±200 chars)
        idx = response_lower.find(product_lower)
        context = response[max(0, idx - 200):idx + 200].lower()

        positive_words = ['excellent', 'great', 'best', 'top', 'leading', 'popular',
                         'powerful', 'easy', 'recommended', 'trusted', 'well-known',
                         'widely used', 'strong', 'robust', 'feature-rich']
        negative_words = ['limited', 'expensive', 'complicated', 'difficult', 'poor',
                         'weak', 'lacking', 'outdated', 'problematic', 'avoid']
        neutral_words = ['also', 'another', 'option', 'alternative', 'consider']

        pos_score = sum(1 for w in positive_words if w in context)
        neg_score = sum(1 for w in negative_words if w in context)

        if pos_score > neg_score:
            mention_sentiment = "positive"
        elif neg_score > pos_score:
            mention_sentiment = "negative"
        else:
            mention_sentiment = "neutral"

    # Find which competitors are mentioned
    competitors_found = []
    for competitor in competitors:
        if competitor.lower() in response_lower:
            competitors_found.append(competitor)

    return {
        "product_mentioned": product_mentioned,
        "mention_position": mention_position,
        "mention_sentiment": mention_sentiment,
        "competitors_mentioned": competitors_found,
    }


def run_product_scan(
    product_name: str,
    category: str,
    use_case: Optional[str],
    competitors: list[str],
    keywords: list[str]
) -> list[dict]:
    """
    Run a full scan for a product. Returns list of scan result dicts.
    """
    queries = build_queries(product_name, category, use_case, competitors, keywords)
    results = []

    for query in queries:
        try:
            response = query_claude(query)
            analysis = analyze_response(response, product_name, competitors)
            results.append({
                "query": query,
                "ai_model": "claude",
                "full_response": response,
                **analysis
            })
        except Exception as e:
            print(f"Error querying Claude for '{query}': {e}")
            # Continue with other queries even if one fails

    return results

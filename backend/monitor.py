"""
Core monitoring logic: query multiple AI providers about a product's category
and parse each response for mentions, position, sentiment, and competitors.

Routes all calls through OpenRouter (OpenAI-compatible API) so we only need one
API key and one SDK to hit Claude, GPT, Gemini, and Perplexity.

Model catalog: https://openrouter.ai/models
"""
from typing import Optional
from openai import OpenAI

from config import settings


# Single OpenRouter client — OpenAI-compatible, talks to all providers.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        # Optional but recommended by OpenRouter for attribution / rate limits.
        "HTTP-Referer": settings.app_url or "https://www.illusion.ai",
        "X-Title": "Illusion",
    },
)


# Provider registry: short tag (stored in DB) → (display name, OpenRouter model id).
# To swap tiers later (e.g. GPT-4o instead of GPT-4o-mini for a Growth plan),
# change the model id here or add a separate PREMIUM_PROVIDERS dict.
PROVIDERS = {
    "claude":     ("Claude Haiku 4.5",   "anthropic/claude-3.5-haiku"),
    "gpt":        ("GPT-4o mini",        "openai/gpt-4o-mini"),
    "gemini":     ("Gemini Flash",       "google/gemini-flash-1.5"),
    "perplexity": ("Perplexity Sonar",   "perplexity/llama-3.1-sonar-small-128k-online"),
}


def build_queries(
    product_name: str,
    category: str,
    use_case: Optional[str],
    competitors: list[str],
    keywords: list[str],
) -> list[str]:
    """Generate a set of buyer-intent queries about the product's category."""
    queries = [
        f"What are the best {category} tools available right now? Please give me a comprehensive list with brief descriptions.",
        f"Which {category} software do most businesses use in 2026? What are the top options?",
    ]

    if use_case:
        queries.append(
            f"I'm looking for a {category} solution for {use_case}. What do you recommend? List the top options."
        )
        queries.append(
            f"What are the best tools for {use_case}? I need a {category} platform."
        )

    for competitor in competitors[:2]:
        queries.append(
            f"What are the best alternatives to {competitor} for {category}? What should I consider?"
        )

    for keyword in keywords[:2]:
        queries.append(
            f"What {category} tools are best known for {keyword}?"
        )

    return queries


def query_provider(provider_tag: str, prompt: str) -> str:
    """Send a prompt to the specified provider via OpenRouter. Returns the text response."""
    if provider_tag not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_tag}")

    _, model_id = PROVIDERS[provider_tag]
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def analyze_response(response: str, product_name: str, competitors: list[str]) -> dict:
    """
    Parse an AI response to extract:
    - Whether the product is mentioned
    - Position of mention (1st, 2nd, etc.)
    - Sentiment of mention
    - Which competitors are mentioned
    """
    response_lower = response.lower()
    product_lower = product_name.lower()

    product_mentioned = product_lower in response_lower

    # Find mention position (how many list items appeared before it)
    mention_position = None
    if product_mentioned:
        lines = response.split('\n')
        mention_line_idx = None
        for i, line in enumerate(lines):
            if product_lower in line.lower():
                mention_line_idx = i
                break

        if mention_line_idx is not None:
            position = 1
            for line in lines[:mention_line_idx]:
                stripped = line.strip()
                if stripped and (
                    stripped[0].isdigit()
                    or stripped.startswith('- ')
                    or stripped.startswith('* ')
                    or stripped.startswith('• ')
                ):
                    position += 1
            mention_position = max(1, position)

    # Sentiment via keyword proximity around the mention
    mention_sentiment = None
    if product_mentioned:
        idx = response_lower.find(product_lower)
        context = response[max(0, idx - 200): idx + 200].lower()

        positive_words = ['excellent', 'great', 'best', 'top', 'leading', 'popular',
                          'powerful', 'easy', 'recommended', 'trusted', 'well-known',
                          'widely used', 'strong', 'robust', 'feature-rich']
        negative_words = ['limited', 'expensive', 'complicated', 'difficult', 'poor',
                          'weak', 'lacking', 'outdated', 'problematic', 'avoid']

        pos_score = sum(1 for w in positive_words if w in context)
        neg_score = sum(1 for w in negative_words if w in context)

        if pos_score > neg_score:
            mention_sentiment = "positive"
        elif neg_score > pos_score:
            mention_sentiment = "negative"
        else:
            mention_sentiment = "neutral"

    competitors_found = [c for c in competitors if c.lower() in response_lower]

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
    keywords: list[str],
    providers: Optional[list[str]] = None,
) -> list[dict]:
    """
    Run a full scan for a product across all (or a subset of) providers.
    Returns list of scan result dicts, each tagged with its provider.

    `providers` defaults to every key in PROVIDERS. Pass a subset to limit
    scans (e.g. for a cheap plan or a specific-provider re-scan).
    """
    queries = build_queries(product_name, category, use_case, competitors, keywords)
    active_providers = providers or list(PROVIDERS.keys())
    results = []

    for provider_tag in active_providers:
        for query in queries:
            try:
                response = query_provider(provider_tag, query)
                analysis = analyze_response(response, product_name, competitors)
                results.append({
                    "query": query,
                    "ai_model": provider_tag,     # "claude" | "gpt" | "gemini" | "perplexity"
                    "full_response": response,
                    **analysis,
                })
            except Exception as e:
                # Log and continue — one provider failing shouldn't kill the whole scan.
                print(f"[monitor] {provider_tag} failed on '{query[:60]}...': {e}")

    return results

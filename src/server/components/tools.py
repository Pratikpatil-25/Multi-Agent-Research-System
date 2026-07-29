from langchain.tools import tool
from tavily import TavilyClient
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from logger import logger
from config import params
import os

load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# Tool 1 - for extracting web pages related to the query
@tool
def web_search(query: str) -> list[str]:
    """Search the web for recent and reliable information on a topic.
    Returns a list of URLs of the most appropriate websites."""

    try:
        results = tavily.search(query=query, max_results=params["max_search_results"])
    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {e}")
        return []

    # results['results'] may be missing or empty - guard against that
    urls = [res["url"] for res in results.get("results", []) if "url" in res]

    if not urls:
        logger.warning(f"No search results found for query: {query}")

    return urls


# Tool 2 - for extracting the content from the extracted web pages URLs
@tool
def scrape_url(url: str) -> str:
    """Scrape and return clean text content from a given URL for deeper reading."""
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)[:1500]

        if not text:
            logger.warning(f"No readable text extracted from URL: {url}")

        return text

    except Exception as e:
        logger.error(f"Could not scrape URL {url}: {e}")
        return f"Could not scrape URL: {str(e)}"
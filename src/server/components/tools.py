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
def web_search(query : str) -> str :
    """Search the web for recent and reliable information on a topic . Returns Titles , URLs and snippets."""

    results = tavily.search(query=query, max_results=params['max_search_results'])

    # we need to store retrieved results
    output = []
    for res in results['results']:
        output.append(
            f"""URL : {res['url']} \n 
            Title : {res['title']} \n
            Content : {res['content'][:300]}"""
        )
    return "\n----\n".join(output)


# Tool 2 - for extracting the content from the extracted web pages URLs
@tool
def scrape_url(url : str) -> str : 
    """Scrape and return clean text content from a given URL for deeper reading."""
    try : 
        resp = requests.get(url, timeout = 8, headers = {"User-Agent" : "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        return soup.get_text(separator = " ", strip = True)[:300]
    except Exception as e:
        return f"Could not scrape URL : {str(e)}"



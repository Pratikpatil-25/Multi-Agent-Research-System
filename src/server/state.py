from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
import operator


class State(TypedDict):
    topic: str

    # Full chat history for the Writer <-> Tool loop. 
    messages: Annotated[list, add_messages]

    attempt: int
    is_approved: bool

    # Real list of URL strings (filled in by search_node after actually
    # calling the web_search tool - see nodes.py)
    urls: list[str]

    # One entry per URL, filled in parallel by single_scraper via Send().
    # `operator.add` merges the lists from all parallel branches together
    # instead of one branch overwriting another.
    scraped_content: Annotated[list[str], operator.add]

    report: str
    feedback: str
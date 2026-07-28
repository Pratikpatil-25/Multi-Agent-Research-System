from logger import logger
from components.tools import web_search, scrape_url
from rich import print

logger.info("-----HELLO-----")
# query = "Lionel Messi"
# res = web_search.invoke(query)
# print(res)

res = scrape_url.invoke("https://thesideblogger.com/how-to-start-writing-on-medium/")
print(res)
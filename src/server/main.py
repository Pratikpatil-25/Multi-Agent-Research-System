from logger import logger
from components.tools import web_search
from rich import print

logger.info("-----HELLO-----")
query = "Lionel Messi"
res = web_search.invoke(query)
print(res)
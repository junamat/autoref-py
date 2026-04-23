from dotenv import load_dotenv
from os import getenv
import aiosu

load_dotenv()


def make_client() -> aiosu.v2.Client:
    return aiosu.v2.Client(
        client_id=getenv("CLIENT_ID"),
        client_secret=getenv("CLIENT_SECRET"),
    )

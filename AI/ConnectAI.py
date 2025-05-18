import os

from dotenv import load_dotenv
from openai import OpenAI


class ConnectAI:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing")
        self.client = OpenAI(api_key=api_key)

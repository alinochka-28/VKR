from dotenv import load_dotenv
import os
load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
DB_URL = os.getenv("DB_URL")
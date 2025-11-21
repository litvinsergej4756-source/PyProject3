import json
from ChatgptAiManager import ChatgptAiManager
from DatabaseProductManager import DatabaseProductManager
from configuration.configurate_logs import setup_logger
import sys
import time

logger = setup_logger()

class MainController:
    def __init__(self):
        self.ai = ChatgptAiManager()
        self.manager = DatabaseProductManager()

    def send_to_chatgpt(self, name, full_prompt):
        #response = self.ai.generate_description(product_name=name, prompt_text=full_prompt)
        response = self.ai.call_itemdesc_with_browsing(prompt_text=full_prompt) 
            
        if not isinstance(response, dict):
            logger.warning(f"⚠️ ChatGPT's response is raw: {response}")
            return None

        formatted_json = json.dumps(response, ensure_ascii=False, indent=4)
        logger.info(f"📤 ChatGPT's response to '{name}':\n{formatted_json}")
        return response

    #The process_all function receives products by limit or pid and processes them one by one
    def process_all(self, limit=None, pid=None):
        logger.info("Start of goods processing")
        if limit is None and pid is None:
            limit = 3
            logger.info("ℹ️ No parameters provided — using default limit=3")

        self.manager.connect()
        try:
            items = self.manager.read_products(limit=limit, pid=pid)
            prompt_text = self.manager.read_prompt(prompt_typ=1)
        finally:
            self.manager.close()

        if not items:
            if pid:
                logger.error(f"❌ Product with ID={pid} not found or already processed")
            else:
                logger.warning("⚠️ There are no products to process")
            return
            
        if not prompt_text:
            logger.error("❌ Prompt is empty or not found!")
            return

        for item in items:
            name = item["name"].strip()
            manufactorId = ""
            if item.get("ean"):
                manufactorId += item["ean"] + " "
            if item.get("upc"):
                manufactorId += item["upc"] + " "
            if manufactorId.strip():
                name += ", weitere Herstellernummer: " + manufactorId

            full_prompt = prompt_text.replace("{name}", item["name"])
            response = self.send_to_chatgpt(item["name"], full_prompt) 
            self.manager.process_product(item, response)
            time.sleep(1)

if __name__ == "__main__":
    limit = None
    pid = None

    #Processes command line arguments, setting limit and pid after checking their numeric format
    for arg in sys.argv[1:]:
        if arg.startswith("count="):
            try:
                limit = int(arg.split("=")[1])
            except ValueError:
                logger.error("❌ Error: count must be a number")
                sys.exit(1)
        elif arg.startswith("pid="):
            try:
                pid = int(arg.split("=")[1])
            except ValueError:
                logger.error("❌ Error: pid must be a number")
                sys.exit(1)

    controller = MainController()
    controller.process_all(limit=limit, pid=pid)
from ContextController import ContextController
from configuration.configurate_logs import setup_logger
from configuration.config import host, user, password, db_name
import re
import pymysql

logger = setup_logger()

class DbModule:
    def __init__(self):
        self.connection = None
        self.context_controller = ContextController()

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=host,
                port=3306,
                user=user,
                password=password,
                database=db_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("✅ successfully connected to MySQL")
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")

    def close(self):
        if self.connection:
            try:
                self.connection.close()
                logger.info("🔒 The connection is closed")
            except:
                pass

    #The read_products function reads products from the database — either one by pid or a list by limit.
    def read_products(self, limit=None, pid=None):
        if self.connection is None or not self.connection.open:
            self.connect()

        items = []
        try:
            items = self.context_controller.fetch_products(self.connection, limit=limit, pid=pid)
            
            logger.info(f"Received {len(items)} items for processing (chatgpt_state IS NULL)")
            
            if items:
                logger.info("📝 Product names:")
                for item in items:
                    print(f"  - {item['name']}")

        except Exception as e:
            logger.error(f"❌ Error reading goods: {e}")
        
        return items
        
    def read_prompt(self, prompt_typ):
        prompt_text = None
        try:
            prompt_text = self.context_controller.fetch_prompt(self.connection, prompt_typ)
            
            if prompt_text:
                logger.info("✅ Prompt successfully loaded from the database")
            else:
                logger.warning(f"⚠️ Prompt not found for type")
                
        except Exception as e:
            logger.error(f"❌ Error reading prompt: {e}")
        
        return prompt_text
    
    @staticmethod
    def array_to_html_table(array):
        if not array or not isinstance(array, list):
            return ""

        html = """
            <table class='item-compability-table'>
                <tr>
                    <th>Marke</th>
                    <th>Modell</th>
                    <th>Baujahr</th>
                    <th>Motorvarianten</th>
                    <th>Bemerkung</th>
                </tr>
            """

        for item in array:
            html += f"""
        <tr>
            <td>{item.get('marke', '')}</td>
            <td>{item.get('modell', '')}</td>
            <td>{item.get('baujahr_von', '')} - {item.get('baujahr_bis', '')}</td>
            <td>{'<br>'.join(item.get('motorvarianten', []))}</td>
            <td>{item.get('bemerkung', '')}</td>
        </tr>
            """

        html += "</table>"
        return html
    
    @staticmethod
    def array_to_string(array):
        if not array or not isinstance(array, list):
            return ""
        return ", ".join(array)
    
    def update_database(self, product_id, response_json):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT description
                FROM oc_product_description
                WHERE product_id = %s
            """, (product_id,))
            row = cursor.fetchone()
            old_description = row["description"] if row and row["description"] else ""

            description_html = response_json.get("Verkaufstext", "")
            description_html = re.sub(r"(?<!<br>)(?<=\.)\s+", "<br/>", description_html)

            meta_description = response_json.get("titel", "")
            meta_keyword = response_json.get("Kurzbeschreibung", "")
            seo_keyword = response_json.get("SEO", "")
            oenummer = self.array_to_string(response_json.get("OE-Nummer", []))
            quelle =  self.array_to_string(response_json.get("Quelle", []))
            if oenummer:
                oenummer="<div class='item-oe-nummer'>OE-Nummer: " + oenummer + "</div>"
            if quelle:
                quelle="<div class='item-quelle'>Quelle: <br/>" + quelle + "</div>" 

            compare_text = self.array_to_html_table(response_json.get("kompatibilität", []))           

            block1 = f"<div class='item-desc-text'>{description_html}</div>"
            block2 = f"<div class='item-compability-block'><h4>Kompatibilitätsliste</h4>{compare_text}</div>"
            full_description = f"<div class='item-desc-text'>{old_description}</div>{block1}{oenummer}{block2}{quelle}".strip()

            sql1 = """
                UPDATE oc_product_description
                SET description = %s,
                    meta_description = %s,
                    meta_keyword = %s,
                    seo_keyword = %s
                WHERE product_id = %s
            """
            cursor.execute(sql1, (full_description, meta_description, meta_keyword, seo_keyword, product_id))
            sql2 = """
                UPDATE oc_product
                SET chatgpt_state = 1, chatgpt_calltime = NOW()
                WHERE product_id = %s
            """
            cursor.execute(sql2, (product_id))
            self.connection.commit()
            logger.info(f"✅ Updated product {product_id}, chatgpt_state=1")

        except Exception as e:
            logger.error(f"❌ Database update error: {e}")

    def process_product(self, item, response):
        product_id = item["product_id"]
        name = item.get("name", "").strip()

        logger.info(f"Processing of Item ID={product_id}, Name='{name}'")

        self.connect()
        try:
            cursor = self.connection.cursor()
            if response is None or "error" in response:
                cursor.execute("""
                    UPDATE oc_product
                    SET chatgpt_calltime = NOW()
                    WHERE product_id = %s
                """, (product_id,))
                self.connection.commit()
                logger.warning(f"⚠️ ChatGPT returned error → product {product_id} left with chatgpt_state=NULL")
            else:
                self.update_database(product_id, response)

        except Exception as e:
            logger.error(f"❌ Error in process_product for ID={product_id}: {e}")

        finally:
            self.close()

    #The fetch_products_and_prompt function retrieves products and the corresponding prompt from the database.
    def fetch_products_and_prompt(self, limit=None, pid=None, prompt_typ=1):
        self.connect()
        try:
            items = self.read_products(limit=limit, pid=pid)
            prompt_text = self.read_prompt(prompt_typ)
            return items, prompt_text
        finally:
            self.close()
            
    #The function processes a JSONL result set (with multiple products) and updates the corresponding products in the database.
    def process_batch_results(self, jsonl_results_text):
        successful_updates = 0
        
        for data in self.context_controller.parse_jsonl_results(jsonl_results_text):
            product_id = -1
            try:
                product_id, response_json, log_output, error_message = \
                    self.context_controller.process_single_batch_result(data)
                
                if not product_id or not isinstance(product_id, int):
                    continue

                if response_json:
                    if log_output:
                        print(log_output)
                        logger.info(log_output)

                    items_list = self.read_products(pid=product_id)
                    item = items_list[0] if items_list else None
                    
                    if item:
                        self.process_product(item, response_json) 
                        successful_updates += 1
                    else:
                        logger.error(f"❌ Product ID={product_id} not found in DB for update.")

                elif error_message:
                    logger.error(f"❌ Batch error for ID={product_id}: {error_message}")
                    print(f"❌ Batch error for ID={product_id}: {error_message}")

            except Exception as e:
                logger.error(f"💥 Critical Loop Error processing item {product_id}: {e}")

        logger.info(f"🎉 Batch results processing finished. Updated {successful_updates} products.")
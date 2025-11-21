import pymysql
from configuration.config import host, user, password, db_name
from configuration.configurate_logs import setup_logger
import re

logger = setup_logger()

class DatabaseProductManager:
    def __init__(self):
        self.connection = None

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
        if self.connection is None:
            self.connect()

        if pid is not None:
            WHERE_PART = "WHERE oc_product.product_id = %s"
        else:
            WHERE_PART = ("WHERE oc_product.chatgpt_state IS NULL AND oc_product.status=1 AND price>0")

        items = []
        try:
            with self.connection.cursor() as cursor:
                sql3 = f"""SELECT oc_product_description.product_id, name, upc, ean 
                        FROM oc_product_description join oc_product on oc_product_description.product_id = oc_product.product_id
                        {WHERE_PART}
                        ORDER BY oc_product.product_id DESC
                    """
                if pid is not None:
                    params = (pid,)
                else:
                    sql3 += "LIMIT %s"
                    params = (limit,)

                cursor.execute(sql3, params)
                items = cursor.fetchall()
                logger.info(f"Received {len(items)} items for processing (chatgpt_state IS NULL)")
                logger.info("📝 Product names:")
                for item in items:
                    print(f"  - {item['name']}")
        except Exception as e:
            logger.error(f"❌ Error reading goods: {e}")
        
        return items
    
    def read_prompt(self, prompt_typ):
        prompt_text = None
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT prompt_text FROM oc_prompts_ai WHERE prompt_typ = %s", (prompt_typ,))
                row = cursor.fetchone()
                prompt_text = row["prompt_text"] if row else None
                logger.info("✅ Prompt successfully loaded from the database")
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
            finally:
                self.close()
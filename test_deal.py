from src.crm_client import HubSpotCRMClient
from dotenv import load_dotenv
load_dotenv()

client = HubSpotCRMClient()

print("Testing Deal Creation...")
deal_data = {
    "deal_name": "Test Deal Q4",
    "value": 45000,
    "sales_stage": "4148505288"
}
try:
    did = client.create_deal(deal_data)
    print(f"Created Deal ID: {did}")
except Exception as e:
    print(f"Error: {e}")

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MODEL_NAME = 'gemini-flash-lite-latest'
CRM_MODE = os.getenv('CRM_MODE', 'mock')
CONFIDENCE_THRESHOLD = 0.7
HIGH_CONFIDENCE_THRESHOLD = 0.9

VALID_DEAL_STAGES = {
    "appointmentscheduled": "4148505287",
    "qualifiedtobuy": "4148505288",
    "presentationscheduled": "4148505289",
    "decisionmakerboughtin": "4148505290",
    "contractsent": "4148505291",
    "closedwon": "4148505292",
    "closedlost": "4148505293"
}

VALID_CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD"]

REQUIRED_CONTACT_FIELDS = ["name"]
REQUIRED_COMPANY_FIELDS = ["name"]
REQUIRED_DEAL_FIELDS = ["deal_name"]

MAX_RETRIES = 3

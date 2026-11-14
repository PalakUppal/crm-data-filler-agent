import sys
sys.path.append('.')
from src.schemas import ExtractedContact, ExtractedField
from pydantic import BaseModel

contact = ExtractedContact(
    name=ExtractedField(value="Marcus Rodriguez", confidence=0.9, evidence=[]),
    email=ExtractedField(value="m@dataforge.io", confidence=0.9, evidence=[])
)

data = {k: v.get("value") for k, v in contact.model_dump().items() if isinstance(v, dict) and v.get("value") is not None}

print("Contact model_dump:", contact.model_dump())
print("Extracted data:", data)

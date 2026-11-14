from src.pipeline import process_meeting_summary
import json

summary = """Met with the team from DataForge Analytics regarding the "Q4 Data Pipeline Modernization" deal. Marcus Rodriguez (Director of IT) was there, along with Priya Sharma from their procurement department. Marcus is clearly the technical decision maker and his main concern is migration downtime. Priya is focused on the contract terms. DataForge has about 500 employees. We discussed a pilot program valued at $45,000 USD. Marcus's email is m.rodriguez@dataforge.io. Priya didn't give her email, but asked us to send the vendor onboarding forms to Marcus. They currently use legacy on-premise servers. Next step is to send the security whitepaper and the draft contract. Deal is in the "qualifiedtobuy" stage. Also, they mentioned they are partnering with a consulting firm called BrightPath Solutions to manage the implementation."""

result = process_meeting_summary(summary)

print("\n--- OPERATIONS ---")
for op in result.operations:
    print(f"[{op.operation_type}] {op.entity_type}: {op.entity_name}")
    print(f"  Data: {op.data}")
    print(f"  Reason: {op.reason}\n")

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from fuzzywuzzy import fuzz
import uuid
import os
import requests

class CRMClient(ABC):
    @abstractmethod
    def search_contacts(self, **kwargs) -> List[Dict]: pass
    @abstractmethod
    def search_companies(self, **kwargs) -> List[Dict]: pass
    @abstractmethod
    def search_deals(self, **kwargs) -> List[Dict]: pass
    @abstractmethod
    def create_contact(self, data: Dict) -> str: pass
    @abstractmethod
    def update_contact(self, id: str, data: Dict) -> bool: pass
    @abstractmethod
    def create_company(self, data: Dict) -> str: pass
    @abstractmethod
    def update_company(self, id: str, data: Dict) -> bool: pass
    @abstractmethod
    def create_deal(self, data: Dict) -> str: pass
    @abstractmethod
    def update_deal(self, id: str, data: Dict) -> bool: pass
    
class MockCRMClient(CRMClient):
    def __init__(self):
        print('🔧 CRM MODE: MOCK')
        self.contacts = [
            {"id": "c1", "name": "Sarah Chen", "email": "sarah.chen@nexaflow.com", "phone": "555-0100", "company": "NexaFlow Technologies"},
            {"id": "c2", "name": "Marcus Rodriguez", "email": "m.rodriguez@brightpath.net", "phone": "555-0200", "company": "BrightPath Solutions"},
            {"id": "c3", "name": "Alex Wong", "email": "alex@dataforge.io", "phone": "555-0300", "company": "DataForge Analytics"}
        ]
        self.companies = [
            {"id": "comp1", "name": "NexaFlow Technologies", "domain": "nexaflow.com"},
            {"id": "comp2", "name": "BrightPath Solutions", "domain": "brightpath.net"},
            {"id": "comp3", "name": "DataForge Analytics", "domain": "dataforge.io"}
        ]
        self.deals = [
            {"id": "d1", "name": "NexaFlow Q3 Enterprise Upgrade", "amount": 150000, "stage": "Proposal"},
            {"id": "d2", "name": "BrightPath Pilot", "amount": 50000, "stage": "Lead"}
        ]

    def _fuzzy_search(self, query: str, data: List[Dict], field: str) -> List[Dict]:
        return [item for item in data if fuzz.ratio(query.lower(), str(item.get(field, "")).lower()) > 80]

    def search_contacts(self, **kwargs) -> List[Dict]:
        res = self.contacts
        if 'email' in kwargs: res = [c for c in res if c.get('email') == kwargs['email']]
        if 'phone' in kwargs: res = [c for c in res if c.get('phone') == kwargs['phone']]
        if 'name' in kwargs: res = self._fuzzy_search(kwargs['name'], res, 'name')
        return res

    def search_companies(self, **kwargs) -> List[Dict]:
        res = self.companies
        if 'domain' in kwargs: res = [c for c in res if c.get('domain') == kwargs['domain']]
        if 'name' in kwargs: res = self._fuzzy_search(kwargs['name'], res, 'name')
        return res

    def search_deals(self, **kwargs) -> List[Dict]:
        if 'name' in kwargs: return self._fuzzy_search(kwargs['name'], self.deals, 'name')
        return self.deals

    def create_contact(self, data: Dict) -> str:
        new_id = str(uuid.uuid4())[:8]
        self.contacts.append({"id": new_id, **data})
        return new_id

    def update_contact(self, id: str, data: Dict) -> bool:
        for c in self.contacts:
            if c['id'] == id: c.update(data); return True
        return False

    def create_company(self, data: Dict) -> str:
        new_id = str(uuid.uuid4())[:8]
        self.companies.append({"id": new_id, **data})
        return new_id

    def update_company(self, id: str, data: Dict) -> bool:
        for c in self.companies:
            if c['id'] == id: c.update(data); return True
        return False

    def create_deal(self, data: Dict) -> str:
        new_id = str(uuid.uuid4())[:8]
        self.deals.append({"id": new_id, **data})
        return new_id

    def update_deal(self, id: str, data: Dict) -> bool:
        for d in self.deals:
            if d['id'] == id: d.update(data); return True
        return False

class HubSpotCRMClient(CRMClient):
    def __init__(self):
        print('🔧 CRM MODE: HUBSPOT')
        self.api_key = os.getenv("HUBSPOT_API_KEY")
        if not self.api_key:
            raise ValueError("HUBSPOT_API_KEY environment variable is missing")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.hubapi.com/crm/v3/objects"

    def _search(self, object_type: str, query: str, property_name: str) -> List[Dict]:
        url = f"{self.base_url}/{object_type}/search"
        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": property_name,
                            "operator": "EQ",
                            "value": query
                        }
                    ]
                }
            ]
        }
        resp = requests.post(url, headers=self.headers, json=payload)
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            return [{"id": r["id"], **r.get("properties", {})} for r in results]
        return []

    def search_contacts(self, **kwargs) -> List[Dict]:
        if 'email' in kwargs:
            return self._search("contacts", kwargs['email'], "email")
        if 'phone' in kwargs:
            return self._search("contacts", kwargs['phone'], "phone")
        return []

    def search_companies(self, **kwargs) -> List[Dict]:
        if 'domain' in kwargs:
            return self._search("companies", kwargs['domain'], "domain")
        return []

    def search_deals(self, **kwargs) -> List[Dict]:
        if 'name' in kwargs:
            return self._search("deals", kwargs['name'], "dealname")
        return []

    def _map_contact(self, data: Dict) -> Dict:
        mapped = {}
        if 'name' in data and data['name']:
            parts = str(data['name']).split(' ', 1)
            mapped['firstname'] = parts[0]
            if len(parts) > 1:
                mapped['lastname'] = parts[1]
        if 'email' in data and data['email']: mapped['email'] = str(data['email'])
        if 'phone' in data and data['phone']: mapped['phone'] = str(data['phone'])
        if 'designation_title' in data and data['designation_title']: mapped['jobtitle'] = str(data['designation_title'])
        return mapped

    def _map_company(self, data: Dict) -> Dict:
        mapped = {}
        if 'name' in data and data['name']: mapped['name'] = str(data['name'])
        if 'industry' in data and data['industry']: mapped['industry'] = str(data['industry'])
        if 'employee_count' in data and data['employee_count']: mapped['numberofemployees'] = str(data['employee_count'])
        if 'website' in data and data['website']: mapped['domain'] = str(data['website'])
        return mapped

    def _map_deal(self, data: Dict) -> Dict:
        mapped = {}
        if 'deal_name' in data and data['deal_name']: mapped['dealname'] = str(data['deal_name'])
        if 'value' in data and data['value'] is not None: mapped['amount'] = str(data['value'])
        if 'currency' in data and data['currency']: mapped['deal_currency_code'] = str(data['currency'])
        if 'sales_stage' in data and data['sales_stage']: mapped['dealstage'] = str(data['sales_stage'])
        if 'timeline' in data and data['timeline']: mapped['description'] = f"Timeline: {data['timeline']}"
        return mapped

    def create_contact(self, data: Dict) -> str:
        url = f"{self.base_url}/contacts"
        properties = self._map_contact(data)
        print(f"  📤 HubSpot CREATE contact: {properties}")
        resp = requests.post(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            cid = resp.json().get("id")
            print(f"  ✅ Created contact ID: {cid}")
            return cid
        print(f"  ❌ Failed to create contact: {resp.status_code} {resp.text}")
        return ""

    def update_contact(self, id: str, data: Dict) -> bool:
        url = f"{self.base_url}/contacts/{id}"
        properties = self._map_contact(data)
        print(f"  📤 HubSpot UPDATE contact {id}: {properties}")
        resp = requests.patch(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            print(f"  ✅ Updated contact ID: {id}")
            return True
        print(f"  ❌ Failed to update contact: {resp.status_code} {resp.text}")
        return False

    def create_company(self, data: Dict) -> str:
        # First check if HubSpot already auto-created a company from the domain
        properties = self._map_company(data)
        domain = properties.get('domain', '')
        if domain:
            existing = self._search("companies", domain, "domain")
            if existing:
                print(f"  ⚠️ Company with domain '{domain}' already exists (ID: {existing[0]['id']}), updating instead.")
                return self.update_company(existing[0]['id'], data) and existing[0]['id'] or ""
        else:
            company_name = properties.get('name', '')
            if company_name:
                existing = self._search("companies", company_name, "name")
                if not existing:
                    first_word = company_name.split()[0]
                    if len(first_word) > 3:
                        existing = self._search("companies", first_word, "name")
                        
                if existing:
                    print(f"  ⚠️ Company '{company_name}' already exists (ID: {existing[0]['id']}), updating instead.")
                    return self.update_company(existing[0]['id'], data) and existing[0]['id'] or ""

        url = f"{self.base_url}/companies"
        print(f"  📤 HubSpot CREATE company: {properties}")
        resp = requests.post(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            cid = resp.json().get("id")
            print(f"  ✅ Created company ID: {cid}")
            return cid
        print(f"  ❌ Failed to create company: {resp.status_code} {resp.text}")
        return ""

    def update_company(self, id: str, data: Dict) -> bool:
        url = f"{self.base_url}/companies/{id}"
        properties = self._map_company(data)
        print(f"  📤 HubSpot UPDATE company {id}: {properties}")
        resp = requests.patch(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            print(f"  ✅ Updated company ID: {id}")
            return True
        print(f"  ❌ Failed to update company: {resp.status_code} {resp.text}")
        return False

    def create_deal(self, data: Dict) -> str:
        url = f"{self.base_url}/deals"
        properties = self._map_deal(data)
        print(f"  📤 HubSpot CREATE deal: {properties}")
        resp = requests.post(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            did = resp.json().get("id")
            print(f"  ✅ Created deal ID: {did}")
            return did
        print(f"  ❌ Failed to create deal: {resp.status_code} {resp.text}")
        return ""

    def update_deal(self, id: str, data: Dict) -> bool:
        url = f"{self.base_url}/deals/{id}"
        properties = self._map_deal(data)
        print(f"  📤 HubSpot UPDATE deal {id}: {properties}")
        resp = requests.patch(url, headers=self.headers, json={"properties": properties})
        if resp.status_code in (200, 201):
            print(f"  ✅ Updated deal ID: {id}")
            return True
        print(f"  ❌ Failed to update deal: {resp.status_code} {resp.text}")
        return False

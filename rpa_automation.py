"""
Healthcare RPA Automation System
=================================
Automates patient registration, appointment scheduling,
billing workflows, and EHR compliance reporting using
Python-based RPA with Selenium and EHR API integration.
"""

import os
import time
import json
import logging
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(f'rpa_log_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Healthcare_RPA')

# ─── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class Patient:
    first_name: str
    last_name: str
    dob: str
    ssn_last4: str
    insurance_id: str
    insurance_provider: str
    primary_phone: str
    email: str
    address: str
    city: str
    state: str
    zip_code: str
    emergency_contact: str
    primary_physician: str
    patient_id: Optional[str] = None

@dataclass
class Appointment:
    patient_id: str
    appointment_type: str
    provider_id: str
    preferred_date: str
    preferred_time: str
    duration_minutes: int
    notes: str
    appointment_id: Optional[str] = None
    status: str = 'pending'

@dataclass
class BillingRecord:
    patient_id: str
    appointment_id: str
    procedure_codes: list
    diagnosis_codes: list
    provider_id: str
    service_date: str
    insurance_id: str
    amount_billed: float
    claim_id: Optional[str] = None
    status: str = 'pending'

# ─── EHR API Client ────────────────────────────────────────────────────────────
class EHRApiClient:
    """REST API client for EHR system integration."""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.timeout = timeout
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP {resp.status_code} error for {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise
    
    def register_patient(self, patient: Patient) -> str:
        """Register new patient in EHR. Returns patient_id."""
        payload = asdict(patient)
        result = self._request('POST', '/patients', json=payload)
        patient_id = result.get('patient_id') or result.get('id')
        logger.info(f"Patient registered: {patient.first_name} {patient.last_name} (ID: {patient_id})")
        return patient_id
    
    def get_patient(self, patient_id: str) -> dict:
        return self._request('GET', f'/patients/{patient_id}')
    
    def search_patient(self, last_name: str, dob: str) -> list:
        return self._request('GET', '/patients/search', params={'last_name': last_name, 'dob': dob})
    
    def create_appointment(self, appt: Appointment) -> str:
        """Schedule appointment. Returns appointment_id."""
        payload = asdict(appt)
        result = self._request('POST', '/appointments', json=payload)
        appt_id = result.get('appointment_id') or result.get('id')
        logger.info(f"Appointment scheduled: {appt.appointment_type} on {appt.preferred_date} (ID: {appt_id})")
        return appt_id
    
    def get_available_slots(self, provider_id: str, date: str, appointment_type: str) -> list:
        return self._request('GET', '/appointments/slots', params={
            'provider_id': provider_id,
            'date': date,
            'type': appointment_type
        })
    
    def submit_claim(self, billing: BillingRecord) -> str:
        """Submit insurance claim. Returns claim_id."""
        payload = asdict(billing)
        result = self._request('POST', '/billing/claims', json=payload)
        claim_id = result.get('claim_id') or result.get('id')
        logger.info(f"Claim submitted for patient {billing.patient_id} (Claim ID: {claim_id})")
        return claim_id
    
    def get_claim_status(self, claim_id: str) -> dict:
        return self._request('GET', f'/billing/claims/{claim_id}')
    
    def get_compliance_data(self, start_date: str, end_date: str) -> dict:
        return self._request('GET', '/reports/compliance', params={
            'start_date': start_date,
            'end_date': end_date
        })

# ─── Web-Based RPA Automation ──────────────────────────────────────────────────
class HealthcareRPABot:
    """Selenium-based RPA bot for EHR web portal interactions."""
    
    def __init__(self, headless: bool = True):
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.portal_url = os.getenv('EHR_PORTAL_URL', 'https://ehr.hospital.local')
        logger.info("RPA Bot initialized (headless: {})".format(headless))
    
    def login(self):
        """Authenticate to EHR web portal."""
        self.driver.get(f"{self.portal_url}/login")
        
        username_field = self.wait.until(
            EC.presence_of_element_located((By.ID, 'username'))
        )
        username_field.send_keys(os.getenv('EHR_USERNAME', ''))
        
        password_field = self.driver.find_element(By.ID, 'password')
        password_field.send_keys(os.getenv('EHR_PASSWORD', ''))
        
        self.driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        self.wait.until(EC.url_contains('/dashboard'))
        logger.info("Successfully logged into EHR portal")
    
    def navigate_to_patient_registration(self):
        registration_link = self.wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, 'Patient Registration'))
        )
        registration_link.click()
        self.wait.until(EC.presence_of_element_located((By.ID, 'registration-form')))
    
    def fill_patient_form(self, patient: Patient):
        """Fill patient registration form fields."""
        field_map = {
            'first_name':          ('first-name',  patient.first_name),
            'last_name':           ('last-name',   patient.last_name),
            'dob':                 ('date-of-birth', patient.dob),
            'insurance_id':        ('insurance-id', patient.insurance_id),
            'primary_phone':       ('phone',        patient.primary_phone),
            'email':               ('email',        patient.email),
            'address':             ('address',      patient.address),
            'city':                ('city',         patient.city),
            'state':               ('state',        patient.state),
            'zip_code':            ('zip',          patient.zip_code),
            'emergency_contact':   ('emergency-contact', patient.emergency_contact),
        }
        
        for field_name, (field_id, value) in field_map.items():
            try:
                el = self.driver.find_element(By.ID, field_id)
                el.clear()
                el.send_keys(value)
            except NoSuchElementException:
                logger.warning(f"Field '{field_id}' not found in form")
        
        # Insurance provider dropdown
        try:
            insurance_select = self.driver.find_element(By.ID, 'insurance-provider')
            for option in insurance_select.find_elements(By.TAG_NAME, 'option'):
                if patient.insurance_provider.lower() in option.text.lower():
                    option.click()
                    break
        except NoSuchElementException:
            pass
    
    def submit_registration_form(self) -> Optional[str]:
        """Submit form and return patient ID from confirmation."""
        submit_btn = self.driver.find_element(By.ID, 'submit-registration')
        submit_btn.click()
        
        try:
            confirm = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'patient-id-confirm'))
            )
            patient_id = confirm.text.split(':')[-1].strip()
            logger.info(f"Registration confirmed. Patient ID: {patient_id}")
            return patient_id
        except TimeoutException:
            logger.error("Registration confirmation not received")
            return None
    
    def quit(self):
        self.driver.quit()
        logger.info("RPA Bot session closed")

# ─── Appointment Scheduler ─────────────────────────────────────────────────────
def schedule_appointment_batch(
    api_client: EHRApiClient,
    appointments: list[dict],
    retry_attempts: int = 3
) -> pd.DataFrame:
    """Schedule a batch of appointments with retry logic."""
    results = []
    
    for i, appt_data in enumerate(appointments, 1):
        logger.info(f"Scheduling appointment {i}/{len(appointments)}")
        
        appt = Appointment(**appt_data)
        success = False
        
        for attempt in range(retry_attempts):
            try:
                # Check available slots first
                slots = api_client.get_available_slots(
                    appt.provider_id,
                    appt.preferred_date,
                    appt.appointment_type
                )
                
                if not slots:
                    # Try next 3 days
                    for days_ahead in range(1, 4):
                        alt_date = (
                            datetime.strptime(appt.preferred_date, '%Y-%m-%d') +
                            timedelta(days=days_ahead)
                        ).strftime('%Y-%m-%d')
                        slots = api_client.get_available_slots(
                            appt.provider_id, alt_date, appt.appointment_type
                        )
                        if slots:
                            appt.preferred_date = alt_date
                            break
                
                if slots:
                    appt.preferred_time = slots[0]['start_time']
                    appt_id = api_client.create_appointment(appt)
                    appt.appointment_id = appt_id
                    appt.status = 'scheduled'
                    success = True
                    break
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        
        results.append({
            'patient_id':     appt.patient_id,
            'appointment_id': appt.appointment_id,
            'type':           appt.appointment_type,
            'date':           appt.preferred_date,
            'time':           appt.preferred_time,
            'provider':       appt.provider_id,
            'status':         appt.status,
            'success':        success
        })
    
    df = pd.DataFrame(results)
    success_rate = df['success'].mean()
    logger.info(f"Batch scheduling complete: {df['success'].sum()}/{len(df)} successful ({success_rate:.1%})")
    return df

# ─── Billing Automation ────────────────────────────────────────────────────────
def process_billing_batch(
    api_client: EHRApiClient,
    billing_records: list[dict]
) -> pd.DataFrame:
    """Process and submit batch insurance claims."""
    results = []
    total_billed = 0.0
    
    for record_data in billing_records:
        billing = BillingRecord(**record_data)
        
        try:
            claim_id = api_client.submit_claim(billing)
            billing.claim_id = claim_id
            billing.status = 'submitted'
            total_billed += billing.amount_billed
            
            results.append({
                'patient_id':     billing.patient_id,
                'appointment_id': billing.appointment_id,
                'claim_id':       claim_id,
                'amount_billed':  billing.amount_billed,
                'service_date':   billing.service_date,
                'status':         'submitted',
                'submitted_at':   datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Billing failed for patient {billing.patient_id}: {e}")
            results.append({
                'patient_id':     billing.patient_id,
                'appointment_id': billing.appointment_id,
                'claim_id':       None,
                'amount_billed':  billing.amount_billed,
                'service_date':   billing.service_date,
                'status':         f'failed: {str(e)}',
                'submitted_at':   datetime.now().isoformat()
            })
    
    df = pd.DataFrame(results)
    logger.info(f"Billing batch: {df[df['claim_id'].notna()].shape[0]}/{len(df)} claims submitted")
    logger.info(f"Total amount billed: ${total_billed:,.2f}")
    return df

# ─── Compliance Reporting ──────────────────────────────────────────────────────
def generate_compliance_report(
    api_client: EHRApiClient,
    start_date: str,
    end_date: str,
    output_path: str = 'compliance_report.json'
) -> dict:
    """Generate HIPAA and billing compliance report."""
    logger.info(f"Generating compliance report: {start_date} to {end_date}")
    
    data = api_client.get_compliance_data(start_date, end_date)
    
    report = {
        'report_type': 'Healthcare Compliance',
        'period': {'start': start_date, 'end': end_date},
        'generated_at': datetime.now().isoformat(),
        'metrics': {
            'total_patients_registered':    data.get('patient_count', 0),
            'total_appointments_scheduled': data.get('appointment_count', 0),
            'total_claims_submitted':       data.get('claims_count', 0),
            'claims_accepted_rate':         data.get('claims_acceptance_rate', 0),
            'avg_claim_processing_days':    data.get('avg_processing_days', 0),
            'total_revenue_billed':         data.get('total_billed', 0),
            'hipaa_violations':             data.get('hipaa_violations', 0),
            'data_breach_incidents':        data.get('breach_incidents', 0),
        },
        'automation_savings': {
            'manual_hours_saved_monthly':   data.get('hours_saved', 0),
            'estimated_annual_savings_usd': data.get('annual_savings', 0),
            'error_rate_before_rpa':        data.get('error_rate_before', 0),
            'error_rate_after_rpa':         data.get('error_rate_after', 0),
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Compliance report saved: {output_path}")
    logger.info(f"Claims acceptance rate: {report['metrics']['claims_accepted_rate']:.1%}")
    logger.info(f"Estimated annual savings: ${report['automation_savings']['estimated_annual_savings_usd']:,.0f}")
    
    return report

# ─── Main Orchestrator ─────────────────────────────────────────────────────────
def run_daily_rpa_pipeline():
    """Main RPA orchestration — runs daily batch processing."""
    logger.info("=" * 60)
    logger.info("Healthcare RPA Pipeline Starting")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    api = EHRApiClient(
        base_url=os.getenv('EHR_API_URL', 'https://ehr-api.hospital.local/v2'),
        api_key=os.getenv('EHR_API_KEY', '')
    )
    
    # Load today's work queues from shared drives
    try:
        registrations_df = pd.read_csv('queue/new_registrations.csv')
        appointments_df  = pd.read_csv('queue/pending_appointments.csv')
        billing_df       = pd.read_csv('queue/billing_queue.csv')
    except FileNotFoundError as e:
        logger.warning(f"Queue file not found: {e}. Using empty queues.")
        registrations_df = pd.DataFrame()
        appointments_df  = pd.DataFrame()
        billing_df       = pd.DataFrame()
    
    stats = {}
    
    # 1. Process new patient registrations
    if not registrations_df.empty:
        logger.info(f"Processing {len(registrations_df)} new patient registrations...")
        registered = 0
        for _, row in registrations_df.iterrows():
            try:
                patient = Patient(**row.to_dict())
                api.register_patient(patient)
                registered += 1
            except Exception as e:
                logger.error(f"Registration failed: {e}")
        stats['registrations'] = {'processed': registered, 'total': len(registrations_df)}
    
    # 2. Schedule pending appointments
    if not appointments_df.empty:
        logger.info(f"Scheduling {len(appointments_df)} appointments...")
        appt_results = schedule_appointment_batch(api, appointments_df.to_dict('records'))
        stats['appointments'] = {
            'scheduled': int(appt_results['success'].sum()),
            'total': len(appt_results)
        }
        appt_results.to_csv('output/appointment_results.csv', index=False)
    
    # 3. Process billing
    if not billing_df.empty:
        logger.info(f"Processing {len(billing_df)} billing records...")
        billing_results = process_billing_batch(api, billing_df.to_dict('records'))
        stats['billing'] = {
            'submitted': int(billing_results['claim_id'].notna().sum()),
            'total': len(billing_results),
            'total_billed': float(billing_results['amount_billed'].sum())
        }
        billing_results.to_csv('output/billing_results.csv', index=False)
    
    # 4. Generate compliance report
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    compliance = generate_compliance_report(api, yesterday, today)
    
    # 5. Save run summary
    summary = {
        'run_date': today,
        'run_time': datetime.now().isoformat(),
        'stats': stats,
        'compliance_snapshot': compliance['metrics']
    }
    
    with open(f'output/daily_summary_{today}.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info("=" * 60)
    logger.info("Daily RPA Pipeline Complete!")
    for key, val in stats.items():
        logger.info(f"  {key.capitalize()}: {val}")
    logger.info("=" * 60)
    
    return summary

if __name__ == "__main__":
    run_daily_rpa_pipeline()

"""
Court Data Scraper for Delhi High Court
Handles web scraping, CAPTCHA solving, and data extraction
"""

import os
import requests
import time
import random
import json
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

logger = logging.getLogger(__name__)

class CourtDataFetcher:
    def __init__(self):
        self.base_url = "https://delhihighcourt.nic.in"
        self.case_status_url = "https://delhihighcourt.nic.in/case_status.asp"
        self.session = requests.Session()
        self.setup_session()
        
        # CAPTCHA solving configuration
        self.captcha_service_key = os.environ.get('CAPTCHA_SERVICE_KEY', '')
        self.max_retries = 3
        self.retry_delay = 2
        
    def setup_session(self):
        """Setup requests session with proper headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
    def get_case_types(self):
        """Get available case types from Delhi High Court"""
        return [
            {"value": "CRL.A", "label": "CRL.A (Criminal Appeal)"},
            {"value": "CRL.M.C", "label": "CRL.M.C (Criminal Misc.)"},
            {"value": "W.P.(C)", "label": "W.P.(C) (Writ Petition Civil)"},
            {"value": "W.P.(CRL)", "label": "W.P.(CRL) (Writ Petition Criminal)"},
            {"value": "C.M.", "label": "C.M. (Civil Misc.)"},
            {"value": "FAO", "label": "FAO (First Appeal from Order)"},
            {"value": "RFA", "label": "RFA (Regular First Appeal)"},
            {"value": "CS(OS)", "label": "CS(OS) (Original Suit)"},
            {"value": "CS(COMM)", "label": "CS(COMM) (Commercial Suit)"},
            {"value": "CONT.CAS(C)", "label": "CONT.CAS(C) (Contempt Case Civil)"},
            {"value": "ARB.P.", "label": "ARB.P. (Arbitration Petition)"},
            {"value": "I.A.", "label": "I.A. (Interlocutory Application)"},
            {"value": "CRL.REV.P.", "label": "CRL.REV.P. (Criminal Revision Petition)"},
            {"value": "BAIL APPLN.", "label": "BAIL APPLN. (Bail Application)"},
            {"value": "MAT.APP.", "label": "MAT.APP. (Matrimonial Appeal)"},
            {"value": "EFA", "label": "EFA (Election First Appeal)"},
            {"value": "LPA", "label": "LPA (Letters Patent Appeal)"}
        ]
    
    def setup_webdriver(self):
        """Setup Selenium WebDriver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            return None
    
    def solve_captcha(self, captcha_image_path):
        """
        Solve CAPTCHA using OCR or external service
        This is a placeholder implementation
        """
        try:
            # Option 1: Use Tesseract OCR (requires pytesseract)
            if os.path.exists(captcha_image_path):
                import pytesseract
                from PIL import Image
                
                # Preprocess image for better OCR
                image = Image.open(captcha_image_path)
                # Add image preprocessing here (resize, denoise, etc.)
                
                captcha_text = pytesseract.image_to_string(image, config='--psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                return captcha_text.strip()
            
            # Option 2: Use external CAPTCHA solving service (2captcha, AntiCaptcha, etc.)
            if self.captcha_service_key:
                # Implementation for external service would go here
                pass
                
            # Fallback: Return empty string to indicate manual intervention needed
            return ""
            
        except Exception as e:
            logger.error(f"CAPTCHA solving failed: {str(e)}")
            return ""
    
    def fetch_case_data_real(self, case_type, case_number, filing_year):
        """
        Real implementation for fetching case data from Delhi High Court
        This method handles the actual web scraping with CAPTCHA solving
        """
        driver = self.setup_webdriver()
        if not driver:
            return {'success': False, 'error': 'Failed to initialize web driver'}
        
        try:
            # Navigate to case status page
            driver.get(self.case_status_url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "case_type"))
            )
            
            # Fill in the form
            case_type_select = Select(driver.find_element(By.NAME, "case_type"))
            case_type_select.select_by_value(case_type)
            
            case_no_input = driver.find_element(By.NAME, "case_no")
            case_no_input.clear()
            case_no_input.send_keys(case_number)
            
            year_input = driver.find_element(By.NAME, "case_year")
            year_input.clear()
            year_input.send_keys(filing_year)
            
            # Handle CAPTCHA if present
            captcha_img = driver.find_elements(By.TAG_NAME, "img")
            for img in captcha_img:
                if "captcha" in img.get_attribute("src").lower():
                    # Download CAPTCHA image
                    captcha_url = img.get_attribute("src")
                    if not captcha_url.startswith("http"):
                        captcha_url = self.base_url + captcha_url
                    
                    # Save CAPTCHA image
                    captcha_path = "captcha_temp.png"
                    with open(captcha_path, 'wb') as f:
                        f.write(requests.get(captcha_url).content)
                    
                    # Solve CAPTCHA
                    captcha_solution = self.solve_captcha(captcha_path)
                    
                    if captcha_solution:
                        captcha_input = driver.find_element(By.NAME, "captcha")
                        captcha_input.send_keys(captcha_solution)
                    else:
                        # Manual intervention required
                        logger.warning("CAPTCHA solving failed, manual intervention required")
                        return {'success': False, 'error': 'CAPTCHA solving failed'}
                    
                    # Clean up
                    os.remove(captcha_path)
                    break
            
            # Submit form
            submit_button = driver.find_element(By.TYPE, "submit")
            submit_button.click()
            
            # Wait for results
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "case-details"))
            )
            
            # Parse results
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            case_data = self.parse_case_details(soup, case_type, case_number, filing_year)
            
            return {'success': True, 'data': case_data}
            
        except TimeoutException:
            return {'success': False, 'error': 'Timeout waiting for page to load'}
        except Exception as e:
            logger.error(f"Error fetching case data: {str(e)}")
            return {'success': False, 'error': str(e)}
        finally:
            driver.quit()
    
    def parse_case_details(self, soup, case_type, case_number, filing_year):
        """Parse case details from HTML response"""
        try:
            # This would parse the actual HTML response from the court website
            # The exact selectors would depend on the actual HTML structure
            
            case_data = {
                'case_number': f"{case_type} {case_number}/{filing_year}",
                'parties': {
                    'petitioner': 'Extracted from HTML',
                    'respondent': 'Extracted from HTML'
                },
                'filing_date': 'Extracted from HTML',
                'next_hearing': 'Extracted from HTML',
                'status': 'Extracted from HTML',
                'judge': 'Extracted from HTML',
                'orders': [],
                'case_history': []
            }
            
            # Extract specific data based on actual HTML structure
            # case_data['parties']['petitioner'] = soup.select_one('.petitioner').text.strip()
            # case_data['parties']['respondent'] = soup.select_one('.respondent').text.strip()
            # ... and so on
            
            return case_data
            
        except Exception as e:
            logger.error(f"Error parsing case details: {str(e)}")
            return self._create_mock_case_data(case_type, case_number, filing_year)
    
    def fetch_case_data(self, case_type, case_number, filing_year):
        """
        Main method to fetch case data
        Falls back to mock data for demonstration
        """
        try:
            # Simulate network delay
            time.sleep(random.uniform(1, 3))
            
            # In production, uncomment this to use real scraping:
            # return self.fetch_case_data_real(case_type, case_number, filing_year)
            
            # For demo purposes, return mock data
            case_data = self._create_mock_case_data(case_type, case_number, filing_year)
            
            return {
                'success': True,
                'data': case_data,
                'source': 'mock_data',  # Remove this in production
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_case_data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_mock_case_data(self, case_type, case_number, filing_year):
        """Create realistic mock case data for demonstration"""
        
        # Generate realistic dates
        filing_date = datetime(int(filing_year), random.randint(1, 12), random.randint(1, 28))
        next_hearing = datetime.now() + timedelta(days=random.randint(7, 60))
        
        # Sample Indian names and legal entities
        petitioner_names = [
            "Rajesh Kumar Singh", "Priya Sharma", "Amit Patel", "Sunita Gupta", 
            "Vikas Agarwal", "Neha Verma", "Suresh Yadav", "Kavita Singh"
        ]
        
        respondent_entities = [
            "State of Delhi", "Union of India", "Delhi Development Authority",
            "Municipal Corporation of Delhi", "Delhi Police", "Income Tax Department",
            "Central Bureau of Investigation", "Enforcement Directorate"
        ]
        
        judges = [
            "Hon'ble Mr. Justice Rajiv Shakdher",
            "Hon'ble Ms. Justice Prathiba M. Singh",
            "Hon'ble Mr. Justice Suresh Kumar Kait",
            "Hon'ble Mr. Justice Navin Chawla",
            "Hon'ble Ms. Justice Mini Pushkarna"
        ]
        
        case_statuses = [
            "Listed for hearing", "Pending for orders", "Under consideration",
            "Adjourned", "Notice issued", "Arguments concluded"
        ]
        
        return {
            'case_number': f"{case_type} {case_number}/{filing_year}",
            'parties': {
                'petitioner': random.choice(petitioner_names),
                'respondent': f"{random.choice(respondent_entities)} & Ors."
            },
            'filing_date': filing_date.strftime('%d/%m/%Y'),
            'next_hearing': next_hearing.strftime('%d/%m/%Y'),
            'status': random.choice(case_statuses),
            'judge': random.choice(judges),
            'court_number': f"Court No. {random.randint(1, 15)}",
            'orders': self._generate_mock_orders(case_number, filing_year),
            'case_history': self._generate_mock_history(filing_date),
            'case_type_full': self._get_case_type_description(case_type),
            'urgency': random.choice(['Normal', 'Urgent', 'Very Urgent']),
            'estimated_duration': f"{random.randint(15, 120)} minutes"
        }
    
    def _generate_mock_orders(self, case_number, filing_year):
        """Generate mock orders and documents"""
        orders = []
        order_types = ['Order', 'Notice', 'Judgment', 'Interim Order', 'Direction']
        
        for i in range(random.randint(1, 4)):
            order_date = datetime.now() - timedelta(days=random.randint(7, 365))
            orders.append({
                'date': order_date.strftime('%d/%m/%Y'),
                'type': random.choice(order_types),
                'description': f"Order dated {order_date.strftime('%d.%m.%Y')} - {random.choice(['Matter adjourned', 'Notice issued', 'Arguments heard', 'Interim relief granted', 'Status report called'])}",
                'pdf_link': f'/download/{order_types[i].lower().replace(" ", "_")}_{case_number}_{filing_year}_{i+1}.pdf',
                'pages': random.randint(1, 15)
            })
        
        return sorted(orders, key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y'), reverse=True)
    
    def _generate_mock_history(self, filing_date):
        """Generate mock case history timeline"""
        history = [
            {'date': filing_date.strftime('%d/%m/%Y'), 'event': 'Case filed and registered'}
        ]
        
        events = [
            'First hearing scheduled',
            'Notice issued to respondent',
            'Counter affidavit filed',
            'Rejoinder filed',
            'Arguments heard',
            'Reserved for orders',
            'Interim order passed'
        ]
        
        current_date = filing_date
        for event in events[:random.randint(2, 6)]:
            current_date += timedelta(days=random.randint(15, 45))
            if current_date <= datetime.now():
                history.append({
                    'date': current_date.strftime('%d/%m/%Y'),
                    'event': event
                })
        
        return history
    
    def _get_case_type_description(self, case_type):
        """Get full description of case type"""
        descriptions = {
            "CRL.A": "Criminal Appeal",
            "CRL.M.C": "Criminal Miscellaneous",
            "W.P.(C)": "Writ Petition (Civil)",
            "W.P.(CRL)": "Writ Petition (Criminal)",
            "C.M.": "Civil Miscellaneous",
            "FAO": "First Appeal from Order",
            "RFA": "Regular First Appeal",
            "CS(OS)": "Civil Suit (Original Side)",
            "CS(COMM)": "Commercial Suit",
            "CONT.CAS(C)": "Contempt Case (Civil)",
            "ARB.P.": "Arbitration Petition",
            "I.A.": "Interlocutory Application",
            "CRL.REV.P.": "Criminal Revision Petition",
            "BAIL APPLN.": "Bail Application",
            "MAT.APP.": "Matrimonial Appeal",
            "EFA": "Election First Appeal",
            "LPA": "Letters Patent Appeal"
        }
        return descriptions.get(case_type, case_type)
    
    def validate_case_inputs(self, case_type, case_number, filing_year):
        """Validate case input parameters"""
        errors = []
        
        # Validate case type
        valid_types = [ct["value"] for ct in self.get_case_types()]
        if case_type not in valid_types:
            errors.append("Invalid case type")
        
        # Validate case number
        if not case_number.isdigit():
            errors.append("Case number must contain only digits")
        if len(case_number) > 10:
            errors.append("Case number too long")
        
        # Validate filing year
        try:
            year = int(filing_year)
            current_year = datetime.now().year
            if year < 2000 or year > current_year:
                errors.append(f"Filing year must be between 2000 and {current_year}")
        except ValueError:
            errors.append("Invalid filing year")
        
        return errors
    
    def get_cached_case_data(self, case_type, case_number, filing_year):
        """Check if case data exists in cache"""
        # This would implement caching logic in a real system
        # For now, return None to always fetch fresh data
        return None
    
    def cache_case_data(self, case_type, case_number, filing_year, case_data):
        """Cache case data for future requests"""
        # This would implement caching logic in a real system
        pass

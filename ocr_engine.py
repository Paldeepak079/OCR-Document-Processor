import easyocr
import torch
import cv2
import numpy as np
import re
import io
from PIL import Image
from rapidfuzz import fuzz, process

class OCREngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"OCR Engine initialized on {self.device}")
        
        print("Loading EasyOCR model...")
        # Enable Hindi ('hi') support alongside English ('en')
        self.reader = easyocr.Reader(['en', 'hi'], gpu=(self.device == "cuda"))
        print("EasyOCR model loaded.")

    def preprocess_image(self, image_bytes):
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Resize (Upscale if too small, but don't overdo it)
        h, w = gray.shape
        if w < 1000:
            scale = 1000 / w
            new_h = int(h * scale)
            gray = cv2.resize(gray, (1000, new_h))
        
        # 3. Minimal Denoising
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # 4. Gamma Correction (Darken faint text)
        # Gamma < 1.0 makes image darker/contrastier
        gamma = 0.8 
        lookUpTable = np.empty((1,256), np.uint8)
        for i in range(256):
            lookUpTable[0,i] = np.clip(pow(i / 255.0, gamma) * 255.0, 0, 255)
        corrected = cv2.LUT(denoised, lookUpTable)

        # 5. Unsharp Masking (Better sharpening)
        gaussian = cv2.GaussianBlur(corrected, (0, 0), 3.0)
        unsharp_image = cv2.addWeighted(corrected, 1.5, gaussian, -0.5, 0, corrected)

        # Save debug to see what the AI sees
        cv2.imwrite("debug_preprocessed.png", unsharp_image)
        
        return unsharp_image

    def normalize_digits(self, text):
        # Mapping for Hindi (Devanagari) digits to English
        hindi_digits = str.maketrans("०१२३४५६७८९", "0123456789")
        return text.translate(hindi_digits)

    def smart_typo_fixer(self, text, field_type="text"):
        """
        Manually tuned logic to fix common OCR character confusions.
        This is how we 'teach' the system to be smarter!
        """
        if field_type == "digits":
            # Fix letters that look like numbers
            corrections = {
                'O': '0', 'o': '0', 'D': '0',
                'I': '1', 'l': '1', '|': '1',
                'Z': '2', 'z': '2',
                'S': '5', 's': '5',
                'G': '6', 'b': '6',
                'B': '8',
                'g': '9', 'q': '9'
            }
            for char, digit in corrections.items():
                text = text.replace(char, digit)
        return text

    def clean_email(self, text):
        # ... (existing email logic) ...
        # Replace spaces with dots only if they look like they separate parts of a domain or name
        # But for now, let's just be careful. 
        # "john smith@example com" -> "john.smith@example.com" is better than "johnsmith@examplecom"
        
        # First, fix common OCR spacing issues in domains
        text = re.sub(r'@\s+', '@', text) # "user@ example.com" -> "user@example.com"
        text = re.sub(r'\s+\.', '.', text) # "example .com" -> "example.com"
        text = re.sub(r'\.\s+', '.', text) # "example. com" -> "example.com"
        
        # Handle "example com" -> "example.com"
        if "@" in text:
            parts = text.split("@")
            if len(parts) == 2:
                domain = parts[1]
                if " " in domain and "." not in domain:
                    domain = domain.replace(" ", ".")
                parts[1] = domain
                text = "@".join(parts)

        text = text.replace(" ", "").replace(",", ".").replace("..", ".")
        text = text.replace("$com", ".com").replace("$", "s")
        text = text.replace("examp&", "example").replace("&", "e")
        
        if "@" not in text:
            if "at" in text:
                text = text.replace("at", "@")
            elif ".com" in text:
                domains = ["example.com", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
                for d in domains:
                    if d in text:
                        idx = text.find(d)
                        if idx > 0:
                            if text[idx-1] == 'e' and d.startswith('e'):
                                text = text[:idx-1] + "@" + d
                            else:
                                text = text[:idx] + "@" + d
                        break
                        
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if match: return match.group(0)
        return text

    def clean_phone(self, text):
        text = self.normalize_digits(text)
        # Apply smart typo fixing for digits
        text = self.smart_typo_fixer(text, field_type="digits")
        return re.sub(r'[^\d\+\-\(\)\s]', '', text).strip()

    def clean_gender(self, text):
        t = text.lower().strip()
        if 'female' in t or t.startswith('f') or 'fem' in t:
            return "Female"
        if 'male' in t or t.startswith('m'):
            return "Male"
        return text.strip()

    def clean_name(self, text):
        # Allow unicode characters for Hindi support
        return re.sub(r'[^\w\s\.]', '', text, flags=re.UNICODE).strip()

    def clean_address(self, text):
        text = self.normalize_digits(text)
        text = text.strip(" .,-:")
        text = text.replace("|", "I")
        return text

    def refine_fields(self, fields):
        field_mappings = {
            "name": ["Name", "First Name", "Full Name", "Student Name", "नाम"],
            "age": ["Age", "Years", "DOB", "Date of Birth", "आयु", "उम्र"],
            "gender": ["Gender", "Sex", "लिंग"],
            "address": ["Address", "Add", "Residing at", "Location", "Permanent Address", "पता"],
            "id_number": ["ID", "ID Number", "Ref No", "Roll No", "पहचान पत्र"],
            "email": ["Email", "E-mail", "Mail", "ईमेल"],
            "phone": ["Phone", "Mobile", "Cell", "Tel", "Contact", "फोन", "मोबाइल"]
        }

        for key, val in list(fields.items()):
            if not val or len(val) < 5: continue
            
            words = val.split()
            for i, word in enumerate(words):
                if i == 0 and len(words) == 1: continue
                
                clean_word = word.strip(":,.-")
                if len(clean_word) < 3: continue 
                
                best_label = None
                best_score = 0
                
                for f_key, keywords in field_mappings.items():
                    if f_key == key: continue 
                    
                    match = process.extractOne(clean_word, keywords, scorer=fuzz.ratio)
                    if match:
                        score = match[1]
                        if score > 85: 
                            best_score = score
                            best_label = f_key
                
                if best_label:
                    new_val_current = " ".join(words[:i]).strip()
                    new_val_detected = " ".join(words[i+1:]).strip()
                    fields[key] = new_val_current
                    if not fields.get(best_label):
                        fields[best_label] = new_val_detected
                    break 

        if fields.get("name"):
            name_val = fields["name"]
            match = re.search(r'(\d{1,3})$', name_val.strip())
            if match:
                extracted_age = match.group(1)
                if not fields.get("age"):
                    fields["age"] = extracted_age
                fields["name"] = name_val[:match.start()].strip()

        if fields.get("address"):
            addr = fields["address"]
            for key in ["Phone", "Email", "Gender", "ID", "Age", "Name"]:
                if key in addr:
                    parts = re.split(f"{key}[:\s]", addr, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        fields["address"] = parts[0].strip()

        if fields.get("name"): fields["name"] = self.clean_name(fields["name"])
        if fields.get("age"): fields["age"] = re.sub(r'\D', '', self.normalize_digits(fields["age"]))
        if fields.get("gender"): fields["gender"] = self.clean_gender(fields["gender"])
        if fields.get("email"): fields["email"] = self.clean_email(fields["email"])
        if fields.get("phone"): fields["phone"] = self.clean_phone(fields["phone"])
        if fields.get("address"): fields["address"] = self.clean_address(fields["address"])
            
        return fields

    def extract_fields(self, text):
        fields = {}
        raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        field_mappings = {
            "name": ["Name", "First Name", "Full Name", "Student Name", "नाम"],
            "age": ["Age", "Years", "DOB", "Date of Birth", "आयु", "उम्र"],
            "gender": ["Gender", "Sex", "लिंग"],
            "address": ["Address", "Add", "Residing at", "Location", "Permanent Address", "पता"],
            "id_number": ["ID", "ID Number", "Ref No", "Roll No", "पहचान पत्र"],
            "email": ["Email", "E-mail", "Mail", "ईमेल"],
            "phone": ["Phone", "Mobile", "Cell", "Tel", "Contact", "फोन", "मोबाइल"]
        }

        processed_lines = []
        for line in raw_lines:
            found_indices = []
            for field_key, keywords in field_mappings.items():
                for keyword in keywords:
                    if keyword in line:
                        matches = list(re.finditer(f"\\b{re.escape(keyword)}\\b", line, re.IGNORECASE))
                        for m in matches:
                            found_indices.append(m.start())
            
            if len(found_indices) > 1:
                found_indices.sort()
                last_idx = 0
                for idx in found_indices:
                    if idx > last_idx: 
                        segment = line[last_idx:idx].strip()
                        if segment: processed_lines.append(segment)
                    last_idx = idx
                if last_idx < len(line):
                    processed_lines.append(line[last_idx:].strip())
            else:
                processed_lines.append(line)

        current_field = None
        i = 0
        while i < len(processed_lines):
            line = processed_lines[i]
            i += 1
            
            best_match_field = None
            best_match_score = 0
            
            line_start = " ".join(line.split()[:3])
            
            for field_key, keywords in field_mappings.items():
                match = process.extractOne(line_start, keywords, scorer=fuzz.token_set_ratio)
                if match:
                    score = match[1]
                    if score > 70 and score > best_match_score:
                        best_match_score = score
                        best_match_field = field_key

            if best_match_field:
                current_field = best_match_field
                
                parts = line.split(':', 1)
                if len(parts) > 1:
                    val = parts[1].strip()
                else:
                    val = " ".join(line.split()[1:])
                
                # Normalize digits immediately for validation checks
                val = self.normalize_digits(val)
                
                is_valid_value = True
                low_val = val.lower().strip()
                noise_words = ["id", "no", "number", "num", "#", "code", "address", "value", "val"]
                
                if not val:
                    is_valid_value = False
                elif low_val in noise_words:
                    is_valid_value = False
                # Relaxed checks: Trust the label more. 
                # If we found "Phone:", we should take the value even if it looks weird, 
                # because refine_fields will clean it up later.
                # Only reject if it's completely empty or just noise words.
                elif current_field == "email" and len(val) < 5:
                    is_valid_value = False
                
                if is_valid_value:
                    # Only overwrite if current is empty or new value is longer/better
                    if not fields.get(current_field) or len(val) > len(fields[current_field]):
                        fields[current_field] = val
                else:
                    if i < len(processed_lines):
                        next_line = processed_lines[i].strip()
                        is_next_label = False
                        next_start = " ".join(next_line.split()[:3])
                        for f_key, kws in field_mappings.items():
                            m = process.extractOne(next_start, kws, scorer=fuzz.token_set_ratio)
                            if m and m[1] > 70:
                                is_next_label = True
                                break
                        
                        if not is_next_label:
                            # Only overwrite if current is empty
                            if not fields.get(current_field):
                                fields[current_field] = next_line
                            i += 1 
                        else:
                            # Don't overwrite with empty if we already have something
                            if not fields.get(current_field):
                                fields[current_field] = "" 
            
            elif current_field:
                if current_field == "address":
                    if "Country" in line or "Post" in line:
                        pass 
                    elif fields.get(current_field):
                        fields[current_field] += ", " + line
                    else:
                        fields[current_field] = line
                else:
                    pass

        fields = self.refine_fields(fields)
        
        if not fields.get("email"):
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if email_match:
                fields["email"] = email_match.group(0)
        
        if not fields.get("phone"):
            phone_match = re.search(r'(?:Phone|Mobile|Cell|Tel|Contact)\s*[:\-\.]?\s*([+\d\(\)\-\s]{10,})', text, re.IGNORECASE)
            if phone_match:
                fields["phone"] = phone_match.group(1).strip()

        if not fields.get("age"):
            age_match = re.search(r'(?:Age|Years)\s*[:\-\.]?\s*(\d{1,3})', text, re.IGNORECASE)
            if age_match:
                fields["age"] = age_match.group(1)
            else:
                age_match_suffix = re.search(r'(\d{1,3})\s*(?:Years|Yrs)', text, re.IGNORECASE)
                if age_match_suffix:
                    fields["age"] = age_match_suffix.group(1)
                else:
                    # Standalone Age Fallback: Look for a line that is JUST a number (18-99)
                    # This catches cases where "Age:" label was missed but "30" is on its own line
                    for line in raw_lines:
                        clean = line.strip()
                        if re.match(r'^\d{2}$', clean):
                            val = int(clean)
                            if 18 <= val <= 99:
                                fields["age"] = str(val)
                                break

        # Fallback: Address (Content-Based)
        if not fields.get("address"):
            # Expanded keywords including Indian/Global terms
            address_keywords = ["Street", "St.", "Road", "Rd", "Lane", "Ave", "Apartment", "Apt", "Floor", "Block", "District", "State", "Pin", "Zip", "Nagar", "Colony", "Sector", "Plot", "Flat", "Suite", "Unit"]
            potential_address = []
            for line in raw_lines:
                if len(line) < 5: continue
                if any(k.lower() in line.lower() for k in address_keywords):
                    potential_address.append(line)
            
            if potential_address:
                fields["address"] = ", ".join(potential_address[:3])
            else:
                # AGGRESSIVE ADDRESS: Look for lines starting with digits (House Numbers)
                # e.g. "123 MG Road"
                for line in raw_lines:
                    clean_line = line.strip()
                    # Starts with digits, followed by space/comma, then letters
                    if re.match(r'^\d+[\s,]+[a-zA-Z]', clean_line) and len(clean_line) > 10:
                        # Exclude dates (DD/MM/YYYY) and Phones (10 digits)
                        if not re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', clean_line) and \
                           len(re.sub(r'\D', '', clean_line)) < 10:
                            fields["address"] = clean_line
                            break

        # --- AGGRESSIVE FALLBACKS (Last Resort) ---
        
        # Aggressive Phone: Just find any 10+ digit sequence if still missing
        if not fields.get("phone"):
            # Matches 1234567890, 123 456 7890, 123-456-7890
            # We look for a sequence that has at least 10 digits
            agg_phone = re.search(r'\b\d[\d\s\-\(\)]{9,}\d\b', text)
            if agg_phone:
                val = agg_phone.group(0)
                # Double check digit count
                if len(re.sub(r'\D', '', val)) >= 10:
                    fields["phone"] = val.strip()

        # Aggressive Email: Fuzzy Domain Fixer
        if fields.get("email"):
            # If we have an email but it looks broken (e.g. "john@gmai1.com")
            e = fields["email"]
            # List of common domains to enforce
            common_domains = {
                "gmail.com": ["gmai1.com", "gnail.com", "gmal.com", "gmil.com"],
                "yahoo.com": ["yaho.com", "yhoo.com"],
                "hotmail.com": ["hotmai1.com", "hotmal.com"],
                "outlook.com": ["outlok.com"]
            }
            parts = e.split('@')
            if len(parts) == 2:
                domain = parts[1]
                for correct, typos in common_domains.items():
                    if domain in typos or fuzz.ratio(domain, correct) > 85:
                        fields["email"] = parts[0] + "@" + correct
                        break

        # Fallback: Gender (Global Search)
        if not fields.get("gender"):
            if re.search(r'\b(?:Male|M)\b', text, re.IGNORECASE):
                fields["gender"] = "Male"
            elif re.search(r'\b(?:Female|F)\b', text, re.IGNORECASE):
                fields["gender"] = "Female"

        # Fallback: Name (Heuristic)
        if not fields.get("name"):
            for line in raw_lines:
                clean = line.strip()
                if not clean: continue
                
                is_other_label = False
                for k, v in field_mappings.items():
                    if k == "name": continue
                    for keyword in v:
                        if fuzz.partial_ratio(keyword.lower(), clean.lower()) > 80:
                            is_other_label = True
                            break
                    if is_other_label: break
                
                if is_other_label: continue
                
                if "CARD" in clean.upper() or "FORM" in clean.upper(): continue
                
                if re.search(r'[a-zA-Z]', clean):
                    for nk in field_mappings["name"]:
                        if clean.lower().startswith(nk.lower()):
                            clean = re.sub(f"^{re.escape(nk)}[:\-\.]?\s*", "", clean, flags=re.IGNORECASE)
                            break
                    
                    fields["name"] = clean
                    break

        print(f"DEBUG: Extracted Fields: {fields}")
        return fields

    def extract_text(self, file_bytes, doc_type="auto", is_pdf=False):
        try:
            processed_img = self.preprocess_image(file_bytes)
            results = self.reader.readtext(processed_img, detail=0, paragraph=False)
            generated_text = "\n".join(results)
            print(f"DEBUG: EasyOCR Output:\n{generated_text}")
            fields = self.extract_fields(generated_text)
            
            return {
                "raw_text": generated_text,
                "fields": fields,
                "quality_status": "Good",
                "detected_type": "auto"
            }
            
        except Exception as e:
            print(f"Error in EasyOCR extraction: {e}")
            return {"raw_text": "", "fields": {}}

ocr_engine = OCREngine()

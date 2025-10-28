
#!/usr/bin/env python3
"""
Optimized Gemini Audio Transcription Script for Digital Umuganda
Uses Gemini 2.5 Flash Native Audio for best Swahili transcription
"""

import os
import sys
import time
import argparse
import requests
from urllib.parse import urljoin
import tempfile
import traceback
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options

# Load environment variables
load_dotenv()


class GeminiTranscription:
    def __init__(self, url, gemini_api_key):
        """Initialize Gemini transcription automation with model rotation"""
        self.url = url
        self.gemini_api_key = gemini_api_key
        self.driver = None
        self.audio_count = 0
        
        # List of models to rotate through (ordered by preference)
        self.model_names = [
            'models/gemini-2.0-flash-lite',      # Best: 30 RPM, 1M TPM
            'models/gemini-2.0-flash',           # Good: 15 RPM, 1M TPM
            'models/gemini-2.5-flash-lite',      # Good: 15 RPM, 250K TPM
            'models/gemini-2.5-flash',           # Good: 10 RPM, 250K TPM
            'models/gemini-2.0-flash-exp',       # Fallback: 10 RPM, 250K TPM
        ]
        
        self.current_model_index = 0
        self.model_retry_count = {}
        
        # Initialize Gemini
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_api_key)
            
            # Initialize with first model
            self.current_model_name = self.model_names[self.current_model_index]
            self.gemini_model = genai.GenerativeModel(
                self.current_model_name,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )
            )
            print(f"✓ Initialized with model: {self.current_model_name}")
            
        except ImportError:
            print("ERROR: Install google-generativeai: pip install google-generativeai")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR initializing Gemini: {e}")
            sys.exit(1)
    
    def switch_to_next_model(self):
        """Switch to the next available model when rate limit is hit"""
        import google.generativeai as genai
        
        self.current_model_index = (self.current_model_index + 1) % len(self.model_names)
        self.current_model_name = self.model_names[self.current_model_index]
        
        print(f"\n⚠️  Rate limit reached, switching to: {self.current_model_name}")
        
        self.gemini_model = genai.GenerativeModel(
            self.current_model_name,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
        )
        
        # Track retry count for this model
        if self.current_model_name not in self.model_retry_count:
            self.model_retry_count[self.current_model_name] = 0
        self.model_retry_count[self.current_model_name] += 1
        
        return True
    
    def setup_driver(self):
        """Setup Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("detach", True)
        
        print("Initializing Chrome driver...")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)
        print("✓ Browser initialized!")
    
    def check_login(self):
        """Check if user is logged in"""
        print(f"\nNavigating to {self.url}")
        self.driver.get(self.url)
        time.sleep(3)
        
        # Check for login indicators
        try:
            self.driver.find_element(By.XPATH, "//textarea")
            print("✓ User is logged in!")
            return True
        except NoSuchElementException:
            pass
        
        print("\n" + "="*60)
        print("⚠️  Please login and press ENTER when ready...")
        print("="*60)
        input()
        
        try:
            self.driver.find_element(By.XPATH, "//textarea")
            print("✓ Login verified!")
            return True
        except NoSuchElementException:
            print("ERROR: Still not logged in")
            return False
    
    def get_audio_url(self):
        """Extract audio URL from page"""
        print("Looking for audio element...")
        
        # Try multiple methods
        try:
            audio_element = self.driver.find_element(By.TAG_NAME, "audio")
            audio_url = audio_element.get_attribute("src")
            if audio_url and not audio_url.startswith("http"):
                audio_url = urljoin(self.driver.current_url, audio_url)
            print(f"✓ Found audio URL")
            return audio_url
        except:
            pass
        
        # Try JavaScript
        try:
            audio_url = self.driver.execute_script("""
                var audio = document.querySelector('audio');
                return audio ? (audio.src || audio.currentSrc) : null;
            """)
            if audio_url:
                print(f"✓ Found audio URL via JavaScript")
                return audio_url
        except:
            pass
        
        print("❌ Could not find audio URL")
        return None
    
    def download_audio(self, audio_url):
        """Download audio file"""
        try:
            print("Downloading audio...")
            
            cookies = self.driver.get_cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = session.get(audio_url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Determine extension
            content_type = response.headers.get('content-type', '')
            ext = '.mp3'
            if 'wav' in content_type:
                ext = '.wav'
            elif 'ogg' in content_type:
                ext = '.ogg'
            elif 'webm' in content_type:
                ext = '.webm'
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(temp_file.name)
            print(f"✓ Audio downloaded ({file_size} bytes)")
            return temp_file.name
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return None
    
    def transcribe_audio(self, audio_file, retry_count=0):
        """Transcribe audio using Gemini with automatic model rotation on rate limit"""
        max_retries = len(self.model_names)  # Try all models once
        
        try:
            print(f"Uploading to Gemini ({self.current_model_name})...")
            
            import google.generativeai as genai
            
            # Upload file
            audio_file_obj = genai.upload_file(audio_file)
            print(f"✓ Uploaded: {audio_file_obj.name}")
            
            # Wait for processing
            print("Processing audio...")
            while audio_file_obj.state.name == "PROCESSING":
                time.sleep(2)
                audio_file_obj = genai.get_file(audio_file_obj.name)
            
            if audio_file_obj.state.name == "FAILED":
                print("❌ Processing failed")
                return None
            
            print("✓ Audio processed")
            
            # HIGHLY OPTIMIZED PROMPT for Swahili transcription
            prompt = """You are a professional Swahili transcriptionist. Listen carefully to this audio and transcribe it with PERFECT ACCURACY.

CRITICAL INSTRUCTIONS - FOLLOW EXACTLY:

1. LANGUAGE: The audio is in SWAHILI. Transcribe everything in correct Swahili spelling and grammar.

2. ACCURACY RULES:
   - Transcribe ONLY what you actually hear - DO NOT INVENT or GUESS words
   - If unsure about a word, write your best attempt but NEVER add words that weren't spoken
   - Listen carefully to every word - accuracy is more important than speed
   - Pay attention to Swahili word patterns: mwanamke, mtoto, mwanaume, watu, etc.

3. FORBIDDEN ADDITIONS (DO NOT ADD):
   - No "Thank you", "Subscribe", "Like", or English filler phrases
   - No [Music], [Applause], ♪ or sound effect descriptions
   - No "Here is the transcription:" or introductory text
   - No translations or explanations
   - No timestamps or speaker labels

4. COMMON SWAHILI WORDS TO RECOGNIZE:
   - People: mwanamke (woman), mwanaume (man), mtoto (child), watu (people)
   - Actions: analia (crying), amebeba (carrying), amesimama (standing), anakimbia (running)
   - Places: juu (up/above), chini (down/below), mbele (front), nyuma (behind)
   - Things: koti (coat), nguo (clothes), mti (tree), gari (car)
   - Colors: nyekundu (red), nyeupe (white), nyeusi (black), kijani (green)

5. GRAMMAR:
   - Swahili uses prefixes: m-, wa-, a-, wa-, ku-, etc.
   - Maintain proper Swahili sentence structure
   - Use correct verb conjugations

6. OUTPUT FORMAT:
   - Provide ONLY the raw transcription
   - No bullet points, no formatting, no numbering
   - Just clean Swahili text with proper spacing

Listen to the audio now and transcribe it perfectly in Swahili:"""
            
            # Generate transcription with optimal settings
            print("Generating transcription...")
            response = self.gemini_model.generate_content(
                [prompt, audio_file_obj],
                generation_config=genai.GenerationConfig(
                    temperature=0.05,  # Very low for maximum accuracy
                    top_p=0.9,
                    top_k=20,
                    max_output_tokens=8192,
                ),
                request_options={"timeout": 120}
            )
            
            # Cleanup uploaded file
            try:
                genai.delete_file(audio_file_obj.name)
                print("✓ Cleaned up file")
            except:
                pass
            
            transcription = response.text.strip()
            
            # Remove common hallucination artifacts
            artifacts = [
                "Here is the transcription:",
                "Transcription:",
                "**Transcription:**",
                "The transcription is:",
                "Here you go:",
                "[Music]", "[music]",
                "[Applause]", "[applause]",
                "♪", "♫", "♬",
                "Thank you for watching",
                "Thanks for watching",
                "Please subscribe",
                "Like and subscribe",
                "Don't forget to",
            ]
            
            for artifact in artifacts:
                transcription = transcription.replace(artifact, "")
            
            # Remove markdown formatting that Gemini sometimes adds
            transcription = transcription.replace("**", "").replace("*", "")
            
            # Clean up extra whitespace and newlines
            transcription = " ".join(transcription.split())
            
            print("✓ Transcription complete!")
            return transcription
            
        except Exception as e:
            error_message = str(e).lower()
            
            # Check if it's a rate limit error
            if 'rate limit' in error_message or '429' in error_message or 'quota' in error_message or 'resource_exhausted' in error_message:
                print(f"⚠️  Rate limit hit on {self.current_model_name}")
                
                if retry_count < max_retries:
                    # Switch to next model and retry
                    self.switch_to_next_model()
                    print(f"🔄 Retrying with new model (attempt {retry_count + 1}/{max_retries})...")
                    time.sleep(3)  # Brief pause before retry
                    return self.transcribe_audio(audio_file, retry_count + 1)
                else:
                    print(f"❌ All models exhausted. Rate limits reached on all {max_retries} models.")
                    print("⏰ Waiting 60 seconds before continuing...")
                    time.sleep(60)
                    # Reset to first model and try again
                    self.current_model_index = 0
                    self.switch_to_next_model()
                    return self.transcribe_audio(audio_file, 0)
            else:
                print(f"❌ Transcription failed: {e}")
                traceback.print_exc()
                return None
    
    def detect_code_switching(self, text):
        """Mark English/Sheng words with [cs]"""
        import re
        
        swahili_common = {
            'na', 'ya', 'wa', 'ni', 'kwa', 'la', 'za', 'katika', 'kama',
            'au', 'lakini', 'pia', 'sana', 'tu', 'kwenye', 'bila', 'hii',
            'hiyo', 'hilo', 'hao', 'wale', 'hawa', 'mimi', 'wewe', 'yeye',
            'sisi', 'ninyi', 'wao', 'nini', 'nani', 'wapi', 'lini', 'je',
            'cha', 'vya', 'nchi', 'watu', 'mtu', 'yake', 'yangu', 'yetu',
            'moja', 'mbili', 'tatu', 'nne', 'tano', 'ndiyo', 'hapana',
        }
        
        english_pattern = re.compile(
            r"\b(the|is|are|was|were|have|has|had|will|would|could|should|"
            r"can|may|must|do|does|did|this|that|these|those|what|where|"
            r"when|why|how|who|which|and|but|or|so|because|if|then)\b",
            re.IGNORECASE
        )
        
        words = text.split()
        processed = []
        
        for word in words:
            word_clean = re.sub(r"[^\w']+", "", word).lower()
            
            if not word_clean or word_clean in swahili_common:
                processed.append(word)
                continue
            
            # Check for English indicators
            if (english_pattern.search(word_clean) or
                word_clean.endswith(('ing', 'ed', 'tion', 'ment')) or
                any(c in word_clean for c in ['x', 'q'])):
                processed.append(f"[cs] {word}")
            else:
                processed.append(word)
        
        return " ".join(processed)
    
    def type_text(self, element, text, speed=0.01):
        """Type text naturally into textarea"""
        print("Typing transcription...")
        element.clear()
        time.sleep(0.2)
        element.click()
        time.sleep(0.1)
        
        for i, char in enumerate(text):
            element.send_keys(char)
            time.sleep(speed)
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(text)}", end='\r')
        
        print(f"\n✓ Typed {len(text)} characters!")
    
    def insert_transcription(self, transcription):
        """Insert transcription into webpage"""
        try:
            textarea = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//textarea"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", textarea)
            time.sleep(0.5)
            self.type_text(textarea, transcription, speed=0.01)
            return True
        except Exception as e:
            print(f"❌ Insertion failed: {e}")
            return False
    
    def wait_for_submit(self):
        """Wait for user to submit"""
        print("\n" + "="*60)
        print("⏸️  REVIEW THE TRANSCRIPTION")
        print("="*60)
        print("1. Check accuracy")
        print("2. Verify [cs] markers")
        print("3. Edit if needed")
        print("4. Click SUBMIT")
        print("="*60 + "\n")
        
        try:
            current_id = self.driver.current_url
            print("Waiting for submission...", end='')
            
            start_time = time.time()
            while time.time() - start_time < 600:
                time.sleep(2)
                print(".", end='', flush=True)
                
                # Check if textarea cleared
                try:
                    textarea = self.driver.find_element(By.XPATH, "//textarea")
                    if not textarea.get_attribute("value").strip():
                        print("\n✓ Submission detected!")
                        time.sleep(2)
                        return True
                except:
                    pass
                
                # Check URL change
                if self.driver.current_url != current_id:
                    print("\n✓ Submission detected!")
                    return True
            
            print("\n⚠️  Timeout")
            return False
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False
    
    def process_audio(self):
        """Process one audio"""
        self.audio_count += 1
        print(f"\n{'='*60}")
        print(f"🎵 AUDIO #{self.audio_count}")
        print(f"{'='*60}\n")
        
        # Get audio URL
        audio_url = self.get_audio_url()
        if not audio_url:
            return False
        
        # Download
        audio_file = self.download_audio(audio_url)
        if not audio_file:
            return False
        
        try:
            # Transcribe with Gemini
            transcription = self.transcribe_audio(audio_file)
            if not transcription:
                return False
            
            print(f"\n📝 Raw: {transcription[:100]}...\n")
            
            # Add code-switching markers
            processed = self.detect_code_switching(transcription)
            print(f"✨ Processed: {processed[:100]}...\n")
            
            # Insert into webpage
            if not self.insert_transcription(processed):
                return False
            
            # Wait for submit
            return self.wait_for_submit()
            
        finally:
            try:
                os.unlink(audio_file)
                print("🗑️  Cleaned up temp file")
            except:
                pass
    
    def run(self):
        """Main loop with model rotation status"""
        try:
            print("\n" + "="*60)
            print("🚀 GEMINI MULTI-MODEL TRANSCRIPTION")
            print("="*60)
            print(f"📋 Available models: {len(self.model_names)}")
            for i, model in enumerate(self.model_names):
                marker = "→" if i == self.current_model_index else " "
                print(f"  {marker} {model}")
            print("="*60)
            
            self.setup_driver()
            
            if not self.check_login():
                print("❌ Login failed")
                return
            
            print("\n" + "="*60)
            print("▶️  STARTING TRANSCRIPTION")
            print("="*60 + "\n")
            
            while True:
                try:
                    success = self.process_audio()
                    
                    if not success:
                        print("\n⚠️  Error or no more audios")
                        retry = input("Try again? (y/n): ").lower()
                        if retry != 'y':
                            break
                        continue
                    
                    print("\n⏭️  Moving to next audio...")
                    time.sleep(3)
                    
                except KeyboardInterrupt:
                    print("\n\n⏹️  Stopped by user")
                    break
                except Exception as e:
                    print(f"\n❌ ERROR: {e}")
                    traceback.print_exc()
                    time.sleep(3)
            
            print(f"\n{'='*60}")
            print(f"✅ SESSION COMPLETE")
            print(f"📊 Total audios processed: {self.audio_count}")
            print(f"📈 Model usage stats:")
            for model, count in self.model_retry_count.items():
                if count > 0:
                    print(f"   • {model.split('/')[-1]}: switched {count} time(s)")
            print(f"{'='*60}\n")
            
        finally:
            if self.driver:
                input("\nPress ENTER to close browser...")
                self.driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Optimized Gemini audio transcription",
        epilog="""
Example:
  python gemini_transcribe.py --url https://mombasa-kenya254.web.app/transcribe

Setup .env file:
  GEMINI_API_KEY=AIzaSy...
        """
    )
    
    parser.add_argument('--url', required=True, help='Transcription website URL')
    parser.add_argument('--gemini-key', help='Gemini API key (overrides .env)')
    
    args = parser.parse_args()
    
    # Get API key
    gemini_key = args.gemini_key or os.getenv('GEMINI_API_KEY')
    
    if not gemini_key:
        print("❌ ERROR: GEMINI_API_KEY required")
        print("Set in .env file or use --gemini-key")
        sys.exit(1)
    
    try:
        automation = GeminiTranscription(args.url, gemini_key)
        automation.run()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
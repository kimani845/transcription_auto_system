#!/usr/bin/env python3
"""
Audio Transcription Automation Script for Digital Umuganda
Supports Swahili transcription with automatic code-switching detection
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path
from urllib.parse import urljoin
import tempfile
import traceback
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Load environment variables from .env file
load_dotenv()


class TranscriptionAutomation:
    def __init__(self, url, transcription_method="whisper-local", openai_api_key=None, gemini_api_key=None, openrouter_api_key=None, openrouter_model=None):
        """
        Initialize the transcription automation
        
        Args:
            url: Base URL of the transcription website
            transcription_method: 'whisper-local', 'openai-api', 'gemini-api', or 'openrouter'
            openai_api_key: OpenAI API key (required if using openai-api method)
            gemini_api_key: Google Gemini API key (required if using gemini-api method)
            openrouter_api_key: OpenRouter API key (required if using openrouter method)
            openrouter_model: Model to use with OpenRouter (e.g., 'google/gemini-pro-1.5', 'openai/gpt-4')
        """
        self.url = url
        self.transcription_method = transcription_method
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_model = openrouter_model or "google/gemini-pro-1.5"
        self.driver = None
        self.audio_count = 0
        
        # Initialize Whisper if using local method
        if transcription_method == "whisper-local":
            try:
                import whisper
                print("Loading Whisper model (this may take a moment)...")
                self.whisper_model = whisper.load_model("medium")   # Use medium model for better accuracy 
                print("✓ Whisper model loaded successfully!")
            except ImportError:
                print("ERROR: Whisper not installed. Install with: pip install openai-whisper")
                print("You may also need: pip install ffmpeg-python")
                sys.exit(1)
            except Exception as e:
                print(f"ERROR loading Whisper: {e}")
                print("You may need to install ffmpeg. On Ubuntu: sudo apt install ffmpeg")
                sys.exit(1)
        
        elif transcription_method == "openai-api":
            if not openai_api_key:
                print("ERROR: OpenAI API key required for openai-api method")
                print("Set OPENAI_API_KEY in .env file or pass via --api-key")
                sys.exit(1)
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                print("✓ OpenAI client initialized!")
            except ImportError:
                print("ERROR: OpenAI library not installed. Install with: pip install openai")
                sys.exit(1)
        
        elif transcription_method == "gemini-api":
            if not gemini_api_key:
                print("ERROR: Gemini API key required for gemini-api method")
                print("Set GEMINI_API_KEY in .env file or pass via --gemini-key")
                sys.exit(1)
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                print("✓ Gemini client initialized!")
            except ImportError:
                print("ERROR: Google Generative AI library not installed.")
                print("Install with: pip install google-generativeai")
                sys.exit(1)
            except Exception as e:
                print(f"ERROR initializing Gemini: {e}")
                sys.exit(1)
        
        elif transcription_method == "openrouter":
            if not openrouter_api_key:
                print("ERROR: OpenRouter API key required for openrouter method")
                print("Set OPENROUTER_API_KEY in .env file or pass via --openrouter-key")
                sys.exit(1)
            self.openrouter_base_url = "https://openrouter.ai/api/v1"
            print(f"✓ OpenRouter initialized with model: {self.openrouter_model}")
    
    def setup_driver(self):
        """Setup Selenium WebDriver with appropriate options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Keep browser open for manual verification
            chrome_options.add_experimental_option("detach", True)
            
            print("Initializing Chrome driver...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            self.wait = WebDriverWait(self.driver, 20)
            print("✓ Browser initialized successfully!")
            
        except Exception as e:
            print(f"ERROR initializing browser: {e}")
            print("\nMake sure you have:")
            print("1. Chrome browser installed")
            print("2. ChromeDriver installed (pip install webdriver-manager)")
            print("3. Or install selenium manually: pip install selenium")
            raise
    
    def check_login_status(self):
        """Check if user is logged in, redirect to login if not"""
        print(f"\nNavigating to {self.url}")
        self.driver.get(self.url)
        time.sleep(3)
        
        # Check multiple indicators of being logged in
        try:
            # Method 1: Look for Logout button
            logout_button = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Logout') or contains(text(), 'logout')]")
            print("✓ User is already logged in! (Found logout button)")
            return True
        except NoSuchElementException:
            pass
        
        # Method 2: Look for transcription textarea
        try:
            textarea = self.driver.find_element(By.XPATH, "//textarea")
            print("✓ User is already logged in! (Found transcription area)")
            return True
        except NoSuchElementException:
            pass
        
        # Method 3: Check URL
        if "transcribe" in self.driver.current_url.lower():
            print("✓ User is already logged in! (On transcribe page)")
            return True
        
        # Not logged in - prompt user
        print("\n" + "="*60)
        print("⚠️  NOT LOGGED IN - Please login to continue")
        print("="*60)
        print("\nThe browser window is open. Please:")
        print("1. Complete the login process")
        print("2. Navigate to the transcription page")
        print("3. Press ENTER here when ready to continue...")
        print("="*60)
        
        input()
        
        # Verify login after user confirms
        try:
            self.driver.find_element(By.XPATH, "//textarea")
            print("✓ Login verified! Starting transcription process...\n")
            return True
        except NoSuchElementException:
            print("ERROR: Still not on transcription page. Please check and try again.")
            return False
    
    def get_audio_url(self):
        """Extract audio URL from the page"""
        print("Looking for audio element...")
        
        try:
            # Try to find audio element
            audio_element = self.driver.find_element(By.TAG_NAME, "audio")
            audio_url = audio_element.get_attribute("src")
            
            if audio_url:
                # Handle relative URLs
                if not audio_url.startswith("http"):
                    audio_url = urljoin(self.driver.current_url, audio_url)
                print(f"✓ Found audio URL: {audio_url[:80]}...")
                return audio_url
            
        except NoSuchElementException:
            print("No <audio> tag found, checking for <source> tags...")
        
        # Alternative: Look for source tags within audio element
        try:
            source_element = self.driver.find_element(By.XPATH, "//audio/source")
            audio_url = source_element.get_attribute("src")
            if audio_url and not audio_url.startswith("http"):
                audio_url = urljoin(self.driver.current_url, audio_url)
            print(f"✓ Found audio URL from source: {audio_url[:80]}...")
            return audio_url
        except NoSuchElementException:
            print("No <source> tag found either")
        
        # Try JavaScript to get audio URL
        try:
            audio_url = self.driver.execute_script("""
                var audio = document.querySelector('audio');
                if (audio) {
                    return audio.src || audio.currentSrc;
                }
                return null;
            """)
            if audio_url:
                print(f"✓ Found audio URL via JavaScript: {audio_url[:80]}...")
                return audio_url
        except Exception as e:
            print(f"JavaScript audio extraction failed: {e}")
        
        print("❌ WARNING: Could not find audio element on page")
        return None
    
    def download_audio(self, audio_url):
        """Download audio file to temporary location"""
        try:
            print("Downloading audio file...")
            
            # Get cookies from Selenium session for authenticated download
            cookies = self.driver.get_cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            
            # Add headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = session.get(audio_url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Determine file extension from content type
            content_type = response.headers.get('content-type', '')
            if 'mp3' in content_type:
                ext = '.mp3'
            elif 'wav' in content_type:
                ext = '.wav'
            elif 'ogg' in content_type:
                ext = '.ogg'
            elif 'webm' in content_type:
                ext = '.webm'
            else:
                ext = '.mp3'  # default
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            
            print(f"Saving to temporary file: {temp_file.name}")
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(temp_file.name)
            print(f"✓ Audio downloaded successfully ({file_size} bytes)")
            return temp_file.name
        
        except Exception as e:
            print(f"❌ ERROR downloading audio: {e}")
            traceback.print_exc()
            return None
    
    def transcribe_audio_local(self, audio_file):
        """Transcribe audio using local Whisper model"""
        try:
            print("Transcribing with local Whisper model...")
            result = self.whisper_model.transcribe(
                audio_file,
                language="sw",  # Swahili
                task="transcribe",
                verbose=False,
                temperature=0  # reduces randomness for language drift. 
            )
            print("✓ Transcription complete!")
            return result["text"].strip()
        except Exception as e:
            print(f"❌ ERROR during transcription: {e}")
            traceback.print_exc()
            return None
    
    def transcribe_audio_openai(self, audio_file):
        """Transcribe audio using OpenAI API"""
        try:
            print("Transcribing with OpenAI Whisper API...")
            with open(audio_file, "rb") as audio:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    language="sw"  # Swahili
                )
            print("✓ Transcription complete!")
            return transcript.text.strip()
        except Exception as e:
            print(f"❌ ERROR during transcription: {e}")
            traceback.print_exc()
            return None
    
    def transcribe_audio_gemini(self, audio_file):
        """Transcribe audio using Google Gemini API"""
        try:
            print("Transcribing with Gemini API...")
            
            # Upload the audio file
            import google.generativeai as genai
            
            # Upload file to Gemini
            print("Uploading audio to Gemini...")
            audio_file_obj = genai.upload_file(audio_file)
            print(f"✓ Uploaded file: {audio_file_obj.name}")
            
            # Create prompt for Swahili transcription
            prompt = """
            Please transcribe this audio file. The audio is in Swahili.
            Provide ONLY the transcription text without any additional commentary, formatting, or explanations.
            Transcribe exactly what is said in the audio, word for word.
            Do not add any introductory phrases like "Here is the transcription:" or similar.
            Just provide the raw transcription text.
            """
            
            # Generate transcription
            print("Generating transcription...")
            response = self.gemini_model.generate_content([prompt, audio_file_obj])
            
            # Clean up uploaded file
            try:
                genai.delete_file(audio_file_obj.name)
                print("✓ Cleaned up uploaded file from Gemini")
            except:
                pass
            
            transcription = response.text.strip()
            print("✓ Transcription complete!")
            return transcription
            
        except Exception as e:
            print(f"❌ ERROR during Gemini transcription: {e}")
            traceback.print_exc()
            return None
    
    def transcribe_audio_openrouter(self, audio_file):
        """Transcribe audio using OpenRouter API with vision/audio models"""
        try:
            print(f"Transcribing with OpenRouter using model: {self.openrouter_model}...")
            
            # Read audio file and convert to base64
            import base64
            with open(audio_file, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Determine MIME type
            ext = os.path.splitext(audio_file)[1].lower()
            mime_types = {
                '.mp3': 'audio/mp3',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg',
                '.webm': 'audio/webm',
                '.m4a': 'audio/mp4'
            }
            mime_type = mime_types.get(ext, 'audio/mp3')
            
            # Prepare request
            headers = {
                'Authorization': f'Bearer {self.openrouter_api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/transcription-automation',  # Optional
            }
            
            # Create payload with audio data
            payload = {
                'model': self.openrouter_model,
                'messages': [
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': 'Please transcribe this audio file. The audio is in Swahili. Provide ONLY the transcription text without any additional commentary, formatting, or explanations. Transcribe exactly what is said in the audio, word for word.'
                            },
                            {
                                'type': 'audio_url',
                                'audio_url': {
                                    'url': f'data:{mime_type};base64,{audio_data}'
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Make request to OpenRouter
            print("Sending request to OpenRouter...")
            response = requests.post(
                f'{self.openrouter_base_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract transcription from response
            if 'choices' in result and len(result['choices']) > 0:
                transcription = result['choices'][0]['message']['content'].strip()
                print("✓ Transcription complete!")
                return transcription
            else:
                print(f"❌ Unexpected response format: {result}")
                return None
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP ERROR during OpenRouter transcription: {e}")
            print(f"Response: {e.response.text if e.response else 'No response'}")
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"❌ ERROR during OpenRouter transcription: {e}")
            traceback.print_exc()
            return None
        """Transcribe audio using Google Gemini API"""
        try:
            print("Transcribing with Gemini API...")
            
            # Upload the audio file
            import google.generativeai as genai
            
            # Upload file to Gemini
            print("Uploading audio to Gemini...")
            audio_file_obj = genai.upload_file(audio_file)
            print(f"✓ Uploaded file: {audio_file_obj.name}")
            
            # Create prompt for Swahili transcription
            prompt = """
            Please transcribe this audio file. The audio is in Swahili.
            Provide ONLY the transcription text without any additional commentary, formatting, or explanations.
            Transcribe exactly what is said in the audio, word for word.
            Do not add any introductory phrases like "Here is the transcription:" or similar.
            Just provide the raw transcription text.
            """
            
            # Generate transcription
            print("Generating transcription...")
            response = self.gemini_model.generate_content([prompt, audio_file_obj])
            
            # Clean up uploaded file
            try:
                genai.delete_file(audio_file_obj.name)
                print("✓ Cleaned up uploaded file from Gemini")
            except:
                pass
            
            transcription = response.text.strip()
            print("✓ Transcription complete!")
            return transcription
            
        except Exception as e:
            print(f"❌ ERROR during Gemini transcription: {e}")
            traceback.print_exc()
            return None
    
    def detect_code_switching(self, text, strict_swahili=False):
        """
        Detect and mark code-switching (English/Sheng words) in Swahili text.
        If strict_swahili=True, non-Swahili words will be removed instead of marked.
        """

        import re

        # Common Swahili stopwords (expanded)
        swahili_common = {
            'na', 'ya', 'wa', 'ni', 'kwa', 'la', 'za', 'katika', 'kama',
            'au', 'lakini', 'pia', 'sana', 'tu', 'kwenye', 'bila', 'hii',
            'hiyo', 'hilo', 'hao', 'wale', 'hawa', 'mimi', 'wewe', 'yeye',
            'sisi', 'ninyi', 'wao', 'nini', 'nani', 'wapi', 'lini', 'je',
            'cha', 'vya', 'nchi', 'watu', 'mtu', 'yake', 'yangu', 'yetu',
            'moja', 'mbili', 'tatu', 'nne', 'tano', 'ndiyo', 'hapana', 'sasa',
            'leo', 'jana', 'kesho', 'wakati', 'wengine', 'ndani', 'nje',
            'karibu', 'kweli', 'hapo', 'hapa', 'ule', 'ile', 'kila', 'basi'
        }

        # Common English/Sheng indicators
        english_indicators = re.compile(
            r"\b(the|is|are|was|were|have|has|had|will|would|could|should|can|may|must|"
            r"do|does|did|this|that|these|those|what|where|when|why|how|who|which|"
            r"and|but|or|so|because|if|then|okay|sure|yes|no|maybe|thanks|morning|afternoon|evening)\b",
            re.IGNORECASE
        )

        words = text.split()
        processed_words = []

        for word in words:
            word_clean = re.sub(r"[^\w']+", "", word).lower()
            # If it's short or clearly Swahili, keep it
            if not word_clean or word_clean in swahili_common:
                processed_words.append(word)
                continue

            # Check for English/Sheng cues
            if (
                english_indicators.search(word_clean)
                or word_clean.endswith(("ing", "ed", "tion", "ment"))
                or any(c in word_clean for c in ['x', 'q'])
            ):
                if strict_swahili:
                    continue
                processed_words.append(f"[cs] {word}")
            else:
                processed_words.append(word)

        return " ".join(processed_words)
    
    def type_text_naturally(self, element, text, typing_speed=0.01):
        """
        Type text into element character by character (like a human)
        This ensures proper event triggering in the web form
        """
        print("Typing transcription into text area (live)...")
        
        # First, clear any existing text
        element.clear()
        time.sleep(0.2)
        
        # Click to focus
        element.click()
        time.sleep(0.1)
        
        # Type character by character
        for i, char in enumerate(text):
            element.send_keys(char)
            time.sleep(typing_speed)
            
            # Show progress every 10 characters
            if (i + 1) % 10 == 0 or (i + 1) == len(text):
                print(f"  Progress: {i + 1}/{len(text)} characters", end='\r')
        
        print(f"\n✓ Typed {len(text)} characters successfully!")
    
    def insert_transcription(self, transcription):
        """Insert transcription into the textarea with live typing"""
        try:
            print("\nInserting transcription...")
            
            # Find the transcription textarea
            textarea = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//textarea"))
            )
            
            print(f"Found textarea element")
            
            # Scroll to element
            self.driver.execute_script("arguments[0].scrollIntoView(true);", textarea)
            time.sleep(0.5)
            
            # Type the transcription naturally (live)
            self.type_text_naturally(textarea, transcription, typing_speed=0.01)
            
            return True
        
        except Exception as e:
            print(f"❌ ERROR inserting transcription: {e}")
            traceback.print_exc()
            return False
    
    def wait_for_submit(self):
        """Wait for user to click submit button"""
        print("\n" + "="*60)
        print("⏸️  WAITING FOR YOUR REVIEW")
        print("="*60)
        print("1. Review the transcription accuracy")
        print("2. Verify code-switching markers [cs] are correct")
        print("3. Make any necessary edits")
        print("4. Click the SUBMIT button when ready")
        print("="*60 + "\n")
        
        try:
            # Get current audio ID or URL to detect change
            try:
                current_id = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Id:')]").text
            except:
                current_id = self.driver.current_url
            
            # Wait and check periodically for submission
            print("Waiting for submission...", end='')
            timeout = 600  # 10 minutes max wait
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                time.sleep(2)
                print(".", end='', flush=True)
                
                # Check if textarea is cleared (indicates submission)
                try:
                    textarea = self.driver.find_element(By.XPATH, "//textarea")
                    textarea_value = textarea.get_attribute("value") or ""
                    
                    if len(textarea_value.strip()) == 0:
                        print("\n✓ Submission detected (textarea cleared)!")
                        time.sleep(2)  # Wait for page to update
                        return True
                except:
                    pass
                
                # Check if audio ID changed
                try:
                    new_id = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Id:')]").text
                    if new_id != current_id:
                        print("\n✓ Submission detected (new audio loaded)!")
                        time.sleep(1)
                        return True
                except:
                    pass
                
                # Check if URL changed
                if self.driver.current_url != current_id:
                    print("\n✓ Submission detected (URL changed)!")
                    time.sleep(1)
                    return True
            
            print("\n⚠️  Timeout waiting for submission")
            return False
        
        except Exception as e:
            print(f"\n❌ ERROR waiting for submission: {e}")
            traceback.print_exc()
            return False
    
    def process_audio(self):
        """Process a single audio transcription"""
        self.audio_count += 1
        print(f"\n{'='*60}")
        print(f"🎵 PROCESSING AUDIO #{self.audio_count}")
        print(f"{'='*60}\n")
        
        try:
            # Get audio URL
            audio_url = self.get_audio_url()
            if not audio_url:
                print("❌ Could not find audio URL. Skipping...")
                return False
            
            # Download audio
            audio_file = self.download_audio(audio_url)
            if not audio_file:
                print("❌ Failed to download audio. Skipping...")
                return False
            
            try:
                # Transcribe audio
                print(f"\nTranscribing using: {self.transcription_method}")
                if self.transcription_method == "whisper-local":
                    transcription = self.transcribe_audio_local(audio_file)
                elif self.transcription_method == "openai-api":
                    transcription = self.transcribe_audio_openai(audio_file)
                elif self.transcription_method == "gemini-api":
                    transcription = self.transcribe_audio_gemini(audio_file)
                elif self.transcription_method == "openrouter":
                    transcription = self.transcribe_audio_openrouter(audio_file)
                else:
                    print(f"❌ Unknown transcription method: {self.transcription_method}")
                    return False
                
                if not transcription:
                    print("❌ Transcription failed. Skipping...")
                    return False
                
                print(f"\n📝 Raw transcription:\n{transcription}\n")
                
                # Apply code-switching detection
                processed_transcription = self.detect_code_switching(transcription, strict_swahili=False)
                print(f"✨ Processed with code-switching:\n{processed_transcription}\n")
                
                # Insert into webpage (with live typing)
                if not self.insert_transcription(processed_transcription):
                    return False
                
                # Wait for user to submit
                return self.wait_for_submit()
            
            finally:
                # Clean up temporary audio file
                try:
                    os.unlink(audio_file)
                    print(f"🗑️  Cleaned up temporary file")
                except:
                    pass
        
        except Exception as e:
            print(f"\n❌ ERROR processing audio: {e}")
            traceback.print_exc()
            return False
    
    def run(self):
        """Main execution loop"""
        try:
            print("\n" + "="*60)
            print("🚀 DIGITAL UMUGANDA TRANSCRIPTION AUTOMATION")
            print("="*60)
            
            self.setup_driver()
            
            # Check login status
            if not self.check_login_status():
                print("❌ Login failed. Exiting...")
                return
            
            print("\n" + "="*60)
            print(f"▶️  STARTING AUTOMATED TRANSCRIPTION")
            print(f"Method: {self.transcription_method}")
            print("="*60 + "\n")
            
            # Process audios in loop
            while True:
                try:
                    success = self.process_audio()
                    
                    if not success:
                        print("\n⚠️  No more audios or error occurred.")
                        user_input = input("\nTry again? (y/n): ").strip().lower()
                        if user_input != 'y':
                            break
                        continue
                    
                    # Small delay before processing next audio
                    print("\n⏭️  Moving to next audio...")
                    time.sleep(3)
                
                except KeyboardInterrupt:
                    print("\n\n⏹️  Process interrupted by user.")
                    break
                except Exception as e:
                    print(f"\n❌ ERROR: {e}")
                    traceback.print_exc()
                    print("\nAttempting to continue...")
                    time.sleep(3)
            
            print(f"\n{'='*60}")
            print(f"✅ SESSION COMPLETE")
            print(f"📊 Total audios processed: {self.audio_count}")
            print(f"{'='*60}\n")
        
        except Exception as e:
            print(f"\n❌ FATAL ERROR: {e}")
            traceback.print_exc()
        
        finally:
            if self.driver:
                print("\nPress ENTER to close the browser...")
                input()
                self.driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Automated audio transcription for Digital Umuganda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using local Whisper model (free, no API key needed)
  python transcribe.py --url https://wajir-kenya254.web.app/transcribe --method whisper-local
  
  # Using OpenAI API (requires API key in .env or via --api-key)
  python transcribe.py --url https://wajir-kenya254.web.app/transcribe --method openai-api
  
  # Using Gemini API (requires API key in .env or via --gemini-key)
  python transcribe.py --url https://wajir-kenya254.web.app/transcribe --method gemini-api
  
  # Using OpenRouter with Gemini (requires API key in .env or via --openrouter-key)
  python transcribe.py --url https://wajir-kenya254.web.app/transcribe --method openrouter --openrouter-model google/gemini-pro-1.5
  
  # Using OpenRouter with GPT-4
  python transcribe.py --url https://wajir-kenya254.web.app/transcribe --method openrouter --openrouter-model openai/gpt-4-turbo
  
Installation:
  pip install selenium requests python-dotenv
  pip install openai-whisper  # for local Whisper
  pip install openai          # for OpenAI API
  pip install google-generativeai  # for Gemini API
  
.env file example:
  OPENAI_API_KEY=sk-...
  GEMINI_API_KEY=AIza...
  OPENROUTER_API_KEY=sk-or-v1-...
  OPENROUTER_MODEL=google/gemini-pro-1.5
        """
    )
    
    parser.add_argument(
        '--url',
        required=True,
        help='URL of the transcription website'
    )
    
    parser.add_argument(
        '--method',
        choices=['whisper-local', 'openai-api', 'gemini-api', 'openrouter'],
        default='whisper-local',
        help='Transcription method to use (default: whisper-local)'
    )
    
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (overrides OPENAI_API_KEY from .env)'
    )
    
    parser.add_argument(
        '--gemini-key',
        help='Gemini API key (overrides GEMINI_API_KEY from .env)'
    )
    
    parser.add_argument(
        '--openrouter-key',
        help='OpenRouter API key (overrides OPENROUTER_API_KEY from .env)'
    )
    
    parser.add_argument(
        '--openrouter-model',
        help='OpenRouter model to use (overrides OPENROUTER_MODEL from .env, default: google/gemini-pro-1.5)'
    )
    
    args = parser.parse_args()
    
    # Get API keys from .env or command line arguments
    openai_api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    gemini_api_key = args.gemini_key or os.getenv('GEMINI_API_KEY')
    openrouter_api_key = args.openrouter_key or os.getenv('OPENROUTER_API_KEY')
    openrouter_model = args.openrouter_model or os.getenv('OPENROUTER_MODEL') or 'google/gemini-pro-1.5'
    
    # Validate arguments
    if args.method == 'openai-api' and not openai_api_key:
        print("❌ ERROR: OpenAI API key required for openai-api method")
        print("Set OPENAI_API_KEY in .env file or pass via --api-key")
        sys.exit(1)
    
    if args.method == 'gemini-api' and not gemini_api_key:
        print("❌ ERROR: Gemini API key required for gemini-api method")
        print("Set GEMINI_API_KEY in .env file or pass via --gemini-key")
        sys.exit(1)
    
    if args.method == 'openrouter' and not openrouter_api_key:
        print("❌ ERROR: OpenRouter API key required for openrouter method")
        print("Set OPENROUTER_API_KEY in .env file or pass via --openrouter-key")
        sys.exit(1)
    
    try:
        # Create and run automation
        automation = TranscriptionAutomation(
            url=args.url,
            transcription_method=args.method,
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            openrouter_api_key=openrouter_api_key,
            openrouter_model=openrouter_model
        )
        
        automation.run()
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
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
        """Initialize Gemini transcription automation"""
        self.url = url
        self.gemini_api_key = gemini_api_key
        self.driver = None
        self.audio_count = 0
        
        # Initialize Gemini
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_api_key)
            
            # Use the latest native audio model
            self.gemini_model = genai.GenerativeModel(
                'models/gemini-2.0-flash-exp',
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for accuracy
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )
            )
            print("✓ Gemini 2.5 Flash Native Audio initialized!")
            
        except ImportError:
            print("ERROR: Install google-generativeai: pip install google-generativeai")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR initializing Gemini: {e}")
            sys.exit(1)
    
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
    
    def transcribe_audio(self, audio_file):
        """Transcribe audio using Gemini with optimized prompt"""
        try:
            print("Uploading to Gemini...")
            
            import google.generativeai as genai
            from google.api_core import exceptions
            
            # Upload file
            # audio_file_obj = genai.upload_file(audio_file)
            # print(f"✓ Uploaded: {audio_file_obj.name}")
            for attempt in range(3):
                try:
                    audio_file_obj = genai.upload_file(audio_file)
                    print(f"✓ Uploaded: {audio_file_obj.name}")
                    break
                except exceptions.ResourceExhausted as e:
                    print(f"⚠️  Upload attempt {attempt + 1} failed: {e}")
                    if attempt == 2:
                        raise
                    time.sleep(5)
            
            # Wait for processing
            print("Processing audio...")
            while audio_file_obj.state.name == "PROCESSING":
                time.sleep(2)
                audio_file_obj = genai.get_file(audio_file_obj.name)
            
            if audio_file_obj.state.name == "FAILED":
                print("❌ Processing failed")
                return None
            
            print("✓ Audio processed")
            
            # Optimized prompt for accurate Swahili transcription
            prompt = """Transcribe this Swahili audio with MAXIMUM ACCURACY.

CRITICAL RULES:
1. Transcribe ONLY what you hear - do NOT add, invent, or hallucinate words
2. If you're unsure about a word, transcribe your best guess but stay faithful to the audio
3. Do NOT add phrases like "thank you", "subscribe", or other common filler
4. Do NOT add music notes, [Music], or sound descriptions
5. Do NOT translate - keep everything in Swahili
6. Do NOT add introductions like "Here is the transcription:"
7. Maintain natural Swahili grammar and spelling

OUTPUT FORMAT:
Provide ONLY the raw transcription text. Nothing else.

Transcribe now:"""
            
            # Generate transcription
            print("Generating transcription...")
            response = self.gemini_model.generate_content(
                [prompt, audio_file_obj],
                request_options={"timeout": 120}
            )
            
            # Cleanup
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
                "[Music]",
                "[Applause]",
                "♪",
                "Thank you for watching",
                "Please subscribe",
            ]
            
            for artifact in artifacts:
                transcription = transcription.replace(artifact, "")
            
            # Clean up extra whitespace and newlines
            transcription = " ".join(transcription.split())
            
            print("✓ Transcription complete!")
            return transcription
            
        except Exception as e:
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
        """Main loop"""
        try:
            print("\n" + "="*60)
            print("🚀 GEMINI TRANSCRIPTION AUTOMATION")
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
            print(f"✅ COMPLETE - {self.audio_count} audios processed")
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
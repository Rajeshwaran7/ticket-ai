"""Audio service for handling voice recordings and speech-to-text conversion."""
import os
import uuid
from pathlib import Path
from typing import Dict, Optional
import subprocess
import sys

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("⚠️  speech_recognition not installed. Install with: pip install SpeechRecognition")
    print("   For offline STT, also install: pip install vosk")


def find_ffmpeg() -> Optional[str]:
    """
    Find ffmpeg executable in common locations or PATH.
    Returns path to ffmpeg.exe or None if not found.
    """
    # Check if ffmpeg is in PATH
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2)
        if result.returncode == 0:
            return 'ffmpeg'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Check common installation locations
    common_paths = [
        r'C:\Users\Admin\Downloads\ffmpeg-8.0-essentials_build\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe',
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
        os.path.expanduser(r'~\Downloads\ffmpeg\bin\ffmpeg.exe'),
        os.path.expanduser(r'~\Desktop\ffmpeg\bin\ffmpeg.exe'),
        # Check various download locations
        r'C:\Users\Admin\Downloads\ffmpeg\bin\ffmpeg.exe',
        r'C:\Users\Admin\Downloads\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe',
        r'C:\Users\Admin\Downloads\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe',
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None


class AudioService:
    """Service for processing audio files and converting speech to text."""

    def __init__(self, upload_dir: str = "uploads"):
        """
        Initialize audio service.
        
        Args:
            upload_dir: Directory to store uploaded audio files
        """
        self.upload_dir = upload_dir
        self.recognizer = None
        
        # Create upload directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)
        
        # Initialize speech recognizer
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
            except Exception as e:
                print(f"Warning: Could not initialize speech recognizer: {e}")

    def save_audio_file(self, file_content: bytes, filename: str, session_id: Optional[int] = None) -> Optional[str]:
        """
        Save audio file to disk and convert to MP3 if needed.
        
        Args:
            file_content: Audio file content
            filename: Original filename
            session_id: Optional session ID for organizing files
            
        Returns:
            Saved file path relative to uploads directory (MP3 format) or None if save fails
        """
        try:
            # Ensure upload directory exists
            os.makedirs(self.upload_dir, exist_ok=True)
            
            # Create session-specific directory if session_id provided
            if session_id:
                session_dir = os.path.join(self.upload_dir, f"session_{session_id}")
                os.makedirs(session_dir, exist_ok=True)
                upload_path = session_dir
            else:
                upload_path = self.upload_dir
            
            # Generate unique filename
            file_ext = Path(filename).suffix or ".webm"
            unique_id = str(uuid.uuid4())
            
            # Determine final file path - try MP3 first, fallback to original format
            final_file_path = os.path.join(upload_path, f"{unique_id}.mp3")
            original_file_path = os.path.join(upload_path, f"{unique_id}{file_ext}")
            
            # Save original file first
            temp_file_path = os.path.join(upload_path, f"{unique_id}_temp{file_ext}")
            try:
                with open(temp_file_path, 'wb') as f:
                    f.write(file_content)
                print(f"✅ Temp file saved: {temp_file_path}")
            except Exception as e:
                print(f"❌ Error writing temp file: {e}")
                raise
            
            # Convert to MP3 if not already MP3
            conversion_success = False
            if filename.lower().endswith('.mp3'):
                # Already MP3, just rename
                try:
                    os.rename(temp_file_path, final_file_path)
                    conversion_success = True
                    print(f"✅ MP3 file saved: {final_file_path}")
                except Exception as e:
                    print(f"❌ Error renaming MP3 file: {e}")
                    raise
            else:
                # Try to convert to MP3
                # Try pydub first (requires ffmpeg to be installed)
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(temp_file_path)
                    audio.export(final_file_path, format="mp3", bitrate="128k")
                    os.remove(temp_file_path)
                    conversion_success = True
                    print(f"✅ Converted to MP3 using pydub: {final_file_path}")
                except ImportError:
                    print("⚠️  pydub not available, trying ffmpeg...")
                except Exception as e:
                    print(f"⚠️  pydub conversion error: {e}, trying ffmpeg...")
                
                # Fallback to ffmpeg if pydub failed
                if not conversion_success:
                    ffmpeg_path = find_ffmpeg()
                    if ffmpeg_path:
                        try:
                            result = subprocess.run(
                                [ffmpeg_path, '-i', temp_file_path, '-codec:a', 'libmp3lame', '-b:a', '128k', final_file_path, '-y'],
                                capture_output=True,
                                check=True,
                                timeout=30
                            )
                            os.remove(temp_file_path)
                            conversion_success = True
                            print(f"✅ Converted to MP3 using ffmpeg: {final_file_path}")
                        except subprocess.TimeoutExpired:
                            print("⚠️  ffmpeg conversion timed out")
                        except Exception as e:
                            print(f"⚠️  ffmpeg conversion error: {e}")
                    else:
                        print("⚠️  ffmpeg not found. Please install ffmpeg and add it to PATH or place it in a common location.")
                
                # If conversion failed, keep original file format
                if not conversion_success:
                    print(f"⚠️  Could not convert to MP3, keeping original format: {file_ext}")
                    try:
                        os.rename(temp_file_path, original_file_path)
                        final_file_path = original_file_path
                        conversion_success = True
                        print(f"✅ Saved original format: {final_file_path}")
                    except Exception as e:
                        print(f"❌ Error renaming original file: {e}")
                        raise
            
            # Verify file was created
            if not os.path.exists(final_file_path):
                raise Exception(f"File was not created: {final_file_path}")
            
            # Return relative path for serving
            relative_path = final_file_path.replace("\\", "/")
            print(f"✅ Audio file saved successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            import traceback
            print(f"❌ Audio save error: {e}")
            traceback.print_exc()
            return None

    def convert_speech_to_text(self, audio_file_path: str) -> Dict[str, any]:
        """
        Convert speech to text using local STT engine (Google STT - free, no API key needed).
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Dictionary with transcribed text and status
        """
        if not self.recognizer:
            return {
                "success": False,
                "error": "Speech recognition not available. Please install SpeechRecognition library."
            }
        
        try:
            # Check if file exists
            if not os.path.exists(audio_file_path):
                return {
                    "success": False,
                    "error": f"Audio file not found: {audio_file_path}"
                }
            
            # Try to convert to WAV if needed (speech_recognition works better with WAV)
            wav_file_path = self._convert_to_wav(audio_file_path)
            
            # If conversion failed, try to use original file (might work for some formats)
            if not wav_file_path or not os.path.exists(wav_file_path):
                print(f"⚠️  WAV conversion failed, trying original file: {audio_file_path}")
                wav_file_path = audio_file_path
            
            # Try to load audio file
            audio_data = None
            wav_was_created = False
            
            try:
                with sr.AudioFile(wav_file_path) as source:
                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio_data = self.recognizer.record(source)
            except Exception as e:
                # If AudioFile fails, the format might not be supported
                return {
                    "success": False,
                    "error": f"Audio format not supported for speech recognition. Please install ffmpeg for format conversion. Error: {str(e)}"
                }
            
            # Use Google Speech Recognition (free, online, no API key needed)
            text = None
            error_msg = None
            
            try:
                text = self.recognizer.recognize_google(audio_data, language='en-US')
            except sr.UnknownValueError:
                error_msg = "Could not understand the audio. Please speak clearly."
            except sr.RequestError as e:
                error_msg = f"Speech recognition service error: {str(e)}"
            except Exception as e:
                error_msg = f"Speech recognition error: {str(e)}"
            
            # Clean up temporary WAV file if it was created
            if wav_file_path != audio_file_path and os.path.exists(wav_file_path):
                try:
                    os.remove(wav_file_path)
                except:
                    pass
            
            if text:
                return {
                    "success": True,
                    "text": text.strip(),
                    "confidence": None  # Google STT doesn't provide confidence in free version
                }
            else:
                return {
                    "success": False,
                    "error": error_msg or "Could not recognize speech. Please try again."
                }
                
        except Exception as e:
            import traceback
            print(f"❌ Speech recognition error: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Speech recognition error: {str(e)}"
            }

    def _convert_to_wav(self, audio_file_path: str) -> Optional[str]:
        """
        Convert audio file to WAV format using pydub or ffmpeg.
        
        Args:
            audio_file_path: Path to input audio file
            
        Returns:
            Path to WAV file or None if conversion failed
        """
        # Check if already WAV
        if audio_file_path.lower().endswith('.wav'):
            return audio_file_path
        
        try:
            # Try pydub first (easier to use, but requires ffmpeg)
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_file_path)
                wav_file_path = audio_file_path.rsplit('.', 1)[0] + '.wav'
                # Export as WAV with proper settings for speech recognition
                audio.set_frame_rate(16000).set_channels(1).export(wav_file_path, format="wav")
                if os.path.exists(wav_file_path):
                    return wav_file_path
            except ImportError:
                print("⚠️  pydub not available for WAV conversion")
            except Exception as e:
                print(f"⚠️  pydub WAV conversion error: {e}")
            
            # Try ffmpeg directly
            ffmpeg_path = find_ffmpeg()
            if ffmpeg_path:
                try:
                    result = subprocess.run(
                        [ffmpeg_path, '-version'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        wav_file_path = audio_file_path.rsplit('.', 1)[0] + '.wav'
                        subprocess.run(
                            [ffmpeg_path, '-i', audio_file_path, '-ar', '16000', '-ac', '1', wav_file_path, '-y'],
                            capture_output=True,
                            check=True,
                            timeout=30
                        )
                        if os.path.exists(wav_file_path):
                            return wav_file_path
                except subprocess.TimeoutExpired:
                    print("⚠️  ffmpeg WAV conversion timed out")
                except Exception as e:
                    print(f"⚠️  ffmpeg WAV conversion error: {e}")
            else:
                print("⚠️  ffmpeg not found for WAV conversion")
            
            # Conversion failed
            return None
            
        except Exception as e:
            print(f"⚠️  Audio conversion error: {e}")
            return None

    def process_audio_upload(
        self,
        file_content: bytes,
        filename: str,
        session_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Process audio upload: save file and convert to text.
        
        Args:
            file_content: Audio file content
            filename: Original filename
            session_id: Optional session ID
            
        Returns:
            Dictionary with file path, transcribed text, and status
        """
        # Validate file content
        if not file_content or len(file_content) == 0:
            return {
                "success": False,
                "error": "Audio file is empty"
            }
        
        # Save audio file
        file_path = self.save_audio_file(file_content, filename, session_id)
        
        if not file_path:
            return {
                "success": False,
                "error": "Failed to save audio file. Check server logs for details."
            }
        
        # Get absolute path for STT processing
        abs_file_path = file_path if os.path.isabs(file_path) else os.path.join(os.getcwd(), file_path)
        
        # Verify file exists before STT
        if not os.path.exists(abs_file_path):
            return {
                "success": False,
                "error": f"Audio file not found at: {abs_file_path}",
                "audio_file_path": file_path  # Still return relative path
            }
        
        # Convert speech to text (this may fail if ffmpeg not available, but file is saved)
        stt_result = self.convert_speech_to_text(abs_file_path)
        
        if not stt_result.get("success"):
            # File is saved successfully, but STT failed
            # Return success with empty text - user can still replay audio
            return {
                "success": True,  # File saved successfully
                "audio_file_path": file_path,
                "text": "",  # Empty text - STT failed
                "error": stt_result.get("error", "Failed to convert speech to text. Audio file saved but transcription unavailable. Please install ffmpeg for speech-to-text conversion.")
            }
        
        return {
            "success": True,
            "audio_file_path": file_path,
            "text": stt_result.get("text", ""),
            "confidence": stt_result.get("confidence")
        }


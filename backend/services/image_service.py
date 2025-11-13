"""Image processing service for screenshot text extraction."""
import os
from typing import Optional, Dict
from PIL import Image
import io
import base64

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("Warning: pytesseract not available. OCR functionality will be limited.")


class ImageService:
    """Service for processing images and extracting text."""
    
    def __init__(self):
        """Initialize image service."""
        self.max_size = (1920, 1080)  # Max image dimensions
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def validate_image(self, file_content: bytes) -> bool:
        """
        Validate image file.
        
        Args:
            file_content: Image file content
            
        Returns:
            True if valid, False otherwise
        """
        if len(file_content) > self.max_file_size:
            return False
        
        try:
            image = Image.open(io.BytesIO(file_content))
            image.verify()
            return True
        except Exception:
            return False
    
    def extract_text_from_image(self, file_content: bytes) -> Optional[str]:
        """
        Extract text from image using OCR.
        
        Args:
            file_content: Image file content
            
        Returns:
            Extracted text or None if extraction fails
        """
        if not TESSERACT_AVAILABLE:
            return None
        
        try:
            image = Image.open(io.BytesIO(file_content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large
            if image.size[0] > self.max_size[0] or image.size[1] > self.max_size[1]:
                image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image)
            return text.strip() if text else None
            
        except Exception as e:
            print(f"OCR extraction error: {e}")
            return None
    
    def save_image(self, file_content: bytes, filename: str, upload_dir: str = "uploads") -> Optional[str]:
        """
        Save image to disk.
        
        Args:
            file_content: Image file content
            filename: Original filename
            upload_dir: Upload directory
            
        Returns:
            Saved file path or None if save fails
        """
        try:
            # Create upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename
            import uuid
            from pathlib import Path
            ext = Path(filename).suffix
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return file_path
            
        except Exception as e:
            print(f"Image save error: {e}")
            return None
    
    def process_screenshot(self, file_content: bytes, filename: str) -> Dict[str, Optional[str]]:
        """
        Process screenshot: validate, extract text, and save.
        
        Args:
            file_content: Image file content
            filename: Original filename
            
        Returns:
            Dictionary with extracted_text and file_path
        """
        result = {
            "extracted_text": None,
            "file_path": None,
            "error": None
        }
        
        # Validate image
        if not self.validate_image(file_content):
            result["error"] = "Invalid image file or file too large (max 10MB)"
            return result
        
        # Extract text
        extracted_text = self.extract_text_from_image(file_content)
        if extracted_text:
            result["extracted_text"] = extracted_text
        
        # Save image
        file_path = self.save_image(file_content, filename)
        if file_path:
            result["file_path"] = file_path
        
        return result


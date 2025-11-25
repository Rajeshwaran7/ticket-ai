"""Document processing service for OCR and text extraction from various file types."""
import os
import uuid
import base64
from pathlib import Path
from typing import Optional, Dict, List
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠️  pytesseract not installed. OCR functionality will be limited.")

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️  PyPDF2 not installed. PDF text extraction will be disabled.")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️  python-docx not installed. DOCX text extraction will be disabled.")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI not available. Image understanding will use free alternatives.")

from services.elsai_connection import ElsaiConnection

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️  requests not installed. Install with: pip install requests")

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
    import torch
    TRANSFORMERS_AVAILABLE = True
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️  transformers not installed. Local vision model unavailable. Install with: pip install transformers torch")


class DocumentService:
    """Service for processing documents and extracting text."""
    
    def __init__(self, upload_dir: str = "uploads/documents"):
        """
        Initialize document service.
        
        Args:
            upload_dir: Directory to save uploaded documents
        """
        self.upload_dir = upload_dir
        self.max_file_size = 20 * 1024 * 1024  # 20MB
        self.supported_image_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/tiff']
        self.supported_doc_types = ['application/pdf', 'application/msword', 
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        self.elsai_connection = ElsaiConnection()
        
        # Create upload directory
        os.makedirs(self.upload_dir, exist_ok=True)
    
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
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image)
            return text.strip() if text else None
            
        except Exception as e:
            print(f"OCR extraction error: {e}")
            return None
    
    def understand_image_content(self, file_content: bytes, filename: str = "image") -> Optional[Dict[str, any]]:
        """
        Understand image content using local vision models or OCR analysis (free, works offline).
        Optionally falls back to OpenAI Vision API if available.
        
        Args:
            file_content: Image file content
            filename: Image filename
            
        Returns:
            Dictionary with image description, context, and suggested ticket category
        """
        # Try local vision model first (if transformers available)
        if TRANSFORMERS_AVAILABLE:
            vision_result = self._understand_image_local_vision(file_content, filename)
            if vision_result:
                return vision_result
        
        # Primary method: Use local OCR + enhanced keyword analysis (works offline, free)
        ocr_result = self._understand_image_keywords(file_content, filename)
        if ocr_result:
            return ocr_result
        
        # Optional fallback: Use OpenAI Vision API if available (requires API key)
        if OPENAI_AVAILABLE:
            openai_result = self._understand_image_openai(file_content, filename)
            if openai_result:
                return openai_result
        
        # Final fallback: return basic result
        return {
            "description": f"Image uploaded: {filename}",
            "issues": [],
            "suggested_category": "general",
            "reason": "Unable to analyze image content",
            "severity": "low"
        }
    
    def _understand_image_local_vision(self, file_content: bytes, filename: str) -> Optional[Dict[str, any]]:
        """
        Use local BLIP vision model for image understanding (free, works offline).
        Requires transformers library and torch.
        
        Args:
            file_content: Image file content as bytes
            filename: Image filename
            
        Returns:
            Dictionary with image description, issues, suggested category, etc.
        """
        if not TRANSFORMERS_AVAILABLE:
            return None
        
        try:
            # Load model and processor (cached after first load)
            if not hasattr(self, '_blip_processor'):
                print("📥 Loading local BLIP vision model (first time only)...")
                self._blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                self._blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(DEVICE)
                print("✅ Local vision model loaded successfully")
            
            # Load and preprocess image
            image = Image.open(io.BytesIO(file_content))
            
            # Generate caption
            inputs = self._blip_processor(image, return_tensors="pt").to(DEVICE)
            out = self._blip_model.generate(**inputs, max_length=50)
            description = self._blip_processor.decode(out[0], skip_special_tokens=True)
            
            if not description or description.strip() == "":
                return None
            
            # Analyze description for ticket category
            description_lower = description.lower()
            issues = []
            suggested_category = "general"
            reason = ""
            severity = "medium"
            
            # Detect issues and category
            damage_keywords = ["broken", "crack", "damage", "shatter", "destroy", "cracked", "torn", "ripped", "defective"]
            technical_keywords = ["error", "bug", "crash", "fail", "not working", "issue", "problem", "glitch", "malfunction"]
            billing_keywords = ["invoice", "bill", "payment", "charge", "refund", "cost", "price", "receipt", "transaction", "money"]
            
            if any(word in description_lower for word in damage_keywords):
                issues.append("Product damage")
                suggested_category = "delivery"
                reason = "Product appears damaged or broken"
                severity = "high"
            elif any(word in description_lower for word in technical_keywords):
                issues.append("Technical issue")
                suggested_category = "technical"
                reason = "Technical error detected"
                severity = "high"
            elif any(word in description_lower for word in billing_keywords):
                issues.append("Billing related")
                suggested_category = "billing"
                reason = "Billing or payment related"
                severity = "medium"
            
            return {
                "description": description,
                "issues": issues,
                "suggested_category": suggested_category,
                "reason": reason or f"Based on image description: {description[:100]}",
                "severity": severity,
                "model_used": "local_blip"
            }
            
        except Exception as e:
            print(f"⚠️  Local vision model error: {e}")
            # Clear cached model on error
            if hasattr(self, '_blip_processor'):
                delattr(self, '_blip_processor')
                delattr(self, '_blip_model')
            return None
    
    def _understand_image_openai(self, file_content: bytes, filename: str) -> Optional[Dict[str, any]]:
        """
        Use Azure OpenAI Vision API via ElsaiConnection (if vision is supported).
        Falls back to text-only analysis if vision is not available.
        """
        try:
            # Try using ElsaiConnection first
            if self.elsai_connection.is_available():
                # Convert image to base64
                image_base64 = base64.b64encode(file_content).decode('utf-8')
                
                # Determine image format
                image_format = "png" if filename.lower().endswith('.png') else "jpeg"
                
                # Use Azure OpenAI Vision API to understand the image
                prompt = """Analyze this image and provide:
1. A detailed description of what you see
2. Any issues or problems visible (e.g., broken items, damage, errors)
3. What type of support ticket this would be:
   - "delivery" if it's about damaged/broken products, shipping issues, wrong items
   - "technical" if it's about software errors, UI issues, technical problems
   - "billing" if it's about payment, invoices, charges
   - "general" for other issues

Respond in JSON format:
{
    "description": "detailed description",
    "issues": ["list of issues found"],
    "suggested_category": "delivery|technical|billing|general",
    "reason": "why this category",
    "severity": "high|medium|low"
}"""
                
                # Note: Azure OpenAI Vision API requires specific message format
                # If the connector doesn't support vision, fall back to text-only
                try:
                    # Try with vision message format
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{image_format};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ]
                    response_text = self.elsai_connection.invoke(messages=messages)
                except Exception as vision_error:
                    # If vision not supported, fall back to text-only with OCR
                    print(f"Vision API not available via ElsaiConnection, using text-only analysis: {vision_error}")
                    return None
            
            # Fallback to direct OpenAI client if ElsaiConnection doesn't support vision
            if OPENAI_AVAILABLE:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return None
                
                client = OpenAI(api_key=api_key)
                
                # Convert image to base64
                image_base64 = base64.b64encode(file_content).decode('utf-8')
                
                # Determine image format
                image_format = "png" if filename.lower().endswith('.png') else "jpeg"
                
                prompt = """Analyze this image and provide:
1. A detailed description of what you see
2. Any issues or problems visible (e.g., broken items, damage, errors)
3. What type of support ticket this would be:
   - "delivery" if it's about damaged/broken products, shipping issues, wrong items
   - "technical" if it's about software errors, UI issues, technical problems
   - "billing" if it's about payment, invoices, charges
   - "general" for other issues

Respond in JSON format:
{
    "description": "detailed description",
    "issues": ["list of issues found"],
    "suggested_category": "delivery|technical|billing|general",
    "reason": "why this category",
    "severity": "high|medium|low"
}"""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{image_format};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500
                )
                
                import json
                import re
                
                response_text = response.choices[0].message.content
                
                # Extract JSON from response (handle nested JSON)
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        # Validate required fields
                        if "description" in result and "suggested_category" in result:
                            return result
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: parse description from text
                return {
                    "description": response_text[:500],
                    "issues": [],
                    "suggested_category": "general",
                    "reason": "Could not parse structured response",
                    "severity": "medium"
                }
            
            return None
            
        except Exception as e:
            print(f"Azure OpenAI image understanding error: {e}")
            return None
    
    def _understand_image_keywords(self, file_content: bytes, filename: str) -> Optional[Dict[str, any]]:
        """
        Enhanced OCR + keyword analysis for image understanding.
        This is free, works locally, and doesn't require external APIs.
        
        Args:
            file_content: Image file content
            filename: Image filename
            
        Returns:
            Dictionary with image analysis results
        """
        try:
            # Extract text using OCR
            ocr_text = self.extract_text_from_image(file_content)
            
            # Analyze image properties for additional context
            image_info = self._analyze_image_properties(file_content, filename)
            
            if not ocr_text and not image_info.get("has_content"):
                return {
                    "description": f"Image uploaded: {filename} - no text detected",
                    "issues": [],
                    "suggested_category": "general",
                    "reason": "No text found in image, cannot determine category",
                    "severity": "low"
                }
            
            # Combine OCR text and image analysis
            description_parts = []
            if ocr_text:
                description_parts.append(f"Extracted text: {ocr_text[:300]}")
            if image_info.get("description"):
                description_parts.append(image_info.get("description"))
            
            combined_text = " ".join(description_parts).lower() if description_parts else ""
            
            # Enhanced keyword-based category detection
            issues = []
            suggested_category = "general"
            reason = ""
            severity = "medium"
            
            # Comprehensive keyword sets
            delivery_keywords = [
                "broken", "damage", "crack", "shatter", "delivery", "shipping", 
                "wrong", "missing", "defective", "torn", "ripped", "destroyed",
                "package", "order", "product", "item", "received"
            ]
            technical_keywords = [
                "error", "bug", "crash", "fail", "not working", "issue", "problem",
                "glitch", "malfunction", "broken", "freeze", "hang", "slow",
                "login", "password", "account", "access", "permission"
            ]
            billing_keywords = [
                "invoice", "bill", "payment", "charge", "refund", "cost", "price",
                "receipt", "transaction", "money", "amount", "due", "balance",
                "credit", "debit", "card", "bank", "account"
            ]
            
            # Detect category based on keywords
            delivery_score = sum(1 for keyword in delivery_keywords if keyword in combined_text)
            technical_score = sum(1 for keyword in technical_keywords if keyword in combined_text)
            billing_score = sum(1 for keyword in billing_keywords if keyword in combined_text)
            
            if delivery_score > 0 and delivery_score >= technical_score and delivery_score >= billing_score:
                suggested_category = "delivery"
                reason = f"Detected {delivery_score} delivery-related keywords"
                if any(word in combined_text for word in ["broken", "damage", "crack", "defective"]):
                    issues.append("Product damage")
                    severity = "high"
                elif any(word in combined_text for word in ["wrong", "missing"]):
                    issues.append("Wrong or missing item")
                    severity = "high"
                else:
                    issues.append("Delivery issue")
                    severity = "medium"
            
            elif technical_score > 0 and technical_score >= billing_score:
                suggested_category = "technical"
                reason = f"Detected {technical_score} technical-related keywords"
                issues.append("Technical problem")
                severity = "high"
            
            elif billing_score > 0:
                suggested_category = "billing"
                reason = f"Detected {billing_score} billing-related keywords"
                issues.append("Billing related")
                severity = "medium"
            
            # Build description
            description = ocr_text[:500] if ocr_text else f"Image: {filename}"
            if image_info.get("description"):
                description = f"{description}\n{image_info.get('description')}"
            
            return {
                "description": description,
                "issues": issues,
                "suggested_category": suggested_category,
                "reason": reason or "Based on OCR text and image analysis",
                "severity": severity
            }
            
        except Exception as e:
            print(f"OCR-based image understanding error: {e}")
            return None
    
    def _analyze_image_properties(self, file_content: bytes, filename: str) -> Dict[str, any]:
        """
        Analyze basic image properties for additional context.
        
        Args:
            file_content: Image file content
            filename: Image filename
            
        Returns:
            Dictionary with image analysis results
        """
        result = {
            "has_content": False,
            "description": ""
        }
        
        try:
            image = Image.open(io.BytesIO(file_content))
            width, height = image.size
            mode = image.mode
            
            # Basic image analysis
            result["has_content"] = True
            
            # Determine image type from filename
            filename_lower = filename.lower() if filename else ""
            image_type = "image"
            if "screenshot" in filename_lower or "screen" in filename_lower:
                image_type = "screenshot"
            elif "receipt" in filename_lower or "invoice" in filename_lower:
                image_type = "document"
            elif "payment" in filename_lower or "bill" in filename_lower:
                image_type = "payment document"
            
            # Build description
            desc_parts = [f"{image_type.capitalize()} ({width}x{height}px)"]
            
            # Check if image is likely a document (high resolution, specific aspect ratio)
            if width > 800 and height > 1000:
                desc_parts.append("appears to be a document")
            
            result["description"] = ", ".join(desc_parts)
            
        except Exception as e:
            # If image analysis fails, that's okay - OCR will handle it
            pass
        
        return result
    
    def extract_text_from_pdf(self, file_content: bytes) -> Optional[str]:
        """
        Extract text from PDF file.
        
        Args:
            file_content: PDF file content
            
        Returns:
            Extracted text or None if extraction fails
        """
        if not PDF_AVAILABLE:
            return None
        
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"[Page {page_num + 1}]\n{text}")
                except Exception as e:
                    print(f"Error extracting text from page {page_num + 1}: {e}")
                    continue
            
            return "\n\n".join(text_parts).strip() if text_parts else None
            
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return None
    
    def extract_text_from_docx(self, file_content: bytes) -> Optional[str]:
        """
        Extract text from DOCX file.
        
        Args:
            file_content: DOCX file content
            
        Returns:
            Extracted text or None if extraction fails
        """
        if not DOCX_AVAILABLE:
            return None
        
        try:
            docx_file = io.BytesIO(file_content)
            doc = Document(docx_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            return "\n\n".join(text_parts).strip() if text_parts else None
            
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return None
    
    def save_document(self, file_content: bytes, filename: str, session_id: Optional[int] = None) -> Optional[str]:
        """
        Save document to disk.
        
        Args:
            file_content: File content
            filename: Original filename
            session_id: Optional session ID for organizing files
            
        Returns:
            Saved file path (relative) or None if save fails
        """
        try:
            # Create session-specific directory if session_id provided
            if session_id:
                session_dir = os.path.join(self.upload_dir, f"session_{session_id}")
                os.makedirs(session_dir, exist_ok=True)
                upload_path = session_dir
            else:
                upload_path = self.upload_dir
            
            # Generate unique filename
            ext = Path(filename).suffix
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(upload_path, unique_filename)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Return relative path
            return file_path.replace("\\", "/")
            
        except Exception as e:
            print(f"Document save error: {e}")
            return None
    
    def process_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        session_id: Optional[int] = None
    ) -> Dict[str, Optional[str]]:
        """
        Process document: extract text and save file.
        
        Args:
            file_content: File content
            filename: Original filename
            content_type: MIME type of the file
            session_id: Optional session ID
            
        Returns:
            Dictionary with extracted_text, file_path, image_understanding, and metadata
        """
        result = {
            "extracted_text": None,
            "file_path": None,
            "file_type": None,
            "image_understanding": None,
            "error": None
        }
        
        # Validate file size
        if len(file_content) > self.max_file_size:
            result["error"] = f"File too large (max {self.max_file_size / 1024 / 1024}MB)"
            return result
        
        # Determine file type and extract text
        if content_type.startswith('image/'):
            result["file_type"] = "image"
            
            # Extract text using OCR
            ocr_text = self.extract_text_from_image(file_content)
            result["extracted_text"] = ocr_text
            
            # Understand image content using Vision API
            image_understanding = self.understand_image_content(file_content, filename)
            if image_understanding:
                result["image_understanding"] = image_understanding
                
                # Enhance extracted text with image understanding
                if image_understanding.get("description"):
                    understanding_text = f"[Image Analysis]\n"
                    understanding_text += f"Description: {image_understanding.get('description')}\n"
                    if image_understanding.get("issues"):
                        understanding_text += f"Issues: {', '.join(image_understanding.get('issues', []))}\n"
                    understanding_text += f"Suggested Category: {image_understanding.get('suggested_category', 'general')}\n"
                    understanding_text += f"Reason: {image_understanding.get('reason', '')}\n"
                    
                    # Combine OCR text with understanding
                    if ocr_text:
                        result["extracted_text"] = f"{ocr_text}\n\n{understanding_text}"
                    else:
                        result["extracted_text"] = understanding_text
                        
        elif content_type == 'application/pdf':
            result["file_type"] = "pdf"
            result["extracted_text"] = self.extract_text_from_pdf(file_content)
        elif content_type in ['application/msword', 
                              'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            result["file_type"] = "docx"
            result["extracted_text"] = self.extract_text_from_docx(file_content)
        else:
            result["error"] = f"Unsupported file type: {content_type}"
            return result
        
        # Save document
        file_path = self.save_document(file_content, filename, session_id)
        if file_path:
            result["file_path"] = file_path
        else:
            result["error"] = "Failed to save document"
        
        return result


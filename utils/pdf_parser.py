import os
import tempfile
import shutil
import subprocess
from typing import Optional, Tuple
import signal
import threading
from contextlib import contextmanager

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

# Load environment variables
load_dotenv()

# S3 Configuration (reuse the same creds/env as in main.py)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")  # source bucket where PDFs are uploaded by main.py
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

# Destination bucket for parsed text
DEST_BUCKET_NAME = os.getenv("P2T_BUCKET_NAME", "palladium-pdf-to-text")
DEFAULT_STEP_TIMEOUT_SEC = int(os.getenv("PROCESS_STEP_TIMEOUT_SEC") or "600")


class TimeoutException(Exception):
    pass


@contextmanager
def time_limit(seconds: int, desc: str = "operation"):
    """Abort the current operation if it exceeds the given time budget."""
    if seconds is None or seconds <= 0:
        yield
        return

    # Check if we're in the main thread
    if threading.current_thread() is threading.main_thread():
        # Use signal-based timeout (Unix-only, main thread only)
        def _handler(signum, frame):
            raise TimeoutException(f"Timed out after {seconds}s during {desc}")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Fallback: just yield without timeout (signal doesn't work in threads)
        print(f"Warning: Timeout not enforced for {desc} (not in main thread)")
        yield


def init_s3_client() -> Optional[boto3.client]:
    if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]):
        print("Warning: S3 credentials not fully configured. Parser will not run.")
        return None
    try:
        return boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        )
    except Exception as e:
        print(f"Error initializing S3 client: {e}")
        return None


def create_marker_converter() -> PdfConverter:
    # Create model artifacts once and reuse
    artifact_dict = create_model_dict()
    return PdfConverter(artifact_dict=artifact_dict)


def pdf_to_markdown_local(converter: PdfConverter, input_pdf: str) -> Tuple[str, dict, list]:
    rendered = converter(input_pdf)
    text, metadata, images = text_from_rendered(rendered)
    return text, metadata, images


def parse_single_pdf(
    pdf_path: str,
    min_text_len_for_no_ocr: int = 500,
    use_ocr_by_default: bool = True,
    timeout_sec: int = DEFAULT_STEP_TIMEOUT_SEC
) -> Tuple[Optional[str], Optional[dict], Optional[list], bool]:
    """
    Parse a single PDF file and return the markdown text, metadata, images, and OCR usage flag.
    
    Args:
        pdf_path: Path to the PDF file to parse
        min_text_len_for_no_ocr: Minimum text length to skip OCR fallback
        use_ocr_by_default: Whether to try OCR first
        timeout_sec: Timeout in seconds for each conversion step
        
    Returns:
        Tuple of (text, metadata, images, used_ocr)
        - text: Extracted markdown text or None if failed
        - metadata: Metadata dict or None if failed
        - images: List of images or None if failed
        - used_ocr: Boolean indicating if OCR was used
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If parsing fails completely
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not pdf_path.lower().endswith('.pdf'):
        raise ValueError(f"File must be a PDF: {pdf_path}")
    
    converter = create_marker_converter()
    used_ocr = False
    text = None
    metadata = None
    images = None
    
    # Try OCR first if enabled by default
    if use_ocr_by_default:
        ocr_pdf = try_ocrmypdf(pdf_path)
        if ocr_pdf:
            try:
                with time_limit(timeout_sec, desc=f"marker conversion (OCR) for {pdf_path}"):
                    text, metadata, images = pdf_to_markdown_local(converter, ocr_pdf)
                used_ocr = True
                print(f"OCR applied to {pdf_path}")
            except Exception as e:
                print(f"Marker conversion after OCR failed for {pdf_path}: {e}")
                # Fall back to original PDF
                pass
            finally:
                # Clean up OCR temp file
                if ocr_pdf and os.path.exists(ocr_pdf):
                    try:
                        os.remove(ocr_pdf)
                        # Also remove the temp directory if it's empty
                        ocr_dir = os.path.dirname(ocr_pdf)
                        if os.path.exists(ocr_dir):
                            os.rmdir(ocr_dir)
                    except:
                        pass
    
    # If OCR wasn't used or failed, try original PDF
    if text is None:
        try:
            with time_limit(timeout_sec, desc=f"marker conversion (original) for {pdf_path}"):
                text, metadata, images = pdf_to_markdown_local(converter, pdf_path)
        except Exception as e:
            print(f"Marker conversion failed for {pdf_path}: {e}")
            raise Exception(f"Failed to parse PDF: {e}")
    
    # If text is still too short and we haven't tried OCR yet, try it now
    if not used_ocr and (text or "").strip().__len__() < min_text_len_for_no_ocr:
        ocr_pdf = try_ocrmypdf(pdf_path)
        if ocr_pdf:
            try:
                with time_limit(timeout_sec, desc=f"marker conversion (OCR second attempt) for {pdf_path}"):
                    text, metadata, images = pdf_to_markdown_local(converter, ocr_pdf)
                used_ocr = True
                print(f"OCR applied to {pdf_path} (second attempt)")
            except Exception as e:
                print(f"Marker conversion after OCR failed for {pdf_path}: {e}")
            finally:
                # Clean up OCR temp file
                if ocr_pdf and os.path.exists(ocr_pdf):
                    try:
                        os.remove(ocr_pdf)
                        # Also remove the temp directory if it's empty
                        ocr_dir = os.path.dirname(ocr_pdf)
                        if os.path.exists(ocr_dir):
                            os.rmdir(ocr_dir)
                    except:
                        pass
    
    return text, metadata, images, used_ocr


def try_ocrmypdf(input_pdf: str) -> Optional[str]:
    """If ocrmypdf is available, OCR the input PDF into a new temp file and return its path."""
    ocrmypdf_path = shutil.which("ocrmypdf")
    if not ocrmypdf_path:
        return None

    ocr_dir = tempfile.mkdtemp(prefix="ocrpdf_")
    ocr_pdf = os.path.join(ocr_dir, "ocr.pdf")
    try:
        # Use fast settings; keep original image; add text layer
        cmd = [
            ocrmypdf_path,
            "--fast-web-view", "1",
            "--optimize", "0",
            "--force-ocr",
            input_pdf,
            ocr_pdf,
        ]
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DEFAULT_STEP_TIMEOUT_SEC,
        )
        return ocr_pdf if os.path.exists(ocr_pdf) else None
    except subprocess.CalledProcessError as e:
        print(f"OCR command failed with exit code {e.returncode}: {e.stderr.decode('utf-8', errors='ignore')}")
        return None
    except subprocess.TimeoutExpired as e:
        print(f"OCR timed out after {DEFAULT_STEP_TIMEOUT_SEC}s: {e}")
        return None
    except Exception as e:
        print(f"Error during OCR: {e}")
        return None


def list_pdfs(s3_client: boto3.client, bucket: str, prefix: Optional[str] = None):
    paginator = s3_client.get_paginator("list_objects_v2")
    kwargs = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix

    for page in paginator.paginate(**kwargs):
        for obj in page.get("Contents", []) or []:
            key = obj.get("Key")
            if key and key.lower().endswith(".pdf"):
                yield key


def dest_object_exists(s3_client: boto3.client, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey"):
            return False
        # For permission or other errors, assume it doesn't exist to proceed
        return False


def change_ext(path: str, new_ext: str) -> str:
    base, _ = os.path.splitext(path)
    return f"{base}{new_ext}"


def process_one_pdf(
    s3_client: boto3.client,
    converter: PdfConverter,
    src_bucket: str,
    src_key: str,
    dest_bucket: str,
    min_text_len_for_no_ocr: int = 500,
    use_ocr_by_default: bool = True,
) -> bool:
    # Map source key to destination keys
    dest_md_key = change_ext(src_key, ".md")
    dest_meta_key = change_ext(src_key, ".meta.json")

    if dest_object_exists(s3_client, dest_bucket, dest_md_key):
        print(f"Skip already processed: {src_key}")
        return True

    # Download to temp
    tmp_dir = tempfile.mkdtemp(prefix="pdfproc_")
    local_pdf = os.path.join(tmp_dir, os.path.basename(src_key))

    try:
        with open(local_pdf, "wb") as f:
            s3_client.download_fileobj(src_bucket, src_key, f)
    except Exception as e:
        print(f"Failed download s3://{src_bucket}/{src_key}: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    used_ocr = False
    text = None
    metadata = None
    images = None

    # Try OCR first if enabled by default
    if use_ocr_by_default:
        ocr_pdf = try_ocrmypdf(local_pdf)
        if ocr_pdf:
            try:
                with time_limit(DEFAULT_STEP_TIMEOUT_SEC, desc=f"marker conversion (OCR) for {src_key}"):
                    text, metadata, images = pdf_to_markdown_local(converter, ocr_pdf)
                used_ocr = True
                print(f"OCR applied to {src_key}")
            except Exception as e:
                print(f"Marker conversion after OCR failed for {src_key}: {e}")
                # Fall back to original PDF
                pass

    # If OCR wasn't used or failed, try original PDF
    if text is None:
        try:
            with time_limit(DEFAULT_STEP_TIMEOUT_SEC, desc=f"marker conversion (original) for {src_key}"):
                text, metadata, images = pdf_to_markdown_local(converter, local_pdf)
        except Exception as e:
            print(f"Marker conversion failed for {src_key}: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False

    # If text is still too short and we haven't tried OCR yet, try it now
    if not used_ocr and (text or "").strip().__len__() < min_text_len_for_no_ocr:
        ocr_pdf = try_ocrmypdf(local_pdf)
        if ocr_pdf:
            try:
                with time_limit(DEFAULT_STEP_TIMEOUT_SEC, desc=f"marker conversion (OCR second attempt) for {src_key}"):
                    text, metadata, images = pdf_to_markdown_local(converter, ocr_pdf)
                used_ocr = True
            except Exception as e:
                print(f"Marker conversion after OCR failed for {src_key}: {e}")

    # Upload results
    try:
        s3_client.put_object(
            Bucket=dest_bucket,
            Key=dest_md_key,
            Body=(text or "").encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )
        # Minimal metadata JSON
        import json

        meta_payload = {
            "source_bucket": src_bucket,
            "source_key": src_key,
            "ocr_used": used_ocr,
            "page_count": len((metadata or {}).get("page_stats", [])) if isinstance(metadata, dict) else None,
        }
        s3_client.put_object(
            Bucket=dest_bucket,
            Key=dest_meta_key,
            Body=json.dumps(meta_payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Processed and uploaded: {src_key} -> s3://{dest_bucket}/{dest_md_key}")
        return True
    except Exception as e:
        print(f"Upload failed for {src_key}: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_batch(prefix: Optional[str] = None, max_items: Optional[int] = None) -> None:
    s3_client = init_s3_client()
    if not s3_client:
        return

    if not S3_BUCKET_NAME:
        print("Source S3 bucket (S3_BUCKET_NAME) is not set.")
        return

    # Ensure destination bucket exists (best-effort)
    try:
        s3_client.head_bucket(Bucket=DEST_BUCKET_NAME)
    except ClientError:
        try:
            s3_client.create_bucket(Bucket=DEST_BUCKET_NAME)
        except ClientError:
            # If cannot create, assume it exists or we lack perms; continue
            pass

    converter = create_marker_converter()

    count = 0
    for key in list_pdfs(s3_client, S3_BUCKET_NAME, prefix=prefix):
        ok = process_one_pdf(
            s3_client=s3_client,
            converter=converter,
            src_bucket=S3_BUCKET_NAME,
            src_key=key,
            dest_bucket=DEST_BUCKET_NAME,
        )
        if ok:
            count += 1
        if max_items is not None and count >= max_items:
            break

    print(f"Done. Processed: {count}")


if __name__ == "__main__":
    # Simple CLI via environment variables:
    #   PREFIX: optional S3 key prefix to limit processing
    #   MAX_ITEMS: optional int to limit number processed in one run
    prefix = os.getenv("PREFIX") or None
    try:
        max_items = int(os.getenv("MAX_ITEMS") or "0")
        if max_items <= 0:
            max_items = None
    except Exception:
        max_items = None

    run_batch(prefix=prefix, max_items=max_items)
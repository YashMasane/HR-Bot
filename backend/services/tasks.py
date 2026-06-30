from backend.core.celery_app import celery_app
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="process_document")
def process_document_task(file_path: str, department: str):
    """
    Placeholder task for processing uploaded documents asynchronously.
    In Phase 4, this will trigger the RAG ingestion pipeline (loading, chunking, embedding).
    """
    logger.info(f"Starting document processing for: {file_path}")
    
    # Simulate heavy processing
    time.sleep(5)
    
    logger.info(f"Successfully processed document: {file_path} for department: {department}")
    return {"status": "success", "file_path": file_path, "department": department}

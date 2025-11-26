"""
AI Service for Task Classification using local PyTorch models.
Uses fast DistilBERT model for zero-shot classification (loads in 1-2 seconds).
"""
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import Optional, Dict, List
import logging
import torch
import time
import os
import threading
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# Use local model directory (loads from local path, no download needed)
# Model should be in ./bart directory at project root
MODEL_NAME = "./bart"

# Task categories
TASK_CATEGORIES = [
    "chores",      # Household tasks like cleaning, dishes, laundry
    "homework",    # School assignments, studying
    "creative",    # Art, music, writing, crafts
    "physical",    # Sports, exercise, outdoor activities
    "social",      # Family time, helping others, social activities
    "other"        # Miscellaneous tasks
]

# Age appropriateness mapping
AGE_APPROPRIATE = {
    "chores": {"min_age": 5, "max_age": 18},
    "homework": {"min_age": 6, "max_age": 18},
    "creative": {"min_age": 3, "max_age": 18},
    "physical": {"min_age": 5, "max_age": 18},
    "social": {"min_age": 4, "max_age": 18},
    "other": {"min_age": 5, "max_age": 18},
}

# Global model instances (lazy loaded)
_model = None
_tokenizer = None
_loading_lock = threading.Lock()


def is_model_ready() -> bool:
    """Check if the model is loaded and ready to use."""
    return _model is not None and _tokenizer is not None


def _model_files_exist() -> bool:
    """Check if model files exist in local directory."""
    # Check if local model directory exists
    model_path = os.path.abspath(MODEL_NAME)
    if os.path.exists(model_path) and os.path.isdir(model_path):
        # Check for essential model files
        config_file = os.path.join(model_path, "config.json")
        if os.path.exists(config_file):
            return True
    return False


def _load_model():
    """Load the model and tokenizer from local directory (synchronous, no download)."""
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        # Use lock to prevent multiple simultaneous loads
        with _loading_lock:
            # Double-check after acquiring lock
            if _model is not None and _tokenizer is not None:
                return _model, _tokenizer
            
            start_time = time.time()
            logger.info("=" * 60)
            logger.info("Loading AI Model from Local Directory")
            logger.info("=" * 60)
            model_path = os.path.abspath(MODEL_NAME)
            logger.info(f"Model path: {model_path}")
            
            # Check if model directory exists
            if not os.path.exists(model_path) or not os.path.isdir(model_path):
                raise FileNotFoundError(f"Model directory not found: {model_path}. Please ensure the model is in ./bart")
            
            logger.info(f"Device: {'CUDA (GPU)' if torch.cuda.is_available() else 'CPU'}")
            logger.info(f"PyTorch Version: {torch.__version__}")
            logger.info("Loading model and tokenizer from local files...")
            
            try:
                # Load model from local directory (no download, fast)
                _model = AutoModelForSequenceClassification.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                    local_files_only=True,  # Only use local files, no download
                    low_cpu_mem_usage=True
                )
                
                if not torch.cuda.is_available():
                    _model = _model.to("cpu")
                
                _tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    local_files_only=True  # Only use local files, no download
                )
                
                loading_time = time.time() - start_time
                logger.info(f"✓ Model loaded in {loading_time:.2f} seconds")
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"Failed to load model from {model_path}: {e}")
                raise
    
    return _model, _tokenizer


def _zero_shot_classify(text: str, candidate_labels: List[str], model, tokenizer) -> Dict:
    """
    Perform zero-shot classification manually.
    
    Args:
        text: Input text to classify
        candidate_labels: List of possible categories
        model: Loaded model
        tokenizer: Loaded tokenizer
        
    Returns:
        Dict with labels and scores
    """
    # Create hypothesis templates for each label
    # For MNLI models, we use "This text is about {label}" format
    hypothesis_template = "This text is about {}."
    
    # Prepare inputs for each candidate label
    results = []
    
    for label in candidate_labels:
        hypothesis = hypothesis_template.format(label)
        
        # Tokenize the premise (text) and hypothesis
        inputs = tokenizer(
            text,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        )
        
        # Move to same device as model
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Get model predictions
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            
            # MNLI has 3 labels: contradiction (0), neutral (1), entailment (2)
            # We want entailment score (index 2)
            entailment_score = F.softmax(logits, dim=-1)[0][2].item()
            results.append((label, entailment_score))
    
    # Sort by score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)
    
    labels = [r[0] for r in results]
    scores = [r[1] for r in results]
    
    return {"labels": labels, "scores": scores}


def classify_task(title: str, description: Optional[str] = None) -> Dict[str, any]:
    """
    Classify a task into categories using a local PyTorch model.
    
    Args:
        title: Task title
        description: Optional task description
        
    Returns:
        Dict with category, confidence, and suggested age range
    """
    # Combine title and description
    text = title
    if description:
        text += f". {description}"
    
    try:
        logger.debug(f"Classifying task: '{title[:50]}...'")
        inference_start = time.time()
        
        # Load model and tokenizer
        model, tokenizer = _load_model()
        
        # Run zero-shot classification
        logger.debug(f"Running inference on text (length: {len(text)} chars)")
        result = _zero_shot_classify(text, TASK_CATEGORIES, model, tokenizer)
        inference_time = time.time() - inference_start
        
        logger.debug(f"Inference completed in {inference_time:.2f} seconds")
        
        # Extract results
        labels = result.get("labels", [])
        scores = result.get("scores", [])
        
        if labels and scores:
            # Get the best match
            category = labels[0]  # Already sorted by score
            confidence = float(scores[0])
        else:
            # Fallback if model fails
            category = "other"
            confidence = 0.5
            logger.warning("Model returned empty results, using fallback")
            
    except FileNotFoundError as e:
        logger.warning(f"Model not preloaded: {e}")
        # Return "other" category if model files don't exist
        category = "other"
        confidence = 0.3
    except Exception as e:
        logger.error(f"Classification error: {e}")
        # Fallback to "other" if model fails
        category = "other"
        confidence = 0.3
    
    age_info = AGE_APPROPRIATE.get(category, {"min_age": 5, "max_age": 18})
    
    return {
        "category": category,
        "confidence": confidence,
        "suggested_min_age": age_info["min_age"],
        "suggested_max_age": age_info["max_age"],
        "description": _get_category_description(category)
    }


def _get_category_description(category: str) -> str:
    """Get human-readable description for category."""
    descriptions = {
        "chores": "Household tasks and cleaning activities",
        "homework": "School assignments and educational tasks",
        "creative": "Artistic and creative projects",
        "physical": "Sports and physical activities",
        "social": "Social interactions and helping others",
        "other": "General tasks"
    }
    return descriptions.get(category, "General task")


def suggest_assignments(
    category: str,
    family_members: List[Dict],
    task_difficulty: Optional[str] = None
) -> List[Dict]:
    """
    Suggest which family members are best suited for a task based on category and age.
    
    Args:
        category: Task category
        family_members: List of dicts with member info (id, role, age if available)
        task_difficulty: Optional difficulty level (easy, medium, hard)
        
    Returns:
        List of suggested members sorted by suitability
    """
    age_info = AGE_APPROPRIATE.get(category, {"min_age": 5, "max_age": 18})
    suggestions = []
    
    for member in family_members:
        score = 0.5  # Base score
        
        # Age-based scoring (if age is provided)
        if "age" in member and member["age"]:
            age = member["age"]
            if age_info["min_age"] <= age <= age_info["max_age"]:
                score += 0.3
            elif age < age_info["min_age"]:
                score -= 0.2  # Too young
            else:
                score -= 0.1  # Might be too old
        
        # Role-based scoring
        if member.get("role") == "CHILD":
            if category in ["homework", "creative", "physical"]:
                score += 0.2  # Children typically do these
        elif member.get("role") == "PARENT":
            if category in ["chores", "social"]:
                score += 0.1  # Parents often handle these
        
        suggestions.append({
            "member_id": member.get("id"),
            "member_name": member.get("display_name") or member.get("full_name", "Unknown"),
            "role": member.get("role"),
            "suitability_score": round(score, 2),
            "reason": _get_suggestion_reason(category, member, age_info)
        })
    
    # Sort by suitability score (highest first)
    suggestions.sort(key=lambda x: x["suitability_score"], reverse=True)
    
    return suggestions


def _get_suggestion_reason(category: str, member: Dict, age_info: Dict) -> str:
    """Generate a reason for the suggestion."""
    role = member.get("role", "")
    age = member.get("age")
    
    reasons = {
        "chores": f"Age-appropriate household task",
        "homework": f"Suitable for school-age children" if role == "CHILD" else "Educational task",
        "creative": f"Great for creative activities",
        "physical": f"Good for physical development",
        "social": f"Encourages social interaction",
        "other": f"General task assignment"
    }
    
    base_reason = reasons.get(category, "Task assignment")
    
    if age and age_info["min_age"] <= age <= age_info["max_age"]:
        return f"{base_reason} - Age appropriate"
    
    return base_reason

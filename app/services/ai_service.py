"""
AI Service for Task Classification using Hugging Face models.
Uses Hugging Face Inference API (free, no API key required) or local transformers.
"""
import requests
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

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

# Difficulty keywords for each category
CATEGORY_KEYWORDS = {
    "chores": ["clean", "wash", "dish", "laundry", "vacuum", "sweep", "organize", "tidy", "room", "kitchen", "bathroom"],
    "homework": ["homework", "study", "math", "reading", "essay", "project", "assignment", "book", "learn"],
    "creative": ["draw", "paint", "art", "music", "write", "craft", "create", "design", "color"],
    "physical": ["exercise", "sport", "run", "walk", "play", "bike", "swim", "outdoor", "gym"],
    "social": ["help", "family", "visit", "call", "friend", "together", "share", "care"],
}


def classify_task(title: str, description: Optional[str] = None) -> Dict[str, any]:
    """
    Classify a task into categories using keyword matching and Hugging Face API.
    
    Args:
        title: Task title
        description: Optional task description
        
    Returns:
        Dict with category, confidence, and suggested age range
    """
    text = title.lower()
    if description:
        text += " " + description.lower()
    
    # First, try keyword-based classification (fast and free)
    category = _classify_by_keywords(text)
    confidence = 0.7  # Medium confidence for keyword matching
    
    # If we want to use Hugging Face API for better accuracy (optional)
    # Uncomment the following to use HF Inference API:
    # try:
    #     hf_result = _classify_with_hf_api(text)
    #     if hf_result:
    #         category = hf_result.get("category", category)
    #         confidence = hf_result.get("confidence", confidence)
    # except Exception as e:
    #     logger.warning(f"HF API classification failed: {e}, using keyword fallback")
    
    age_info = AGE_APPROPRIATE.get(category, {"min_age": 5, "max_age": 18})
    
    return {
        "category": category,
        "confidence": confidence,
        "suggested_min_age": age_info["min_age"],
        "suggested_max_age": age_info["max_age"],
        "description": _get_category_description(category)
    }


def _classify_by_keywords(text: str) -> str:
    """Classify task using keyword matching."""
    scores = {cat: 0 for cat in TASK_CATEGORIES}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[category] += 1
    
    # Find category with highest score
    max_score = max(scores.values())
    if max_score > 0:
        return max(scores, key=scores.get)
    
    return "other"  # Default category


def _classify_with_hf_api(text: str) -> Optional[Dict]:
    """
    Classify using Hugging Face Inference API (free, no API key needed).
    Uses a zero-shot classification model.
    """
    try:
        # Using Hugging Face Inference API (free tier)
        API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
        
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": TASK_CATEGORIES,
                "multi_label": False
            }
        }
        
        response = requests.post(API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            labels = result.get("labels", [])
            scores = result.get("scores", [])
            
            if labels and scores:
                best_idx = scores.index(max(scores))
                return {
                    "category": labels[best_idx],
                    "confidence": scores[best_idx]
                }
    except Exception as e:
        logger.warning(f"HF API call failed: {e}")
    
    return None


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


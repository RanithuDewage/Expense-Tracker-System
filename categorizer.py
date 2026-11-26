import math
import re
from collections import defaultdict
from database import get_all_expenses, get_categories

# Seed keywords for cold-start before the database has enough historical records
SEED_KEYWORDS = {
    "Food & Dining": [
        "rice", "curry", "kottu", "lunch", "dinner", "breakfast", "canteen",
        "tea", "coffee", "snack", "bakery", "keells", "cargills", "food",
        "grocery", "pizza", "burger", "milk", "water", "restaurant", "hopper"
    ],
    "Transport": [
        "bus", "train", "pickme", "uber", "tuk", "fuel", "petrol", "ticket",
        "highway", "fare", "cab", "commute", "ride", "bicycle", "parking"
    ],
    "Education & Books": [
        "book", "notebook", "print", "photocopy", "stationery", "pen", "course",
        "coursera", "udemy", "exam", "fee", "lab", "reference", "binding", "paper"
    ],
    "Utilities & Data": [
        "dialog", "mobitel", "slt", "data", "reload", "wifi", "internet",
        "electricity", "water bill", "phone", "package", "bill", "sim"
    ],
    "Entertainment": [
        "movie", "cinema", "netflix", "spotify", "game", "steam", "outing",
        "trip", "concert", "match", "party", "subscription"
    ],
    "Health & Personal": [
        "pharmacy", "medicine", "panadol", "doctor", "clinic", "hospital",
        "gym", "haircut", "soap", "shampoo", "toothpaste", "vitamin", "dental"
    ],
}


def tokenize(text):
    if not text:
        return []
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [w for w in cleaned.split() if len(w) > 1]


class SmartCategorizer:
    """
    Lightweight Naive Bayes + Keyword categorizer.
    Uses seed keywords along with past expense descriptions stored in SQLite
    to predict the most likely category when adding a new expense.
    """

    def __init__(self):
        self.word_counts = defaultdict(lambda: defaultdict(int))
        self.category_counts = defaultdict(int)
        self.vocab = set()
        self.train()

    def train(self):
        self.word_counts.clear()
        self.category_counts.clear()
        self.vocab.clear()

        # 1. Load baseline seed keywords (given a small weight)
        for category, words in SEED_KEYWORDS.items():
            for w in words:
                for token in tokenize(w):
                    self.word_counts[category][token] += 2
                    self.category_counts[category] += 2
                    self.vocab.add(token)

        # 2. Learn from actual user history in the database
        past_expenses = get_all_expenses()
        for exp in past_expenses:
            cat = exp["category"]
            tokens = tokenize(exp.get("description", ""))
            for token in tokens:
                self.word_counts[cat][token] += 3
                self.category_counts[cat] += 3
                self.vocab.add(token)

    def predict(self, description):
        tokens = tokenize(description)
        if not tokens:
            return "Other", 0.0

        categories = [c["name"] for c in get_categories()]
        if not categories:
            categories = list(SEED_KEYWORDS.keys()) + ["Other"]

        vocab_size = max(len(self.vocab), 1)
        total_docs = sum(self.category_counts.values()) + len(categories)

        scores = {}
        matched_any = False

        for cat in categories:
            # Log prior probability
            cat_total = self.category_counts.get(cat, 0)
            log_prob = math.log((cat_total + 1.0) / total_docs)

            # Laplace-smoothed log likelihood
            for token in tokens:
                count = self.word_counts[cat].get(token, 0)
                if count > 0:
                    matched_any = True
                log_prob += math.log((count + 1.0) / (cat_total + vocab_size))

            scores[cat] = log_prob

        if not matched_any:
            return "Other", 0.0

        # Convert log scores to normalized probabilities using softmax
        max_log = max(scores.values())
        exp_scores = {cat: math.exp(val - max_log) for cat, val in scores.items()}
        sum_exp = sum(exp_scores.values())
        probs = {cat: val / sum_exp for cat, val in exp_scores.items()}

        best_cat = max(probs, key=probs.get)
        return best_cat, round(probs[best_cat] * 100, 1)

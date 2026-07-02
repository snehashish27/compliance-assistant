import re
import spacy
from collections import defaultdict
import logging
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logging.warning("SpaCy model 'en_core_web_sm' not found. NLP detection will be skipped.")
    nlp = None
PII_PATTERNS = {
    "Aadhaar Number": r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    "PAN Number": r"\b[A-Z]{5}\d{4}[A-Z]{1}\b",
    "Email Address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
    "Phone Number": r"\b(?:\+91[\-\s]?)?[6789]\d{9}\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
    "Bank Details (IFSC)": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "API Key": r"\b(?:sk-[a-zA-Z0-9]{32,48})\b",
    "Employee ID": r"\b(?:EMP|ID|Employee)[\-\s:]*[A-Z0-9]+\b"
}
CONFIDENTIAL_KEYWORDS = ["confidential", "proprietary", "internal use only", "trade secret"]
CORPORATE_SUFFIXES = {
    "ltd", "limited", "inc", "incorporated", "corp", "corporation",
    "pvt", "private", "llc", "llp", "plc", "gmbh", "co.", "& co",
    "foundation", "holdings", "ventures", "enterprises", "solutions",
    "technologies", "consulting", "services", "associates", "partners",
    "group", "capital", "industries", "systems"
}
TECHNICAL_WHITELIST = {
    "python", "java", "javascript", "typescript", "golang", "rust",
    "kotlin", "swift", "scala", "ruby", "php", "bash", "sql", "c", "r",
    "tensorflow", "keras", "pytorch", "scikit-learn", "sklearn", "xgboost",
    "lightgbm", "catboost", "huggingface", "transformers", "langchain",
    "faiss", "jax", "flax", "fastai",
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
    "opencv", "nltk", "spacy", "gensim", "pillow", "requests", "flask",
    "fastapi", "django", "streamlit", "gradio", "beautifulsoup", "scrapy",
    "tiktoken", "easyocr", "pymupdf",
    "lstm", "cnn", "rnn", "gru", "bert", "gpt", "transformer",
    "dropout", "relu", "sigmoid", "softmax", "adamw", "adam", "sgd",
    "backpropagation", "batch normalization", "early stopping",
    "multilayer perceptron", "stacked lstm", "physionet",
    "docker", "kubernetes", "aws", "azure", "gcp", "firebase",
    "nginx", "redis", "celery", "rabbitmq",
    "mysql", "postgresql", "mongodb", "sqlite", "elasticsearch",
    "linux", "ubuntu", "git", "github", "gitlab", "bitbucket",
    "jupyter", "anaconda", "vscode", "intellij", "postman",
    "iit", "iit madras", "iim", "nptel", "coursera", "udemy",
}
def _is_technical_term(text: str) -> bool:
    """True if the entity is a known tech term that should never be redacted."""
    lower = text.strip().lower()
    if lower in TECHNICAL_WHITELIST:
        return True
    words = lower.split()
    if all(w in TECHNICAL_WHITELIST for w in words):
        return True
    return False
def _is_corporate_entity(text: str) -> bool:
    """
    True only if the entity looks like a real registered business.
    Requires the presence of a known corporate suffix word.
    This prevents academic concepts, project names, and tech tools
    from being flagged as organisations.
    """
    lower = text.lower()
    return any(f" {suffix}" in f" {lower}" or lower.endswith(suffix)
               for suffix in CORPORATE_SUFFIXES)
def detect_and_mask(text: str) -> dict:
    """
    Scans text for sensitive data using Regex and NLP.
    Only genuinely sensitive PII is masked:
      - Regex: phone, email, Aadhaar, PAN, credit card, IFSC, API keys
      - NLP PERSON: multi-word person names (first + last)
      - NLP ORG: only registered business entities (contain corporate suffix)
    Returns the masked text and a count dictionary.
    """
    if not text or not isinstance(text, str):
        return {"masked_text": "", "counts": {}, "total_findings": 0}
    masked_text = text
    findings_count = defaultdict(int)
    for entity_name, pattern in PII_PATTERNS.items():
        matches = set(re.findall(pattern, masked_text))
        for match in matches:
            findings_count[entity_name] += 1
            masked_text = masked_text.replace(match, f"[REDACTED_{entity_name.upper()}]")
            logging.info(f"Detected and masked: {entity_name}")
    lower_text = masked_text.lower()
    for keyword in CONFIDENTIAL_KEYWORDS:
        if keyword in lower_text:
            findings_count["Confidential Business Information"] += lower_text.count(keyword)
            masked_text = re.sub(f"(?i){keyword}", "[REDACTED_CONFIDENTIAL]", masked_text)
    if nlp:
        doc = nlp(masked_text)
        for ent in doc.ents:
            if len(ent.text) <= 3:
                continue
            if "[REDACTED" in ent.text:
                continue
            if "http" in ent.text or "/" in ent.text:
                continue
            if _is_technical_term(ent.text):
                continue
            if ent.label_ == "PERSON":
                if len(ent.text.split()) >= 2:
                    findings_count["Named Entity (PERSON)"] += 1
                    masked_text = masked_text.replace(ent.text, "[REDACTED_PERSON]")
            elif ent.label_ == "ORG":
                if _is_corporate_entity(ent.text):
                    findings_count["Named Entity (ORG)"] += 1
                    masked_text = masked_text.replace(ent.text, "[REDACTED_ORG]")
    return {
        "masked_text": masked_text,
        "counts": dict(findings_count),
        "total_findings": sum(findings_count.values())
    }
def classify_risk(findings_dict: dict) -> str:
    """Classifies the document risk based on detected entities."""
    high_risk_entities = ["Aadhaar Number", "PAN Number", "Credit Card", "API Key"]
    if any(entity in findings_dict for entity in high_risk_entities):
        return "High Risk"
    medium_risk_entities = ["Email Address", "Phone Number", "Bank Details (IFSC)",
                            "Confidential Business Information"]
    if any(entity in findings_dict for entity in medium_risk_entities):
        return "Medium Risk"
    return "Low Risk"

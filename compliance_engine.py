import os
import logging
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_core.embeddings import Embeddings
from typing import List
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
class GeminiEmbeddings(Embeddings):
    """Custom embeddings class calling the Gemini REST API directly.
    Uses models/gemini-embedding-001 — confirmed available for this API key."""
    MODEL = "models/gemini-embedding-001"
    EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:embedContent"
    def _embed(self, text: str, task_type: str) -> List[float]:
        payload = {
            "model": self.MODEL,
            "content": {"parts": [{"text": text}]},
            "taskType": task_type
        }
        resp = requests.post(
            self.EMBED_URL,
            params={"key": GOOGLE_API_KEY},
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t, "RETRIEVAL_DOCUMENT") for t in texts]
    def embed_query(self, text: str) -> List[float]:
        return self._embed(text, "RETRIEVAL_QUERY")
try:
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.1)
    embeddings = GeminiEmbeddings()
except Exception as e:
    logging.error(f"Failed to initialize Gemini models: {e}")
    llm, embeddings = None, None
def generate_compliance_summary(total_findings: int, findings_dict: dict, risk_tier: str) -> str:
    """
    Generates a structured compliance report using Gemini based on the detected metrics.
    Raw PII is NEVER sent here; only the aggregate counts are analyzed.
    """
    if not llm:
        return "⚠️ Error: AI model not initialized. Check your API Key."
    prompt = f"""
    Act as an expert Indian Cybersecurity and Privacy Compliance Officer.
    You are reviewing the metadata of an internal document scan.
    Detection Metrics:
    - Overall Risk Level: {risk_tier}
    - Total Sensitive Entities Found: {total_findings}
    - Breakdown of Entities: {findings_dict}
    Based strictly on these metrics, provide a highly professional, structured markdown report.
    You MUST include the following sections:
    ### 1. Compliance Observations
    Provide observations specifically referencing India's Digital Personal Data Protection (DPDP) Act, 2023 and the DPDP Rules 2025. For example, if Aadhaar or PAN data is exposed, mention the strict requirements for verifiable anonymization and informed consent.
    ### 2. Security Risks
    Highlight the specific dangers of the exposed entities listed in the breakdown (e.g., identity theft risk if PAN is exposed, phishing risk if emails are exposed).
    ### 3. Suggested Remediation Steps
    Provide 3 to 4 actionable, technical steps the organization should take (e.g., implementing encryption, utilizing data masking APIs, enforcing access controls).
    Keep the tone authoritative, concise, and focused purely on data governance.
    """
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logging.error(f"Summary generation failed: {e}")
        return f"⚠️ Error generating summary: {str(e)}"
def build_rag_chain(masked_text: str):
    """
    Chunks the sanitized text, loads it into a FAISS vector database,
    and returns a conversational chain for the Chat UI.
    """
    if not embeddings or not llm:
        logging.error("build_rag_chain: LLM or embeddings not initialized.")
        return None
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_text(masked_text)
    if not chunks:
        chunks = ["No readable or meaningful text found in the document."]
    try:
        vectorstore = FAISS.from_texts(texts=chunks, embedding=embeddings)
    except Exception as e:
        logging.error(f"FAISS index creation failed: {e}")
        print(f"[ERROR] FAISS index creation failed: {e}")
        return None
    try:
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer")
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
            memory=memory,
            return_source_documents=False
        )
    except Exception as e:
        logging.error(f"Chain construction failed: {e}")
        print(f"[ERROR] Chain construction failed: {e}")
        return None
    return qa_chain

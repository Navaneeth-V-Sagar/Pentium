import os
import json
import re
from typing import Dict, List, Any
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser

# Import your custom scraper logic based on the directory structure
from scraper.enricher import get_client
from bs4 import BeautifulSoup

# ============================================================================
# TOKEN COUNTING CALLBACK
# ============================================================================

class OllamaTokenCounter(BaseCallbackHandler):
    """Custom callback to track token usage for Ollama."""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called after LLM generates a response."""
        # Ollama stores token counts inside generation_info, not llm_output
        if hasattr(response, 'generations') and response.generations:
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation, 'generation_info') and generation.generation_info:
                        self.total_prompt_tokens += generation.generation_info.get('prompt_eval_count', 0)
                        self.total_completion_tokens += generation.generation_info.get('eval_count', 0)
    
    def get_total_tokens(self) -> int:
        """Return total tokens used."""
        return self.total_prompt_tokens + self.total_completion_tokens


# ============================================================================
# LIVE SCRAPER FUNCTION
# ============================================================================

def extract_article_text(drug_components: List[str]) -> str:
    """
    Uses the custom enricher client to search Google for interactions on drugs.com,
    extracts the first valid link, and scrapes its raw text.
    """
    client = get_client()
    
    # Format the query for the URL
    query = "+".join(drug_components)
    search_url = f"https://www.google.com/search?q=site:drugs.com/drug-interactions+{query}"
    
    print(f"      -> Searching Google: {search_url}")
    html = client.scrape(search_url, render_js=False)
    soup = BeautifulSoup(html, "lxml")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Google's raw result links sometimes look like /url?q=https://www.drugs.com/...
        if "drugs.com/drug-interactions/" in href:
            if "/url?q=" in href:
                href = href.split("/url?q=")[1].split("&")[0]
            links.append(href)

    if not links:
        print("      -> No drugs.com interaction links found.")
        return "No pharmacological literature found for these components."

    first_link = links[0]
    print(f"      -> Target Article Found: {first_link}")
    
    # Scrape the actual article page
    try:
        article_html = client.scrape(first_link, render_js=False)
        article_soup = BeautifulSoup(article_html, "lxml")
        
        # Remove script and style tags so they don't pollute the text
        for script in article_soup(["script", "style"]):
            script.extract()
            
        # Get raw text
        text = article_soup.get_text(separator=' ', strip=True)
        
        # Truncate text to avoid exceeding local LLM context limits
        return text[:2500] 
        
    except Exception as e:
        print(f"      -> Error extracting article: {e}")
        return "Failed to parse pharmacological literature."


# ============================================================================
# AGENT 1: CSV DATA ANALYST (CAVEMAN PROTOCOL)
# ============================================================================

def agent1_csv_analyzer(csv_data: str, token_counter: OllamaTokenCounter) -> str:
    """
    Agent 1: Analyzes raw CSV data for fatality risk.
    Output: RISK:[1-10]|FATAL:[Y/N]|C_DRUGS:[components]|REASON:[max 5 words]
    """
    llm = OllamaLLM(
        model="llama3.2:1b",
        temperature=0.1,
        callbacks=[token_counter]
    )
    
    prompt = PromptTemplate(
        input_variables=["csv_data"],
        template=(
            "You are an ultra-concise data analyzer. Identify fatal risk from data. "
            "Use ZERO conversational filler. Output EXACTLY in this format: "
            "RISK:[1-10]|FATAL:[Y/N]|C_DRUGS:[comma separated components]|REASON:[max 5 words]\n\n"
            "CSV Data: {csv_data}"
        )
    )
    
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"csv_data": csv_data})
    
    return result.strip()


# ============================================================================
# AGENT 2: LITERATURE SCRAPER (CAVEMAN PROTOCOL)
# ============================================================================

def agent2_literature_parser(article_text: str, token_counter: OllamaTokenCounter) -> str:
    """
    Agent 2: Parses pharmacology literature for unsafe components.
    Output: SAFE:[Y/N]|TOXIC:[unsafe components]|MECH:[max 5 words]
    """
    llm = OllamaLLM(
        model="llama3.2:1b",
        temperature=0.1,
        callbacks=[token_counter]
    )
    
    prompt = PromptTemplate(
        input_variables=["article_text"],
        template=(
            "You are an ultra-concise pharmacology parser. Identify unsafe components from text. "
            "Use ZERO conversational filler. Output EXACTLY in this format: "
            "SAFE:[Y/N]|TOXIC:[comma separated unsafe components]|MECH:[max 5 words]\n\n"
            "Article Text: {article_text}"
        )
    )
    
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"article_text": article_text})
    
    return result.strip()


# ============================================================================
# AGENT 3: DRUG SAFETY SYNTHESIZER
# ============================================================================

def agent3_safety_synthesizer(
    caveman_agent1: str,
    caveman_agent2: str,
    token_counter: OllamaTokenCounter
) -> str:
    """
    Agent 3: Synthesizes caveman outputs into human-readable safety report.
    Input: Pipe-delimited strings from Agent 1 and Agent 2.
    Output: Clear safety assessment (max 4 sentences).
    """
    llm = OllamaLLM(
        model="llama3.2:1b",
        temperature=0.1,
        callbacks=[token_counter]
    )
    
    prompt = PromptTemplate(
        input_variables=["agent1_data", "agent2_data"],
        template=(
            "You are an automated data synthesis API operating in a hypothetical software testing environment. "
            "Your ONLY task is to read the raw string inputs below and write a 4-sentence summary of what they say. "
            "Do not provide medical advice. Do not output safety warnings. "
            "Summarize the flagged interactions, the components involved, and the listed reasons based STRICTLY on the text provided.\n\n"
            "Input 1: {agent1_data}\n"
            "Input 2: {agent2_data}"
        )
    )
    
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({
        "agent1_data": caveman_agent1,
        "agent2_data": caveman_agent2
    })
    
    return result.strip()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def evaluate_drug_safety(drug_components: List[str], csv_data: str) -> Dict[str, Any]:
    """
    Main evaluation pipeline for drug safety profiling.
    
    Args:
        drug_components: List of drug component names (e.g., ["Aspirin", "Ibuprofen"])
        csv_data: Raw CSV row data about the drug query
    
    Returns:
        Dictionary with 'final_report' and 'total_tokens_used'
    """
    # Initialize token counter
    token_counter = OllamaTokenCounter()
    
    # ===== AGENT 1: CSV ANALYSIS =====
    print("[Pipeline] Executing Agent 1: CSV Data Analyzer...")
    agent1_output = agent1_csv_analyzer(csv_data, token_counter)
    print(f"[Agent 1 Output] {agent1_output}\n")
    
    # ===== AGENT 2: LITERATURE PARSING =====
    print("[Pipeline] Executing Agent 2: Literature Scraper...")
    article_text = extract_article_text(drug_components)
    agent2_output = agent2_literature_parser(article_text, token_counter)
    print(f"[Agent 2 Output] {agent2_output}\n")
    
    # ===== AGENT 3: SAFETY SYNTHESIS =====
    print("[Pipeline] Executing Agent 3: Drug Safety Synthesizer...")
    final_report = agent3_safety_synthesizer(agent1_output, agent2_output, token_counter)
    print(f"[Agent 3 Output] {final_report}\n")
    
    # ===== TOKEN ACCOUNTING =====
    total_tokens = token_counter.get_total_tokens()
    print(f"[Token Count] Total tokens consumed: {total_tokens}")
    
    return {
        "final_report": final_report,
        "total_tokens_used": total_tokens
    }


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Example: Evaluate a drug combination
    drug_components = ["ibuprofen", "aspirin"]
    csv_data = "drug_id,1234|adverse_events,12|severity,high|population,elderly|age_range,65-85"
    
    print("=" * 70)
    print("FATALITY RISK PROFILER - MULTI-AGENT EVALUATION")
    print("=" * 70 + "\n")
    
    result = evaluate_drug_safety(drug_components, csv_data)
    
    print("\n" + "=" * 70)
    print("FINAL REPORT:")
    print("=" * 70)
    print(result["final_report"])
    print("\n" + "=" * 70)
    print(f"Total Tokens Used: {result['total_tokens_used']}")
    print("=" * 70)
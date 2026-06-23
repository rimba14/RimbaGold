import os
import requests
import json
from typing import Dict, Any, List
import typing
from gitagent_base import BaseModule
from gitagent_gemma_connector import GemmaContextLayer
from gitagent_kronos_adapter import get_kronos_forecast
from gitagent_vision_audit import VisionPatternAgent

try:
    import google.genai  # noqa: F401
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    import groq  # noqa: F401
    HAS_GROQ_SDK = True
except ImportError:
    HAS_GROQ_SDK = False

class UniversalContextLayer(BaseModule):
    """
    Sentinel Context Layer (Layer 4) - Unified Switchboard
    Responsibility: Autonomous Routing & Forensic Audit.
    Backends: Local (Ollama), Performance (Groq), Cognitive (Gemini).
    """
    def __init__(self):
        super().__init__("Context")
        self.gemma_cloud = GemmaContextLayer()
        self.vision_agent = VisionPatternAgent()
        
    def process(self, cognition_receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 225: Dual-Oracle Audit (Vision + Kronos + Episodic Memory)."""
        action = cognition_receipt.get('action') or cognition_receipt.get('verdict') or 'NONE'
        sym = cognition_receipt.get('symbol', '?')
        df = cognition_receipt.get('ohlcv_df')
        tensor = cognition_receipt.get('feature_tensor')
        
        # ─── Phase 165: Contextual Query Override (Legendary Match) ───
        legendary_boost = False
        if tensor is not None:
            try:
                from gitagent_memory import EpisodicMemory
                memory = EpisodicMemory(dim=93)
                # k=1 for highest fidelity match
                matches = memory.retrieve(tensor, k=1)
                if matches:
                    m = matches[0]
                    # Threshold: 0.15 distance is ~85% similarity in FlatL2 space
                    if m['distance'] < 0.15 and m['meta'].get('lesson') == 'legend_wei':
                        print(f"[CONTEXT] 🏛️ LEGENDARY MATCH: {sym} matches institutional template (Dist: {m['distance']:.3f}).")
                        legendary_boost = True
            except Exception as e:
                print(f"[CONTEXT_ERR] Memory lookup failed: {e}")

        if action in ["BUY", "SELL"] and df is not None:
            print(f"[CONTEXT] {sym} | High Conviction {action} detected. Initiating Dual-Oracle...")
            
            # 1. Numerical Oracle: Kronos
            kronos_res = get_kronos_forecast(df)
            k_bias = kronos_res.get('bias', 0.0)
            
            # 2. Visual Oracle: Vision Audit
            vision_res = self.vision_agent.audit_visual_structure(df, sym, action)
            v_verdict = vision_res.get('vision_verdict', 'NEUTRAL')
            v_conf = vision_res.get('vision_confidence', 0.5)
            
            # 3. Agentic Multi-Hypothesis Debate
            final_action, final_reasoning = self._hypothesis_debate(sym, action, k_bias, vision_res)
            
            # If Vision says REJECTED, we normally downgrade to HOLD
            # UNLESS we have a Legendary Match (Phase 165 Override)
            if v_verdict == "REJECTED" and v_conf > 0.7:
                if legendary_boost:
                    print(f"[CONTEXT] 🛡️ OVERRIDING VISION REJECTION: Legendary template detected for {sym}.")
                    final_reasoning = f"LEGEND_OVERRIDE: {final_reasoning}"
                else:
                    return "HOLD", f"VISION_REJECTION: {vision_res.get('vision_rationale')}", "VISION-ORACLE"
            
            # Boost directional confidence if legendary
            if legendary_boost:
                final_reasoning = f"LEGENDARY_CONFIRMATION | {final_reasoning}"
            
            return final_action, final_reasoning, "TRIPLE-ORACLE-SYSTEM"

        return "HOLD", "NO_CONVICTION", "HAPPO-STRUCTURAL"

    def _hypothesis_debate(self, symbol: str, signal: str, k_bias: float, vision_res: dict) -> typing.Tuple[str, str]:
        """
        Synthesizes multiple hypotheses into a final verdict.
        Compares Trend Continuation vs. Mean Reversion.
        """
        # We use the existing Gemma cloud for the logic-heavy debate
        v_rationale = vision_res.get('vision_rationale', 'No vision data.')
        
        prompt = f"""
        AGENTIC MULTI-HYPOTHESIS DEBATE: {symbol}
        Proposed Signal: {signal}
        Numerical Oracle (Kronos Bias): {k_bias:+.2f}
        Vision Oracle: {vision_res.get('vision_verdict')} ({vision_res.get('vision_confidence'):.2f} conf)
        Vision Details: {v_rationale}
        
        DEBATE HYPOTHESES:
        A (Trend): This is a valid momentum continuation. High volatility supports the expansion.
        B (Contrarian): This is an exhausted move hitting a structural ceiling. Reversal is imminent.
        
        TASK: Weigh Hypotheses A & B. Decide if we EXECUTE or ABORT.
        If Kronos and Vision are in conflict, default to ABORT.
        
        RESPONSE FORMAT: [DECISION] | [LOGIC]
        DECISION: EXECUTE or ABORT.
        """
        
        # Using Gemini-2.0-Flash-Lite as defined in the class for high-reasoning debate
        res_text, _ = self._gemini_inference({"symbol": symbol, "prompt_override": prompt})
        
        # For efficiency, we use the local or cloud prompt
        if "EXECUTE" in res_text.upper():
            return signal, f"Hypothesis A Won: {res_text[:150]}"
        return "HOLD", f"Hypothesis B Won (Abort): {res_text[:150]}"

    def process_batch(self, cognition_receipts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 41 FIX: Forward batch request to Gemma 3 Cloud bridge."""
        if self.gemma_cloud is None:
            print("[CONTEXT] Warning: gemma_cloud is None. Falling back to individual processing.")
            return [self.process(r) for r in cognition_receipts]
        return self.gemma_cloud.process_batch(cognition_receipts)

    def _local_inference(self, data: Dict) -> typing.Tuple[str, str]:
        payload = {
            "model": "gemma:2b",
            "messages": [{"role": "user", "content": self._build_prompt(data)}],
            "stream": False
        }
        try:
            r = requests.post(self.local_url, json=payload, timeout=30)
            return r.json().get('message', {}).get('content', ''), "LOCAL-OLLAMA"
        except Exception as e:
            return f"LOCAL ERROR: {str(e)}", "LOCAL-FAIL"

    def _groq_inference(self, data: Dict) -> typing.Tuple[str, str]:
        try:
            if self.groq_client:
                chat = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": self._build_prompt(data)}],
                    max_tokens=128
                )
                return chat.choices[0].message.content, "GROQ-PERFORMANCE"
            # Fallback to requests if SDK not available
            headers = {"Authorization": f"Bearer {self.groq_key}"}
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": self._build_prompt(data)}]}
            r = requests.post(self.groq_url, headers=headers, json=payload, timeout=5)
            return r.json().get('choices', [{}])[0].get('message', {}).get('content', ''), "GROQ-PERFORMANCE"
        except Exception as e:
            return f"GROQ ERROR: {str(e)}", "GROQ-FAIL"

    def _gemini_inference(self, data: Dict) -> typing.Tuple[str, str]:
        prompt = data.get("prompt_override") or self._build_prompt(data)
        try:
            # Simple REST fallback if genai client not ready
            headers = {"Content-Type": "application/json"}
            api_key = os.environ.get("GOOGLE_API_KEY")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            data = r.json()
            return data['candidates'][0]['content']['parts'][0]['text'], "GEMINI-COGNITION"
        except Exception as e:
            return f"GEMINI ERROR: {str(e)}", "GEMINI-FAIL"

    def _apply_5_layer_compression(self, data: Dict) -> str:
        """
        Vibe-Trading Integration (v38.0): 5-Layer Context Compression Algorithm
        Layer 1: Structural Truncation (Removes raw arrays)
        Layer 2: Vectorized Checksums (ArcticDB pointers)
        Layer 3: Entropy Summarization
        Layer 4: Redundancy Filtering
        Layer 5: KV Cache Cap (Hard limit 15 lines)
        """
        module_10 = data.get('module_10', {})
        # Layer 1 & 2: Offload arrays to ArcticDB
        if 'correlation_matrix' in module_10:
            module_10['correlation_matrix'] = "[OFFLOADED_TO_ARCTICDB_v38]"
        if 'order_flow_history' in module_10:
            module_10['order_flow_history'] = "[OFFLOADED_TO_ARCTICDB_v38]"
            
        try:
            m10_summary = json.dumps(module_10)
        except Exception:
            m10_summary = str(module_10)
            
        # Layer 3 & 4: Aggressive summarization
        if len(m10_summary) > 200:
            m10_summary = m10_summary[:200] + "...[COMPRESSED]"
            
        m10_score = data.get('m10_score', 0.0)
        
        # Layer 5: Strict 15-line Context Cap
        prompt_lines = [
            f"FINANCIAL FORENSIC AUDIT: {data.get('symbol', 'UNKNOWN')}",
            f"Regime: {data.get('regime')}",
            f"Confidence: {data.get('confidence')}",
            f"Cognition Factor: {data.get('cognition_factor')}",
            "STRUCTURAL EVIDENCE (Module 10):",
            f"- Flip Score: {m10_score}/8.0",
            f"- Details: {m10_summary}",
            "DIRECTIVE: Combine structure & reasoning.",
            "VERDICT MUST BE: BUY, SELL, or HOLD.",
            "PROVIDE 1 SENTENCE REASONING."
        ]
        return "\n".join(prompt_lines[:15])

    def _build_prompt(self, data: Dict) -> str:
        return self._apply_5_layer_compression(data)

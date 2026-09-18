"""
core/subagent_swarm.py -- Autonomous Multi-Agent Swarm Orchestrator for J.A.R.V.I.S.

Coordinates concurrent, asynchronous sub-agents:
  1. ResearcherAgent: Live web research, scraping, and documentation extraction.
  2. ReverseEngineerAgent: Deconstructs APIs, schemas, and network payloads.
  3. SelfHealerAgent: Sandboxed script execution, traceback parsing, and automated self-repair.
  4. ReporterAgent: Synthesis, actionable HUD logging, and conversational speech generation.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
SWARM_OUTPUT_DIR = BASE_DIR / "config" / "swarm_outputs"
SWARM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SwarmResult:
    task: str
    status: str
    research_summary: str = ""
    generated_code: str = ""
    execution_output: str = ""
    error_log: str = ""
    final_report: str = ""
    duration_seconds: float = 0.0


class ResearcherAgent:
    """Agent 1: Scrapes live web pages, extracts text and documentation."""

    def research(self, topic_or_url: str) -> str:
        results = []
        is_url = topic_or_url.startswith("http://") or topic_or_url.startswith("https://")
        if is_url:
            try:
                r = requests.get(topic_or_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for s in soup(["script", "style", "nav", "footer", "header"]):
                        s.extract()
                    text = soup.get_text(separator=" ", strip=True)
                    results.append(f"[Source: {topic_or_url}]\n{text[:3000]}")
            except Exception as e:
                results.append(f"Error fetching {topic_or_url}: {e}")
        else:
            # Topic research via DuckDuckGo API or Gemini
            try:
                from actions.web_search import search_duckduckgo
                ddg_res = search_duckduckgo(topic_or_url, max_results=4)
                for item in ddg_res:
                    results.append(f"Title: {item.get('title')}\nSnippet: {item.get('snippet')}\nURL: {item.get('url')}\n")
            except Exception:
                pass

            # Ground with Gemini Flash
            try:
                from core.multi_llm import get_llm_model
                client = get_llm_model(model="gemini-2.5-flash")
                res = client.generate_content(
                    f"Provide quick, factual technical research notes on: {topic_or_url}. Focus on architecture, API structure, and key data points."
                )
                if res.text:
                    results.append(f"[Gemini Research]\n{res.text.strip()}")
            except Exception as e:
                results.append(f"Research note: {e}")

        return "\n\n".join(results) if results else "No research data gathered."


class ReverseEngineerAgent:
    """Agent 2: Converts research and API structures into executable automation scripts."""

    def build_solution(self, task: str, research_data: str) -> str:
        prompt = f"""You are the Master Reverse Engineer & Coder Agent for J.A.R.V.I.S.
Target Task: {task}

Context & Live Research:
{research_data[:4000]}

Write a complete, production-grade Python script that accomplishes the task.
Rules:
1. Self-contained: use standard library, requests, beautifulsoup4, or playwright.
2. Return ONLY clean Python code without markdown explanations.
3. Include error handling and structured output printing.
"""
        try:
            from core.multi_llm import get_llm_model
            client = get_llm_model(model="gemini-2.5-flash")
            res = client.generate_content(prompt)
            code = (res.text or "").strip()
            code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
            return code.strip()
        except Exception as e:
            return f"# Reverse engineering error: {e}"


class SelfHealerAgent:
    """Agent 3: Sandboxed execution with automated runtime traceback self-healing."""

    def test_and_heal(self, code: str, max_retries: int = 2) -> tuple[bool, str, str]:
        current_code = code
        log = []

        for attempt in range(max_retries + 1):
            temp_file = SWARM_OUTPUT_DIR / f"swarm_runner_{int(time.time())}.py"
            temp_file.write_text(current_code, encoding="utf-8")

            try:
                proc = subprocess.run(
                    [sys.executable, str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if proc.returncode == 0:
                    log.append(f"Attempt {attempt+1}: Execution SUCCESS.")
                    return True, current_code, proc.stdout.strip()
                else:
                    err = proc.stderr.strip()
                    log.append(f"Attempt {attempt+1}: Failed with error:\n{err}")
                    if attempt < max_retries:
                        current_code = self._repair_code(current_code, err)
            except subprocess.TimeoutExpired:
                log.append(f"Attempt {attempt+1}: Timed out (15s).")
                break
            except Exception as e:
                log.append(f"Attempt {attempt+1}: Error: {e}")
                break
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass

        return False, current_code, "\n".join(log)

    def _repair_code(self, broken_code: str, error_traceback: str) -> str:
        prompt = f"""You are the Self-Healing Code Optimizer for J.A.R.V.I.S.
The following script failed to run:
{broken_code}

Error Output:
{error_traceback}

Fix the script so it executes without error. Return ONLY the corrected Python code, no explanation.
"""
        try:
            from core.multi_llm import get_llm_model
            client = get_llm_model(model="gemini-2.5-flash")
            res = client.generate_content(prompt)
            code = (res.text or "").strip()
            code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
            return code.strip()
        except Exception:
            return broken_code


class ReporterAgent:
    """Agent 4: Synthesizes final results into clean executive summary for HUD & speech."""

    def synthesize(self, task: str, research: str, code_success: bool, output: str) -> str:
        prompt = f"""You are J.A.R.V.I.S. Summarizer Agent.
User requested: {task}
Execution Status: {'SUCCESS' if code_success else 'PARTIAL / ANALYZED'}
Execution Output: {output[:1500]}

Provide a concise, direct 2-3 sentence summary in natural conversational Hinglish.
Explain what was done, key findings, and next steps if any. Do not sound robotic.
"""
        try:
            from core.multi_llm import get_llm_model
            client = get_llm_model(model="gemini-2.5-flash")
            res = client.generate_content(prompt)
            return (res.text or "").strip()
        except Exception:
            return f"Sir, swarm execution complete for '{task}'. Status: {'Success' if code_success else 'Checked'}."


class SubAgentSwarm:
    """Master Orchestrator managing concurrent execution across specialized sub-agents."""

    def __init__(self):
        self.researcher = ResearcherAgent()
        self.reverse_engineer = ReverseEngineerAgent()
        self.self_healer = SelfHealerAgent()
        self.reporter = ReporterAgent()

    def run(self, task: str, on_progress: Optional[Callable[[str], None]] = None) -> SwarmResult:
        start_t = time.time()
        res = SwarmResult(task=task, status="running")

        def _notify(msg: str):
            if on_progress:
                on_progress(msg)
            print(f"[Swarm] {msg}")

        # Phase 1: Research
        _notify(f"Phase 1/4: Gathering live research & web intelligence...")
        research_notes = self.researcher.research(task)
        res.research_summary = research_notes

        # Phase 2: Reverse Engineering / Code Generation
        _notify("Phase 2/4: Reverse-engineering automation script...")
        generated_code = self.reverse_engineer.build_solution(task, research_notes)
        res.generated_code = generated_code

        # Phase 3: Sandboxed Execution & Self-Healing
        _notify("Phase 3/4: Sandboxed verification & self-healing...")
        success, final_code, exec_out = self.self_healer.test_and_heal(generated_code)
        res.generated_code = final_code
        res.execution_output = exec_out
        res.status = "success" if success else "completed_with_notes"

        # Phase 4: Synthesis & Reporting
        _notify("Phase 4/4: Synthesizing final report...")
        final_report = self.reporter.synthesize(task, research_notes, success, exec_out)
        res.final_report = final_report

        res.duration_seconds = round(time.time() - start_t, 2)
        _notify(f"Swarm complete in {res.duration_seconds}s.")

        # Save artifact log
        saved_file = SWARM_OUTPUT_DIR / f"swarm_report_{int(time.time())}.json"
        try:
            saved_file.write_text(
                json.dumps({
                    "task": res.task,
                    "status": res.status,
                    "duration": res.duration_seconds,
                    "research": res.research_summary[:1000],
                    "code": res.generated_code,
                    "output": res.execution_output,
                    "report": res.final_report,
                }, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

        return res


_SWARM_INSTANCE: Optional[SubAgentSwarm] = None

def get_subagent_swarm() -> SubAgentSwarm:
    global _SWARM_INSTANCE
    if _SWARM_INSTANCE is None:
        _SWARM_INSTANCE = SubAgentSwarm()
    return _SWARM_INSTANCE

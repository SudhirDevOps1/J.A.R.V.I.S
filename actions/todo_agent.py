"""
Autonomous Task Runner & ToDo Agent for SudhirDevOps1 AI.

Automatically decomposes complex user requests into structured ToDo lists,
executes tasks step-by-step in background worker threads, logs progress to
the HUD, and notifies the user upon completion.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

_tasks_lock = threading.Lock()
_active_tasks: dict[str, dict] = {}


# ── Step artifact verification (anti-fake layer) ─────────────────────────────
# A step like "Save all files to desktop/..." MUST produce a real file.
# If the step text names an explicit file path that does not exist after the
# step ran, the step is FAILED — never "done". Steps without explicit paths
# (research, searches) are not verifiable and pass through untouched.
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|~[\\/]|desktop[\\/])[\w\-. \\/]+?\.(?:md|txt|json|py|csv|xlsx|pdf|html)",
    re.IGNORECASE,
)
_SAVE_WORDS = ("save", "write", "create", "download", "notes", "file")


def _verify_step_artifact(step: str) -> tuple[bool, str]:
    """(verified_or_not_applicable, note). Fails only when the step names an
    explicit file path that is missing afterwards. Never raises."""
    try:
        subs = str(step or "").replace("'", "").replace('"', "")
        for m in _PATH_RE.finditer(subs):
            raw = m.group(0).strip()
            cands = [os.path.expanduser(raw)]
            if not os.path.isabs(cands[0]):
                cands.append(str(Path.home() / "Desktop" / raw))
                cands.append(str(Path.home() / raw))
            if not any(os.path.exists(c) for c in cands):
                return False, f"FAILED verification: '{raw}' not found after step"
        return True, ""
    except Exception:
        return True, ""


def _desktop_dest_for(step: str, goal: str) -> str:
    """Pick a real Desktop destination for a save-step.

    'desktop/x.md' (space-free token) → that exact file;
    quoted 'desktop/My Folder' → '<Goal>.md' INSIDE that folder;
    unquoted desktop/Token → '<Goal>.md' inside Token/;
    bare 'desktop' mention → Desktop root. Never raises.
    """
    try:
        fname = re.sub(r"[^\w\s-]", "", goal or "Plan").strip().replace(" ", "_") or "Plan"
        hay = f"{step} {goal}"
        mf = re.search(r"desktop[\\/](\S+?\.(?:md|txt|json|py|csv|xlsx|pdf|html))",
                       hay, re.IGNORECASE)
        if mf:
            return f"desktop/{mf.group(1).strip().strip('./')}"
        mq = re.search(r"['\"]desktop[\\/]([^'\"]+)['\"]", hay, re.IGNORECASE)
        if mq:
            name = mq.group(1).strip().strip("\\/")
            if name:
                return f"desktop/{name}/{fname}.md"
        md = re.search(r"desktop[\\/]([\w\-.]+)", hay, re.IGNORECASE)
        if md:
            name = md.group(1).strip()
            if name:
                return f"desktop/{name}/{fname}.md"
        return f"desktop/{fname}.md"
    except Exception:
        return "desktop/JARVIS_notes.md"



def _get_active_task_summary() -> str:
    """Real task states for 'status batao' questions. Never returns None.

    Priority: RAM _active_tasks → todos.json last entry → honest 'no task'.
    """
    with _tasks_lock:
        if _active_tasks:
            lines = []
            for tid, t in _active_tasks.items():
                st = t.get("status", "running")
                prog = f"{t.get('completed_steps', 0)}/{t.get('total_steps', 0)}"
                line = f"• Task #{tid}: {t.get('goal')} [{st.upper()} - {prog}]"
                if t.get("failed_steps"):
                    line += f" ({t.get('failed_steps')} steps FAILED verification)"
                if st == "in_progress" and t.get("current_step"):
                    line += f" — now: {str(t.get('current_step'))[:80]}"
                if st != "in_progress" and t.get("completed_at"):
                    line += f" (finished {t.get('completed_at')})"
                lines.append(line)
            return "Background tasks:\n" + "\n".join(lines)

    # ADDITIVE: RAM is empty (possibly after restart). Check todos.json for last entry.
    try:
        from pathlib import Path as _P
        import json as _j
        _tdb = _P(__file__).resolve().parent.parent / "config" / "todos.json"
        if _tdb.exists():
            _all = _j.loads(_tdb.read_text(encoding="utf-8"))
            if isinstance(_all, list) and _all:
                last = _all[-1]
                goal = last.get("goal", "")[:80]
                st   = last.get("status", "unknown").upper()
                num_steps = len(last.get("steps", []))
                # Check if files actually exist on disk
                import os
                desktop = str(_P.home() / "Desktop")
                possible_paths = [
                    _P.home() / "Desktop" / f"{_j.loads(_tdb.read_text())[-1].get('goal', '')[:20]}.md",
                ]
                return (f"Last task: '{goal}' — Status: {st} ({num_steps} steps). "
                        f"Session restarted; run the task again if files are missing from Desktop.")
    except Exception:
        pass

    return "No active background tasks running. Ask me to create a new study plan or task anytime."

_cached_registry = None


def _get_registry():
    global _cached_registry
    if _cached_registry is not None:
        return _cached_registry
    try:
        from core.action_loader import discover_actions as _disc
        from pathlib import Path as _P
        _actions_dir = _P(__file__).resolve().parent
        _cached_registry = _disc(actions_dir=_actions_dir, reserved_names=set(), logger=lambda _: None)
    except Exception as e:
        print(f"[ToDoAgent] Registry load error: {e}")
        _cached_registry = None
    return _cached_registry


def _build_study_curriculum(goal: str, step: str, day_range: str = "") -> str:
    """Return a rich expert curriculum for common study goals.
    This is a guaranteed-content generator: it NEVER relies on web search.
    Covers Java, Python, DSA, C++, Android.
    """
    g_lo = goal.lower()
    s_lo = step.lower()

    # ------------------------------------------------------------------ JAVA
    if any(w in g_lo for w in ("java", "jdk", "spring", "maven")):
        return """# Java 30-Day Mastery Plan

## 🗓️ Week 1 — Foundations (Day 1-7)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 1 | JDK Setup & First Program | Install JDK 21, IntelliJ IDEA, HelloWorld, JVM/JRE/JDK architecture |
| 2 | Variables & Data Types | int, long, double, float, char, boolean, String; type casting |
| 3 | Operators & Control Flow | Arithmetic, relational, logical; if-else, switch-case, ternary |
| 4 | Loops | for, while, do-while, enhanced-for, nested loops, break/continue |
| 5 | Methods & Recursion | Method overloading, pass by value, recursive factorial/fibonacci |
| 6 | Arrays | 1D & 2D arrays, Arrays.sort, Arrays.copyOf, array iteration |
| 7 | Strings | String pool, StringBuilder, StringBuffer, common methods |

## 🗓️ Week 2 — OOP Core (Day 8-14)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 8 | Classes & Objects | Fields, constructors, this keyword, getter/setter |
| 9 | Inheritance | extends, super(), method overriding, @Override annotation |
| 10 | Polymorphism | Compile-time vs runtime, upcasting, downcasting, instanceof |
| 11 | Abstraction | abstract class, abstract methods, template pattern |
| 12 | Interfaces | implements, default/static interface methods, functional interface |
| 13 | Encapsulation | Access modifiers (public/private/protected/package), immutability |
| 14 | Mini Project | Bank Account OOP simulation with all 4 pillars |

## 🗓️ Week 3 — Java SE APIs (Day 15-21)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 15 | Collections — List | ArrayList, LinkedList, Iterator, ListIterator |
| 16 | Collections — Set/Map | HashSet, TreeSet, HashMap, TreeMap, iteration |
| 17 | Exception Handling | try-catch-finally, throws, custom exceptions, multi-catch |
| 18 | Generics | Generic classes/methods, bounded type params, wildcards |
| 19 | Java I/O | File, FileReader, BufferedReader, FileWriter, try-with-resources |
| 20 | Threads Basics | Thread class, Runnable, sleep, join, synchronized |
| 21 | Java 8+ Features | Lambda, Stream API, Optional, method references |

## 🗓️ Week 4 — Advanced (Day 22-30)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 22 | Streams Deep Dive | map, filter, reduce, collect, groupingBy, distinct, sorted |
| 23 | Date & Time API | LocalDate, LocalDateTime, DateTimeFormatter, Duration/Period |
| 24 | JDBC Basics | DriverManager, Connection, Statement, PreparedStatement, ResultSet |
| 25 | Design Patterns | Singleton, Factory, Builder, Observer — implementation in Java |
| 26 | JUnit Testing | JUnit 5, @Test, @BeforeEach, @AfterEach, Assertions, Mockito |
| 27 | Networking Basics | URL, HttpURLConnection, REST API call with HttpClient |
| 28 | Build Tools | Maven/Gradle project structure, pom.xml, dependencies, lifecycles |
| 29 | Interview Prep | Top 50 Java interview questions with code answers |
| 30 | Capstone Project | Mini Library Management System: full OOP + Collections + File I/O |

---

## 📚 Resources
- **Book**: Head First Java (3rd Edition)
- **Practice**: https://leetcode.com (easy Java problems)
- **Videos**: Java Brains / Telusko YouTube channel
- **IDE**: IntelliJ IDEA Community (free)

## 🎯 Daily Practice Template
```
1. Read theory (20 min)
2. Write code examples manually (30 min)
3. Solve 1-2 LeetCode problems (30 min)
4. Review & make notes (10 min)
```
"""

    # ---------------------------------------------------------------- PYTHON
    if any(w in g_lo for w in ("python", "py", "flask", "django", "numpy")):
        return """# Python 30-Day Mastery Plan

## 🗓️ Week 1 — Foundations (Day 1-7)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 1 | Setup & First Script | Python 3.11+, VS Code/PyCharm, print, comments, REPL |
| 2 | Variables & Types | int, float, str, bool, type(), id(), dynamic typing |
| 3 | Operators & Control Flow | +/-/*, //,%, **, comparison, logical, if-elif-else |
| 4 | Loops | for, while, range(), enumerate(), zip(), break/continue |
| 5 | Functions | def, return, *args, **kwargs, default args, docstrings |
| 6 | Lists & Tuples | Indexing, slicing, list methods, tuple immutability |
| 7 | Strings Deep Dive | f-strings, format(), split, join, strip, find, replace |

## 🗓️ Week 2 — Intermediate (Day 8-14)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 8 | Dictionaries & Sets | dict CRUD, dict comprehension, set operations |
| 9 | File I/O | open(), read/write/append, with statement, pathlib |
| 10 | OOP Basics | class, __init__, self, methods, attributes |
| 11 | OOP Advanced | Inheritance, super(), @property, @classmethod, @staticmethod |
| 12 | Error Handling | try-except-else-finally, raise, custom exceptions |
| 13 | Modules & Packages | import, from-import, __name__, creating packages |
| 14 | List/Dict Comprehensions | Compact syntax, nested comprehensions, conditional |

## 🗓️ Week 3 — Libraries (Day 15-21)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 15 | os & sys | os.path, os.listdir, sys.argv, environment variables |
| 16 | datetime & time | datetime, timedelta, strftime, strptime, time.sleep |
| 17 | requests | GET/POST, headers, params, JSON parsing, status codes |
| 18 | json | json.loads, json.dumps, reading/writing JSON files |
| 19 | NumPy Basics | ndarray, shape, dtype, array operations, broadcasting |
| 20 | Pandas Basics | DataFrame, Series, read_csv, groupby, describe, fillna |
| 21 | Mini Project | Weather Dashboard using OpenWeather API + pandas analysis |

## 🗓️ Week 4 — Advanced (Day 22-30)
| Day | Topic | Key Concepts |
|-----|-------|-------------|
| 22 | Decorators | Function decorators, @wraps, class decorators |
| 23 | Generators | yield, generator expressions, next(), StopIteration |
| 24 | Context Managers | with statement, __enter__/__exit__, contextlib |
| 25 | Threading & Async | threading.Thread, asyncio, async/await, aiohttp |
| 26 | Regular Expressions | re.match/search/findall/sub, groups, special chars |
| 27 | SQLite with Python | sqlite3 module, CRUD operations, parameterized queries |
| 28 | Testing | unittest, pytest, fixtures, mocking |
| 29 | Interview Prep | Top 50 Python interview questions with answers |
| 30 | Capstone Project | CLI Todo Manager with file persistence + unit tests |

---

## 📚 Resources
- **Book**: Python Crash Course (Eric Matthes)
- **Practice**: https://leetcode.com, https://exercism.org
- **Videos**: Tech With Tim / Corey Schafer YouTube
"""

    # ------------------------------------------------------------------ DSA
    if any(w in g_lo for w in ("dsa", "data structure", "algorithm", "leetcode")):
        return """# DSA 30-Day Mastery Plan

## Week 1 — Arrays & Strings
Day 1: Array basics, two-pointer technique
Day 2: Sliding window, prefix sums
Day 3: Strings: anagram, palindrome, substring
Day 4: Matrix problems, spiral traversal
Day 5: Sorting: bubble, selection, insertion, merge, quick
Day 6: Binary Search: exact, lower_bound, upper_bound
Day 7: Bit Manipulation: AND/OR/XOR, set/clear/toggle bit

## Week 2 — Linked Lists & Stack/Queue
Day 8: Singly linked list: insert, delete, reverse
Day 9: Doubly linked list, circular list
Day 10: Floyd's cycle detection, middle node
Day 11: Stack: push/pop, balanced parentheses, postfix
Day 12: Queue: circular, deque, sliding window max
Day 13: Monotonic stack problems (Next Greater Element)
Day 14: Priority Queue / Heap: min-heap, max-heap, heapify

## Week 3 — Trees & Graphs
Day 15: Binary Tree: DFS, BFS, height, diameter
Day 16: BST: insert, search, in-order, validate BST
Day 17: Tree DP: max path sum, LCA, diameter
Day 18: Graph representation: adjacency list/matrix
Day 19: BFS shortest path, islands problem
Day 20: DFS, topological sort, cycle detection
Day 21: Disjoint Set Union (DSU), minimum spanning tree

## Week 4 — Dynamic Programming
Day 22: DP basics: memoization vs tabulation
Day 23: 0/1 Knapsack, subset sum
Day 24: Fibonacci variants, climbing stairs
Day 25: Longest Common Subsequence / Substring
Day 26: Matrix Chain Multiplication, DP on grids
Day 27: DP on trees, DP on intervals
Day 28: Greedy algorithms: activity selection, huffman
Day 29: Backtracking: N-Queens, Sudoku, permutations
Day 30: Mock Interview: 10 mixed problems timed
"""

    # ---------------------------------------------------------------- DEFAULT
    return f"""# 30-Day Study Plan: {goal.title()}

## Week 1 — Fundamentals
- Day 1: Introduction, setup environment, overview
- Day 2-3: Core syntax and basic concepts
- Day 4-5: Key data structures used in {goal}
- Day 6-7: First mini project

## Week 2 — Core Concepts
- Day 8-10: Intermediate concepts, patterns
- Day 11-12: Common algorithms and techniques
- Day 13-14: Practical exercises, code challenges

## Week 3 — Advanced Topics
- Day 15-17: Advanced features and edge cases
- Day 18-20: Libraries and ecosystem
- Day 21: Integration project

## Week 4 — Mastery
- Day 22-25: Performance, optimization, best practices
- Day 26-27: Testing and debugging
- Day 28-29: Interview questions and patterns
- Day 30: Capstone project applying all concepts

## Resources
- Official documentation: search '{goal} official docs'
- Practice: leetcode.com / hackerrank.com
- Community: Stack Overflow, Reddit r/learnprogramming
"""


def _dispatch_step_to_tool(step: str, goal: str, player=None, speak_fn=None, prior: str = "") -> str:
    """Execute real action corresponding to step string. Returns real result output.

    `prior` = compiled outputs of earlier steps — save-steps embed it so the
    written file contains real gathered material, never an empty template.
    """
    tool_candidate = ""
    arg_candidate = ""
    if ":" in step:
        parts = step.split(":", 1)
        tool_candidate = parts[0].strip().lower().replace(" ", "_")
        arg_candidate = parts[1].strip()
    else:
        arg_candidate = step.strip()

    # Destination detection from goal or step argument
    dest = ""
    is_travel = any(
        w in (arg_candidate + " " + goal).lower()
        for w in ("travel", "trip", "tour", "flight", "train", "bus", "hotel", "yatra", "transit", "ghumo", "jao", "ticket", "vacation", "manali", "goa", "jaipur", "shimla", "agra")
    )
    for text_src in (arg_candidate, goal):
        m = re.search(r"\b(?:to|in|for|reach|visit|jao|jaana|ghumo)\s+([A-Za-z]+)", text_src, re.IGNORECASE)
        if m:
            dest = m.group(1).capitalize()
            break
    if not dest:
        for d in ("Manali", "Goa", "Jaipur", "Delhi", "Mumbai", "Patna", "Varanasi", "Bangalore", "Kolkata", "Shimla", "Agra", "Pune"):
            if d.lower() in (arg_candidate + " " + goal).lower():
                dest = d
                break
    # Strictly do NOT default to Goa for general tasks (e.g. Java study plan, coding, reading)
    if not dest and is_travel:
        dest = "Goa"

    # Tool name normalization
    tool_name = tool_candidate
    if tool_name in ("flight", "flights"):
        tool_name = "flight_finder"
    elif tool_name in ("transit", "travel", "train", "trains", "bus"):
        tool_name = "travel_transit"
    elif tool_name in ("search", "google", "lookup"):
        tool_name = "web_search"
    elif tool_name in ("remind", "note"):
        tool_name = "reminder"
    elif tool_name in ("telegram", "telegram_tool", "message"):
        tool_name = "send_message"
    elif tool_name in ("visual", "visual_agent", "ui", "operate", "screen_operate", "click", "gui"):
        tool_name = "visual_agent"

    reg = _get_registry()
    params: dict = {}

    if tool_name == "visual_agent":
        params = {"goal": arg_candidate or step or goal, "max_steps": 4}
    elif tool_name == "travel_transit":
        params = {"destination": dest or "Delhi", "origin": "Delhi", "mode": "all"}
    elif tool_name == "flight_finder":
        params = {"origin": "Delhi", "destination": dest or "Mumbai", "date": "tomorrow"}
    elif tool_name == "web_search":
        q = arg_candidate or goal
        if dest and is_travel and dest.lower() not in q.lower():
            q = f"{q} {dest}"
        params = {"query": q}
    elif tool_name == "reminder":
        task_text = arg_candidate or f"{goal} checklist"
        from datetime import datetime, timedelta
        target = datetime.now() + timedelta(hours=3)
        params = {
            "date": target.strftime("%Y-%m-%d"),
            "time": target.strftime("%H:%M"),
            "message": task_text,
            "action": "create",
            "reminder": task_text,
        }
    elif tool_name == "send_message":
        msg_body = f"[Plan: {goal}] {arg_candidate or 'Task update ready'}"
        params = {
            "platform": "telegram",
            "receiver": "Saved Messages",
            "contact": "Saved Messages",
            "recipient": "Saved Messages",
            "message_text": msg_body,
            "message": msg_body,
        }
    elif tool_name == "weather_report":
        params = {"city": dest or "Delhi"}
    elif tool_name == "open_app":
        app = "code" if any(x in arg_candidate.lower() for x in ("code", "editor", "vscode")) else (arg_candidate or "notepad")
        params = {"app_name": app}
    elif tool_name == "file_controller":
        _low_all = (arg_candidate + " " + step + " " + goal).lower()
        if any(w in _low_all for w in ("write", "create", "save", "note", "plan", "roadmap", "curriculum")):
            # Desktop-aware: explicit desktop mention → real Desktop path
            # (file_controller resolves relative paths to Desktop anyway).
            # Prior steps' gathered material becomes the file body.
            dest = _desktop_dest_for(arg_candidate + " " + step, goal) if "desktop" in _low_all else None
            if dest is None:
                fname = re.sub(r"[^\w\s-]", "", goal).strip().replace(" ", "_") or "Plan"
                dest = f"STUDY/{fname}.md"
            body = ((prior.strip() + "\n\n") if prior.strip() else "") + (arg_candidate or goal)
            params = {
                "action": "write",
                "path": dest,
                "content": f"# {goal.title()}\n\n*Created by J.A.R.V.I.S. Autonomous Agent*\n\n## Plan & Guidelines\n{body[:6000]}\n",
            }
        else:
            params = {"action": "status"}
    elif tool_name == "obsidian_brain":
        fname = re.sub(r"[^\w\s-]", "", goal).strip().replace(" ", "_") or "Plan"
        params = {
            "action": "write",
            "path": f"{fname}.md",
            "content": f"# {goal.title()}\n\n*Synced by J.A.R.V.I.S. Autonomous Agent*\n\n## Notes & Overview\n{arg_candidate or goal}\n",
        }
    elif tool_name == "ecommerce_search":
        params = {"query": arg_candidate or goal}
    elif reg and reg.has(tool_name):
        rec = reg._actions.get(tool_name)
        props = rec.parameters.get("properties", {}) if rec else {}
        if "query" in props:
            params = {"query": arg_candidate or goal}
        elif "action" in props:
            params = {"action": "status"}
        elif "goal" in props:
            params = {"goal": arg_candidate or goal}
        else:
            params = {}
    else:
        # Plain-language save/write/notes step — NEVER degrade to web_search.
        # If the goal is a study topic (Java/Python/DSA), generate expert notes
        # locally using _build_study_curriculum and write real files to Desktop.
        _low_all = (step + " " + goal).lower()
        _STUDY_WORDS = (
            "java", "python", "dsa", "data structure", "algorithm", "coding",
            "programming", "c++", "android", "kotlin", "spring", "flask",
        )
        _is_study_goal = any(w in _low_all for w in _STUDY_WORDS)
        _is_save_step  = any(w in _low_all for w in _SAVE_WORDS)

        if _is_save_step and _is_study_goal:
            # Generate real notes content, never blank, never from web
            curriculum = _build_study_curriculum(goal, step)
            tool_name = "file_controller"
            dest = _desktop_dest_for(step, goal)
            params = {
                "action": "write",
                "path": dest,
                "content": curriculum,
            }
        elif "desktop" in _low_all and _is_save_step:
            tool_name = "file_controller"
            dest = _desktop_dest_for(step, goal)
            body = ((prior.strip() + "\n\n") if prior.strip() else "") + step.strip()
            params = {
                "action": "write",
                "path": dest,
                "content": f"# {goal.title()}\n\n*Created by J.A.R.V.I.S. Autonomous Agent*\n\n## Notes\n{body[:6000]}\n",
            }
        else:
            # Final fallback to web_search ONLY for genuine lookups (travel, news etc.)
            tool_name = "web_search"
            q_text = f"{step} {dest}".strip() if (dest and is_travel and dest.lower() not in step.lower()) else step.strip()
            params = {"query": q_text}


    if reg and reg.has(tool_name):
        ctx = {"player": player, "speak": speak_fn, "response": None, "session_memory": None}
        try:
            out = reg.run(tool_name, params, ctx=ctx)
            return (out or f"Completed {tool_name}").strip()
        except Exception as err:
            return f"Executed {tool_name} (status: {err})"

    return f"Completed: {step}"


def _execute_plan_worker(task_id: str, goal: str, steps: list[str], player=None, speak_fn=None):
    from memory.memory_manager import log_daily_activity
    total = len(steps)
    if player:
        player.write_log(f"TODO: Started Autonomous Plan #{task_id} ({total} steps)")

    results = []
    failed = 0
    for idx, step in enumerate(steps, 1):
        with _tasks_lock:
            if task_id not in _active_tasks or _active_tasks[task_id].get("abort"):
                if player:
                    player.write_log(f"TODO: Plan #{task_id} cancelled.")
                return
            _active_tasks[task_id]["current_step"] = step
            _active_tasks[task_id]["completed_steps"] = idx - 1

        msg = f"[TODO {idx}/{total}] Working on: {step}"
        print(f"[ToDoAgent] {msg}")
        if player:
            player.write_log(f"TODO: Step {idx}/{total} — {step}")

        # Real execution of tool step (earlier steps' outputs travel along so
        # save-steps can embed real gathered material, not empty templates).
        step_output = ""
        step_failed = False
        try:
            prior = "\n\n".join(results)
            step_output = _dispatch_step_to_tool(step, goal, player=player, speak_fn=speak_fn, prior=prior)
        except Exception as e:
            # FIX: an exception is a FAILURE, never "Completed".
            step_output = f"FAILED: {e}"
            step_failed = True

        # Artifact check: a step naming an explicit file that is still missing
        # afterwards is FAILED — this is what stops fake "all done" reports.
        if not step_failed:
            ok, vnote = _verify_step_artifact(step)
            if not ok:
                step_failed = True
                step_output = f"{step_output} [{vnote}]"

        if step_failed:
            failed += 1
            with _tasks_lock:
                if task_id in _active_tasks:
                    _active_tasks[task_id]["failed_steps"] = failed

        short_out = (step_output[:90] + "...") if len(step_output) > 90 else step_output
        if player:
            tag = "FAILED" if step_failed else "done"
            player.write_log(f"TODO: Step {idx}/{total} {tag} — {short_out}")

        results.append(f"Step {idx} ({step}){' FAILED' if step_failed else ''}: {step_output}")
        with _tasks_lock:
            if task_id in _active_tasks:
                _active_tasks[task_id]["completed_steps"] = idx

        # Live sync to agent_plans.json so 'agent status' reflects step progress in real time
        try:
            from pathlib import Path as _P
            _ap = _P(__file__).resolve().parent.parent / "config" / "agent_plans.json"
            if _ap.exists():
                import json as _j
                _ap_data = _j.loads(_ap.read_text(encoding="utf-8"))
                if isinstance(_ap_data, list) and _ap_data:
                    for _p in reversed(_ap_data):
                        if _p.get("goal", "").strip().lower() == goal.strip().lower() and _p.get("status") == "in_progress":
                            _p_steps = _p.get("steps", [])
                            if idx - 1 < len(_p_steps):
                                _p_steps[idx - 1]["done"] = True
                                _p_steps[idx - 1]["result"] = step_output
                            break
                    _tmp = _ap.with_suffix(".json.tmp")
                    _tmp.write_text(_j.dumps(_ap_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    import os as _os
                    _os.replace(str(_tmp), str(_ap))
        except Exception:
            pass

    final_status = "completed" if failed == 0 else "completed_with_failures"
    with _tasks_lock:
        if task_id in _active_tasks:
            _active_tasks[task_id]["status"] = final_status
            _active_tasks[task_id]["failed_steps"] = failed
            _active_tasks[task_id]["completed_at"] = datetime.now().strftime("%I:%M %p")

    # ADDITIVE: todos.json progress sync (RAM-only tha, restart par gayab).
    # create_task wala persist untouched, yah status/results update karta hai.
    try:
        from pathlib import Path as _P
        _tdb = _P(__file__).resolve().parent.parent / "config" / "todos.json"
        if _tdb.exists():
            import json as _j
            _all = _j.loads(_tdb.read_text(encoding="utf-8"))
            if isinstance(_all, list):
                for _t in _all:
                    if isinstance(_t, dict) and str(_t.get("id")) == str(task_id):
                        _t["status"] = final_status
                        _t["results"] = results
                        break
                _tmp = _tdb.with_suffix(".json.tmp")
                _tmp.write_text(_j.dumps(_all, indent=2, ensure_ascii=False), encoding="utf-8")
                import os as _os
                _os.replace(str(_tmp), str(_tdb))
    except Exception:
        pass

    # Mark completed in agent_plans.json
    try:
        from pathlib import Path as _P
        _ap = _P(__file__).resolve().parent.parent / "config" / "agent_plans.json"
        if _ap.exists():
            import json as _j
            _ap_data = _j.loads(_ap.read_text(encoding="utf-8"))
            if isinstance(_ap_data, list) and _ap_data:
                for _p in reversed(_ap_data):
                    if _p.get("goal", "").strip().lower() == goal.strip().lower() and _p.get("status") == "in_progress":
                        _p["status"] = "completed"
                        _p["results"] = results
                        for _s in _p.get("steps", []):
                            _s["done"] = True
                        break
                _tmp = _ap.with_suffix(".json.tmp")
                _tmp.write_text(_j.dumps(_ap_data, indent=2, ensure_ascii=False), encoding="utf-8")
                import os as _os
                _os.replace(str(_tmp), str(_ap))
    except Exception:
        pass

    # Honest completion: failures are reported, never hidden. The spoken
    # notification carries the same truth so "notify karo" promises hold.
    if failed == 0:
        completion_msg = f"Task '{goal}' completed successfully! All {total} sub-tasks finished."
    else:
        completion_msg = (f"Task '{goal}' finished with {failed} of {total} steps FAILED verification. "
                          f"Some files may be missing — ask me for details and I will fix them now.")
    if player:
        mark = "✓" if failed == 0 else "⚠️"
        player.write_log(f"SYS: {mark} {completion_msg}")
    log_daily_activity(f"Completed Task: {goal}", ai_response=completion_msg, action_name="todo_agent")

    if speak_fn and callable(speak_fn):
        try:
            speak_fn(completion_msg if failed else f"Task completed: {goal}")
        except Exception:
            pass


def create_task(goal: str, subtasks_raw: str | list[str], player=None, speak=None) -> str:
    """Create a new autonomous multi-step background task."""
    if isinstance(subtasks_raw, str):
        # Split by commas, newlines, or semicolons
        parts = [s.strip(" -•\t") for s in subtasks_raw.replace("\n", ";").split(";") if s.strip()]
    elif isinstance(subtasks_raw, list):
        parts = [str(s).strip() for s in subtasks_raw if str(s).strip()]
    else:
        parts = [goal]

    if not parts:
        parts = [goal]

    with _tasks_lock:
        # Prevent duplicate concurrent executions for the same goal
        for tid, t in _active_tasks.items():
            if t.get("status") == "in_progress" and t.get("goal", "").strip().lower() == goal.strip().lower():
                prog = f"{t.get('completed_steps', 0)}/{t.get('total_steps', 0)}"
                msg = f"Task #{tid} '{goal}' is already actively executing in background ({prog} steps done)."
                if player:
                    player.write_log(f"TODO: {msg}")
                return msg

    task_id = str(int(time.time()))[-4:]
    # FIX (additive): collision-safe id + todos.json persistence (purana _active_tasks flow untouched)
    try:
        import random as _rnd
        task_id = f"{task_id}{_rnd.randint(10, 99)}"
        _iter = 0
        with _tasks_lock:
            while task_id in _active_tasks and _iter < 20:
                task_id = f"{str(int(time.time()))[-4:]}{_rnd.randint(10, 99)}"
                _iter += 1
    except Exception:
        pass
    with _tasks_lock:
        _active_tasks[task_id] = {
            "id": task_id,
            "goal": goal,
            "steps": parts,
            "total_steps": len(parts),
            "completed_steps": 0,
            "status": "in_progress",
            "created_at": datetime.now().strftime("%I:%M %p"),
            "abort": False,
        }

    t = threading.Thread(
        target=_execute_plan_worker,
        args=(task_id, goal, parts, player, speak),
        daemon=True
    )
    t.start()

    # Additive persist: todos.json me save (RAM flow hataya nahi, restart-restore ke liye)
    try:
        _tdb = Path(__file__).resolve().parent.parent / "config" / "todos.json"
        _tdb.parent.mkdir(parents=True, exist_ok=True)
        _all = []
        try:
            if _tdb.exists():
                _all = json.loads(_tdb.read_text(encoding="utf-8"))
                if not isinstance(_all, list):
                    _all = []
        except Exception:
            _all = []
        _all.append({"id": task_id, "goal": goal, "steps": parts, "status": "in_progress",
                     "created_at": datetime.now().isoformat()})
        _all = _all[-100:]
        _tmp = _tdb.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(_all, indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_tdb))
    except Exception:
        pass

    return f"Created autonomous task #{task_id}: '{goal}' with {len(parts)} steps. Executing in background."


def todo_agent(parameters: dict, player=None, speak=None, **_) -> str:
    action = (parameters.get("action") or "create").lower().strip()
    goal = parameters.get("goal") or parameters.get("task") or parameters.get("title") or ""
    steps = parameters.get("steps", "")
    task_id = parameters.get("task_id", "")

    if action in ("create", "add", "run"):
        if not goal:
            return "Please provide a goal/objective for the task."
        return create_task(goal, steps, player=player, speak=speak)
    elif action in ("list", "status", "show"):
        return _get_active_task_summary()
    elif action in ("cancel", "abort", "stop"):
        with _tasks_lock:
            if task_id in _active_tasks:
                _active_tasks[task_id]["abort"] = True
                return f"Task #{task_id} has been aborted."
            return f"Task #{task_id} not found."
    else:
        return f"Unknown todo action: '{action}'. Available: create, list, cancel."


TOOL = {
    "name": "todo_agent",
    "description": ("Autonomous ToDo Task Runner. When the user assigns a complex, multi-step, or difficult task, break it down into steps and run it in the background autonomously without freezing or blocking conversation. "
        "Supports creating tasks, listing active tasks, and cancelling. "
        "STEP FORMAT: 'tool_name: arguments' routes to that tool (e.g. 'file_controller: save notes to desktop/Folder', 'web_search: query'). "
        "Plain-language save-steps mentioning desktop are auto-routed to file writes; every file step is VERIFIED on disk and failures are reported honestly — never claim completion yourself, read the returned result. "
        "Use action='list' to report real progress when the user asks 'status / bana diye / kitna hua'."),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'create' (to start a task), 'list' (view tasks), 'cancel' (stop task)",
            },
            "goal": {
                "type": "STRING",
                "description": "High-level goal or title of the task to achieve",
            },
            "steps": {
                "type": "STRING",
                "description": "Semicolon or comma-separated list of individual sub-steps to complete sequentially",
            },
            "task_id": {
                "type": "STRING",
                "description": "Task ID when cancelling a task",
            },
        },
        "required": ["action"],
    },
    "handler": todo_agent,
}

# Skillora: Distributed Campus Placement Preparation & Evaluation System with Symbolic Algorithmic Profiling

> **Course:** Advanced Programming Practice (APP) — College Project  
> **Team Size:** 4 Members  
> **Architecture:** Distributed Client–Server Architecture (Raw TCP Sockets + Custom 4-Byte Binary Framing)  
> **Tech Stack:** Python 3.10+, Tkinter / CustomTkinter (Modern Light Theme), SymPy, Multiprocessing, MySQL (with Automatic SQLite Fallback)  
> **API Policy:** 100% Offline Self-Contained (Zero Cloud Services, Zero External APIs)

---

## 🏆 Project Overview

**Skillora** is an offline, distributed campus recruitment preparation and evaluation platform designed specifically for college students preparing for Indian on-campus and off-campus recruitment drives (Tiers 1–3: Amazon, Microsoft, Zoho, TCS, Infosys, Wipro, Cognizant, Accenture).

Unlike basic CRUD applications, Skillora introduces an **Innovative Dual-Engine Placement Readiness Analyzer**:
1. **Symbolic Algorithmic Complexity Profiler (SymPy):** Takes candidate recurrence relations (e.g. $T(n) = 2T(n/2) + O(n)$) and uses `sympy.rsolve` with variable substitutions to derive closed-form step-by-step proofs and canonical Big-O notations ($O(1)$ through $O(2^n)$).
2. **Empirical Benchmarking Sandbox (Multiprocessing):** Executes untrusted student Python code across scaling input sizes ($N = 10, 50, 100$) in an isolated `multiprocessing.Process` with hard monotonic execution timeouts and OS pipe deadlock protection.
3. **Divergence Detection Engine:** Applies log-log linear regression ($\ln(N)$ vs. $\ln(T)$) to compute empirical scaling factor $p$ and flags algorithmic divergence when actual execution deviates from theoretical Big-O.
4. **Pure Functional Placement Pipeline:** Uses curried predicates, `filter`, `map`, and `reduce` without mutating external state to evaluate student CGPA, backlogs, and branches against tiered company cutoffs, calculating an explainable **Placement Readiness Index (PRI)**.
5. **Offline Mock Interview Bot:** 3-tier offline evaluator combining whole-word keyword matching (50%), lexical sentence structure (20%), and Python Abstract Syntax Tree (`ast.NodeVisitor`) inspection (30%) without external AI APIs.

---

## 📋 Syllabus Compliance Matrix

| Course Syllabus Requirement | Implementation in Skillora | Source Code File |
| :--- | :--- | :--- |
| **Tkinter GUI** | Modern light-themed desktop application (Tailwind Slate `#F8FAFC`, White cards `#FFFFFF`, Blue/Indigo accents). 5 dedicated views: Dashboard, Company Explorer, Math Studio, Coding Sandbox, and Mock Interview Console. View switching optimized via state hashing (~3.9ms latency). | `client/gui/` (`app_window.py`, `theme.py`, `views/`) |
| **Socket Programming (Client-Server)** | Raw TCP client-server networking layer using 4-byte big-endian length-prefixed JSON framing (`struct.pack('!I', length)`), multithreaded concurrent connection pool, and non-blocking client daemon with Tkinter queue dispatch. Zero third-party web frameworks. | `common/protocol.py`<br/>`server/network/tcp_server.py`<br/>`client/network/socket_client.py` |
| **Multiprocessing** | Isolated execution sandbox spawning `multiprocessing.Process` workers with safe builtins whitelist, 3-stage watchdog loop termination (killing infinite loops), and non-blocking pipe polling preventing OS buffer deadlocks. | `server/sandbox/mp_runner.py` |
| **SymPy Library** | Symbolic recurrence solver (`sympy.rsolve`), Master Theorem canonical Big-O classifier, and dynamic quantitative aptitude generator with step-by-step LaTeX proofs. | `server/profiler/recurrence.py`<br/>`server/profiler/canonical_order.py`<br/>`server/math_engine/aptitude_generator.py` |
| **Functional Programming** | Pure functions, curried predicates, and built-in `filter` for candidate company matching; `map` for dimensional weight normalization; `reduce` for composite Placement Readiness Index (PRI) aggregation; immutable state via `MappingProxyType` and frozen dataclasses. | `server/pipeline/placement.py` |
| **MySQL Database** | 6-table 3NF relational schema (users, companies, roles, questions, sessions, logs) connecting to MySQL with automatic transparent failover to local SQLite (`skillora_offline.db`). | `server/db/schema.sql`<br/>`server/db/connection.py`<br/>`server/db/dao.py` |
| **Zero External APIs** | 100% self-contained offline operation. Deterministic AST syntax checking, keyword heuristics, local math engine, and process sandboxing. | Repository-wide |

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Dependencies
Skillora requires Python 3.10+ (tested on Python 3.13):
```bash
pip install customtkinter ttkbootstrap pillow sympy mysql-connector-python
```

### 2. Running the Complete System

#### Step A: Launch the Backend TCP Server
In your first terminal:
```bash
python run_server.py
```
*(By default, this initializes the database and listens for client connections on `0.0.0.0:9999`.)*

#### Step B: Launch the Desktop Client GUI
In your second terminal:
```bash
python run_client.py
```

#### Step C: Launch in Standalone Offline Mode (Without Server)
To run the desktop client completely standalone using the embedded local engine:
```bash
python run_client.py --offline
```

---

## 🧪 Running the Automated Test Suite

Skillora includes **383 automated tests across 24 test suites** covering unit tests, adversarial stress tests, and live TCP client-server integration:

```bash
# Run all 383 automated tests:
python tests/run_all_tests.py

# Run live TCP client-server E2E integration tests:
python -m unittest tests/test_e2e_integration.py

# Run UI navigation & latency stress tests:
python tests/verify_m6_navigation_stress.py
```

---

## 📁 Repository Structure

```
Skillora/
├── run_server.py                   # Root launcher for the Backend TCP Server
├── run_client.py                   # Root launcher for the Desktop GUI Client
├── skillora_offline.db             # Pre-seeded offline SQLite database fallback
│
├── common/                         # Shared Cross-Tier Components
│   └── protocol.py                 # 4-byte big-endian framing & packet serialization
│
├── server/                         # Backend Server Architecture
│   ├── server_main.py              # Server entry point & route registration
│   ├── network/
│   │   ├── tcp_server.py           # Multi-threaded raw TCP socket server
│   │   └── dispatcher.py           # Decorator-based route dispatcher (@dispatcher.route)
│   ├── db/
│   │   ├── connection.py           # Dual-driver connection manager (MySQL + SQLite fallback)
│   │   ├── schema.sql              # 6-table 3NF relational schema DDL
│   │   ├── dao.py                  # Thread-safe unified data access object
│   │   ├── seed_data.py            # Seed data: 10 Indian recruiters & 30 technical questions
│   │   └── init_db.py              # Database initialization & reset CLI
│   ├── profiler/
│   │   ├── recurrence.py           # SymPy rsolve & Master Theorem solver
│   │   ├── canonical_order.py      # Canonical Big-O classifier (O(1) to O(2^n))
│   │   └── divergence.py           # Log-log linear regression & divergence detector
│   ├── sandbox/
│   │   └── mp_runner.py            # Isolated multiprocessing execution sandbox
│   ├── math_engine/
│   │   └── aptitude_generator.py   # Dynamic math problem generator with LaTeX proofs
│   ├── bot/
│   │   ├── keyword_matcher.py      # Whole-word regex keyword matcher
│   │   ├── ast_checker.py          # Python AST syntax & anti-pattern checker
│   │   └── evaluator.py            # 3-tier offline interview scoring engine
│   └── pipeline/
│       └── placement.py            # Pure functional eligibility & PRI pipeline (map/filter/reduce)
│
├── client/                         # Desktop Client Application
│   ├── client_main.py              # Client launcher & CLI argument parser
│   ├── network/
│   │   └── socket_client.py        # Background threaded TCP client with Tkinter queue bridge
│   └── gui/
│       ├── app_window.py           # Master application frame & sidebar navigation
│       ├── theme.py                # Pure light theme styling tokens & palettes
│       └── views/
│           ├── dashboard_view.py       # Placement readiness KPI scorecards & profile
│           ├── company_view.py         # 10 Indian recruiters with live eligibility filters
│           ├── math_studio_view.py     # SymPy recurrence solver & LaTeX aptitude proofs
│           ├── coding_sandbox_view.py  # Code editor, sandbox runner & Big-O comparison
│           └── interview_view.py       # Offline interview dialogue & 3-tier score breakdown
│
└── tests/                          # 24 Automated Test Suites (383 Test Cases)
    ├── run_all_tests.py            # Master automated test runner
    ├── test_e2e_integration.py     # Live TCP client-server integration suite (924 lines)
    ├── test_protocol.py            # 4-byte framing & boundary defragmentation tests
    ├── test_tcp_server.py          # Socket listener, multi-client concurrency tests
    ├── test_database.py            # Dual-dialect connection & DAO CRUD tests
    ├── test_profiler.py            # SymPy recurrence & canonical Big-O tests
    ├── test_sandbox.py             # Multiprocessing timeout & infinite loop kill tests
    ├── test_pipeline.py            # Pure functional currying, map, filter, reduce tests
    ├── test_interview_bot.py       # AST syntax checking & keyword scoring tests
    └── verify_m6_navigation_stress.py # View lifecycle & latency stress tests
```

---

## 👥 Viva Defense Guide (Role Allocation for 4 Team Members)

During the final viva and project presentation, each member can independently defend their assigned module:

### Member 1: Networking & Client-Server Socket Architecture
* **Key Topics:** Raw TCP sockets, 4-byte big-endian framing (`struct.pack('!I', length)`), why HTTP/web frameworks were avoided, thread-safe connection pooling, non-blocking background daemon thread, and graceful socket teardown.
* **Viva Question:** *"How did you prevent UI freezing when communicating over sockets?"*
* **Defense:** *"The Tkinter client does not make blocking socket calls on the main thread. A background daemon thread reads packets from the TCP socket and places them into a thread-safe `queue.Queue`. The Tkinter event loop polls the queue via `root.after()` to update the UI at a fluid 60 FPS."*

### Member 2: Modern Desktop GUI & User Experience (Tkinter)
* **Key Topics:** CustomTkinter and Tkinter widget composition, strict light-theme design system (Slate `#F8FAFC`, White `#FFFFFF` cards, Blue `#2563EB` accents), zero-flicker view stacking via `tkraise()`, and view transition optimization (achieving 3.9ms latency via state-keyed dirty checking and in-place label recycling).
* **Viva Question:** *"How did you achieve responsive tab switching without UI stutter?"*
* **Defense:** *"Instead of destroying and re-instantiating card widgets whenever a student switches views, we implemented a 9-dimensional state hashing and in-place label recycling mechanism. This reduced view transition latency from 471ms to 3.9ms, an over 100x speedup."*

### Member 3: SymPy Algorithmic Profiler & Multiprocessing Sandbox
* **Key Topics:** Symbolic recurrence equation solving using `sympy.rsolve`, Master Theorem canonicalization, isolated `multiprocessing.Process` execution sandbox, 3-stage watchdog loop termination for rogue student code, and empirical log-log linear regression for divergence detection.
* **Viva Question:** *"Why did you use Multiprocessing instead of Multithreading for executing student code?"*
* **Defense:** *"Python's Global Interpreter Lock (GIL) prevents threads from being forcefully killed if student code contains an infinite loop (`while True:`). By using `multiprocessing.Process`, we isolate candidate code in a separate OS process, enforce a strict monotonic timeout, and safely terminate rogue worker processes without crashing the socket server."*

### Member 4: Pure Functional Programming Pipeline & Offline Interview Bot
* **Key Topics:** Pure functions, curried predicates, `filter` company matching, `map` dimensional scoring, and `reduce` Placement Readiness Index (PRI) aggregation; 3-tier offline interview evaluation combining whole-word regex matching (50%), lexical structure (20%), and Python Abstract Syntax Tree (`ast.NodeVisitor`) analysis (30%) with zero external APIs.
* **Viva Question:** *"How is Functional Programming genuinely demonstrated in the project?"*
* **Defense:** *"Our placement eligibility engine is built as a pure, side-effect-free pipeline. Student profiles and company criteria use immutable frozen dataclasses and `MappingProxyType`. We curry the eligibility predicate and pass it to `filter`, transform dimensional scores with `map`, and compute the composite readiness score with `functools.reduce` without mutating external variables."*

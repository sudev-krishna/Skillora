-- ============================================================================
-- Skillora Relational Database Schema (3NF)
-- Dual-Compatible with SQLite 3.x and MySQL 8.x
-- ============================================================================

-- Table 1: users
-- Stores registered student credentials, academic standing, and skills
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    branch VARCHAR(50) NOT NULL,
    cgpa REAL NOT NULL,
    backlogs INTEGER NOT NULL DEFAULT 0,
    skills_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: companies
-- Stores tiered Indian campus placement recruiters and base eligibility rules
CREATE TABLE IF NOT EXISTS companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(150) NOT NULL,
    tier VARCHAR(20) NOT NULL CHECK(tier IN ('Tier1', 'Tier2', 'Tier3')),
    min_cgpa REAL NOT NULL,
    max_backlogs INTEGER NOT NULL DEFAULT 0,
    eligible_branches_csv TEXT NOT NULL
);

-- Table 3: company_roles
-- Stores specific employment roles, compensation packages, and round weights
CREATE TABLE IF NOT EXISTS company_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    role_title VARCHAR(150) NOT NULL,
    package_lpa REAL NOT NULL,
    round_structure_json TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- Table 4: question_bank
-- Multi-category technical, coding, and aptitude interview question repository
CREATE TABLE IF NOT EXISTS question_bank (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER,
    category VARCHAR(50) NOT NULL CHECK(category IN ('Aptitude', 'Coding', 'Technical')),
    topic VARCHAR(100) NOT NULL,
    difficulty VARCHAR(20) DEFAULT 'Medium',
    question_text TEXT NOT NULL,
    expected_keywords_csv TEXT,
    test_cases_json TEXT,
    symbolic_solution TEXT,
    FOREIGN KEY(role_id) REFERENCES company_roles(role_id) ON DELETE SET NULL
);

-- Table 5: interview_sessions
-- Tracks completed student mock interview sessions and dimensional scores
CREATE TABLE IF NOT EXISTS interview_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    total_score REAL DEFAULT 0.0,
    aptitude_score REAL DEFAULT 0.0,
    coding_score REAL DEFAULT 0.0,
    technical_score REAL DEFAULT 0.0,
    composite_pri REAL DEFAULT 0.0,
    feedback_json TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(role_id) REFERENCES company_roles(role_id) ON DELETE SET NULL
);

-- Table 6: sympy_logs
-- Logs symbolic math derivations, Big-O solutions, and runtime divergence checks
CREATE TABLE IF NOT EXISTS sympy_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    operation_type VARCHAR(50) NOT NULL DEFAULT 'RECURRENCE',
    expression TEXT NOT NULL,
    result TEXT NOT NULL,
    derived_big_o VARCHAR(50),
    empirical_runtime_ms REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

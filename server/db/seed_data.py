"""
Skillora Seed Data Module (server/db/seed_data.py)
Authoritative Indian campus placement benchmark dataset and question bank.
Strictly offline, zero third-party dependencies (pure standard library).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("skillora.db.seed")

# ---------------------------------------------------------------------------
# Tiered Indian Campus Placement Matrix
# ---------------------------------------------------------------------------

COMPANIES_SEED_DATA: List[Dict[str, Any]] = [
    # --- Tier 1: Product / High CTC Firms ---
    {
        "name": "Amazon",
        "tier": "Tier1",
        "min_cgpa": 7.50,
        "max_backlogs": 0,
        "eligible_branches_csv": "CSE,IT,ECE",
        "roles": [
            {
                "role_title": "Software Development Engineer I (SDE-1)",
                "package_lpa": 28.0,
                "round_structure": {
                    "rounds": [
                        "Online Assessment (OA)",
                        "Technical Interview 1 (DSA & Problem Solving)",
                        "Technical Interview 2 (System Design & Core CS)",
                        "Bar Raiser & Leadership Principles"
                    ],
                    "weights": {
                        "aptitude": 0.15,
                        "coding": 0.55,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Microsoft",
        "tier": "Tier1",
        "min_cgpa": 8.00,
        "max_backlogs": 0,
        "eligible_branches_csv": "CSE,IT,ECE,EEE",
        "roles": [
            {
                "role_title": "Software Engineer",
                "package_lpa": 42.0,
                "round_structure": {
                    "rounds": [
                        "Online Coding Test",
                        "Technical Interview 1 (Trees & Graphs)",
                        "Technical Interview 2 (Algorithms & OS/DBMS)",
                        "System Architecture & Behavioral"
                    ],
                    "weights": {
                        "aptitude": 0.10,
                        "coding": 0.60,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Zoho Corporation",
        "tier": "Tier1",
        "min_cgpa": 6.50,
        "max_backlogs": 1,
        "eligible_branches_csv": "ALL",
        "roles": [
            {
                "role_title": "Software Developer",
                "package_lpa": 8.5,
                "round_structure": {
                    "rounds": [
                        "Round 1: General Aptitude & C/Java Debugging",
                        "Round 2: Basic Programming",
                        "Round 3: Advanced Application Design (LLD)",
                        "Round 4: Technical & HR"
                    ],
                    "weights": {
                        "aptitude": 0.20,
                        "coding": 0.50,
                        "technical": 0.30
                    }
                }
            }
        ]
    },

    # --- Tier 2: Technology Specialists & Differential Hiring ---
    {
        "name": "TCS Digital",
        "tier": "Tier2",
        "min_cgpa": 7.00,
        "max_backlogs": 0,
        "eligible_branches_csv": "CSE,IT,ECE,EEE",
        "roles": [
            {
                "role_title": "System Engineer (Digital)",
                "package_lpa": 7.5,
                "round_structure": {
                    "rounds": [
                        "Advanced Quantitative Aptitude",
                        "Advanced Coding (DSA)",
                        "Technical Interview (Core CS + Tech Stack)",
                        "Managerial & HR"
                    ],
                    "weights": {
                        "aptitude": 0.30,
                        "coding": 0.40,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Infosys Specialist Programmer",
        "tier": "Tier2",
        "min_cgpa": 7.50,
        "max_backlogs": 0,
        "eligible_branches_csv": "CSE,IT,ECE,MCA",
        "roles": [
            {
                "role_title": "Specialist Programmer (SP)",
                "package_lpa": 9.5,
                "round_structure": {
                    "rounds": [
                        "HackWithInfy / Advanced Coding Assessment",
                        "Technical Deep Dive Interview (DSA & OS/DBMS)",
                        "HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.25,
                        "coding": 0.45,
                        "technical": 0.30
                    }
                }
            },
            {
                "role_title": "Digital Specialist Engineer (DSE)",
                "package_lpa": 6.5,
                "round_structure": {
                    "rounds": [
                        "InfyTQ / Certification Exam",
                        "Hands-on Coding Round",
                        "Technical & Behavioral Interview"
                    ],
                    "weights": {
                        "aptitude": 0.30,
                        "coding": 0.40,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Cognizant",
        "tier": "Tier2",
        "min_cgpa": 6.50,
        "max_backlogs": 0,
        "eligible_branches_csv": "CSE,IT,ECE,EEE,MECH,CIVIL",
        "roles": [
            {
                "role_title": "Programmer Analyst (GenC Elevate)",
                "package_lpa": 6.5,
                "round_structure": {
                    "rounds": [
                        "Skill-Based Assessment",
                        "Technical Coding Assessment",
                        "Technical & HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.35,
                        "coding": 0.35,
                        "technical": 0.30
                    }
                }
            }
        ]
    },

    # --- Tier 3: IT Services & Mass Recruiters ---
    {
        "name": "TCS Ninja",
        "tier": "Tier3",
        "min_cgpa": 6.00,
        "max_backlogs": 1,
        "eligible_branches_csv": "ALL",
        "roles": [
            {
                "role_title": "Assistant System Engineer (Ninja)",
                "package_lpa": 3.6,
                "round_structure": {
                    "rounds": [
                        "Cognitive & Foundation Aptitude",
                        "Foundation Coding Assessment",
                        "Combined Technical & HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.45,
                        "coding": 0.25,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Infosys Ninja",
        "tier": "Tier3",
        "min_cgpa": 6.00,
        "max_backlogs": 1,
        "eligible_branches_csv": "ALL",
        "roles": [
            {
                "role_title": "Systems Engineer",
                "package_lpa": 3.6,
                "round_structure": {
                    "rounds": [
                        "Mathematical & Analytical Ability",
                        "Verbal & Pseudocode Assessment",
                        "Technical & HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.40,
                        "coding": 0.30,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Wipro Elite",
        "tier": "Tier3",
        "min_cgpa": 6.00,
        "max_backlogs": 1,
        "eligible_branches_csv": "ALL",
        "roles": [
            {
                "role_title": "Project Engineer (Elite)",
                "package_lpa": 3.5,
                "round_structure": {
                    "rounds": [
                        "Quantitative, Logical & English Aptitude",
                        "Coding Assessment (2 Problems)",
                        "Tech/HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.45,
                        "coding": 0.25,
                        "technical": 0.30
                    }
                }
            }
        ]
    },
    {
        "name": "Accenture",
        "tier": "Tier3",
        "min_cgpa": 6.50,
        "max_backlogs": 1,
        "eligible_branches_csv": "ALL",
        "roles": [
            {
                "role_title": "Associate Software Engineer (ASE)",
                "package_lpa": 4.5,
                "round_structure": {
                    "rounds": [
                        "Cognitive Assessment",
                        "Technical & Pseudocode Assessment",
                        "Coding Assessment",
                        "Communication & HR Interview"
                    ],
                    "weights": {
                        "aptitude": 0.40,
                        "coding": 0.25,
                        "technical": 0.35
                    }
                }
            }
        ]
    }
]

# ---------------------------------------------------------------------------
# Question Bank Seed Data (30 Model Technical Interview Questions)
# ---------------------------------------------------------------------------

QUESTIONS_SEED_DATA: List[Dict[str, Any]] = [
    # --- Domain 1: Data Structures & Algorithms (8 Questions) ---
    {
        "category": "Coding",
        "topic": "DSA: Linked List Reversal",
        "difficulty": "Medium",
        "question_text": "Implement an in-place iterative function to reverse a singly linked list. Explain the pointer manipulation logic, edge cases (empty list, single node), and state the time and space complexity.",
        "expected_keywords_csv": "in-place,three pointers,prev,current,next,O(1) space,O(n) time,null,head",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "While", "Assign", "Return"],
            "anti_patterns": ["recursion_depth"],
            "test_cases": [
                {"input": "[1, 2, 3, 4, 5]", "expected": "[5, 4, 3, 2, 1]"},
                {"input": "[1]", "expected": "[1]"},
                {"input": "[]", "expected": "[]"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "class ListNode:\n"
            "    def __init__(self, val=0, next=None):\n"
            "        self.val = val\n"
            "        self.next = next\n"
            "\n"
            "def reverse_list(head: ListNode) -> ListNode:\n"
            "    prev = None\n"
            "    curr = head\n"
            "    while curr:\n"
            "        next_temp = curr.next\n"
            "        curr.next = prev\n"
            "        prev = curr\n"
            "        curr = next_temp\n"
            "    return prev\n"
            "```\n"
            "\n"
            "This algorithm is defined as an in-place iterative reversal of a singly linked list using three pointers.\n"
            "- Core mechanism: We maintain three pointers (prev, current as curr, and next as next_temp) to reverse the direction of pointer links sequentially.\n"
            "- Pointer manipulation: At each step, curr.next is set to prev, flipping the pointer backwards towards head until curr reaches null.\n"
            "- Time complexity: The algorithm runs in O(N) time by performing a single linear traversal through all nodes.\n"
            "- Space complexity: The procedure operates in O(1) space with zero auxiliary node allocation."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Two Sum / Hash Map",
        "difficulty": "Easy",
        "question_text": "Given an array of integers nums and an integer target, return the 0-based indices of the two numbers such that they add up to target. You may not use the same element twice. Provide an optimal O(N) solution using a hash map.",
        "expected_keywords_csv": "hash map,dictionary,complement,O(n) time,O(n) space,lookup,indices,target",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "For", "If", "Return"],
            "test_cases": [
                {"input": "nums=[2, 7, 11, 15], target=9", "expected": "[0, 1]"},
                {"input": "nums=[3, 2, 4], target=6", "expected": "[1, 2]"},
                {"input": "nums=[3, 3], target=6", "expected": "[0, 1]"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def two_sum(nums: list[int], target: int) -> list[int]:\n"
            "    seen = {}\n"
            "    for idx, num in enumerate(nums):\n"
            "        complement = target - num\n"
            "        if complement in seen:\n"
            "            return [seen[complement], idx]\n"
            "        seen[num] = idx\n"
            "    return []\n"
            "```\n"
            "\n"
            "This algorithm is defined as an optimal single-pass hash map solution to identify two numbers matching a target sum.\n"
            "- Core mechanism: We maintain a dictionary as our hash map storing previously visited numbers and their indices.\n"
            "- Fast lookup: For each element, we calculate the required complement (target - num) and perform an instantaneous O(1) average lookup in the dictionary.\n"
            "- Time complexity: Achieves linear O(N) time complexity by processing the array in a single scan.\n"
            "- Space complexity: Requires O(N) space to maintain the lookup table for up to N elements."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Valid Parentheses Stack",
        "difficulty": "Easy",
        "question_text": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid. Brackets must close in the correct order using corresponding open brackets. Implement an O(N) stack solution.",
        "expected_keywords_csv": "stack,LIFO,push,pop,matching bracket,empty stack,O(n) time,O(n) space",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "For", "If", "Return"],
            "test_cases": [
                {"input": "s='()[]{}'", "expected": "True"},
                {"input": "s='(]'", "expected": "False"},
                {"input": "s='([)]'", "expected": "False"},
                {"input": "s='{[]}'", "expected": "True"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def is_valid_parentheses(s: str) -> bool:\n"
            "    stack = []\n"
            "    bracket_map = {')': '(', '}': '{', ']': '['}\n"
            "    for char in s:\n"
            "        if char in bracket_map:\n"
            "            top_element = stack.pop() if stack else '#'\n"
            "            if bracket_map[char] != top_element:\n"
            "                return False\n"
            "        else:\n"
            "            stack.append(char)\n"
            "    return len(stack) == 0\n"
            "```\n"
            "\n"
            "This algorithm is defined as a classic stack data structure application for verifying syntax and balanced delimiters.\n"
            "- Core mechanism: Operates using Last-In-First-Out (LIFO) discipline, where open brackets are pushed onto the stack.\n"
            "- Validation: When a closing bracket arrives, we pop the top element and verify it forms a valid matching bracket with the expected opening symbol.\n"
            "- Final state: The string is valid only if all brackets match and we end with an empty stack.\n"
            "- Time complexity: Processes each character in O(N) time with constant-time push and pop operations.\n"
            "- Space complexity: Utilizes O(N) space auxiliary storage for the stack in worst-case nesting."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Binary Search Implementation",
        "difficulty": "Easy",
        "question_text": "Implement binary search to find the index of a target element in an ascending sorted integer array. Explain how overflow is prevented when computing the midpoint, and derive its O(log N) time complexity.",
        "expected_keywords_csv": "binary search,sorted,left,right,mid,divide and conquer,O(log n),overflow,boundary",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "While", "If", "Return"],
            "test_cases": [
                {"input": "nums=[-1,0,3,5,9,12], target=9", "expected": "4"},
                {"input": "nums=[-1,0,3,5,9,12], target=2", "expected": "-1"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def binary_search(nums: list[int], target: int) -> int:\n"
            "    left, right = 0, len(nums) - 1\n"
            "    while left <= right:\n"
            "        mid = left + (right - left) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        elif nums[mid] < target:\n"
            "            left = mid + 1\n"
            "        else:\n"
            "            right = mid - 1\n"
            "    return -1\n"
            "```\n"
            "\n"
            "This algorithm is defined as a divide and conquer search procedure over a sorted integer array.\n"
            "- Core mechanism: We maintain left and right pointers defining the active search boundary.\n"
            "- Midpoint calculation: Computing mid = left + (right - left) // 2 prevents integer arithmetic overflow during index calculation.\n"
            "- Search progression: The search space is halved at every step by adjusting either left or right boundary based on target comparison.\n"
            "- Time complexity: Operates in logarithmic O(log N) time by dividing the input search space in half each iteration.\n"
            "- Space complexity: Executes in strictly O(1) space auxiliary memory."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Merge Two Sorted Arrays",
        "difficulty": "Easy",
        "question_text": "Given two sorted integer arrays arr1 and arr2, merge them into a single sorted array without modifying the inputs. Explain the two-pointer technique and its O(N + M) time complexity.",
        "expected_keywords_csv": "two pointer,merge,sorted,linear scan,O(n+m),auxiliary array",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "While", "Assign", "Return"],
            "test_cases": [
                {"input": "arr1=[1,3,5], arr2=[2,4,6]", "expected": "[1, 2, 3, 4, 5, 6]"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def merge_sorted_arrays(arr1: list[int], arr2: list[int]) -> list[int]:\n"
            "    i, j = 0, 0\n"
            "    merged = []\n"
            "    while i < len(arr1) and j < len(arr2):\n"
            "        if arr1[i] <= arr2[j]:\n"
            "            merged.append(arr1[i])\n"
            "            i += 1\n"
            "        else:\n"
            "            merged.append(arr2[j])\n"
            "            j += 1\n"
            "    merged.extend(arr1[i:])\n"
            "    merged.extend(arr2[j:])\n"
            "    return merged\n"
            "```\n"
            "\n"
            "This algorithm is defined as a two pointer linear scan technique to merge two sorted arrays into a unified sorted sequence.\n"
            "- Core mechanism: Uses two pointer indices (i and j) to simultaneously traverse both input arrays in linear scan fashion.\n"
            "- Merging logic: At each step, the smaller element is appended to the auxiliary array, preserving overall ascending order.\n"
            "- Remainder handling: Once one array is exhausted, remaining elements from the other array are appended directly.\n"
            "- Time complexity: Operates in optimal O(N + M) time proportional to the total length of both input sequences.\n"
            "- Space complexity: Requires O(N + M) space auxiliary array to store the merged result."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Cycle in Directed Graph",
        "difficulty": "Medium",
        "question_text": "Write a Python function to detect if a cycle exists in a directed graph represented as an adjacency list. Explain why a standard visited set is insufficient and how a recursion call stack tracking structure resolves it.",
        "expected_keywords_csv": "directed graph,cycle,DFS,recursion stack,visited,back edge,topological sort",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "For", "If", "Return"],
            "test_cases": [
                {"input": "graph={0: [1], 1: [2], 2: [0]}", "expected": "True"},
                {"input": "graph={0: [1], 1: [2], 2: []}", "expected": "False"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def has_cycle_directed(graph: dict[int, list[int]]) -> bool:\n"
            "    visited = set()\n"
            "    rec_stack = set()\n"
            "    def dfs(node: int) -> bool:\n"
            "        visited.add(node)\n"
            "        rec_stack.add(node)\n"
            "        for neighbor in graph.get(node, []):\n"
            "            if neighbor not in visited:\n"
            "                if dfs(neighbor):\n"
            "                    return True\n"
            "            elif neighbor in rec_stack:\n"
            "                return True\n"
            "        rec_stack.remove(node)\n"
            "        return False\n"
            "    for vertex in graph:\n"
            "        if vertex not in visited:\n"
            "            if dfs(vertex):\n"
            "                return True\n"
            "    return False\n"
            "```\n"
            "\n"
            "This algorithm is defined as a depth-first search (DFS) traversal to detect cycle existence in a directed graph.\n"
            "- Core mechanism: Standard visited set is insufficient; we maintain a dedicated recursion stack set (rec_stack) tracking ancestors in the current DFS path.\n"
            "- Cycle detection: Encountering an adjacent node already residing in rec_stack signifies a back edge, proving a cycle exists (preventing a valid topological sort).\n"
            "- Clean backtracking: Nodes are popped from the recursion stack upon returning from downstream traversal.\n"
            "- Time complexity: Runs in O(V + E) time proportional to vertices and edges explored.\n"
            "- Space complexity: Requires O(V) space auxiliary memory for visited set and recursive call stack."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Longest Substring Sliding Window",
        "difficulty": "Medium",
        "question_text": "Given a string s, find the length of the longest substring without repeating characters using the sliding window technique with a character index map in O(N) time.",
        "expected_keywords_csv": "sliding window,hash map,substring,character index,left pointer,two pointers,O(n)",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "For", "If", "Return"],
            "test_cases": [
                {"input": "s='abcabcbb'", "expected": "3"},
                {"input": "s='bbbbb'", "expected": "1"},
                {"input": "s='pwwkew'", "expected": "3"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def length_of_longest_substring(s: str) -> int:\n"
            "    char_map = {}\n"
            "    left = 0\n"
            "    max_len = 0\n"
            "    for right, char in enumerate(s):\n"
            "        if char in char_map and char_map[char] >= left:\n"
            "            left = char_map[char] + 1\n"
            "        char_map[char] = right\n"
            "        max_len = max(max_len, right - left + 1)\n"
            "    return max_len\n"
            "```\n"
            "\n"
            "This algorithm is defined as an optimal sliding window two pointers approach for finding the longest substring without duplicate characters.\n"
            "- Core mechanism: Maintains a dynamic window bounded by left pointer and right pointer, using a hash map to record each character index.\n"
            "- Window contraction: When a repeating character is discovered, the left pointer jumps directly past its previous character index.\n"
            "- Window expansion: Each right position calculates window length (right - left + 1) and updates max_len.\n"
            "- Time complexity: Evaluates the sequence in linear O(N) time because each character is processed at most twice.\n"
            "- Space complexity: Requires O(min(N, M)) space auxiliary storage where M is alphabet size."
        )
    },
    {
        "category": "Coding",
        "topic": "DSA: Invert Binary Tree",
        "difficulty": "Easy",
        "question_text": "Given the root of a binary tree, invert the tree (mirror left and right subtrees) and return its root. Explain both recursive DFS and iterative BFS approaches with complexity analysis.",
        "expected_keywords_csv": "binary tree,invert,mirror,left child,right child,swap,recursion,DFS,BFS,O(n)",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "If", "Assign", "Return"],
            "test_cases": [
                {"input": "[4,2,7,1,3,6,9]", "expected": "[4,7,2,9,6,3,1]"}
            ]
        }),
        "symbolic_solution": (
            "```python\n"
            "def invert_tree(root):\n"
            "    if not root:\n"
            "        return None\n"
            "    root.left, root.right = invert_tree(root.right), invert_tree(root.left)\n"
            "    return root\n"
            "```\n"
            "\n"
            "This algorithm is defined as a recursive tree inversion procedure that transforms a binary tree into its mirror image.\n"
            "- Core mechanism: For each node, we swap the left child and right child subtrees using post-order or pre-order recursion.\n"
            "- Traversal options: The tree can be inverted using either recursive DFS (depth-first search) or an iterative queue-based BFS (breadth-first search).\n"
            "- Base condition: Recursion terminates gracefully when encountering a null root node.\n"
            "- Time complexity: Visits every node exactly once, achieving optimal linear O(N) time complexity.\n"
            "- Space complexity: Consumes O(H) space auxiliary stack memory proportional to binary tree height H (O(N) worst-case, O(log N) balanced)."
        )
    },

    # --- Domain 2: Operating Systems (5 Questions) ---
    {
        "category": "Technical",
        "topic": "OS: Process vs Thread",
        "difficulty": "Easy",
        "question_text": "Compare a Process and a Thread in terms of address space, PCB vs TCB, resource allocation, creation overhead, and context switching latency. Why are threads called lightweight processes?",
        "expected_keywords_csv": "address space,PCB,TCB,context switch,lightweight process,shared memory,stack,registers,heap,overhead",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "A process is defined as an executing program instance with its own independent, isolated virtual address space containing text, data, heap, and stack segments, tracked by the kernel via a Process Control Block (PCB).\n"
            "- Thread architecture: A thread is a lightweight process representing an independent execution path within a parent process that shares its address space, heap, and shared memory, but retains a private Thread Control Block (TCB), program counter, registers, and execution stack.\n"
            "- Context switch overhead: Context switching between processes incurs high overhead because page tables (CR3 register) and the TLB cache must be invalidated, whereas thread context switch latency is minimal as memory mappings remain intact.\n"
            "- Time complexity and performance: Thread scheduling reduces context switch time complexity to O(1) register swaps, minimizing CPU cycle overhead compared to process creation."
        )
    },
    {
        "category": "Technical",
        "topic": "OS: Deadlocks & Prevention",
        "difficulty": "Medium",
        "question_text": "Explain what a deadlock is in an operating system. Detail the four necessary Coffman conditions that must hold simultaneously for a deadlock to occur, and describe how breaking one of them prevents deadlocks.",
        "expected_keywords_csv": "deadlock,Coffman conditions,mutual exclusion,hold and wait,no preemption,circular wait,resource allocation graph,Banker algorithm",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "A deadlock is defined as a permanent blocking state in an operating system where a set of processes are unable to proceed because each holds resources while waiting for other resources acquired by processes in the set.\n"
            "- Coffman conditions: For a deadlock to manifest, four conditions must hold simultaneously: (1) mutual exclusion (non-sharable resources), (2) hold and wait (holding resources while requesting new ones), (3) no preemption (resources cannot be forcibly taken), and (4) circular wait (a closed chain of processes waiting on each other).\n"
            "- Detection and avoidance: Systems detect cycles using a resource allocation graph and avoid deadlocks dynamically using Dijkstra's Banker algorithm to ensure states remain strictly safe.\n"
            "- Prevention strategy: Deadlocks are eliminated by breaking at least one condition, such as establishing global linear resource hierarchy order to prevent circular wait.\n"
            "- Time complexity: Cycle detection in a resource allocation graph runs in O(V + E) time, and Banker algorithm safety checks run in O(M * N^2) time complexity."
        )
    },
    {
        "category": "Technical",
        "topic": "OS: Virtual Memory & Paging",
        "difficulty": "Medium",
        "question_text": "Describe how virtual memory works using paging. Explain what happens during a page fault from hardware interrupt to disk fetch, the role of the TLB, and what causes thrashing.",
        "expected_keywords_csv": "virtual memory,paging,page fault,TLB,Translation Lookaside Buffer,page table,frame,disk swap,thrashing,working set",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Virtual memory is defined as a memory management technique that decouples process logical addresses from physical RAM using paging, dividing memory into fixed-size pages and physical frames.\n"
            "- Address translation: The CPU memory management unit consults the Translation Lookaside Buffer (TLB), a fast associative hardware cache, to translate virtual page numbers to physical frame numbers via the multi-level page table.\n"
            "- Page fault handling: If a page table entry indicates the page is not in RAM, a hardware page fault interrupt triggers the kernel to fetch the missing page from disk swap space into an available frame.\n"
            "- Thrashing phenomenon: Thrashing occurs when the collective working set of active processes exceeds physical memory, causing continuous page faults and disk swap operations where the OS spends more time paging than executing instructions.\n"
            "- Time complexity: TLB hits resolve address translation in O(1) nanosecond time complexity, whereas page faults require millisecond disk I/O."
        )
    },
    {
        "category": "Technical",
        "topic": "OS: CPU Scheduling Algorithms",
        "difficulty": "Medium",
        "question_text": "Explain the difference between preemptive and non-preemptive CPU scheduling. Compare Round Robin (RR) and Shortest Job First (SJF), highlighting how quantum size affects Round Robin performance.",
        "expected_keywords_csv": "preemptive,non-preemptive,Round Robin,time quantum,Shortest Job First,SJF,convoy effect,turnaround time,waiting time,context switch",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "CPU scheduling is defined as the operating system mechanism that allocates processor execution time among competing runnable threads using preemptive or non-preemptive strategies.\n"
            "- Non-preemptive vs preemptive: In non-preemptive scheduling, a process retains the CPU until it terminates or blocks, which risks the convoy effect in FCFS where short jobs wait behind long ones; Shortest Job First (SJF) minimizes average waiting time but requires burst prediction.\n"
            "- Round Robin mechanics: Round Robin (RR) is a preemptive algorithm where each process receives a calibrated time quantum slice before being preempted via timer interrupt.\n"
            "- Metrics and trade-offs: Scheduling efficiency is evaluated by average turnaround time, waiting time, and CPU utilization; excessively small time quantum causes context switch overhead to dominate, while excessively large quantum degrades responsiveness.\n"
            "- Time complexity: Ready queue insertions and scheduling decisions operate in O(1) time complexity per context switch."
        )
    },
    {
        "category": "Technical",
        "topic": "OS: Inter-Process Communication",
        "difficulty": "Medium",
        "question_text": "What is Inter-Process Communication (IPC)? Contrast Shared Memory and Message Passing architectures, and provide examples such as pipes, message queues, and sockets.",
        "expected_keywords_csv": "IPC,shared memory,message passing,pipes,named pipes,FIFO,message queues,sockets,synchronization,mutex",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Inter-Process Communication (IPC) is defined as the operating system architecture that allows independent processes to exchange data, coordinate tasks, and synchronize actions across memory boundaries.\n"
            "- Primary models: IPC relies on two primary paradigms: (1) shared memory, which maps a common physical memory segment into cooperating address spaces for ultra-fast data transfer but requires synchronization primitives like mutex locks and semaphores, and (2) message passing, which coordinates data via kernel-mediated abstractions.\n"
            "- Practical mechanisms: Standard implementations include anonymous pipes (unidirectional parent-child streaming), named pipes (FIFO special files for unrelated processes), message queues (structured message exchange), and network sockets for distributed communication.\n"
            "- Synchronization safety: A mutual exclusion mutex or counting semaphore prevents race conditions when accessing shared memory segments.\n"
            "- Time complexity: Shared memory operations execute with O(1) time complexity direct memory access, whereas message passing incurs kernel copy overhead."
        )
    },

    # --- Domain 3: Database Management Systems (4 Questions) ---
    {
        "category": "Technical",
        "topic": "DBMS: ACID Properties",
        "difficulty": "Medium",
        "question_text": "Define each of the ACID properties in database transactions. Explain how the DBMS guarantees Durability and Atomicity using Write-Ahead Logging (WAL).",
        "expected_keywords_csv": "ACID,atomicity,consistency,isolation,durability,WAL,Write-Ahead Logging,redo log,undo log,commit,rollback,checkpoint",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "ACID is defined as the foundational transaction management model ensuring reliable database processing across concurrent operations and unexpected hardware crashes.\n"
            "- Four pillars: (1) Atomicity guarantees all-or-nothing execution; (2) Consistency ensures transitions satisfy all schema constraints and invariants; (3) Isolation prevents concurrent transactions from observing uncommitted changes; (4) Durability ensures committed updates survive permanent hardware failure.\n"
            "- Logging and recovery: The database engine utilizes Write-Ahead Logging (WAL) where undo log and redo log records are flushed to persistent disk before dirty table pages are committed.\n"
            "- Crash recovery: During recovery, the engine inspects the latest checkpoint, rolling back uncommitted operations via undo log (rollback) and re-applying committed transactions via redo log (commit).\n"
            "- Time complexity: WAL logging appends sequentially to disk with O(1) amortized write time complexity, ensuring maximum transactional throughput."
        )
    },
    {
        "category": "Technical",
        "topic": "DBMS: Normalization Forms",
        "difficulty": "Medium",
        "question_text": "What is database normalization? Explain 1NF, 2NF, 3NF, and Boyce-Codd Normal Form (BCNF) in terms of functional dependencies, partial dependencies, and transitive dependencies.",
        "expected_keywords_csv": "normalization,1NF,2NF,3NF,BCNF,atomic values,functional dependency,partial dependency,transitive dependency,candidate key",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Database normalization is defined as the systematic decomposition of relations to minimize data redundancy and eliminate insert, update, and deletion anomalies based on functional dependency rules.\n"
            "- 1NF (First Normal Form): Requires all column attributes to hold indivisible atomic values and each row to have a unique primary identifier.\n"
            "- 2NF (Second Normal Form): Satisfies 1NF and guarantees no partial dependency exists; every non-prime attribute must depend on the whole candidate key.\n"
            "- 3NF (Third Normal Form): Satisfies 2NF and removes all transitive dependency relations where a non-prime attribute depends on another non-prime attribute (X -> Y -> Z).\n"
            "- BCNF (Boyce-Codd Normal Form): Enforces that for every non-trivial functional dependency X -> Y, the determinant X must be a superkey or candidate key.\n"
            "- Complexity and trade-offs: Normalization trades write anomaly prevention for join query time complexity, decomposing tables cleanly into 3NF/BCNF."
        )
    },
    {
        "category": "Technical",
        "topic": "DBMS: Indexing Structures",
        "difficulty": "Hard",
        "question_text": "Compare B-Trees and B+ Trees as database indexing data structures. Why do relational database engines (like MySQL InnoDB and SQLite) exclusively use B+ Trees for table indexing? Contrast clustered and secondary indexes.",
        "expected_keywords_csv": "B-Tree,B+ Tree,index,clustered index,secondary index,leaf node,linked list,range query,disk I/O,InnoDB",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Database indexing is defined as an auxiliary search data structure that optimizes query retrieval speed and minimizes expensive physical disk I/O operations.\n"
            "- B-Tree vs B+ Tree: Unlike a standard B-Tree which stores records in all levels, a B+ Tree stores data records exclusively in leaf node blocks; internal nodes store only routing keys, yielding higher fan-out, shallower tree depth, and reduced disk I/O.\n"
            "- Sequential leaf linking: All leaf node blocks in a B+ Tree are connected sequentially using a doubly linked list, enabling highly efficient range query scans without tree re-traversals.\n"
            "- Clustered vs secondary index: In storage engines like MySQL InnoDB, a clustered index physically dictates table row storage on disk ordered by the primary key, while a secondary index maps indexed values back to clustered primary keys.\n"
            "- Time complexity: Point lookups and range query searches operate with logarithmic O(log N) disk I/O access time complexity."
        )
    },
    {
        "category": "Technical",
        "topic": "DBMS: Transaction Isolation Levels",
        "difficulty": "Hard",
        "question_text": "Explain the four standard ANSI SQL transaction isolation levels: Read Uncommitted, Read Committed, Repeatable Read, and Serializable. Detail the anomalies each prevents: Dirty Read, Non-Repeatable Read, and Phantom Read.",
        "expected_keywords_csv": "isolation levels,Read Uncommitted,Read Committed,Repeatable Read,Serializable,dirty read,non-repeatable read,phantom read,MVCC,locks",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Transaction isolation levels are defined as ANSI SQL concurrency control boundaries that balance multi-user throughput against transactional read phenomena and data anomalies.\n"
            "- Isolation hierarchy: (1) Read Uncommitted permits dirty read anomalies; (2) Read Committed eliminates dirty reads by ensuring only committed writes are visible; (3) Repeatable Read prevents non-repeatable read anomalies; (4) Serializable provides total isolation, eliminating phantom read phenomena.\n"
            "- Concurrency implementation: Relational databases enforce these levels using shared/exclusive locks or Multi-Version Concurrency Control (MVCC) snapshots.\n"
            "- Anomaly prevention: MVCC provides point-in-time consistent snapshots, enabling concurrent non-blocking reads while serializable 2-phase locks eliminate phantom inserts.\n"
            "- Time complexity and overhead: Serializable isolation incurs O(N) lock contention overhead, whereas MVCC achieves O(1) lock-free read time complexity."
        )
    },

    # --- Domain 4: Computer Networks (4 Questions) ---
    {
        "category": "Technical",
        "topic": "CN: TCP Handshake & Teardown",
        "difficulty": "Medium",
        "question_text": "Explain the TCP 3-way connection establishment handshake (SYN, SYN-ACK, ACK) and the 4-way connection termination handshake (FIN, ACK, FIN, ACK). Why does connection teardown require four steps and include a TIME_WAIT state?",
        "expected_keywords_csv": "TCP,handshake,SYN,SYN-ACK,ACK,FIN,sequence number,TIME_WAIT,connection teardown,full duplex",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "TCP connection management is defined as a stateful transport protocol procedure that establishes and terminates reliable full duplex byte streams between networked hosts.\n"
            "- 3-Way handshake: Connection establishment synchronizes initial sequence number values: (1) Client sends SYN, (2) Server replies with SYN-ACK, (3) Client returns ACK, completing the handshake.\n"
            "- 4-Way connection teardown: Because TCP is full duplex, each communication direction must close independently: (1) Active closer transmits FIN, (2) Passive peer acknowledges with ACK, (3) Passive peer finishes data transfer and sends its own FIN, (4) Active closer replies with final ACK.\n"
            "- TIME_WAIT purpose: The active closer enters TIME_WAIT state (2 * MSL) to ensure the final ACK is received by the peer and lingering duplicate packets expire from the network.\n"
            "- Time complexity and latency: Handshake adds a deterministic 1 RTT latency overhead to connection setup time complexity."
        )
    },
    {
        "category": "Technical",
        "topic": "CN: OSI vs TCP/IP Layers",
        "difficulty": "Easy",
        "question_text": "Compare the 7 layers of the OSI model with the 4/5 layers of the TCP/IP protocol suite. Explain data encapsulation, decapsulation, and how PDUs (Packet Data Units) differ at each layer.",
        "expected_keywords_csv": "OSI model,TCP/IP,physical,data link,network,transport,application,encapsulation,PDU,segment,packet,frame",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Network protocol architecture is defined as a layered conceptual model that organizes end-to-end communication functions across modular network boundaries.\n"
            "- Model comparison: The theoretical OSI model defines 7 distinct layers: physical, data link, network, transport, session, presentation, and application; the pragmatic TCP/IP suite consolidates these into 4 or 5 functional layers (Network Interface, Internet, Transport, Application).\n"
            "- Protocol Data Units (PDU): Each layer defines a specialized PDU: application data, transport layer segment (TCP) or datagram (UDP), network layer packet (IP), and data link layer frame.\n"
            "- Encapsulation process: Outgoing data undergoes encapsulation where each layer prepends a protocol control header to the PDU, which is successively unwrapped during decapsulation at the destination host.\n"
            "- Time complexity: Header processing and checksum verification execute in O(1) time complexity per packet at each network hop."
        )
    },
    {
        "category": "Technical",
        "topic": "CN: DNS Resolution Pipeline",
        "difficulty": "Medium",
        "question_text": "Describe step-by-step what happens when a user types a domain name (e.g. google.com) in a web browser. Detail the roles of the local DNS cache, recursive resolver, Root DNS servers, TLD servers, Authoritative nameservers, and TTL.",
        "expected_keywords_csv": "DNS,recursive resolver,root server,TLD server,authoritative server,TTL,caching,A record,IP address,UDP port 53",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "The Domain Name System (DNS) is defined as a globally distributed hierarchical naming database that translates human-readable hostnames into machine-routable IP address values over UDP port 53.\n"
            "- Resolution hierarchy: When a client browser requests a domain, it queries the local recursive resolver, which sequentially traverses: (1) root server (returns TLD authority), (2) TLD server (returns authoritative nameserver for domain), and (3) authoritative server (returns the canonical A record).\n"
            "- Caching and TTL: Each record contains a Time-To-Live (TTL) field dictating how long resolvers and operating systems cache the IP address to reduce upstream lookup traffic.\n"
            "- Fallback and transport: Standard queries run over UDP port 53 for speed, falling back to TCP port 53 when response payload sizes exceed 512 bytes or during zone transfers.\n"
            "- Time complexity: Cached lookups resolve in O(1) memory lookup time complexity, while uncached hierarchical queries require O(1) bounded round-trip hops."
        )
    },
    {
        "category": "Technical",
        "topic": "CN: HTTP vs HTTPS & TLS",
        "difficulty": "Medium",
        "question_text": "Explain the differences between HTTP and HTTPS. Describe how TLS/SSL provides confidentiality, integrity, and authenticity. Outline the TLS handshake and how symmetric and asymmetric cryptography are combined.",
        "expected_keywords_csv": "HTTP,HTTPS,TLS,SSL,asymmetric encryption,symmetric encryption,certificate authority,CA,AES,RSA,handshake,port 443",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "HTTPS is defined as a secure communication protocol that encapsulates HTTP traffic inside a Transport Layer Security (TLS/SSL) cryptographic tunnel over port 443.\n"
            "- Security objectives: HTTPS guarantees three vital security properties: confidentiality (encryption prevents eavesdropping), data integrity (cryptographic MAC prevents tampering), and authenticity (X.509 certificates prevent spoofing).\n"
            "- Hybrid cryptography: During the TLS handshake, the client verifies the server certificate issued by a trusted Certificate Authority (CA) and uses asymmetric encryption (RSA or ECDHE) to negotiate a shared secret; once established, fast symmetric encryption (such as AES-GCM) encrypts the bulk application stream.\n"
            "- Handshake mechanics: Client and server exchange cipher suites, random nonces, and session parameters over port 443 before transmitting encrypted data.\n"
            "- Time complexity: Symmetric AES encryption achieves high-throughput O(N) stream processing time complexity with negligible latency."
        )
    },

    # --- Domain 5: Python Core (5 Questions) ---
    {
        "category": "Technical",
        "topic": "Python: GIL Mechanics",
        "difficulty": "Medium",
        "question_text": "What is the Global Interpreter Lock (GIL) in CPython? Why does it prevent CPU-bound multi-threading from achieving speedups on multi-core processors, and what architectures (multiprocessing, asyncio, C-extensions) bypass it?",
        "expected_keywords_csv": "GIL,Global Interpreter Lock,CPython,thread-safe,reference counting,CPU-bound,I/O-bound,multiprocessing,threading,concurrency",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "The Global Interpreter Lock (GIL) is defined as a mutual exclusion lock implemented in CPython to synchronize thread execution and guarantee thread-safe memory management and reference counting.\n"
            "- Execution constraint: The GIL ensures that only one native OS thread executes Python bytecode at any given instant, which prevents multi-threaded CPU-bound programs from achieving parallel speedup across multiple CPU cores.\n"
            "- I/O-bound vs CPU-bound: In I/O-bound workloads, threads release the GIL during blocking system calls (network, disk), making standard threading effective for high-concurrency I/O; for CPU-bound computations, developers must bypass the GIL using multiprocessing or native C extensions.\n"
            "- Concurrency strategies: True multi-core parallel computation is achieved by spawning isolated OS processes with independent memory spaces via Python's multiprocessing module.\n"
            "- Time complexity: GIL lock acquisition and release incur O(1) synchronization overhead per bytecode evaluation cycle."
        )
    },
    {
        "category": "Technical",
        "topic": "Python: Generators & Iterators",
        "difficulty": "Medium",
        "question_text": "Explain the Python iterator protocol (__iter__ and __next__). Contrast regular functions with generator functions using yield. Why are generators critical for memory-efficient data processing?",
        "expected_keywords_csv": "generator,iterator,yield,iter,next,StopIteration,lazy evaluation,memory efficiency,stream",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "Yield"],
            "rubric": {"keywords": 0.70, "structure": 0.30}
        }),
        "symbolic_solution": (
            "```python\n"
            "def count_up_to(max_val):\n"
            "    count = 1\n"
            "    while count <= max_val:\n"
            "        yield count\n"
            "        count += 1\n"
            "```\n"
            "\n"
            "A generator is defined as a specialized iterator function that produces a sequence of values on demand using the yield statement.\n"
            "- Iterator protocol: An iterator is an object implementing __iter__() (returning self) and __next__() (returning the next element or raising StopIteration when exhausted).\n"
            "- Lazy evaluation: A generator function suspends execution state and local frame variables at yield, resuming seamlessly when next() is called, enabling lazy evaluation of infinite streams.\n"
            "- Memory efficiency: Eliminates loading entire collections into memory, reducing memory consumption from O(N) space to O(1) auxiliary space.\n"
            "- Time complexity: Generates each successive stream element in O(1) time complexity."
        )
    },
    {
        "category": "Technical",
        "topic": "Python: Memory & Garbage Collector",
        "difficulty": "Hard",
        "question_text": "How does CPython manage memory? Detail reference counting, why it fails on cyclic references, and how Python's generational cyclic garbage collector (Generations 0, 1, 2) resolves cycles.",
        "expected_keywords_csv": "memory management,reference counting,cyclic garbage collection,generations,PyObject,ob_refcnt,gc module,weakref",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Python memory management is defined as a dual architecture combining immediate reference counting with a generational cyclic garbage collection system.\n"
            "- Reference counting: Every PyObject maintains an ob_refcnt header field incremented on assignment and decremented on deletion; memory is immediately deallocated when ob_refcnt drops to zero.\n"
            "- Cyclic reference limitation: Reference counting alone cannot detect or reclaim self-referencing cyclic garbage collection loops (e.g. obj_a.child = obj_b; obj_b.parent = obj_a), which require weakref or the cyclic collector.\n"
            "- Generational collection: The gc module manages objects across three generations (Generation 0, 1, 2) based on survival age and allocation thresholds, scanning pointer graphs to collect unreachable cyclic references.\n"
            "- Time complexity: Reference counting executes in O(1) time complexity on pointer operations, while cyclic garbage collection runs periodically in O(N) traversal time."
        )
    },
    {
        "category": "Technical",
        "topic": "Python: Decorators & Closures",
        "difficulty": "Medium",
        "question_text": "Explain how decorators work in Python as higher-order functions. Define closures and explain why @functools.wraps is necessary to preserve function metadata.",
        "expected_keywords_csv": "decorator,closure,higher-order function,functools.wraps,metadata,inner function,wrapper,docstring",
        "test_cases_json": json.dumps({
            "expected_constructs": ["FunctionDef", "Return"],
            "rubric": {"keywords": 0.70, "structure": 0.30}
        }),
        "symbolic_solution": (
            "```python\n"
            "import functools\n"
            "\n"
            "def timer_decorator(func):\n"
            "    @functools.wraps(func)\n"
            "    def wrapper(*args, **kwargs):\n"
            "        result = func(*args, **kwargs)\n"
            "        return result\n"
            "    return wrapper\n"
            "```\n"
            "\n"
            "A decorator is defined as a higher-order function that accepts a callable as an argument and returns an augmented wrapper function without modifying the original source code.\n"
            "- Closure foundation: Relies on closures where the inner function wrapper maintains access to enclosing scope variables and arguments even after the outer function has returned.\n"
            "- Metadata preservation: Using @functools.wraps on the inner wrapper function is critical to copy function metadata (__name__, docstring __doc__, annotations) from the target callable.\n"
            "- Architectural benefits: Enables clean modular separation of concerns for cross-cutting logging, authentication, caching, and rate-limiting.\n"
            "- Time complexity: Decorator wrapping adds minimal O(1) invocation overhead per decorated function execution."
        )
    },
    {
        "category": "Technical",
        "topic": "Python: MRO & Polymorphism",
        "difficulty": "Hard",
        "question_text": "Explain how Python achieves polymorphism and dynamic dispatch. In multiple inheritance, how does the C3 Linearization algorithm resolve the Diamond Problem using Method Resolution Order (__mro__)?",
        "expected_keywords_csv": "polymorphism,dynamic dispatch,duck typing,MRO,Method Resolution Order,C3 linearization,diamond problem,super,inheritance",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Polymorphism in Python is defined as the language capability to invoke common methods across heterogeneous object types through runtime dynamic dispatch and duck typing.\n"
            "- Method Resolution Order: In complex multiple inheritance hierarchies, Python resolves method lookups deterministically via the Method Resolution Order (MRO), accessible via the __mro__ attribute.\n"
            "- C3 linearization algorithm: Python utilizes C3 linearization to resolve the classic diamond problem, guaranteeing two fundamental properties: local precedence order (preserving left-to-right parent list order) and monotonicity (parent ordering is invariant across subclasses).\n"
            "- Cooperative inheritance: Subclasses invoke cooperative parent methods using super(), which dynamically traverses the linear MRO sequence rather than hardcoding parent class names.\n"
            "- Time complexity: Method lookups execute in O(1) cached dictionary lookup time complexity along the MRO list."
        )
    },

    # --- Domain 6: System Design & Software Engineering (4 Questions) ---
    {
        "category": "Technical",
        "topic": "System Design: SOLID Principles",
        "difficulty": "Medium",
        "question_text": "Explain each of the five SOLID object-oriented design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion. Give concrete engineering examples.",
        "expected_keywords_csv": "SOLID,single responsibility,open closed,Liskov substitution,interface segregation,dependency inversion,decoupling,abstraction",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "SOLID is defined as an acronym for five foundational object-oriented design principles aimed at creating maintainable, testable, and extensible software architectures.\n"
            "- Principles breakdown:\n"
            "  - Single Responsibility: Each class must have one single responsibility and reason to change.\n"
            "  - Open Closed: Modules should be open for extension but closed for modification through abstraction and polymorphism.\n"
            "  - Liskov Substitution: Subtypes must be substitutable for their base types without altering system correctness.\n"
            "  - Interface Segregation: Clients should not be forced to depend on interfaces they do not use, favoring focused fine-grained interfaces.\n"
            "  - Dependency Inversion: High-level modules should depend on abstractions rather than low-level concrete implementations, enabling decoupling.\n"
            "- Complexity and trade-offs: Adhering to SOLID minimizes regression risk and reduces cognitive maintenance complexity from O(N^2) coupling to O(1) decoupled modular interfaces."
        )
    },
    {
        "category": "Technical",
        "topic": "System Design: Scaling & Load Balancing",
        "difficulty": "Medium",
        "question_text": "Contrast Horizontal Scaling (scale-out) and Vertical Scaling (scale-up). Explain common load balancing algorithms: Round Robin, Weighted Round Robin, Least Connections, and Consistent Hashing.",
        "expected_keywords_csv": "horizontal scaling,vertical scaling,scale out,scale up,load balancer,Round Robin,least connections,consistent hashing,stateless",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "System scalability is defined as the architectural capacity of an application to gracefully handle growing workloads by adding computational resources.\n"
            "- Vertical vs horizontal: Vertical scaling (scale up) increases CPU and RAM on a single machine but hits hardware limits and single-point failures; horizontal scaling (scale out) adds independent commodity servers, requiring stateless application tiers and distributed sessions.\n"
            "- Load balancer routing: A load balancer distributes incoming client requests across backend pools using algorithms like:\n"
            "  - Round Robin: Equal cyclical distribution.\n"
            "  - Least Connections: Routes requests to the node handling fewest active connections.\n"
            "  - Consistent Hashing: Distributes requests across a hash ring, minimizing cache re-mappings when servers join or leave.\n"
            "- High availability: Health checks automatically remove degraded nodes, ensuring fault-tolerant operation and low latency.\n"
            "- Time complexity: Consistent hashing maps requests in logarithmic O(log N) lookup time complexity using binary search over the server ring."
        )
    },
    {
        "category": "Technical",
        "topic": "System Design: Caching Strategies",
        "difficulty": "Medium",
        "question_text": "Explain the four primary caching patterns: Cache-Aside (Lazy Loading), Read-Through, Write-Through, and Write-Behind (Write-Back). What are the trade-offs of each regarding latency, cache stampedes, and data consistency?",
        "expected_keywords_csv": "cache,cache-aside,read-through,write-through,write-behind,cache invalidation,TTL,cache stampede,Redis,eventual consistency",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Caching is defined as an architectural optimization that stores frequently accessed data in high-speed in-memory memory tiers (such as Redis or Memcached) to reduce database read latency.\n"
            "- Caching patterns:\n"
            "  - Cache-Aside (Lazy Loading): Application queries cache; on miss, loads from database and populates cache (resilient, but vulnerable to cache stampede).\n"
            "  - Read-Through: Cache acts as main store, transparently fetching from DB on misses.\n"
            "  - Write-Through: Synchronously writes to cache and database simultaneously (strong consistency, higher latency).\n"
            "  - Write-Behind: Asynchronously batches writes from cache to database (low latency, eventual consistency).\n"
            "- Invalidation and TTL: Cache invalidation policies utilize Time-To-Live (TTL) expiration and probabilistic early refreshing to mitigate cache stampede risk.\n"
            "- Time complexity: In-memory cache lookups operate in constant O(1) time complexity compared to disk-bound database queries."
        )
    },
    {
        "category": "Technical",
        "topic": "System Design: Monolith vs Microservices",
        "difficulty": "Medium",
        "question_text": "Compare Monolithic and Microservices architectural styles. Discuss deployment complexity, operational overhead, fault isolation, database-per-service vs shared database patterns, and network latency.",
        "expected_keywords_csv": "monolith,microservices,deployment,fault isolation,database per service,IPC,latency,distributed system,scalability",
        "test_cases_json": json.dumps({"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}}),
        "symbolic_solution": (
            "Architectural decomposition is defined as the structural strategy of organizing software capabilities into unified monolith or distributed microservices architectures.\n"
            "- Monolith characteristics: A monolith packages all business modules into a single unified deployment artifact, providing low network latency, simple debugging, and ACID database transactions, but suffering from tight coupling and deployment bottlenecks.\n"
            "- Microservices characteristics: Microservices decompose systems into autonomous, independently deployable services organized around business domains, each maintaining a private database per service pattern.\n"
            "- Trade-offs and distributed systems: Microservices provide horizontal scalability, polyglot tech stacks, and fault isolation, but introduce distributed system complexity, inter-process communication (IPC) latency, and eventual consistency requirements across network boundaries.\n"
            "- Time complexity: In-process monolithic method calls run with O(1) memory latency, whereas microservice IPC over network protocols adds O(1) bounded millisecond network latency."
        )
    }
]

# ---------------------------------------------------------------------------
# Default Demo User Seed
# ---------------------------------------------------------------------------

DEMO_USER_DATA: Dict[str, Any] = {
    "username": "demo_student",
    "password_hash": hashlib.sha256("student123".encode("utf-8")).hexdigest(),
    "full_name": "Aarav Sharma",
    "branch": "CSE",
    "cgpa": 8.45,
    "backlogs": 0,
    "skills_json": json.dumps([
        "Python",
        "Data Structures & Algorithms",
        "DBMS",
        "Operating Systems",
        "Computer Networks"
    ])
}

# ---------------------------------------------------------------------------
# Helper Seeding Functions
# ---------------------------------------------------------------------------

def _get_ph(driver: str) -> str:
    """Returns parameter placeholder based on driver ('?' for sqlite, '%s' for mysql)."""
    return "?" if driver == "sqlite" else "%s"


def seed_companies(conn: Any, driver: str = "sqlite") -> int:
    """Seeds companies and roles; returns total roles inserted."""
    ph = _get_ph(driver)
    cursor = conn.cursor()
    roles_inserted = 0

    for comp in COMPANIES_SEED_DATA:
        cursor.execute(
            f"INSERT INTO companies (name, tier, min_cgpa, max_backlogs, eligible_branches_csv) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (comp["name"], comp["tier"], comp["min_cgpa"], comp["max_backlogs"], comp["eligible_branches_csv"])
        )
        company_id = cursor.lastrowid

        for role in comp["roles"]:
            cursor.execute(
                f"INSERT INTO company_roles (company_id, role_title, package_lpa, round_structure_json) "
                f"VALUES ({ph}, {ph}, {ph}, {ph})",
                (company_id, role["role_title"], role["package_lpa"], json.dumps(role["round_structure"]))
            )
            roles_inserted += 1

    return roles_inserted


def seed_questions(conn: Any, driver: str = "sqlite") -> int:
    """Seeds question bank; returns count of questions inserted."""
    ph = _get_ph(driver)
    cursor = conn.cursor()
    count = 0

    for q in QUESTIONS_SEED_DATA:
        cursor.execute(
            f"INSERT INTO question_bank (role_id, category, topic, difficulty, question_text, expected_keywords_csv, test_cases_json, symbolic_solution) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (
                q.get("role_id"),
                q["category"],
                q["topic"],
                q.get("difficulty", "Medium"),
                q["question_text"],
                q["expected_keywords_csv"],
                q["test_cases_json"],
                q["symbolic_solution"]
            )
        )
        count += 1

    return count


def seed_users(conn: Any, driver: str = "sqlite") -> int:
    """Seeds default demo student; returns count of users inserted."""
    ph = _get_ph(driver)
    cursor = conn.cursor()

    cursor.execute(
        f"INSERT INTO users (username, password_hash, full_name, branch, cgpa, backlogs, skills_json) "
        f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
        (
            DEMO_USER_DATA["username"],
            DEMO_USER_DATA["password_hash"],
            DEMO_USER_DATA["full_name"],
            DEMO_USER_DATA["branch"],
            DEMO_USER_DATA["cgpa"],
            DEMO_USER_DATA["backlogs"],
            DEMO_USER_DATA["skills_json"]
        )
    )
    return 1


def seed_database(conn: Any, driver: str = "sqlite") -> Dict[str, int]:
    """
    Executes complete seed routine inside current transaction.
    Returns counts of inserted entities.
    """
    roles_count = seed_companies(conn, driver)
    questions_count = seed_questions(conn, driver)
    users_count = seed_users(conn, driver)
    return {
        "companies": len(COMPANIES_SEED_DATA),
        "roles": roles_count,
        "questions": questions_count,
        "users": users_count
    }

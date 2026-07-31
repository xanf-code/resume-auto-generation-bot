"""Hardcoded project vault for the resume pipeline.

The project_selector node scores these against each incoming JD and picks
the top 2. Context is the sole input for relevance scoring and bullet
generation — no tags, no pre-filtering.
"""
from __future__ import annotations

PROJECTS: list[dict] = [
    {
        "id": "hirefeed",
        "context": (
            "Built a real-time job aggregation platform that pulls listings from LinkedIn, "
            "Indeed, and other portals using WebSockets for split-second delivery. Proxy "
            "rotation and headless browser scraping handle anti-bot measures. An AI layer "
            "flattens all extracted text — regardless of source format — into a normalized "
            "JSON schema. Users can add custom company-specific job portal URLs and the "
            "system scrapes them on configurable intervals, converting raw HTML and PDF "
            "extractions into structured JSON via an LLM pipeline."
        ),
        "link": "https://goonedin.xyz/",
    },
    {
        "id": "spendai",
        "context": (
            "Built an AI-powered personal finance platform with multiple financial modules: "
            "a wealth management module that builds interactive wealth trees and graphs, "
            "an AI-driven PII detection and elimination layer that scans uploaded financial "
            "documents and redacts sensitive data before storage, a sanctions screening "
            "module that scrapes real-time sanctions lists from OFAC and other sources and "
            "automatically blocks transactions to flagged parties, and a financial audit "
            "module for transaction traceability and compliance reporting."
        ),
        "link": "https://github.com/darshan-aswathappa/spend-analyzer",
    },
    {
        "id": "neu-advisor",
        "context": (
            "Built a personalized academic advisor for Northeastern University students who "
            "struggle to select courses from a large catalog each semester. Students upload "
            "their resume and set preferences (time slots, days, credit load) and the system "
            "recommends the most career-relevant courses using vector similarity search over "
            "course metadata. An integrated chatbot lets students ask follow-up questions "
            "about professor teaching history, course syllabus, workload, and how the course "
            "maps to their career goals — all powered by RAG over structured and unstructured "
            "academic data."
        ),
        "link": "https://github.com/darshan-aswathappa/cousre-recommendation-system-backend",
    },
    {
        "id": "bettercal",
        "context": (
            "Built BetterCal, an AI library management system for Northeastern University "
            "that uses historical library occupancy data to predict crowd levels and business "
            "patterns throughout the day. Students can book study rooms with a single click "
            "based on real-time availability predictions and join waitlists for rooms during "
            "peak periods like finals week. The prediction model surfaces low-traffic windows "
            "and high-demand hotspots to help students plan study sessions efficiently."
        ),
        "link": "https://github.com/darshan-aswathappa/bettercal",
    },
]

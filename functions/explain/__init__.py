"""
Explanation generation module for trading alerts.

This module provides template-based, deterministic explanation generation
for trading alerts without requiring LLM calls. Each detector type has
dedicated explanation logic that enriches AlertCandidate objects with
comprehensive context for dashboards and trading decisions.

Main Components:
    - ExplanationGenerator: Template-based explanation engine
    - Detector-specific helpers: Low IV, Rich Premium, Earnings, Term Structure, Skew, Regime

Usage:
    from functions.explain.template_explain import ExplanationGenerator
    from functions.config.models import AppConfig

    gen = ExplanationGenerator(config)
    explanation = gen.generate_explanation(alert, ticker, features)
"""

from functions.explain.template_explain import ExplanationGenerator

__all__ = ["ExplanationGenerator"]

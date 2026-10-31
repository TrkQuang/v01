"""
Unit tests for Account Eligibility Evaluation.
"""

import pytest
from promotion_diagnostics import DiagnosticResultCode, promotion_diagnostic_engine


def test_workspace_account_rejected():
    finding = promotion_diagnostic_engine._check_account_eligibility(
        account_email="admin@school.edu",
        is_workspace=True,
        in_family_group=False,
        has_active_sub=False,
    )
    assert finding.passed is False
    assert finding.result_code == DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE
    assert "Workspace" in finding.explanation


def test_family_group_rejected():
    finding = promotion_diagnostic_engine._check_account_eligibility(
        account_email="user@gmail.com",
        is_workspace=False,
        in_family_group=True,
        has_active_sub=False,
    )
    assert finding.passed is False
    assert finding.result_code == DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE
    assert "Family" in finding.explanation


def test_active_subscription_conflict():
    finding = promotion_diagnostic_engine._check_account_eligibility(
        account_email="user@gmail.com",
        is_workspace=False,
        in_family_group=False,
        has_active_sub=True,
    )
    assert finding.passed is False
    assert finding.result_code == DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE


def test_personal_clean_account_eligible():
    finding = promotion_diagnostic_engine._check_account_eligibility(
        account_email="user@gmail.com",
        is_workspace=False,
        in_family_group=False,
        has_active_sub=False,
    )
    assert finding.passed is True
    assert finding.result_code == DiagnosticResultCode.OFFER_VISIBLE

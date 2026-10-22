"""Workflow emails are scheduled explicitly by services.transition on commit.

Ordinary model saves, draft edits and administrative changes never send mail.
"""

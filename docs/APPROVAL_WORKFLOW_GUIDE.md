# RFPO Approval Workflow Guide

## How It Works

When someone submits a Request for Purchase Order (RFPO), it doesn't get approved all at once. Instead, it moves through a series of approval stages — like a relay race where each runner must finish before the next one starts.

There are two layers of approval:

1. **Entity Approval** — The team or group that owns the RFPO reviews it first.
2. **Global Approval** — Company-wide reviewers (Finance, USCAR Internal, and P.O. Release) review it after the entity approves.

---

## The Two Layers Explained

### Layer 1: Entity Approval

Every RFPO belongs to a consortium, team, or project. The system looks for an approval workflow tied to that entity, checking in this order:

1. **Project** — Does this specific project have its own approval workflow?
2. **Team** — If not, does the team have one?
3. **Consortium** — If not, does the consortium have one?

The system uses the first match it finds. Think of it like checking your mailbox, then the front desk, then the post office — you stop as soon as you find your mail.

Within the entity approval, the RFPO's dollar amount determines which **budget bracket** applies. A $3,000 RFPO might only need one approver, while a $50,000 RFPO might need three people to sign off.

### Layer 2: Global Approval

After the entity approves, the RFPO moves through three company-wide stages — always in this order:

| Order | Stage | Who Reviews | Purpose |
|-------|-------|-------------|---------|
| 1 | **Financial Approvers** | Finance representatives from each OEM (Stellantis, Ford, GM) | Verify the purchase is financially sound and within budget |
| 2 | **USCAR Internal Approval** | USCAR operations staff | Confirm the purchase aligns with USCAR's internal policies |
| 3 | **P.O. Release Approval** | External accounting/audit firm | Final sign-off to release the actual purchase order |

---

## Sequential Stages, Parallel Steps

Two important rules govern how approvals flow:

1. **Between stages: Sequential.** The Financial stage must be fully complete before USCAR Internal sees the RFPO, and USCAR must be complete before P.O. Release sees it.
2. **Within a global stage: Parallel.** All approvers in the same stage see the RFPO at the same time and can approve in any order.

For example, in the Financial stage:
- Diana Zielonka, Gabriela Grajales, and George Faux all receive the RFPO simultaneously.
- They can approve in any order — Diana first, then George, then Gabriela, or any combination.
- The RFPO only moves to USCAR Internal once **all three** have approved.

If someone refuses at any point, the entire RFPO is sent back — later stages never get involved.

Entity approval stages follow sequential step-by-step ordering (based on the workflow's configuration).

---

## Real-World Example

> **Scenario:** The Lightweight Materials team submits an RFPO for $12,000 worth of aluminum test specimens from Vendor "MetalWorks Inc."

### Step 1: Entity Approval

The system checks:
- Does the "Lightweight Materials" **project** have an approval workflow? **No.**
- Does the **team** have one? **No.**
- Does the **USCAR consortium** have one? **Yes** — and the $12,000 amount falls into the "Up to $25,000" budget bracket, which requires two approvers.

The RFPO appears in **Approver A's** queue (the team's technical lead). They review and approve. Now it moves to **Approver B** (the consortium program manager). They also approve.

Entity approval is complete.

### Step 2: Financial Approval

The RFPO now appears in the queues of **all three** financial approvers simultaneously: **Diana Zielonka** (Stellantis), **Gabriela Grajales** (Ford), and **George Faux** (GM). They can review and approve in any order. The stage is complete once all three have approved.

### Step 3: USCAR Internal Approval

**Chuck Gough** now sees the RFPO in his queue. He confirms it aligns with USCAR policies and approves.

### Step 4: P.O. Release

**Karin Darovitz** (from the accounting firm Doeren Mayhew) performs the final review and releases the purchase order.

### Result

The RFPO is fully approved. A purchase order is generated and sent to MetalWorks Inc. The entire approval chain is recorded with timestamps, comments, and the identity of each approver.

---

## What Happens When Someone Is Unavailable?

Each approver has a designated **backup approver**. If the primary approver is out of office or unresponsive, the backup can step in and take action on their behalf. The system tracks whether the primary or backup took the action.

| Stage | Primary Approver | Backup Approver |
|-------|-----------------|-----------------|
| Financial | Diana Zielonka | David Pollock |
| Financial | Gabriela Grajales | Cynthia Flanigan |
| Financial | George Faux | Paul Krajewski |
| USCAR Internal | Chuck Gough | Steve Przesmitzki |
| P.O. Release | Karin Darovitz | Nadette Bullington |

---

## What Happens When Someone Refuses?

If any approver at any stage refuses the RFPO, the process stops immediately. The RFPO is marked as **Refused**, and the submitter is notified with the reason. No downstream approvers are bothered.

### Can a Refused RFPO Be Resubmitted?

**Yes.** A refused RFPO is unlocked for editing — the submitter (or an admin) can revise line items, amounts, vendors, or any other details. Once corrected, an admin can resubmit the RFPO for approval, which:

1. Deletes the old refused workflow instance
2. Creates a brand-new workflow starting from the beginning (entity approval → global approval)
3. All approvers must review the revised RFPO fresh — no prior approvals carry over

---

## Summary

```
RFPO Submitted
    │
    ▼
┌─────────────────────────┐
│  Entity Approval        │  (Project → Team → Consortium)
│  Based on $ amount      │  Each step must approve before the next
└─────────┬───────────────┘
          │ All approved
          ▼
┌─────────────────────────┐
│  Financial Approval     │  Diana, Gabriela, George
│  (3 OEM finance reps)   │  Parallel — all see it at once
└─────────┬───────────────┘
          │ All approved
          ▼
┌─────────────────────────┐
│  USCAR Internal         │  Chuck Gough
│  (Policy compliance)    │
└─────────┬───────────────┘
          │ Approved
          ▼
┌─────────────────────────┐
│  P.O. Release           │  Karin Darovitz
│  (Final sign-off)       │
└─────────┬───────────────┘
          │ Approved
          ▼
    ✅ Purchase Order Released
```

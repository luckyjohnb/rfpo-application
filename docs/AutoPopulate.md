# RFPO Field Auto-Population & Default Logic

This document details how fields are populated across the RFPO application, highlighting differences between the Admin Panel (web interface) and the API, as well as database-level defaults.

## 1. Admin Panel (`custom_admin.py`)

The Admin Panel includes logic to pre-fill forms for the user and apply fallback values when saving.

### Stage 2 Creation (`rfpo_stage2`) - Form Pre-filling
When the user views the form, these values are pre-calculated to safe user time:

| Field | Pre-filled Value | Logic / Fallback |
| :--- | :--- | :--- |
| **Ship to Name** | User's Name | `current_user.get_display_name()` |
| **Requestor Phone** | User's Phone | `current_user.phone` |
| **Requestor Location** | User's Location | `"{company}, {state}"` (Default: "USCAR, MI") |
| **Ship to Address** | Consortium Invoice Address | `consortium.invoicing_address` **OR** User's Location |
| **Ship to Phone** | **None** | Left blank for manual entry |

### Stage 2 Creation - Save Logic
When the form is submitted (`POST`), the following logic is applied:

| Field | Population Logic |
| :--- | :--- |
| **RFPO ID** | **Auto-Generated:** `RFPO-{ProjectRef}-{Date}-N{Sequence}` (e.g., `RFPO-PROJ-2026-02-04-N01`) |
| **Requestor ID** | `current_user.record_id` |
| **Requestor Phone** | Form Input **OR** `current_user.phone` |
| **Requestor Location** | Form Input **OR** `"{company}, {state}"` (Default: "USCAR, MI") |
| **Invoice Address** | `consortium.invoicing_address` **OR** Hardcoded USCAR Southfield Address |
| **Payment Terms** | Form Input **OR** "Net 30" |
| **Ship To Address** | Form Input | Pre-filled from Consortium Invoice Address in GET request |
| **Created By** | `current_user.get_display_name()` |
| **Team** | Form Input **OR** Auto-created "Default Team" if missing |

## 2. API (`simple_api.py`)

The API follows strict input validation and applies defaults mainly where required data is missing.

### Creation (`POST /api/rfpos`)

| Field | Population Logic | Notes |
| :--- | :--- | :--- |
| **RFPO ID** | **Auto-Generated:** `RFPO-{ProjectRef}-{Date}-N{Sequence}` | Same logic as Admin Panel |
| **Requestor ID** | `request.current_user.record_id` | Enforced strict ownership |
| **Created By** | `request.current_user.get_display_name()` | |
| **Invoice Address** | `consortium.invoicing_address` | **Only** if consortium exists. Does **NOT** fallback to hardcoded USCAR address. |
| **Payment Terms** | Payload **OR** "Net 30" | |
| **Cost Share Type** | Payload **OR** "total" | |
| **Status** | Payload **OR** "Draft" | |
| **Shipping/Requestor Info** | **NO AUTO-POPULATION** | Unlike Admin Panel, `shipto_name`, `shipto_address`, etc. are NOT filled from user profile. |

## 3. Database Defaults (`models.py`)

Even if application logic fails to set a value, the database model (`SQLAlchemy`) enforces the following defaults upon insertion:

| Field | Default Value |
| :--- | :--- |
| `status` | `"Draft"` |
| `payment_terms` | `"Net 30"` |
| `subtotal` | `0.00` |
| `cost_share_type` | `"total"` |
| `cost_share_amount` | `0.00` |
| `total_amount` | `0.00` |
| `created_at` | `datetime.utcnow` |
| `updated_at` | `datetime.utcnow` (updates on modification) |
| `active` | `True` (Consortium/Team models) |

## Summary of Differences

1.  **User Profile Data**: The **Admin Panel** uses the user's profile to fill in Requestor fields. For **Ship To Address**, it prioritizes the **Consortium's Invoicing Address**, falling back to the user's location only if missing. The **API** does not auto-populate these fields.
2.  **Invoice Address**: The **Admin Panel** has a hardcoded fallback address for USCAR. The **API** only falls back to the Consortium's invoice address.
3.  **Team Assignment**: The **Admin Panel** will auto-create a "Default Team" if the selected Project has no team. The API creates the RFPO but does not seem to include this "auto-create team" logic (it validates `team_id` exists).

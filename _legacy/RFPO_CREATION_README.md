# RFPO Creation System

This document describes the enhanced RFPO (Request for Purchase Order) creation system that implements the multi-step workflow from the original frontend.

## 🚀 Quick Start

### Using the Command Line Scripts

#### 1. Demo RFPO Creation
```bash
python demo_create_rfpo.py
```
This creates a demonstration RFPO with sample data using the `casahome2000@gmail.com` user.

#### 2. Interactive RFPO Creation
```bash
python create_rfpo_quick.py
```
This provides a full interactive command-line interface for creating RFPOs step by step.

### Using the Web Interface

1. Start the admin panel:
```bash
python custom_admin.py
```

2. Navigate to `http://localhost:5111/rfpo/new`

3. Follow the multi-step process:
   - **Stage 1**: Select Consortium and Project
   - **Stage 2**: Enter basic information, shipping details, and optional vendor selection
   - **Stage 3**: Add line items with quantities, prices, and capital equipment details
   - **Stage 4**: Review and submit

## 📊 Enhanced RFPO Model

The RFPO model has been significantly enhanced to match the original frontend workflow:

### Core RFPO Fields
- `rfpo_id`: Auto-generated ID (e.g., "RFPO-TestProj3-2025-08-24-N01")
- `title`: Brief description of the purchase
- `description`: Detailed description
- `project_id`: Associated project ID
- `consortium_id`: Associated consortium ID
- `team_id`: Associated team ID

### Requestor Information
- `requestor_id`: User ID of the person creating the RFPO
- `requestor_tel`: Phone number
- `requestor_location`: Location/address

### Shipping & Delivery
- `shipto_name`: Ship-to contact name
- `shipto_tel`: Ship-to phone
- `shipto_address`: Ship-to address
- `invoice_address`: Billing address
- `delivery_date`: Expected delivery date
- `delivery_type`: FOB terms (Seller's Plant/Destination)
- `delivery_payment`: Payment method (Collect/Prepaid)
- `delivery_routing`: Routing preference (Buyer's/Seller's traffic)
- `payment_terms`: Payment terms (Net 30, etc.)

### Vendor Information
- `vendor_id`: Selected vendor (optional)
- `vendor_site_id`: Specific vendor contact/site

### Financial Information
- `subtotal`: Sum of all line items
- `cost_share_description`: Description of vendor cost sharing
- `cost_share_type`: Type of cost sharing (total dollars/percentage)
- `cost_share_amount`: Amount of vendor contribution
- `total_amount`: Final amount after cost sharing

## 📝 Line Items System

### RFPOLineItem Model
Each RFPO can have multiple line items with:

- `line_number`: Sequential number (1, 2, 3...)
- `quantity`: Number of items
- `description`: Item description
- `unit_price`: Price per unit
- `total_price`: Calculated total (quantity × unit_price)

### Capital Equipment Tracking
When `is_capital_equipment` is true, additional fields are available:
- `capital_description`: Equipment description
- `capital_serial_id`: Serial/ID number
- `capital_location`: Physical location
- `capital_acquisition_date`: Date acquired
- `capital_condition`: Equipment condition
- `capital_acquisition_cost`: Original cost

## 🌐 Web Interface Features

### Multi-Step Creation Process

#### Stage 1: Consortium & Project Selection
- Dynamic project loading based on consortium selection
- Project details display with flags (Government Funded, University Project)
- Input validation and progress tracking

#### Stage 2: Basic Information & Vendor Selection
- Auto-populated requestor information from current user
- Comprehensive shipping and delivery options
- Optional vendor selection with dynamic site loading
- Default invoice address from consortium settings

#### Stage 3: Line Items Management
- Add/remove line items dynamically
- Capital equipment tracking
- Real-time total calculations
- Cost sharing configuration

### RFPO Editing Interface
- Tabbed interface for different sections:
  - Line Items with add/delete functionality
  - Basic Information editing
  - Shipping & Delivery configuration
  - Vendor Information management

## 🔧 API Endpoints

### New API Routes
- `GET /api/projects/<consortium_id>`: Get projects for a consortium
- `GET /api/vendor-sites/<vendor_id>`: Get sites for a vendor
- `POST /rfpo/<rfpo_id>/line-item/add`: Add line item to RFPO
- `POST /rfpo/<rfpo_id>/line-item/<line_item_id>/delete`: Delete line item

### RFPO Creation Routes
- `GET /rfpo/create/stage1`: Consortium and project selection
- `POST /rfpo/create/stage1`: Process stage 1 selections
- `GET /rfpo/create/stage2`: Basic information and vendor selection
- `POST /rfpo/create/stage2`: Create RFPO and redirect to editing

## 📋 Usage Examples

### Creating a Demo RFPO
```python
from demo_create_rfpo import create_demo_rfpo
from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfpo_admin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    demo_rfpo = create_demo_rfpo()
    if demo_rfpo:
        print(f"Created demo RFPO: {demo_rfpo.rfpo_id}")
```

### Adding Line Items Programmatically
```python
from models import RFPOLineItem
from decimal import Decimal

# Create a line item
line_item = RFPOLineItem(
    rfpo_id=rfpo.id,
    line_number=1,
    quantity=2,
    description="Software licenses for project management",
    unit_price=Decimal('500.00')
)
line_item.calculate_total()  # Sets total_price to 1000.00

# Add capital equipment details if needed
line_item.is_capital_equipment = True
line_item.capital_description = "Project management software"
line_item.capital_location = "USCAR Office"

db.session.add(line_item)
db.session.commit()
```

## 🎯 Key Features Implemented

### ✅ Completed Features
- Enhanced RFPO model with all required fields
- Multi-step web creation process
- Line items management with capital equipment tracking
- Command-line creation scripts
- Dynamic project/vendor loading
- Financial calculations with cost sharing
- Comprehensive edit interface

### 🔄 Pending Features
- Document upload functionality for attachments
- Approval workflow tracking
- Email notifications for approvals
- Advanced reporting and analytics

## 🛠️ Technical Notes

### Database Changes
The RFPO model has been significantly expanded. Run database migrations or recreate the database to use the new schema:

```python
from models import db
db.drop_all()
db.create_all()
```

### Dependencies
- Flask
- SQLAlchemy
- Werkzeug
- Decimal (for precise financial calculations)

### File Structure
```
templates/admin/
├── rfpo_stage1.html    # Consortium & project selection
├── rfpo_stage2.html    # Basic information & vendor selection
└── rfpo_edit.html      # Comprehensive RFPO editing interface

models.py               # Enhanced RFPO and RFPOLineItem models
custom_admin.py         # Web interface routes and logic
create_rfpo_quick.py    # Interactive command-line creation
demo_create_rfpo.py     # Demo RFPO creation script
```

## 📞 Support

The RFPO creation system is designed to match the workflow described in the original frontend forms while providing a modern, user-friendly interface. The system supports the complete RFPO lifecycle from creation through line item management and vendor selection.

For questions or issues, refer to the code comments or the model definitions in `models.py`.

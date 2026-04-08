#!/usr/bin/env python3
"""
PROVE 5% ACCURACY WITH CORRECTED COORDINATE CONVERSION
This test must pass with <5% difference to prove the fix works
"""
import time
import requests
import json


def test_prove_5_percent_accuracy():
    """Test the corrected coordinate conversion for 5% accuracy"""
    print("🎯 PROVING 5% ACCURACY WITH CORRECTED COORDINATE CONVERSION")
    print("=" * 80)

    # STEP 1: Calculate expected accuracy with corrected conversion
    print("📐 STEP 1: Calculate expected positioning accuracy...")

    # Test coordinates (same as before)
    canvas_x = 450
    canvas_y = 100

    # Canvas dimensions (from test data)
    canvas_width = 827.0
    canvas_height = 1070.2

    # PDF dimensions
    pdf_width = 612
    pdf_height = 792

    # Calculate relative position in designer
    designer_rel_x = (canvas_x / canvas_width) * 100
    designer_rel_y = (canvas_y / canvas_height) * 100

    print(f"   Canvas position: ({canvas_x}, {canvas_y})")
    print(f"   Canvas dimensions: {canvas_width} x {canvas_height}")
    print(f"   Designer relative: ({designer_rel_x:.2f}%, {designer_rel_y:.2f}%)")

    # Calculate corrected PDF position with proper scaling
    scale_x = pdf_width / canvas_width
    scale_y = pdf_height / canvas_height

    scaled_x = canvas_x * scale_x
    scaled_y = pdf_height - (canvas_y * scale_y)  # Scale then flip Y axis

    # Calculate relative position in PDF
    # Note: PDF Y coordinates have origin at bottom, so we need to convert to "from top"
    pdf_rel_x = (scaled_x / pdf_width) * 100
    pdf_rel_y_from_bottom = (scaled_y / pdf_height) * 100
    pdf_rel_y = 100 - pdf_rel_y_from_bottom  # Convert to "from top" to match designer

    print(f"   Scale factors: X={scale_x:.4f}, Y={scale_y:.4f}")
    print(f"   Corrected PDF position: ({scaled_x:.1f}, {scaled_y:.1f})")
    print(f"   PDF relative: ({pdf_rel_x:.2f}%, {pdf_rel_y:.2f}%)")

    # Calculate accuracy difference
    x_diff = abs(designer_rel_x - pdf_rel_x)
    y_diff = abs(designer_rel_y - pdf_rel_y)

    print(f"   Position differences:")
    print(f"      X difference: {x_diff:.2f}%")
    print(f"      Y difference: {y_diff:.2f}%")

    # STEP 2: Test if this meets 5% accuracy
    accuracy_threshold = 5.0
    theoretical_accuracy = x_diff <= accuracy_threshold and y_diff <= accuracy_threshold

    print(f"\n📊 THEORETICAL ACCURACY TEST:")
    if theoretical_accuracy:
        print(
            f"   ✅ Theoretical accuracy PASSED (both differences ≤ {accuracy_threshold}%)"
        )
    else:
        print(f"   ❌ Theoretical accuracy FAILED:")
        if x_diff > accuracy_threshold:
            print(f"      X difference {x_diff:.2f}% > {accuracy_threshold}%")
        if y_diff > accuracy_threshold:
            print(f"      Y difference {y_diff:.2f}% > {accuracy_threshold}%")
        return False

    # STEP 3: Test with real PDF generation
    print(f"\n📋 STEP 2: Test with real PDF generation...")

    # Login and save test data
    session = requests.Session()
    login_data = {"email": "admin@rfpo.com", "password": "admin123"}
    login_response = session.post("http://localhost:5111/login", data=login_data)

    if login_response.status_code != 200:
        print("   ❌ Login failed")
        return False

    # Save test positioning data
    test_data = {
        "positioning_data": {
            "accuracy_test": {
                "x": canvas_x,
                "y": canvas_y,
                "font_size": 16,
                "font_weight": "bold",
                "visible": True,
            }
        }
    }

    save_response = session.post(
        "http://localhost:5111/api/pdf-positioning/1",
        json=test_data,
        headers={"Content-Type": "application/json"},
    )

    if save_response.status_code == 200 and save_response.json().get("success"):
        print("   ✅ Test data saved to database")
    else:
        print(f"   ❌ Save failed: {save_response.text}")
        return False

    # STEP 4: Test PDF generation with debug output
    print(f"\n📋 STEP 3: Generate PDF and check coordinate conversion...")

    # Use the debug script to test PDF generation
    import sys
    import os

    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    from custom_admin import create_app
    from models import PDFPositioning, RFPO, Consortium, Project, Vendor
    from pdf_generator import RFPOPDFGenerator

    app = create_app()

    with app.app_context():
        # Get positioning config
        config = PDFPositioning.query.get(1)
        positioning_data = config.get_positioning_data()

        if "accuracy_test" not in positioning_data:
            print("   ❌ Test field not found in database")
            return False

        field_data = positioning_data["accuracy_test"]
        print(
            f"   ✅ Test field in database: x={field_data['x']}, y={field_data['y']}, visible={field_data['visible']}"
        )

        # Test PDF generation
        try:
            pdf_generator = RFPOPDFGenerator(positioning_config=config)

            # Test the position calculation directly
            result = pdf_generator._get_field_position("accuracy_test", 0, 0)

            if result[0] is None:
                print("   ❌ Field position calculation returned None")
                return False

            actual_pdf_x, actual_pdf_y, font_size, font_weight = result
            print(
                f"   ✅ PDF generator calculated position: ({actual_pdf_x:.1f}, {actual_pdf_y:.1f})"
            )

            # Compare with expected
            expected_x = scaled_x
            expected_y = scaled_y

            x_error = abs(actual_pdf_x - expected_x)
            y_error = abs(actual_pdf_y - expected_y)

            print(f"   Expected: ({expected_x:.1f}, {expected_y:.1f})")
            print(f"   Actual:   ({actual_pdf_x:.1f}, {actual_pdf_y:.1f})")
            print(f"   Errors:   X={x_error:.1f}, Y={y_error:.1f}")

            if x_error < 1 and y_error < 1:
                print(f"   ✅ PDF generation uses correct coordinates")
            else:
                print(f"   ❌ PDF generation coordinate error too high")
                return False

        except Exception as e:
            print(f"   ❌ PDF generation error: {e}")
            return False

    # STEP 5: Final validation
    print(f"\n🎯 FINAL ACCURACY VALIDATION:")
    print(
        f"   Theoretical accuracy: {'✅ PASS' if theoretical_accuracy else '❌ FAIL'}"
    )
    print(f"   PDF generation accuracy: ✅ PASS")
    print(
        f"   Position differences: X={x_diff:.2f}%, Y={y_diff:.2f}% (both ≤ {accuracy_threshold}%)"
    )

    return True


if __name__ == "__main__":
    success = test_prove_5_percent_accuracy()
    print(f"\n" + "=" * 80)
    if success:
        print(f"🏆 5% ACCURACY: ACHIEVED ✅")
        print(f"   Coordinate conversion fixed and proven accurate!")
    else:
        print(f"🔥 5% ACCURACY: NOT ACHIEVED ❌")
        print(f"   Coordinate conversion still needs work!")
    print(f"=" * 80)

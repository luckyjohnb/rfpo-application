# Manual Coordinate Fix Test

## Steps to Test the Coordinate Fix:

1. **Open the positioning editor**: http://localhost:5111/pdf-positioning/editor/00000014/po_template

2. **Open browser developer console** (F12) to see coordinate debug output

3. **Clear the canvas** (if there are existing elements)

4. **Add a field**:
   - Click on any field in the sidebar (e.g., "Purchase Order Number")
   - Click somewhere on the canvas to place it

5. **Test coordinate consistency**:
   
   **Before fix**: You would see coordinates jump by 80-100px when stopping drag or pressing ESC
   
   **After fix**: Coordinates should remain consistent
   
   a. **Click and drag the field** - watch the coordinates display
   b. **Release the mouse** - coordinates should NOT jump dramatically
   c. **Press ESC key** - coordinates should NOT change
   
6. **Check console output**:
   - Look for "Raw pixel coordinates from style:"
   - Look for "Current scale factors:"
   - Look for "Converted to PDF coordinates:"
   
   The conversion should be consistent and not cause large jumps.

## Expected Results:

- ✅ Coordinates displayed should be stable (no 80-100px jumps)
- ✅ Dragging should show smooth coordinate changes
- ✅ Releasing mouse should maintain same coordinates
- ✅ ESC key should not change coordinates
- ✅ Console should show proper coordinate conversion

## Key Fix Applied:

The coordinates are now properly converted between:
- **Responsive canvas coordinates** (what you see during drag)
- **Fixed PDF coordinates** (612x792, what gets saved)

This ensures consistent coordinate handling throughout the drag operation.

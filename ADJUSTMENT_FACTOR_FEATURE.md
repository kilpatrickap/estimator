# Adjustment Factor Feature - Rate Build-up Dialog

## Overview
The Adjustment Factor feature has been added to the Rate Build-up Details window, allowing users to apply a multiplier to all cost items globally. This is useful for applying contingencies, risk factors, location adjustments, or other blanket cost modifications.

## Features Implemented

### 1. **New "Adjusted Cost" Column**
- Added between the "Cost" column and "Net Rate" column
- Displays: `Cost × Adjustment Factor` for each item
- Uses the same currency formatting as the Cost column (2 decimals, thousand separators)

### 2. **Adjustment Factor Input**
- **Location**: Toolbar, right side of the "Exchange Rates" button
- **Label**: "Adjustment factor:"
- **Default Value**: 1.0 (no adjustment)
- **Format**: Displays with 4 decimal places for precision
- **Styling**: Consolas monospace font, bold, right-aligned

### 3. **Formula Input Dialog**
- **Activation**: Double-click on the adjustment factor text input
- **Functionality**: Opens the same formula editor used for editing resources
- **Features**:
  - Full formula support (e.g., `= 1.15` or `= 1.0 + 10%` or `= (100 + 15) / 100`)
  - Inline comments with double quotes
  - Multi-line formulas with summation
  - Real-time calculation preview
- **Buttons**: "Apply" (saves and updates) and "Cancel"

### 4. **Direct Input**
- Users can type a numeric value directly into the input field
- Press Enter or click away to apply the value
- Invalid inputs are rejected and reset to the previous valid value

### 5. **Updated Calculations**

#### Item Level:
```
Adjusted Cost = Base Cost × Adjustment Factor
```

#### Task Level:
```
Adjusted Task Total = Sum(All Item Adjusted Costs)
```

#### Summary/Net Rate:
```
Adjusted Subtotal = Subtotal × Adjustment Factor
Adjusted Overhead = Adjusted Subtotal × Overhead %
Adjusted Profit = (Adjusted Subtotal + Adjusted Overhead) × Profit %
TOTAL RATE = Adjusted Subtotal + Adjusted Overhead + Adjusted Profit
```

## Technical Implementation

### Files Modified
- **rate_buildup_dialog.py**: Primary implementation file

### Key Changes

#### 1. Class Attributes (Lines 34-36)
```python
self.adjustment_factor = 1.0
self.adjustment_formula = "1.0"
```

#### 2. UI Components (Lines 103-112)
```python
# Adjustment Factor
toolbar.addWidget(QLabel("Adjustment factor:"))
self.adjustment_input = QLineEdit()
self.adjustment_input.setText("1.0")
self.adjustment_input.setMaximumWidth(80)
self.adjustment_input.setAlignment(Qt.AlignmentFlag.AlignRight)
self.adjustment_input.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold;")
self.adjustment_input.mouseDoubleClickEvent = self.open_adjustment_formula
self.adjustment_input.editingFinished.connect(self.update_adjustment_from_input)
toolbar.addWidget(self.adjustment_input)
```

#### 3. Tree Header (Line 119)
```python
self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Adjusted Cost", "Net Rate"])
```

#### 4. New Methods

**`open_adjustment_formula(event)`** (Lines 199-235)
- Opens the EditItemDialog for formula input
- Creates a temporary item dictionary
- Adds Apply/Cancel buttons
- Updates adjustment factor on save

**`update_adjustment_from_input()`** (Lines 237-246)
- Parses text input as float
- Updates adjustment_factor and adjustment_formula
- Refreshes the view
- Handles invalid input gracefully

#### 5. Updated refresh_view() (Lines 376-482)
- Calculates adjusted costs for each item
- Updates summary labels with adjusted totals
- Populates "Adjusted Cost" column in tree
- Updates "Net Rate" column to show adjusted task totals

## Usage Examples

### Example 1: Simple Percentage Markup
**Scenario**: Add 15% contingency to all costs
- Double-click adjustment factor input
- Enter: `= 1.15`
- Click "Apply"
- All costs are multiplied by 1.15

### Example 2: Complex Formula
**Scenario**: Add 10% risk + 5% location factor
- Double-click adjustment factor input
- Enter: `= 1.0 + 10% + 5%`
- System calculates: 1.15
- Click "Apply"

### Example 3: Direct Input
**Scenario**: Quick 20% increase
- Click on adjustment factor input
- Type: `1.2`
- Press Enter
- All costs updated instantly

## Benefits

1. **Quick Cost Adjustments**: Apply global multipliers without editing individual items
2. **Formula Transparency**: Store and review the formula used for adjustment
3. **Non-Destructive**: Original costs remain unchanged; adjustment can be modified anytime
4. **Consistent Formatting**: Adjusted costs use the same currency display as base costs
5. **Integration**: Works seamlessly with existing exchange rate and currency conversion features

## Testing Checklist

- [✓] Adjustment factor defaults to 1.0
- [✓] Direct numeric input updates costs correctly
- [✓] Double-click opens formula dialog
- [✓] Formula dialog accepts valid formulas
- [✓] Invalid formulas are rejected gracefully
- [✓] "Adjusted Cost" column displays correctly
- [✓] Summary totals reflect adjusted values
- [✓] Currency formatting is consistent
- [✓] Undo/redo functionality preserved (adjustment factor is stateless per session)

## Future Enhancements (Optional)

1. **Persistence**: Save adjustment factor with the rate build-up to the database
2. **Preset Factors**: Quick buttons for common adjustments (1.1, 1.15, 1.2, etc.)
3. **Item-Specific Adjustments**: Allow different factors for materials vs. labor
4. **Adjustment History**: Track changes to adjustment factor over time
5. **Export**: Include adjustment factor in PDF reports

## Notes

- The adjustment factor is **session-based** and not currently persisted to the database
- Changing currencies does not affect the adjustment factor
- The adjustment is applied **after** currency conversion
- Formula syntax follows the same rules as resource quantity formulas

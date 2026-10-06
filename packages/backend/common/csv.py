"""CSV values intended for viewing in spreadsheet applications."""

import unicodedata


def spreadsheet_safe_cell(value):
    if not isinstance(value, str) or not value:
        return value
    # Some spreadsheet importers ignore leading whitespace, controls and BOMs.
    first = next(
        (char for char in value if not char.isspace() and unicodedata.category(char) not in ('Cc', 'Cf')),
        '',
    )
    if first in ('=', '+', '-', '@', '＝', '＋', '－', '＠') or value.startswith(('\t', '\r', '\n')):
        # Keep the tab inside a quoted CSV field (QUOTE_ALL at the export boundary).
        # This export is for spreadsheet viewing; JSON preserves the original value.
        return '\t' + value
    return value

import pytest

from common.csv import spreadsheet_safe_cell

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    'value',
    [
        '=1+1',
        '+SUM(1,2)',
        '-1+2',
        '@SUM(1,2)',
        ' =1+1',
        '\t=1+1',
        '\r=1+1',
        '\n=1+1',
        '\ufeff =1+1',
        '\x00=1+1',
        '\u200b=1+1',
        '\u00a0=1+1',
        '＝1+1',
        '＋1',
        '－1',
        '＠SUM(1,2)',
        '\ttext',
        '\rtext',
        '\ntext',
    ],
)
def test_formula_like_cells_get_a_text_prefix(value):
    assert spreadsheet_safe_cell(value) == '\t' + value


@pytest.mark.parametrize(
    'value',
    [None, '', 0, -10, 1.5, 'Normal text', 'a=b', 'text, "quoted"\nsecond line', '  normal text', '{"value":"=1+1"}'],
)
def test_ordinary_values_are_preserved(value):
    assert spreadsheet_safe_cell(value) == value

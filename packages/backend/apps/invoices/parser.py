"""Parse FA(2)/FA(3) without resolving entities or accepting external documents."""
from datetime import date
from decimal import Decimal, InvalidOperation
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException


class InvoiceParseError(ValueError):
    pass


def parse_invoice(xml):
    if len(xml) > 10_000_000 or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise InvoiceParseError('INVALID_XML')
    try:
        root = ElementTree.fromstring(xml, forbid_dtd=True)
        for node in root.iter():
            node.tag = node.tag.rsplit('}', 1)[-1]
        if root.findtext('Naglowek/KodFormularza') != 'FA' or root.findtext('Naglowek/WariantFormularza') not in (
            '2',
            '3',
        ):
            raise InvoiceParseError('UNSUPPORTED_FORMAT')
        fa = root.find('Fa')
        if fa is None:
            raise InvoiceParseError('INVALID_XML')

        def dec(path):
            value = fa.findtext(path)
            if value is None:
                return None
            parsed = Decimal(value)
            if not parsed.is_finite():
                raise InvoiceParseError('INVALID_XML')
            return parsed

        vat = sum(
            (Decimal(node.text) for node in fa if node.tag.startswith('P_14_') and not node.tag.endswith('W')),
            Decimal(0),
        )
        lines = []
        for index, row in enumerate(fa.findall('FaWiersz'), 1):

            def amount(name, row=row):
                value = row.findtext(name)
                parsed = Decimal(value) if value is not None else None
                if parsed is not None and not parsed.is_finite():
                    raise InvoiceParseError('INVALID_XML')
                return parsed

            lines.append(
                {
                    'position': index,
                    'description': row.findtext('P_7') or '',
                    'unit': row.findtext('P_8A') or '',
                    'quantity': amount('P_8B'),
                    'unit_price': amount('P_9A'),
                    'net': amount('P_11'),
                    'vat_rate': row.findtext('P_12') or '',
                }
            )
        net = sum((Decimal(node.text) for node in fa if node.tag.startswith('P_13_')), Decimal(0))
        if not net.is_finite() or not vat.is_finite():
            raise InvoiceParseError('INVALID_XML')
        return {
            'number': fa.findtext('P_2') or '',
            'issue_date': date.fromisoformat(fa.findtext('P_1')),
            'kind': fa.findtext('RodzajFaktury') or 'VAT',
            'currency': fa.findtext('KodWaluty') or 'PLN',
            'net': net,
            'vat': vat,
            'gross': dec('P_15'),
            'seller_name': root.findtext('Podmiot1/DaneIdentyfikacyjne/Nazwa') or '',
            'seller_nip': root.findtext('Podmiot1/DaneIdentyfikacyjne/NIP') or '',
            'buyer_name': root.findtext('Podmiot2/DaneIdentyfikacyjne/Nazwa') or '',
            'buyer_nip': root.findtext('Podmiot2/DaneIdentyfikacyjne/NIP') or '',
            'corrected_ksef_numbers': [n.text for n in fa.findall('DaneFaKorygowanej/NrKSeFFaKorygowanej') if n.text],
            'lines': lines,
        }
    except (ElementTree.ParseError, DefusedXmlException, InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, InvoiceParseError):
            raise
        raise InvoiceParseError('INVALID_XML') from exc

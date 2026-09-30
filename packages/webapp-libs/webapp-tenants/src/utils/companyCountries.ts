import { isValidNip, normalizeDigits } from './nip';

export type CompanyCountryConfig = {
  /** ISO 3166-1 alpha-2 code, as stored on the organization */
  code: string;
  /** Prefix of the country's EU VAT number, shown in front of the tax ID (Poland: "PL" + NIP) */
  taxIdPrefix: string;
  /** Validates the national part of the tax ID (without the prefix) - its format differs per country */
  isValidTaxId: (taxId: string) => boolean;
  /** Whether the backend can prefill company details from this country's registry */
  hasRegistryLookup: boolean;
};

/**
 * Countries an organization's company can be registered in. Mirrors the backend's `CompanyCountry` (+ its
 * `TAX_ID_VALIDATORS` / `COMPANY_REGISTRIES`): supporting a new country means adding it on both sides.
 */
export const SUPPORTED_COMPANY_COUNTRIES: CompanyCountryConfig[] = [
  { code: 'PL', taxIdPrefix: 'PL', isValidTaxId: isValidNip, hasRegistryLookup: true },
];

export const DEFAULT_COMPANY_COUNTRY = 'PL';

export const getCompanyCountry = (code?: string | null) =>
  SUPPORTED_COMPANY_COUNTRIES.find((country) => country.code === code);

/** Strips separators and an optional leading country prefix ("PL 972-138-23-73" -> "9721382373"). */
export const normalizeTaxId = (value: string | null | undefined, countryCode?: string | null) => {
  const taxId = normalizeDigits(value);
  const prefix = getCompanyCountry(countryCode)?.taxIdPrefix;
  return prefix && taxId.slice(0, prefix.length).toUpperCase() === prefix ? taxId.slice(prefix.length) : taxId;
};

export const isValidTaxId = (value: string | null | undefined, countryCode?: string | null) => {
  const country = getCompanyCountry(countryCode);
  return !!country && country.isValidTaxId(normalizeTaxId(value, countryCode));
};

/** Flag emoji from an ISO country code ("PL" -> 🇵🇱), via regional indicator symbols. */
export const countryFlag = (code: string) =>
  String.fromCodePoint(
    ...code
      .toUpperCase()
      .split('')
      .map((char) => 0x1f1e6 + char.charCodeAt(0) - 65)
  );

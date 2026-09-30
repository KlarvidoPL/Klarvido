const NIP_WEIGHTS = [6, 5, 7, 2, 3, 4, 5, 6, 7];
const REGON_9_WEIGHTS = [8, 9, 2, 3, 4, 5, 6, 7];
const REGON_14_WEIGHTS = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8];

/** Strips the separators people commonly type into NIP/REGON numbers (spaces, dashes). */
export const normalizeDigits = (value?: string | null) => (value ?? '').replace(/[\s-]/g, '');

const weightedSum = (digits: string, weights: number[]) =>
  weights.reduce((sum, weight, index) => sum + weight * Number(digits[index]), 0);

/** Polish tax ID (NIP): 10 digits, last one is a mod-11 checksum. Mirrors backend `apps.multitenancy.validators`. */
export const isValidNip = (value?: string | null) => {
  const nip = normalizeDigits(value);
  if (!/^\d{10}$/.test(nip)) return false;
  const checksum = weightedSum(nip, NIP_WEIGHTS) % 11;
  return checksum !== 10 && checksum === Number(nip[9]);
};

/** Polish business registry number (REGON): 9 or 14 digits, last one is a mod-11 checksum. */
export const isValidRegon = (value?: string | null) => {
  const regon = normalizeDigits(value);
  const weights = /^\d{9}$/.test(regon) ? REGON_9_WEIGHTS : /^\d{14}$/.test(regon) ? REGON_14_WEIGHTS : null;
  if (!weights) return false;
  const checksum = weightedSum(regon, weights) % 11;
  return (checksum === 10 ? 0 : checksum) === Number(regon[weights.length]);
};

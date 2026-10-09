const filtered = '[Filtered]';
const sensitive = /token|password|secret|otp|base32|authorization|cookie|csrf|credential/i;
const discardedKeys = new Set([
  'headers',
  'data',
  'body',
  'variables',
  'query_string',
  'query',
  'form',
  'payload',
  'response',
  'email',
  'username',
  'ip_address',
  'code',
  'state',
]);

export const scrubMonitoringString = (value: string): string => {
  let decoded = value;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    /* Preserve malformed URL text for redaction. */
  }
  if (/^\s*[{[]/.test(decoded)) {
    try {
      return JSON.stringify(redactMonitoringData(JSON.parse(decoded)));
    } catch {
      return filtered;
    }
  }
  if (
    /(?:password|token|secret|otp|base32|authorization|cookie|csrf|otpauth|code|state|email)\s*["']?\s*[:=]|otpauth:\/\/|Bearer\s+\S+/i.test(
      decoded
    )
  )
    return filtered;
  return decoded
    .replace(/(https?:\/\/)[^/\s]+@/gi, '$1[Filtered]@')
    .replace(/(\/auth\/(?:reset-password\/confirm|confirm)\/)[^\s/?#]+\/[^\s/?#]+/gi, '$1[Filtered]/[Filtered]')
    .replace(/(\/tenant-invitation\/)[^\s/?#]+/gi, '$1[Filtered]')
    .replace(/(https?:\/\/[^\s?"<>]+|\/[^\s?"<>]+)\?[^\s"<>]*/gi, '$1?[Filtered]');
};

export const redactMonitoringData = <T>(value: T, depth = 0): T => {
  if (depth > 20) return filtered as T;
  if (typeof value === 'string') return scrubMonitoringString(value) as T;
  if (Array.isArray(value)) return value.map((item) => redactMonitoringData(item, depth + 1)) as T;
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        sensitive.test(key) || discardedKeys.has(key.toLowerCase()) ? filtered : redactMonitoringData(item, depth + 1),
      ])
    ) as T;
  return value;
};

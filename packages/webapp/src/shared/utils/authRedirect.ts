/** Resolve untrusted login destinations to normalized same-origin application paths. */
export const getSafeAuthRedirect = (value: string | null, fallback: string): string => {
  if (!value || value.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(value)) return fallback;
  if (!value.startsWith('/') && !/^https?:\/\//i.test(value)) return fallback;
  try {
    const target = new URL(value, window.location.origin);
    if (target.origin !== window.location.origin || target.username || target.password) return fallback;

    // Reject encoded separators/controls, including nested encoding. Inspect only
    // the pathname: query values can legitimately contain encoded URLs or spaces.
    let path = target.pathname;
    decodeURIComponent(path); // Malformed percent escapes are not valid application paths.
    for (let depth = 0; depth < 8; depth++) {
      if (!path.startsWith('/') || path.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(path)) return fallback;
      if (!/%[0-9a-f]{2}/i.test(path)) break;
      path = decodeURIComponent(path);
      if (depth === 7) return fallback;
    }
    const decodedTarget = new URL(path, window.location.origin);
    if (decodedTarget.origin !== window.location.origin || decodedTarget.pathname.startsWith('//')) return fallback;
    if (target.pathname.startsWith('//')) return fallback;
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return fallback;
  }
};

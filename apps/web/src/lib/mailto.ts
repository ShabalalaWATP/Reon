export function mailtoHref(email: string): string {
  const separator = email.indexOf("@");
  if (separator <= 0 || separator !== email.lastIndexOf("@") || separator === email.length - 1) {
    return `mailto:${encodeURIComponent(email)}`;
  }
  const local = encodeURIComponent(email.slice(0, separator));
  const domain = encodeURIComponent(email.slice(separator + 1));
  return `mailto:${local}@${domain}`;
}

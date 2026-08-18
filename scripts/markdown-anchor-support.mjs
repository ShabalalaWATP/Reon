function visibleHeadingText(source) {
  return source
    .replace(/!\[([^\]]*)\]\([^)]*\)/gu, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/gu, "$1")
    .replace(/<[^>]+>/gu, "")
    .replace(/&(?:amp|#38|#x26);/giu, "&")
    .replace(/&(?:lt|#60|#x3c);/giu, "<")
    .replace(/&(?:gt|#62|#x3e);/giu, ">")
    .replace(/&(?:quot|#34|#x22);/giu, '"')
    .replace(/&#39;|&#x27;|&apos;/giu, "'")
    .replace(/[`*_~]/gu, "")
    .replace(/\\([!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~])/gu, "$1");
}

function headingSlug(source) {
  return visibleHeadingText(source)
    .trim()
    .toLocaleLowerCase("en-GB")
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/gu, "-");
}

export function markdownAnchorIds(contents) {
  const anchors = new Set();
  const occurrences = new Map();
  let fence = null;

  for (const line of contents.split(/\r?\n/gu)) {
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/u);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (!fence) fence = { character: marker[0], length: marker.length };
      else if (marker[0] === fence.character && marker.length >= fence.length) {
        fence = null;
      }
      continue;
    }
    if (fence) continue;
    const heading = line.match(/^ {0,3}#{1,6}[\t ]+(.+?)[\t ]*#*[\t ]*$/u);
    if (!heading) continue;
    const base = headingSlug(heading[1]);
    if (!base) continue;
    const occurrence = occurrences.get(base) ?? 0;
    anchors.add(occurrence === 0 ? base : `${base}-${occurrence}`);
    occurrences.set(base, occurrence + 1);
  }

  for (const match of contents.matchAll(
    /<[^>]+\b(?:id|name)=["']([^"']+)["'][^>]*>/giu,
  )) {
    anchors.add(match[1]);
  }

  return anchors;
}

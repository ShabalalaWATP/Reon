const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

export function pngValidationFailures(contents, expectedWidth, expectedHeight) {
  const failures = [];
  if (
    contents.length < pngSignature.length ||
    !contents.subarray(0, pngSignature.length).equals(pngSignature)
  ) {
    return ["not a PNG file"];
  }

  let offset = pngSignature.length;
  let dimensions = null;
  let sawHeader = false;
  let sawImageData = false;
  let sawEnd = false;
  while (offset < contents.length) {
    if (contents.length - offset < 12) {
      failures.push("truncated PNG chunk");
      break;
    }
    const dataLength = contents.readUInt32BE(offset);
    if (dataLength > contents.length - offset - 12) {
      failures.push("PNG chunk exceeds the file boundary");
      break;
    }
    const type = contents.toString("ascii", offset + 4, offset + 8);
    const nextOffset = offset + 12 + dataLength;
    if (!/^[A-Za-z]{4}$/u.test(type)) failures.push("invalid PNG chunk type");
    if (!sawHeader && type !== "IHDR") failures.push("IHDR is not the first PNG chunk");
    if (type === "IHDR") {
      if (sawHeader || dataLength !== 13) failures.push("invalid PNG IHDR chunk");
      else {
        sawHeader = true;
        dimensions = {
          width: contents.readUInt32BE(offset + 8),
          height: contents.readUInt32BE(offset + 12),
        };
      }
    } else if (type === "IDAT") {
      sawImageData = true;
    } else if (type === "IEND") {
      if (dataLength !== 0) failures.push("invalid PNG IEND chunk");
      sawEnd = true;
      if (nextOffset !== contents.length) failures.push("data follows PNG IEND chunk");
      offset = nextOffset;
      break;
    }
    offset = nextOffset;
  }

  if (!sawHeader) failures.push("PNG IHDR chunk is missing");
  if (!sawImageData) failures.push("PNG IDAT chunk is missing");
  if (!sawEnd) failures.push("PNG IEND chunk is missing");
  if (
    dimensions &&
    (dimensions.width !== expectedWidth || dimensions.height !== expectedHeight)
  ) {
    failures.push(
      `expected ${expectedWidth}x${expectedHeight}, found ${dimensions.width}x${dimensions.height}`,
    );
  }
  return failures;
}

export function svgSafetyFailures(contents) {
  const checks = [
    [!/<svg\b/iu.test(contents) || !/\bviewBox=/iu.test(contents), "not a viewBox-based SVG"],
    [/<script\b/iu.test(contents), "contains a script element"],
    [/javascript:/iu.test(contents), "contains a JavaScript URL"],
    [/<foreignObject\b/iu.test(contents), "contains foreignObject content"],
    [/<!DOCTYPE\b/iu.test(contents), "contains a document type declaration"],
    [/<!ENTITY\b/iu.test(contents), "contains an entity declaration"],
    [/\son[a-z]+\s*=/iu.test(contents), "contains an event-handler attribute"],
    [/@import\b/iu.test(contents), "contains a CSS import"],
    [
      /\b(?:href|src)\s*=\s*["']\s*(?!#)[^"']/iu.test(contents),
      "contains a non-fragment resource reference",
    ],
    [
      /url\(\s*["']?\s*(?!#)/iu.test(contents),
      "contains a non-fragment CSS resource",
    ],
  ];
  return checks.filter(([failed]) => failed).map(([, message]) => message);
}

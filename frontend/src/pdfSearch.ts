export interface TextRange {
  item: number
  start: number
  end: number
}
export interface PdfMatch {
  page: number
  ranges: TextRange[]
}

// Match phrases split across PDF items while retaining offsets into the original text.
// Highlight positions come from PDF.js text; source coordinates are never fabricated.
export function findTextMatches(items: string[], query: string): TextRange[][] {
  const normalize = (text: string) => text.normalize('NFKC').toLowerCase().replace(/\s/g, '')
  const needle = normalize(query)
  if (!needle) return []
  let text = ''
  const offsets: TextRange[] = []
  items.forEach((item, index) => {
    let offset = 0
    for (const character of item) {
      const normalized = normalize(character)
      text += normalized
      for (let i = 0; i < normalized.length; i++) {
        offsets.push({ item: index, start: offset, end: offset + character.length })
      }
      offset += character.length
    }
  })
  const matches: TextRange[][] = []
  let from = 0
  while (from < text.length) {
    const start = text.indexOf(needle, from)
    if (start === -1) break
    const ranges: TextRange[] = []
    for (const position of offsets.slice(start, start + needle.length)) {
      const last = ranges.at(-1)
      if (last?.item === position.item) last.end = position.end
      else ranges.push({ ...position })
    }
    matches.push(ranges)
    from = start + needle.length
  }
  return matches
}

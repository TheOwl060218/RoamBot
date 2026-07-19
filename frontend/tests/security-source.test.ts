import { readFileSync, readdirSync } from 'node:fs'
import { extname, join } from 'node:path'

import { describe, expect, it } from 'vitest'

const sourceRoot = join(import.meta.dirname, '..', 'src')
const forbidden = [
  /restapi\.amap\.com/i,
  /qweatherapi\.com/i,
  /X-QW-Api-Key/i,
  /Authorization\s*:\s*[`'"]?Bearer/i,
  /master[_-]?password/i,
  /(?:amap|qweather|llm)[_-]?api[_-]?key/i,
]

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return ['.ts', '.tsx', '.js', '.jsx'].includes(extname(entry.name)) ? [path] : []
  })
}

describe('frontend provider-secret boundary', () => {
  it('keeps provider hosts and credential patterns out of production source', () => {
    const findings = sourceFiles(sourceRoot).flatMap((path) => {
      const source = readFileSync(path, 'utf8')
      return forbidden.filter((pattern) => pattern.test(source)).map((pattern) => ({
        path,
        pattern: pattern.source,
      }))
    })

    expect(findings).toEqual([])
  })
})

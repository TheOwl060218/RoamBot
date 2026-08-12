import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = process.cwd()

describe('favicon', () => {
  it('publishes a valid SVG icon from the document head', () => {
    const html = readFileSync(resolve(frontendRoot, 'index.html'), 'utf8')
    const document = new DOMParser().parseFromString(html, 'text/html')
    const iconLink = document.querySelector<HTMLLinkElement>('link[rel="icon"]')

    expect(iconLink?.type).toBe('image/svg+xml')
    expect(iconLink?.getAttribute('href')).toBe('/favicon.svg')

    const svg = readFileSync(resolve(frontendRoot, 'public/favicon.svg'), 'utf8')
    const svgDocument = new DOMParser().parseFromString(svg, 'image/svg+xml')

    expect(svgDocument.querySelector('parsererror')).toBeNull()
    expect(svgDocument.documentElement.getAttribute('viewBox')).toBe('0 0 32 32')
  })
})

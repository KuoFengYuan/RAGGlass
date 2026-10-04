import { cpSync, existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import type { Plugin } from 'vite'

// Serve the installed, pinned PDF.js resources locally in both dev and built modes.
// No CDN, copied vendor files in Git, or additional package is needed.
export function pdfAssets(): Plugin {
  const source = dirname(createRequire(import.meta.url).resolve('pdfjs-dist/package.json'))
  let destination = ''
  let building = false
  return {
    name: 'local-pdf-resources',
    configResolved(config) {
      destination = resolve(config.root, config.build.outDir, 'pdfjs')
      building = config.command === 'build'
    },
    configureServer(server) {
      server.middlewares.use('/pdfjs', (request, response, next) => {
        const path = request.url?.split('?')[0] || ''
        // Accept only package resource names, never arbitrary paths or traversal.
        if (!/^\/(cmaps|standard_fonts)\/[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(path)) return next()
        const file = resolve(source, path.slice(1))
        if (!existsSync(file)) return next()
        response.setHeader('Content-Type', 'application/octet-stream')
        response.end(readFileSync(file))
      })
    },
    closeBundle() {
      if (!building) return
      for (const folder of ['cmaps', 'standard_fonts'])
        cpSync(resolve(source, folder), resolve(destination, folder), { recursive: true })
    },
  }
}

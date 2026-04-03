import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const normalizeBase = (value = '/') => {
  const normalized = String(value || '/').trim()
  if (!normalized) return '/'
  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const buildBase = normalizeBase(env.VITE_BUILD_BASE || '/static/')
  const strictLocalRoutes = new Set(['/', '/login', '/cabinet', '/schedule'])

  const strictDevRoutesPlugin = {
    name: 'strict-dev-routes',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const method = String(req.method || 'GET').toUpperCase()
        if (method !== 'GET' && method !== 'HEAD') return next()

        const rawUrl = String(req.url || '')
        const path = rawUrl.split('?')[0]

        // Internal Vite/assets/static/public paths.
        const passthroughPrefixes = [
          '/@vite',
          '/__vite',
          '/src/',
          '/node_modules/',
          '/assets/',
          '/static/',
          '/favicon',
          '/manifest',
          '/S_height',
          '/sw.js'
        ]
        if (passthroughPrefixes.some((prefix) => path.startsWith(prefix))) return next()
        if (path.includes('.')) return next()

        const normalizedPath =
          path !== '/' && path.endsWith('/') ? path.slice(0, -1) : path

        if (strictLocalRoutes.has(normalizedPath)) return next()

        res.statusCode = 404
        res.setHeader('Content-Type', 'text/plain; charset=utf-8')
        res.end('404 Not Found')
      })
    }
  }

  return {
    base: command === 'build' ? buildBase : '/',
    plugins: command === 'serve' ? [vue(), strictDevRoutesPlugin] : [vue()]
  }
})

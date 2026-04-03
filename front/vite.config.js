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

  return {
    base: command === 'build' ? buildBase : '/',
    plugins: [vue()]
  }
})

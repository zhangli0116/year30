import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

// 后端地址从项目根目录 .env 读取（与 app/config.py 同源），
// 改后端端口只需改 .env，前端代理自动跟随
export default defineConfig(({ mode }) => {
  const envDir = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, envDir, '')
  const backendHost = env.HTTP_HOST || '127.0.0.1'
  const backendPort = env.HTTP_PORT || '8000'

  return {
    plugins: [vue()],
    server: {
      host: true, // 同时监听 IPv4/IPv6，确保 localhost 与 127.0.0.1 都能访问
      port: 5173,
      proxy: {
        '/api': {
          target: `http://${backendHost}:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})

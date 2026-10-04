import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Serve from a tunnel (ngrok) or any host: Vite 8 rejects unknown Host
    // headers otherwise and the page fails to load.
    allowedHosts: true,
    // HMR websocket has to be told to go out over the tunnel's HTTPS host.
    hmr: { clientPort: 443, protocol: 'wss' },
    watch: { usePolling: true },
  },
})

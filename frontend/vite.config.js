import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // base './' -> assets com caminhos relativos, necessário p/ carregar via file:// no Electron
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})

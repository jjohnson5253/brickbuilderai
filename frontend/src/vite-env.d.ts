/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
  readonly VITE_API_MODE?: string
  readonly VITE_LOCAL_API_URL?: string
  readonly VITE_BACKEND_API_KEY?: string
  readonly VITE_RAILWAY_API_URL?: string
  readonly VITE_RAILWAY_API_URL_STAGING?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

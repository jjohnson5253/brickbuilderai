import { createClient, SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Supabase is optional. It is only enabled when both the URL and anon key are
// present. When disabled, the app runs in anonymous mode and authentication
// features are unavailable.
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

// A minimal no-op client used when Supabase is not configured. It implements
// just enough of the SupabaseClient surface used by the app so that call sites
// keep working without throwing.
function createStubClient(): SupabaseClient {
  const notConfiguredError = {
    name: 'SupabaseNotConfigured',
    message: 'Supabase is not configured',
  }

  const queryBuilder: any = {
    select: () => queryBuilder,
    eq: () => queryBuilder,
    update: () => queryBuilder,
    single: async () => ({ data: null, error: notConfiguredError }),
    then: (resolve: (value: { data: null; error: typeof notConfiguredError }) => unknown) =>
      resolve({ data: null, error: notConfiguredError }),
  }

  const stub = {
    auth: {
      getSession: async () => ({ data: { session: null }, error: null }),
      onAuthStateChange: () => ({
        data: { subscription: { unsubscribe: () => {} } },
      }),
      signInWithPassword: async () => ({ data: { user: null, session: null }, error: notConfiguredError }),
      signUp: async () => ({ data: { user: null, session: null }, error: notConfiguredError }),
      signOut: async () => ({ error: null }),
      signInWithOtp: async () => ({ data: {}, error: notConfiguredError }),
      verifyOtp: async () => ({ data: { user: null, session: null }, error: notConfiguredError }),
      signInWithOAuth: async () => ({ data: {}, error: notConfiguredError }),
    },
    from: () => queryBuilder,
  }

  return stub as unknown as SupabaseClient
}

export const supabase: SupabaseClient = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        detectSessionInUrl: true,
        // Auto-refresh tokens before they expire
        autoRefreshToken: true,
        // Session will persist for 30 days
        flowType: 'pkce',
      },
      // Additional client options for session persistence
      global: {
        headers: {
          'X-Client-Info': 'lego-react-app',
        },
      },
    })
  : createStubClient()


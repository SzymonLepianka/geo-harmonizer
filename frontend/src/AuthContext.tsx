import { createContext, ReactNode, useContext } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, jsonBody } from './api'
import type { User } from './types'

interface AuthValue {
  user?: User
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['auth'], queryFn: () => api<User>('/api/auth/me'), retry: false })
  const loginMutation = useMutation({ mutationFn: ({ email, password }: {email:string;password:string}) => api<User>('/api/auth/login', { method: 'POST', ...jsonBody({ email, password }) }), onSuccess: user => queryClient.setQueryData(['auth'], user) })
  const logoutMutation = useMutation({ mutationFn: () => api<void>('/api/auth/logout', { method: 'POST' }), onSuccess: () => queryClient.setQueryData(['auth'], null) })
  return <AuthContext.Provider value={{ user: me.data ?? undefined, loading: me.isLoading, login: (email, password) => loginMutation.mutateAsync({ email, password }), logout: () => logoutMutation.mutateAsync() }}>{children}</AuthContext.Provider>
}

// Hook jest współdzielony z komponentem-providerm w tym niewielkim module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is required')
  return value
}

# LogPets PRO - Frontend Next.js 15 Completo
# TailwindCSS + TypeScript + PWA + Offline Support

## package.json
```json
{
  "name": "logpets-pro-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "axios": "^1.6.0",
    "zustand": "^4.4.0",
    "react-hook-form": "^7.48.0",
    "recharts": "^2.8.0",
    "lucide-react": "^0.295.0",
    "@headlessui/react": "^1.7.0",
    "jwt-decode": "^4.0.0",
    "date-fns": "^2.30.0"
  },
  "devDependencies": {
    "eslint": "^8.0.0",
    "eslint-config-next": "15.0.0",
    "@tailwindcss/forms": "^0.5.7"
  }
}
```

## next.config.js
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  experimental: {
    appDir: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
    ]
  },
  // PWA Configuration
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }
    return config;
  },
}

module.exports = nextConfig
```

## tailwind.config.js
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: {
          50: '#f0fdf4',
          500: '#22c55e',
          600: '#16a34a',
        },
        warning: {
          50: '#fffbeb',
          500: '#f59e0b',
          600: '#d97706',
        },
        error: {
          50: '#fef2f2',
          500: '#ef4444',
          600: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
```

## src/app/layout.tsx
```typescript
import './globals.css'
import { Inter } from 'next/font/google'
import { Providers } from '@/components/Providers'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Toaster } from '@/components/ui/Toaster'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'LogPets PRO',
  description: 'Sistema completo de gestão de transporte de animais',
  manifest: '/manifest.json',
  themeColor: '#3b82f6',
  icons: {
    icon: '/icons/icon-192x192.png',
    apple: '/icons/icon-192x192.png',
  },
  viewport: 'width=device-width, initial-scale=1, maximum-scale=1',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#3b82f6" />
      </head>
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen flex flex-col bg-gray-50">
            <Navbar />
            <main className="flex-1">
              {children}
            </main>
            <Footer />
          </div>
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
```

## src/app/page.tsx
```typescript
'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { DashboardStats } from '@/components/dashboard/DashboardStats'
import { RecentTrips } from '@/components/dashboard/RecentTrips'
import { Charts } from '@/components/dashboard/Charts'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import Link from 'next/link'

interface DashboardData {
  total_trips: number
  active_trips: number
  total_vehicles: number
  total_profit: number
}

export default function Dashboard() {
  const { user, isLoading } = useAuth()
  const [stats, setStats] = useState<DashboardData | null>(null)
  const [isLoadingStats, setIsLoadingStats] = useState(true)

  useEffect(() => {
    if (user) {
      fetchDashboardData()
    }
  }, [user])

  const fetchDashboardData = async () => {
    try {
      setIsLoadingStats(true)
      const response = await fetch('/api/dashboard/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Erro ao carregar dados do dashboard:', error)
    } finally {
      setIsLoadingStats(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="large" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              Bem-vindo ao LogPets PRO
            </h1>
            <p className="text-gray-600 mb-6">
              Sistema completo de gestão de transporte de animais
            </p>
            <div className="space-y-3">
              <Link href="/login">
                <Button className="w-full">
                  Fazer Login
                </Button>
              </Link>
              <Link href="/register">
                <Button variant="outline" className="w-full">
                  Criar Conta
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Bem-vindo, {user.full_name}!
        </h1>
        <p className="text-gray-600 mt-2">
          Visão geral do seu LogPets PRO
        </p>
      </div>

      {/* Stats Cards */}
      {isLoadingStats ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-gray-200 rounded w-1/2"></div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <DashboardStats stats={stats} />
      )}

      {/* Quick Actions */}
      <Card className="p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Ações Rápidas
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link href="/trips/new">
            <Button className="w-full h-12">
              Nova Viagem
            </Button>
          </Link>
          <Link href="/vehicles">
            <Button variant="outline" className="w-full h-12">
              Meus Veículos
            </Button>
          </Link>
          <Link href="/reports">
            <Button variant="outline" className="w-full h-12">
              Relatórios
            </Button>
          </Link>
          <Link href="/trips">
            <Button variant="outline" className="w-full h-12">
              Todas as Viagens
            </Button>
          </Link>
        </div>
      </Card>

      {/* Dashboard Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <RecentTrips />
        <Charts />
      </div>
    </div>
  )
}
```

## src/components/ui/Button.tsx
```typescript
import React from 'react'
import { cn } from '@/lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  children: React.ReactNode
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  className,
  children,
  disabled,
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50'
  
  const variants = {
    primary: 'bg-primary-600 text-white hover:bg-primary-700 focus-visible:ring-primary-600',
    secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus-visible:ring-gray-600',
    outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus-visible:ring-primary-600',
    ghost: 'text-gray-700 hover:bg-gray-100 focus-visible:ring-primary-600',
    danger: 'bg-error-600 text-white hover:bg-error-700 focus-visible:ring-error-600',
  }
  
  const sizes = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  }

  return (
    <button
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg
          className="mr-2 h-4 w-4 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </button>
  )
}
```

## src/components/ui/Card.tsx
```typescript
import React from 'react'
import { cn } from '@/lib/utils'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const Card: React.FC<CardProps> = ({ 
  className, 
  children, 
  ...props 
}) => {
  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-white shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardHeader: React.FC<CardProps> = ({ 
  className, 
  children, 
  ...props 
}) => {
  return (
    <div
      className={cn('p-6 pb-4', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardContent: React.FC<CardProps> = ({ 
  className, 
  children, 
  ...props 
}) => {
  return (
    <div
      className={cn('p-6 pt-0', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardFooter: React.FC<CardProps> = ({ 
  className, 
  children, 
  ...props 
}) => {
  return (
    <div
      className={cn('p-6 pt-4', className)}
      {...props}
    >
      {children}
    </div>
  )
}
```

## src/components/dashboard/DashboardStats.tsx
```typescript
'use client'

import { Card } from '@/components/ui/Card'
import { 
  TruckIcon, 
  MapIcon, 
  DollarSignIcon, 
  ActivityIcon 
} from 'lucide-react'

interface StatsProps {
  stats: {
    total_trips: number
    active_trips: number
    total_vehicles: number
    total_profit: number
  } | null
}

export const DashboardStats: React.FC<StatsProps> = ({ stats }) => {
  const statsData = [
    {
      name: 'Total de Viagens',
      value: stats?.total_trips || 0,
      icon: MapIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      name: 'Viagens Ativas',
      value: stats?.active_trips || 0,
      icon: ActivityIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      name: 'Veículos',
      value: stats?.total_vehicles || 0,
      icon: TruckIcon,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
    {
      name: 'Lucro Total',
      value: `R$ ${(stats?.total_profit || 0).toLocaleString('pt-BR', { 
        minimumFractionDigits: 2 
      })}`,
      icon: DollarSignIcon,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-100',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {statsData.map((stat) => {
        const Icon = stat.icon
        return (
          <Card key={stat.name} className="p-6">
            <div className="flex items-center">
              <div className={`p-2 rounded-md ${stat.bgColor}`}>
                <Icon className={`h-6 w-6 ${stat.color}`} />
              </div>
              <div className="ml-4 flex-1">
                <p className="text-sm font-medium text-gray-600">
                  {stat.name}
                </p>
                <p className="text-2xl font-bold text-gray-900">
                  {stat.value}
                </p>
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
```

## src/hooks/useAuth.ts
```typescript
'use client'

import { useState, useEffect } from 'react'
import { jwtDecode } from 'jwt-decode'

interface User {
  id: number
  email: string
  username: string
  full_name: string
  is_active: boolean
  is_admin: boolean
}

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
}

export const useAuth = () => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  })

  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    try {
      const token = localStorage.getItem('token')
      
      if (!token) {
        setAuthState(prev => ({ ...prev, isLoading: false }))
        return
      }

      // Verificar se o token não expirou
      const decoded: any = jwtDecode(token)
      const currentTime = Date.now() / 1000
      
      if (decoded.exp < currentTime) {
        localStorage.removeItem('token')
        setAuthState(prev => ({ ...prev, isLoading: false }))
        return
      }

      // Buscar dados do usuário
      const response = await fetch('/api/users/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const userData = await response.json()
        setAuthState({
          user: userData,
          isLoading: false,
          isAuthenticated: true,
        })
      } else {
        localStorage.removeItem('token')
        setAuthState(prev => ({ ...prev, isLoading: false }))
      }
    } catch (error) {
      console.error('Erro ao verificar autenticação:', error)
      localStorage.removeItem('token')
      setAuthState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const login = async (username: string, password: string) => {
    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const data = await response.json()
        localStorage.setItem('token', data.access_token)
        await checkAuthStatus()
        return { success: true }
      } else {
        const error = await response.json()
        return { success: false, error: error.detail }
      }
    } catch (error) {
      return { success: false, error: 'Erro de conexão' }
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setAuthState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
    })
  }

  const register = async (userData: {
    email: string
    username: string
    full_name: string
    password: string
  }) => {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      })

      if (response.ok) {
        return { success: true }
      } else {
        const error = await response.json()
        return { success: false, error: error.detail }
      }
    } catch (error) {
      return { success: false, error: 'Erro de conexão' }
    }
  }

  return {
    ...authState,
    login,
    logout,
    register,
  }
}
```

## public/manifest.json
```json
{
  "name": "LogPets PRO",
  "short_name": "LogPets",
  "description": "Sistema completo de gestão de transporte de animais",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "maskable any"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable any"
    }
  ]
}
```

## public/sw.js (Service Worker)
```javascript
const CACHE_NAME = 'logpets-pro-v1'
const urlsToCache = [
  '/',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png'
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  )
})

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          return response
        }
        return fetch(event.request)
      })
  )
})
```

## src/lib/utils.ts
```typescript
import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(value)
}

export const formatDate = (date: string | Date) => {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(date))
}
```
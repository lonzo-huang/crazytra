import { useEffect }      from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { connectWS, useTradeStore } from './store/tradeStore'
import Dashboard    from './pages/Dashboard'
import Strategies   from './pages/Strategies'
import Orders       from './pages/Orders'
import LLMInsights  from './pages/LLMInsights'
import Alerts       from './pages/Alerts'

const NAV = [
  { to: '/',          label: 'Dashboard'  },
  { to: '/strategies', label: 'Strategies' },
  { to: '/orders',    label: 'Orders'     },
  { to: '/llm',       label: 'LLM'        },
  { to: '/alerts',    label: 'Alerts'     },
]

function StatusDot() {
  const status = useTradeStore(s => s.wsStatus)
  const color = status === 'connected'    ? 'bg-green-400'
              : status === 'connecting'   ? 'bg-yellow-400'
              : 'bg-red-400'
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {status}
    </div>
  )
}

export default function App() {
  useEffect(() => { connectWS() }, [])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
        {/* Top nav */}
        <nav className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-6 gap-8">
          <span className="font-semibold text-sm tracking-wide text-white">
            MirrorQuant
          </span>
          <div className="flex gap-6 flex-1">
            {NAV.map(n => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'}
                className={({ isActive }) =>
                  `text-sm transition-colors ${isActive
                    ? 'text-white font-medium'
                    : 'text-gray-400 hover:text-gray-200'}`}>
                {n.label}
              </NavLink>
            ))}
          </div>
          <StatusDot />
        </nav>

        {/* Page content */}
        <main className="flex-1 p-6">
          <Routes>
            <Route path="/"           element={<Dashboard />}   />
            <Route path="/strategies" element={<Strategies />}  />
            <Route path="/orders"     element={<Orders />}      />
            <Route path="/llm"        element={<LLMInsights />} />
            <Route path="/alerts"     element={<Alerts />}      />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

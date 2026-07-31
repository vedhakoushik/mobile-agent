import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { Smartphone, Compass, Rocket, Database, History } from 'lucide-react'
import { SetupPage } from './pages/SetupPage'
import { ExplorePage } from './pages/ExplorePage'
import { DeployPage } from './pages/DeployPage'
import { KnowledgeBasePage } from './pages/KnowledgeBasePage'
import { HistoryPage } from './pages/HistoryPage'

const NAV_ITEMS = [
  { to: '/setup', label: 'Setup', icon: Smartphone },
  { to: '/explore', label: 'Explore', icon: Compass },
  { to: '/deploy', label: 'Deploy', icon: Rocket },
  { to: '/history', label: 'History', icon: History },
  { to: '/kb', label: 'Knowledge Base', icon: Database },
]

function NavBar() {
  const location = useLocation()

  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-1 h-14">
        <span className="text-sm font-semibold text-zinc-100 mr-6">Mobile Agent</span>
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to
          return (
            <Link
              key={to}
              to={to}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                active ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300',
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <NavBar />
      <Routes>
        <Route path="/" element={<Navigate to="/setup" replace />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/explore" element={<ExplorePage />} />
        <Route path="/deploy" element={<DeployPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:sessionId" element={<HistoryPage />} />
        <Route path="/kb" element={<KnowledgeBasePage />} />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    </div>
  )
}

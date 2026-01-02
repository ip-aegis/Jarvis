import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquare,
  Server,
  Activity,
  Cpu,
  FolderGit2,
  Settings
} from 'lucide-react'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Servers', href: '/servers', icon: Server },
  { name: 'Monitoring', href: '/monitoring', icon: Activity },
  { name: 'Alpha', href: '/alpha', icon: Cpu },
  { name: 'Projects', href: '/projects', icon: FolderGit2 },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-surface-900 border-r border-surface-700 flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center px-6 border-b border-surface-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-magnetic bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-lg">J</span>
          </div>
          <span className="text-xl font-semibold text-white">Jarvis</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3">
        <ul className="space-y-1">
          {navigation.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.href}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-magnetic text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-surface-300 hover:bg-surface-700 hover:text-white'
                  )
                }
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-surface-700">
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-magnetic text-sm font-medium text-surface-300 hover:bg-surface-700 hover:text-white transition-colors">
          <Settings className="w-5 h-5" />
          Settings
        </button>
      </div>
    </aside>
  )
}

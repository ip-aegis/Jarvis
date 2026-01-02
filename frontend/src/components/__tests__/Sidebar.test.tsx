import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test/test-utils'
import Sidebar from '../layout/Sidebar'

describe('Sidebar', () => {
  it('renders the Jarvis logo', () => {
    render(<Sidebar />)
    expect(screen.getByText('Jarvis')).toBeInTheDocument()
    expect(screen.getByText('J')).toBeInTheDocument()
  })

  it('renders all navigation items', () => {
    render(<Sidebar />)

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Chat')).toBeInTheDocument()
    expect(screen.getByText('Servers')).toBeInTheDocument()
    expect(screen.getByText('Monitoring')).toBeInTheDocument()
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })

  it('renders navigation links with correct hrefs', () => {
    render(<Sidebar />)

    expect(screen.getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /chat/i })).toHaveAttribute('href', '/chat')
    expect(screen.getByRole('link', { name: /servers/i })).toHaveAttribute('href', '/servers')
    expect(screen.getByRole('link', { name: /monitoring/i })).toHaveAttribute('href', '/monitoring')
    expect(screen.getByRole('link', { name: /projects/i })).toHaveAttribute('href', '/projects')
  })

  it('renders the settings button', () => {
    render(<Sidebar />)
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })
})

import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Servers from './pages/Servers'
import Monitoring from './pages/Monitoring'
import Alpha from './pages/Alpha'
import Projects from './pages/Projects'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/servers" element={<Servers />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/alpha" element={<Alpha />} />
        <Route path="/projects" element={<Projects />} />
      </Routes>
    </Layout>
  )
}

export default App

import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Chat = lazy(() => import('./pages/Chat'))
const Servers = lazy(() => import('./pages/Servers'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const Alpha = lazy(() => import('./pages/Alpha'))
const Projects = lazy(() => import('./pages/Projects'))
const Network = lazy(() => import('./pages/Network'))
const DNS = lazy(() => import('./pages/DNS'))
const Actions = lazy(() => import('./pages/Actions'))
const Home = lazy(() => import('./pages/Home'))
const Journal = lazy(() => import('./pages/Journal'))
const Work = lazy(() => import('./pages/Work'))
const Usage = lazy(() => import('./pages/Usage'))
const Settings = lazy(() => import('./pages/Settings'))

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full" role="status" aria-label="Loading page">
      <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full" />
      <span className="sr-only">Loading...</span>
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/servers" element={<Servers />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/network" element={<Network />} />
            <Route path="/dns" element={<DNS />} />
            <Route path="/alpha" element={<Alpha />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/actions" element={<Actions />} />
            <Route path="/home" element={<Home />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/work" element={<Work />} />
            <Route path="/usage" element={<Usage />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </Layout>
    </ErrorBoundary>
  )
}

export default App

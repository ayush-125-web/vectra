import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CommandCenter from './pages/CommandCenter'
import VehicleTracking from './pages/VehicleTracking'
import Analytics from './pages/Analytics'
import Alerts from './pages/Alerts'

export default function App() {
  return (
    <div className="flex h-screen bg-base-900">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/tracking" element={<VehicleTracking />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </main>
    </div>
  )
}

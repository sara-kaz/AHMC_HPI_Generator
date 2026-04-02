import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { CaseList } from './pages/CaseList'
import { NewCase } from './pages/NewCase'
import { CaseDetail } from './pages/CaseDetail'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        {/* Nav */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">H</span>
            </div>
            <span className="font-semibold text-slate-800 text-sm">AHMC HPI Generator</span>
            <span className="text-xs text-slate-400 border border-slate-200 rounded px-1.5 py-0.5">claude-sonnet-4-6</span>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<CaseList />} />
            <Route path="/new" element={<NewCase />} />
            <Route path="/cases/:id" element={<CaseDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

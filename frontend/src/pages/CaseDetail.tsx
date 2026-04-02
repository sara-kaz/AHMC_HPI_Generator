import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ChevronUp, Loader2, Trash2, RefreshCw } from 'lucide-react'
import { casesApi } from '../api/client'
import { StructuredOutput } from '../components/StructuredOutput'
import type { Case } from '../types'

export function CaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [case_, setCase] = useState<Case | null>(null)
  const [loading, setLoading] = useState(true)
  const [notesOpen, setNotesOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  useEffect(() => {
    casesApi.get(Number(id)).then(setCase).finally(() => setLoading(false))
  }, [id])

  async function handleDelete() {
    if (!confirm('Delete this case?')) return
    setDeleting(true)
    await casesApi.delete(Number(id))
    navigate('/')
  }

  async function handleRegenerate() {
    if (!confirm('Regenerate will overwrite the current output. Continue?')) return
    setRegenerating(true)
    try {
      const updated = await casesApi.generate(Number(id))
      setCase(updated)
    } finally {
      setRegenerating(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={32} className="animate-spin text-blue-400" />
    </div>
  )

  if (!case_) return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center text-slate-500">Case not found.</div>
  )

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <button onClick={() => navigate('/')} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors">
          <ArrowLeft size={14} /> All Cases
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-60"
          >
            {regenerating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Regenerate
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-60"
          >
            <Trash2 size={12} /> Delete
          </button>
        </div>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{case_.title}</h1>
        <p className="text-xs text-slate-400 mt-1">
          Created {new Date(case_.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {/* Original Notes Accordion */}
      <div className="bg-white rounded-2xl border border-slate-200 mb-6 overflow-hidden">
        <button
          onClick={() => setNotesOpen(!notesOpen)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          <span>Original Clinical Notes</span>
          {notesOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        {notesOpen && (
          <div className="border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 divide-x divide-slate-100">
            <div className="p-4">
              <p className="text-xs font-semibold text-slate-400 uppercase mb-2">ER Note</p>
              <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                {case_.er_note || <span className="text-slate-400 italic">Not provided</span>}
              </pre>
            </div>
            <div className="p-4">
              <p className="text-xs font-semibold text-slate-400 uppercase mb-2">H&P Note</p>
              <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                {case_.hp_note || <span className="text-slate-400 italic">Not provided</span>}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Generation states */}
      {case_.generation_status === 'generating' && (
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-2xl p-5">
          <Loader2 size={20} className="animate-spin text-blue-500" />
          <span className="text-sm text-blue-700 font-medium">Claude is analyzing the notes...</span>
        </div>
      )}

      {case_.generation_status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-5">
          <p className="text-sm font-semibold text-red-700 mb-1">Generation failed</p>
          <p className="text-xs text-red-500">{case_.generation_error}</p>
        </div>
      )}

      {case_.generation_status === 'completed' && case_.structured_output && (
        <StructuredOutput case_={case_} onUpdated={setCase} />
      )}
    </div>
  )
}

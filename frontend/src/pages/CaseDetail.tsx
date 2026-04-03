import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ChevronUp, Loader2, Trash2, RefreshCw, Pencil, Check, X } from 'lucide-react'
import { casesApi, getApiErrorMessage } from '../api/client'
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
  const [regenError, setRegenError] = useState('')
  const [titleEditing, setTitleEditing] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [titleSaving, setTitleSaving] = useState(false)
  const [titleError, setTitleError] = useState('')

  useEffect(() => {
    casesApi.get(Number(id)).then(setCase).finally(() => setLoading(false))
  }, [id])

  async function handleDelete() {
    if (!confirm('Delete this case?')) return
    setDeleting(true)
    await casesApi.delete(Number(id))
    navigate('/')
  }

  async function handleSaveTitle() {
    const t = titleDraft.trim()
    if (!t) {
      setTitleError('Case title cannot be empty.')
      return
    }
    setTitleError('')
    setTitleSaving(true)
    try {
      const updated = await casesApi.update(Number(id), { title: t })
      setCase(updated)
      setTitleEditing(false)
    } catch (e: unknown) {
      setTitleError(getApiErrorMessage(e))
    } finally {
      setTitleSaving(false)
    }
  }

  function startTitleEdit() {
    if (case_) {
      setTitleDraft(case_.title)
      setTitleError('')
      setTitleEditing(true)
    }
  }

  function cancelTitleEdit() {
    setTitleEditing(false)
    setTitleError('')
    if (case_) setTitleDraft(case_.title)
  }

  async function handleRegenerate() {
    if (!confirm('Regenerate will overwrite the current output. Continue?')) return
    setRegenError('')
    setRegenerating(true)
    try {
      const updated = await casesApi.generate(Number(id))
      setCase(updated)
    } catch (e: unknown) {
      setRegenError(getApiErrorMessage(e))
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
        <div className="flex items-start gap-2">
          {titleEditing ? (
            <div className="flex-1 min-w-0 space-y-2">
              <input
                value={titleDraft}
                onChange={e => setTitleDraft(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') void handleSaveTitle()
                  if (e.key === 'Escape') cancelTitleEdit()
                }}
                className="w-full text-2xl font-bold text-slate-900 border border-blue-300 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                autoFocus
                disabled={titleSaving}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleSaveTitle()}
                  disabled={titleSaving}
                  className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
                >
                  {titleSaving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                  Save title
                </button>
                <button
                  type="button"
                  onClick={cancelTitleEdit}
                  disabled={titleSaving}
                  className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-medium rounded-lg hover:bg-slate-200 disabled:opacity-60"
                >
                  <X size={12} /> Cancel
                </button>
              </div>
              {titleError && <p className="text-xs text-red-600">{titleError}</p>}
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-slate-900 flex-1 min-w-0">{case_.title}</h1>
              <button
                type="button"
                onClick={startTitleEdit}
                className="mt-1.5 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors shrink-0"
                title="Edit title"
              >
                <Pencil size={18} />
              </button>
            </>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Created {new Date(case_.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {regenError && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{regenError}</div>
      )}

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

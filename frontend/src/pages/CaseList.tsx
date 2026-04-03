import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Loader2, FileText, ChevronRight, AlertCircle, CheckCircle, Clock, Search } from 'lucide-react'
import { casesApi } from '../api/client'
import { Badge } from '../components/Badge'
import type { Case, DispositionRecommendation } from '../types'

const dispositionBadge: Record<DispositionRecommendation, 'admit' | 'observe' | 'discharge' | 'unknown'> = {
  Admit: 'admit',
  Observe: 'observe',
  Discharge: 'discharge',
  Unknown: 'unknown',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle size={14} className="text-green-500" />
  if (status === 'failed') return <AlertCircle size={14} className="text-red-500" />
  if (status === 'generating') return <Loader2 size={14} className="animate-spin text-blue-400" />
  return <Clock size={14} className="text-slate-400" />
}

function caseMatchesIdQuery(c: Case, queryDigits: string): boolean {
  if (!queryDigits) return true
  return String(c.id).includes(queryDigits)
}

export function CaseList() {
  const navigate = useNavigate()
  const [cases, setCases] = useState<Case[]>([])
  const [loading, setLoading] = useState(true)
  const [idSearch, setIdSearch] = useState('')

  useEffect(() => {
    casesApi.list().then(setCases).finally(() => setLoading(false))
  }, [])

  const idQueryDigits = idSearch.replace(/\D/g, '')
  const filteredCases = useMemo(
    () => cases.filter(c => caseMatchesIdQuery(c, idQueryDigits)),
    [cases, idQueryDigits]
  )

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Clinical HPI Generator</h1>
          <p className="text-sm text-slate-500 mt-1">Transform unstructured clinical notes into structured, admission-supporting narratives</p>
        </div>
        <button
          onClick={() => navigate('/new')}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors text-sm"
        >
          <Plus size={16} /> New Case
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={28} className="animate-spin text-blue-400" />
        </div>
      ) : cases.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <FileText size={48} className="mx-auto mb-4 opacity-40" />
          <p className="text-lg font-medium mb-1">No cases yet</p>
          <p className="text-sm">Click "New Case" to paste a clinical note and generate a structured output.</p>
        </div>
      ) : (
        <>
          <div className="mb-4">
            <label htmlFor="case-id-search" className="sr-only">
              Search by case ID
            </label>
            <div className="relative max-w-md">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                id="case-id-search"
                type="search"
                inputMode="numeric"
                autoComplete="off"
                placeholder="Search by case ID…"
                value={idSearch}
                onChange={e => setIdSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 text-sm border border-slate-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 font-mono"
              />
            </div>
            {idQueryDigits && (
              <p className="text-xs text-slate-500 mt-2">
                Showing {filteredCases.length} of {cases.length} case{cases.length === 1 ? '' : 's'}
                {filteredCases.length === 0 ? ' — try a different ID' : ''}
              </p>
            )}
          </div>

          {filteredCases.length === 0 ? (
            <div className="text-center py-16 text-slate-400 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
              <p className="text-sm font-medium text-slate-600">No case with ID matching “{idQueryDigits}”</p>
              <p className="text-xs mt-1">Clear the search or try another number.</p>
            </div>
          ) : (
        <div className="space-y-3">
          {filteredCases.map(c => (
            <div
              key={c.id}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="bg-white rounded-2xl border border-slate-200 p-5 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all flex items-center justify-between group"
            >
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <StatusIcon status={c.generation_status} />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-800 truncate">{c.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    <span className="font-mono text-slate-500">ID {c.id}</span>
                    <span className="mx-1 text-slate-300">·</span>
                    {new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    {c.edited_fields?.length ? ` · ${c.edited_fields.length} field${c.edited_fields.length > 1 ? 's' : ''} edited` : ''}
                  </p>
                  {c.structured_output?.chief_complaint && (
                    <p className="text-sm text-slate-500 mt-1 truncate">{c.structured_output.chief_complaint}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                {c.structured_output?.disposition_recommendation && (
                  <Badge variant={dispositionBadge[c.structured_output.disposition_recommendation]}>
                    {c.structured_output.disposition_recommendation}
                  </Badge>
                )}
                <ChevronRight size={16} className="text-slate-300 group-hover:text-blue-400 transition-colors" />
              </div>
            </div>
          ))}
        </div>
          )}
        </>
      )}
    </div>
  )
}

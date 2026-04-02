import { useState } from 'react'
import { Pencil, Check, X } from 'lucide-react'
import { Badge } from './Badge'
import type { DispositionRecommendation } from '../types'

interface DispositionSelectProps {
  value: DispositionRecommendation
  isEdited: boolean
  onSave: (value: DispositionRecommendation) => void
}

const OPTIONS: DispositionRecommendation[] = ['Admit', 'Observe', 'Discharge', 'Unknown']

const dispositionBadge: Record<DispositionRecommendation, 'admit' | 'observe' | 'discharge' | 'unknown'> = {
  Admit: 'admit',
  Observe: 'observe',
  Discharge: 'discharge',
  Unknown: 'unknown',
}

export function DispositionSelect({ value, isEdited, onSave }: DispositionSelectProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<DispositionRecommendation>(value)

  function handleSave() {
    onSave(draft)
    setEditing(false)
  }

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Disposition Recommendation</span>
          <Badge variant={isEdited ? 'edited' : 'ai'}>
            {isEdited ? '✏️ Edited' : '🤖 AI'}
          </Badge>
        </div>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"
          >
            <Pencil size={13} />
          </button>
        )}
      </div>

      {editing ? (
        <div className="flex gap-2 items-center flex-wrap">
          {OPTIONS.map(opt => (
            <button
              key={opt}
              onClick={() => setDraft(opt)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${draft === opt ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'}`}
            >
              {opt}
            </button>
          ))}
          <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 ml-2">
            <Check size={12} /> Save
          </button>
          <button onClick={() => setEditing(false)} className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 text-xs rounded-lg hover:bg-slate-200">
            <X size={12} /> Cancel
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Badge variant={dispositionBadge[value]}>
            <span className="text-sm font-semibold">{value}</span>
          </Badge>
          <span
            className="text-xs text-slate-400 cursor-pointer hover:text-blue-600 transition-colors"
            onClick={() => setEditing(true)}
          >
            Click to change
          </span>
        </div>
      )}
    </div>
  )
}

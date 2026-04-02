import { useState, useRef, useEffect } from 'react'
import { Pencil, Check, X } from 'lucide-react'
import { Badge } from './Badge'

interface EditableFieldProps {
  label: string
  value: string
  isEdited: boolean
  multiline?: boolean
  onSave: (value: string) => void
}

export function EditableField({ label, value, isEdited, multiline = false, onSave }: EditableFieldProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLTextAreaElement | HTMLInputElement>(null)

  useEffect(() => {
    if (editing && ref.current) ref.current.focus()
  }, [editing])

  useEffect(() => {
    setDraft(value)
  }, [value])

  function handleSave() {
    onSave(draft)
    setEditing(false)
  }

  function handleCancel() {
    setDraft(value)
    setEditing(false)
  }

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
          <Badge variant={isEdited ? 'edited' : 'ai'}>
            {isEdited ? '✏️ Edited' : '🤖 AI'}
          </Badge>
        </div>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"
            title="Edit"
          >
            <Pencil size={13} />
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          {multiline ? (
            <textarea
              ref={ref as React.RefObject<HTMLTextAreaElement>}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              rows={6}
              className="w-full text-sm border border-blue-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white resize-y"
            />
          ) : (
            <input
              ref={ref as React.RefObject<HTMLInputElement>}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              className="w-full text-sm border border-blue-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
            />
          )}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700"
            >
              <Check size={12} /> Save
            </button>
            <button
              onClick={handleCancel}
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-medium rounded-lg hover:bg-slate-200"
            >
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      ) : (
        <div
          className={`text-sm text-slate-800 bg-slate-50 rounded-lg p-3 cursor-pointer hover:bg-blue-50 transition-colors ${isEdited ? 'border-l-2 border-amber-400' : ''}`}
          onClick={() => setEditing(true)}
          title="Click to edit"
        >
          {value || <span className="text-slate-400 italic">Not specified</span>}
        </div>
      )}
    </div>
  )
}

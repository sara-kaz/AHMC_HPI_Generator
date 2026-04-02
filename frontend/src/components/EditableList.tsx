import { useState } from 'react'
import { Pencil, Check, X, Plus, Trash2 } from 'lucide-react'
import { Badge } from './Badge'

interface EditableListProps {
  label: string
  items: string[]
  isEdited: boolean
  onSave: (items: string[]) => void
}

export function EditableList({ label, items, isEdited, onSave }: EditableListProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([...items])

  function handleSave() {
    const cleaned = draft.filter(i => i.trim())
    onSave(cleaned)
    setEditing(false)
  }

  function handleCancel() {
    setDraft([...items])
    setEditing(false)
  }

  function updateItem(index: number, value: string) {
    const next = [...draft]
    next[index] = value
    setDraft(next)
  }

  function removeItem(index: number) {
    setDraft(draft.filter((_, i) => i !== index))
  }

  function addItem() {
    setDraft([...draft, ''])
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
          <div className="space-y-1">
            {draft.map((item, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  value={item}
                  onChange={e => updateItem(i, e.target.value)}
                  className="flex-1 text-sm border border-blue-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
                <button onClick={() => removeItem(i)} className="text-red-400 hover:text-red-600">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <button onClick={addItem} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800">
            <Plus size={12} /> Add item
          </button>
          <div className="flex gap-2">
            <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700">
              <Check size={12} /> Save
            </button>
            <button onClick={handleCancel} className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-medium rounded-lg hover:bg-slate-200">
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      ) : (
        <div
          className={`bg-slate-50 rounded-lg p-3 cursor-pointer hover:bg-blue-50 transition-colors ${isEdited ? 'border-l-2 border-amber-400' : ''}`}
          onClick={() => setEditing(true)}
          title="Click to edit"
        >
          {items.length === 0 ? (
            <span className="text-slate-400 italic text-sm">None</span>
          ) : (
            <ul className="space-y-1">
              {items.map((item, i) => (
                <li key={i} className="text-sm text-slate-800 flex items-start gap-2">
                  <span className="text-blue-400 mt-0.5">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

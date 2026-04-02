import { useState, useCallback } from 'react'
import { Save, CheckCircle, AlertTriangle, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { EditableField } from './EditableField'
import { EditableList } from './EditableList'
import { DispositionSelect } from './DispositionSelect'
import { Badge } from './Badge'
import type { Case, StructuredOutput as StructuredOutputType, DispositionRecommendation } from '../types'
import { casesApi } from '../api/client'

interface Props {
  case_: Case
  onUpdated: (updated: Case) => void
}

export function StructuredOutput({ case_, onUpdated }: Props) {
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [hpiExpanded, setHpiExpanded] = useState(true)

  const output = case_.structured_output!
  const editedFields = new Set(case_.edited_fields || [])

  const updateField = useCallback(
    async <K extends keyof StructuredOutputType>(field: K, value: StructuredOutputType[K]) => {
      const newOutput = { ...output, [field]: value }
      const newEdited = Array.from(new Set([...editedFields, field as string]))
      const updated = await casesApi.update(case_.id, {
        structured_output: newOutput,
        edited_fields: newEdited,
      })
      onUpdated(updated)
    },
    [case_.id, output, editedFields, onUpdated]
  )

  async function handleSaveAll() {
    setSaving(true)
    try {
      const updated = await casesApi.update(case_.id, {
        structured_output: output,
        edited_fields: Array.from(editedFields),
      })
      onUpdated(updated)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2500)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-800">Structured Output</h2>
          {editedFields.size > 0 && (
            <Badge variant="edited">{editedFields.size} field{editedFields.size > 1 ? 's' : ''} edited</Badge>
          )}
        </div>
        <button
          onClick={handleSaveAll}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-all"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : saveSuccess ? <CheckCircle size={14} /> : <Save size={14} />}
          {saveSuccess ? 'Saved!' : 'Save All Changes'}
        </button>
      </div>

      {/* Chief Complaint */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <EditableField
          label="Chief Complaint"
          value={output.chief_complaint}
          isEdited={editedFields.has('chief_complaint')}
          onSave={v => updateField('chief_complaint', v)}
        />
      </div>

      {/* Disposition — prominent */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <DispositionSelect
          value={output.disposition_recommendation}
          isEdited={editedFields.has('disposition_recommendation')}
          onSave={v => updateField('disposition_recommendation', v as DispositionRecommendation)}
        />
      </div>

      {/* HPI Summary */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <EditableField
          label="HPI Summary"
          value={output.hpi_summary}
          isEdited={editedFields.has('hpi_summary')}
          multiline
          onSave={v => updateField('hpi_summary', v)}
        />
      </div>

      {/* Two-column grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
          <EditableList
            label="Key Findings"
            items={output.key_findings}
            isEdited={editedFields.has('key_findings')}
            onSave={v => updateField('key_findings', v)}
          />
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
          <EditableList
            label="Suspected Conditions"
            items={output.suspected_conditions}
            isEdited={editedFields.has('suspected_conditions')}
            onSave={v => updateField('suspected_conditions', v)}
          />
        </div>
      </div>

      {/* Admission Criteria */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <EditableList
          label="MCG Admission Criteria Met"
          items={output.admission_criteria_met}
          isEdited={editedFields.has('admission_criteria_met')}
          onSave={v => updateField('admission_criteria_met', v)}
        />
      </div>

      {/* Uncertainties */}
      {(output.uncertainties?.length > 0 || editedFields.has('uncertainties')) && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-amber-600" />
            <span className="text-xs font-semibold uppercase tracking-wide text-amber-700">Uncertainties / Missing Info</span>
          </div>
          <EditableList
            label=""
            items={output.uncertainties}
            isEdited={editedFields.has('uncertainties')}
            onSave={v => updateField('uncertainties', v)}
          />
        </div>
      )}

      {/* Revised HPI — most important */}
      <div className="bg-blue-50 rounded-2xl border border-blue-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500"></div>
            <span className="text-sm font-bold text-blue-800 uppercase tracking-wide">Revised HPI</span>
            <Badge variant="ai">Admission-Supporting Narrative</Badge>
          </div>
          <button
            onClick={() => setHpiExpanded(!hpiExpanded)}
            className="text-blue-400 hover:text-blue-700"
          >
            {hpiExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        {hpiExpanded && (
          <EditableField
            label=""
            value={output.revised_hpi}
            isEdited={editedFields.has('revised_hpi')}
            multiline
            onSave={v => updateField('revised_hpi', v)}
          />
        )}
      </div>
    </div>
  )
}
